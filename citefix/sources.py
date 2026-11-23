"""Lookups against free scholarly indexes. Each function returns Candidate records."""

from __future__ import annotations

import html
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from .textutil import normalize

USER_AGENT = "citefix-prototype/0.1 (research prototype)"
TIMEOUT_S = {"crossref": 12, "openalex": 12, "semantic_scholar": 12, "arxiv": 10}

Years = tuple[int, int]  # inclusive range of publication years
_TAGS = re.compile(r"<[^>]+>")


@dataclass
class Candidate:
    source: str
    title: str
    year: int | None = None
    authors: list[str] = field(default_factory=list)  # full names, written however the source writes them
    doi: str | None = None
    url: str | None = None
    venue: str | None = None
    retracted: bool | None = None
    abstract: str | None = None


class SourceError(Exception):
    """A source could not be queried: network error, rate limit or unreadable reply."""


class _Gate:
    """Limits how fast, and how many at once, requests go to one source.

    After two rate-limit replies in a row the source is skipped for a minute, or for as long as
    its Retry-After header asks.
    """

    def __init__(self, min_interval_s: float, max_concurrent: int):
        self.min_interval_s = min_interval_s
        self.slots = threading.BoundedSemaphore(max_concurrent)
        self._lock = threading.Lock()
        self._next_start = 0.0
        self._rate_limited = 0
        self._paused_until = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._paused_until:
                raise SourceError("rate-limited, skipped for now")
            delay = self._next_start - now
            self._next_start = max(now, self._next_start) + self.min_interval_s
        if delay > 0:
            time.sleep(delay)

    def note_rate_limit(self, retry_after_s: float | None = None) -> None:
        with self._lock:
            self._rate_limited += 1
            if retry_after_s and retry_after_s > 10:
                self._paused_until = time.monotonic() + retry_after_s
            elif self._rate_limited >= 2:
                self._paused_until = time.monotonic() + 60

    def note_success(self) -> None:
        with self._lock:
            self._rate_limited = 0

    def follow(self, headers) -> None:
        """Adopt the pace a source announces in X-Rate-Limit-* headers (Crossref sends them)."""
        try:
            limit = int(headers.get("x-rate-limit-limit", ""))
            interval = float(headers.get("x-rate-limit-interval", "").rstrip("s"))
        except ValueError:
            return
        if limit > 0 and interval > 0:
            with self._lock:
                self.min_interval_s = interval / limit * 1.05


# Crossref's public pool allows 1 request per second, 1 at a time (its X-Rate-Limit headers say so).
# CROSSREF_MAILTO moves requests to its "polite" pool; either way the pace follows those headers.
# arXiv asks for 3 s between calls.
_CROSSREF_POLITE = bool(os.environ.get("CROSSREF_MAILTO"))
_GATES = {
    "crossref": _Gate(1.05, 1),
    "openalex": _Gate(0.1, 4),
    "semantic_scholar": _Gate(1.1, 1),
    "arxiv": _Gate(3.0, 1),
}


def _get(url: str, source: str, headers: dict[str, str] | None = None) -> bytes | None:
    """GET with one retry. Returns None on 404, which these APIs use for "no such record"."""
    gate = _GATES[source]
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    for attempt in (1, 2):
        gate.wait()
        try:
            with gate.slots, urllib.request.urlopen(request, timeout=TIMEOUT_S[source]) as response:
                body = response.read()
                gate.follow(response.headers)
        except urllib.error.HTTPError as err:
            if err.code == 404:
                gate.note_success()
                return None
            if err.code == 429:
                retry_after = _seconds(err.headers.get("Retry-After"))
                gate.note_rate_limit(retry_after)
                if retry_after and retry_after > 10:
                    raise SourceError(f"rate-limited for the next {retry_after / 3600:.1f} h") from err
            if err.code in (429, 500, 502, 503, 504) and attempt == 1:
                time.sleep(2.0)
                continue
            raise SourceError(f"HTTP {err.code}") from err
        except OSError as err:  # URLError, timeouts, connection resets
            reason = getattr(err, "reason", err)
            if isinstance(err, TimeoutError) or isinstance(reason, TimeoutError):
                raise SourceError("timed out") from err  # a slow source stays slow; do not wait twice
            if attempt == 1:
                time.sleep(1.0)
                continue
            raise SourceError(str(reason)) from err
        gate.note_success()
        return body
    raise SourceError("no response")


def _seconds(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:  # Retry-After may also be an HTTP date; treat that as unknown
        return None


def key_hint(failed_sources: set[str]) -> str | None:
    """Advice when lookups failed because a source wants an API key."""
    if any(name.startswith("openalex") for name in failed_sources) and not os.environ.get("OPENALEX_API_KEY"):
        return ("OpenAlex refused requests: without a key, everyone on your IP address shares one small "
                "free daily budget. Get a free key at https://help.openalex.org/api/authentication/ "
                "and set OPENALEX_API_KEY.")
    return None


def _json(body: bytes | None) -> dict:
    if body is None:
        return {}
    try:
        return json.loads(body)
    except ValueError as err:
        raise SourceError("unreadable reply") from err


def _clean_markup(text: str | None) -> str | None:
    """Crossref abstracts arrive as JATS XML; keep only the text."""
    if not text:
        return None
    text = " ".join(html.unescape(_TAGS.sub(" ", text)).split())
    if text.lower().startswith("abstract "):
        text = text[len("abstract "):]
    return text or None


def _inverted_to_text(index: dict | None) -> str | None:
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the text."""
    if not index:
        return None
    placed = sorted((pos, word) for word, positions in index.items() for pos in positions)
    return " ".join(word for _, word in placed) or None


# Crossref record types that are containers (a whole journal or proceedings), not papers.
_CROSSREF_CONTAINERS = {
    "proceedings", "journal", "journal-issue", "journal-volume", "component",
    "proceedings-series", "book-series", "book-set", "report-series", "grant", "peer-review",
}


def crossref(query: str, years: Years | None = None, rows: int = 5) -> list[Candidate]:
    """Crossref's bibliographic search takes a whole reference string or just a title."""
    params = {
        "query.bibliographic": query,
        "rows": rows,
        "select": "DOI,title,author,issued,container-title,type,URL,abstract",
    }
    if years:
        params["filter"] = f"from-pub-date:{years[0]},until-pub-date:{years[1]}"
    if _CROSSREF_POLITE:
        params["mailto"] = os.environ["CROSSREF_MAILTO"]
    data = _json(_get("https://api.crossref.org/works?" + urllib.parse.urlencode(params), "crossref"))
    found = []
    for item in data.get("message", {}).get("items", []):
        title = (item.get("title") or [""])[0]
        if not title or item.get("type") in _CROSSREF_CONTAINERS:
            continue
        date_parts = (item.get("issued") or {}).get("date-parts") or [[None]]
        names = [" ".join(p for p in (a.get("given"), a.get("family")) if p) or a.get("name") or ""
                 for a in item.get("author", [])]
        found.append(Candidate(
            source="crossref",
            title=title,
            year=date_parts[0][0] if date_parts[0] else None,
            authors=[n for n in names if n],
            doi=item.get("DOI"),
            url=item.get("URL"),
            venue=(item.get("container-title") or [None])[0],
            abstract=_clean_markup(item.get("abstract")),
        ))
    return found


def openalex(query: str, years: Years | None = None, per_page: int = 5) -> list[Candidate]:
    search = normalize(query)  # lower case, so words like AND/OR are not read as operators
    if not search:
        return []
    params = {
        "search": search,
        "per-page": per_page,
        "select": "id,doi,display_name,publication_year,authorships,primary_location,is_retracted,"
                  "abstract_inverted_index",
    }
    if years:
        params["filter"] = f"publication_year:{years[0]}-{years[1]}"
    for env_name, param in (("OPENALEX_API_KEY", "api_key"), ("OPENALEX_MAILTO", "mailto")):
        if os.environ.get(env_name):
            params[param] = os.environ[env_name]
    data = _json(_get("https://api.openalex.org/works?" + urllib.parse.urlencode(params), "openalex"))
    found = []
    for work in data.get("results", []):
        doi = work.get("doi") or None
        if doi and doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/"):]
        names = [(a.get("author") or {}).get("display_name") or "" for a in work.get("authorships") or []]
        found.append(Candidate(
            source="openalex",
            title=work.get("display_name") or "",
            year=work.get("publication_year"),
            authors=[n for n in names if n],
            doi=doi,
            url=work.get("id"),
            venue=((work.get("primary_location") or {}).get("source") or {}).get("display_name"),
            retracted=work.get("is_retracted"),
            abstract=_inverted_to_text(work.get("abstract_inverted_index")),
        ))
    return [c for c in found if c.title]


def has_semantic_scholar_key() -> bool:
    """Semantic Scholar's keyless pool rate-limited every call in testing, so it needs a key."""
    return bool(os.environ.get("S2_API_KEY"))


def semantic_scholar(title: str) -> list[Candidate]:
    """Semantic Scholar's title-match endpoint returns its single best match, or 404."""
    params = {"query": title, "fields": "title,year,authors,externalIds,venue,url,abstract"}
    data = _json(_get("https://api.semanticscholar.org/graph/v1/paper/search/match?"
                      + urllib.parse.urlencode(params), "semantic_scholar",
                      {"x-api-key": os.environ.get("S2_API_KEY", "")}))
    found = []
    for paper in data.get("data", []):
        found.append(Candidate(
            source="semantic_scholar",
            title=paper.get("title") or "",
            year=paper.get("year"),
            authors=[a.get("name") for a in paper.get("authors") or [] if a.get("name")],
            doi=(paper.get("externalIds") or {}).get("DOI"),
            url=paper.get("url"),
            venue=paper.get("venue") or None,
            abstract=paper.get("abstract") or None,
        ))
    return [c for c in found if c.title]


_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"
_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "into", "via", "using", "based", "are", "can",
    "its", "our", "their", "than", "which", "when", "where", "have", "has", "was", "were", "been",
    "these", "those", "such", "also", "between", "over", "more", "most", "each", "not",
}


def arxiv(text: str, max_results: int = 3, field: str = "ti") -> list[Candidate]:
    """field "ti" searches titles; "all" also searches abstracts. All words must match."""
    words = [w for w in normalize(text).split() if len(w) > 2 and w not in _STOP]
    words = words[:8] if field == "ti" else words[:6]
    if not words:
        return []
    query = " AND ".join(f"{field}:{w}" for w in words)
    body = _get("https://export.arxiv.org/api/query?"
                + urllib.parse.urlencode({"search_query": query, "max_results": max_results}), "arxiv")
    if not body:
        return []
    try:
        root = ET.fromstring(body)
    except ET.ParseError as err:
        raise SourceError("unreadable reply") from err
    found = []
    for entry in root.findall(f"{_ATOM}entry"):
        published = entry.findtext(f"{_ATOM}published") or ""
        names = [a.findtext(f"{_ATOM}name") or "" for a in entry.findall(f"{_ATOM}author")]
        found.append(Candidate(
            source="arxiv",
            title=" ".join((entry.findtext(f"{_ATOM}title") or "").split()),
            year=int(published[:4]) if published[:4].isdigit() else None,
            authors=[n for n in names if n],
            doi=entry.findtext(f"{_ARXIV}doi"),
            url=entry.findtext(f"{_ATOM}id"),
            venue="arXiv",
            abstract=" ".join((entry.findtext(f"{_ATOM}summary") or "").split()) or None,
        ))
    return [c for c in found if c.title]
