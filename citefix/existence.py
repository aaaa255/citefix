"""Step 1: does each reference point to a paper that exists?

Existence is decided only from records that scholarly indexes return, never from a
language model's memory: made-up references are exactly what language models produce.
"""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from functools import partial

from . import sources
from .sources import Candidate
from .textutil import ParsedRef, normalize, parse_reference, partial_similarity, plausible_abstract, title_similarity

VERIFIED = "verified"
SUSPICIOUS = "suspicious"
NOT_FOUND = "not_found"

SAME_PAPER = 0.90  # title similarity at or above this counts as the same paper
RELATED = 0.75  # below this, the closest record is a different paper

_CJK = re.compile(r"[一-鿿]+")
_PREPRINT = re.compile(r"\b(?:arxiv|biorxiv|medrxiv|chemrxiv|ssrn|corr|preprint)\b", re.IGNORECASE)


@dataclass
class Scored:
    cand: Candidate
    score: float
    via: str  # "title": compared with the parsed title; "text": found inside the raw reference
    year_ok: bool | None
    author_ok: bool | None
    doi_match: bool | None = None  # None when the reference or the record has no DOI


@dataclass
class Lookup:
    source: str
    query: str
    results: int = 0
    best_title: str | None = None
    best_score: float | None = None
    error: str | None = None
    ms: int = 0


@dataclass
class ExistenceResult:
    reference: str
    parsed: ParsedRef
    verdict: str
    reason: str
    match: Scored | None
    trace: list[Lookup] = field(default_factory=list)
    seconds: float = 0.0
    abstract: str | None = None  # of the matched paper, for step 2
    abstract_source: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def author_matches(surname: str, names: list[str]) -> bool:
    """Is the cited first author among these names? Sources write names in different orders
    ("Tom B. Brown", "Brown, Tom B.", "志华 周"), so any word of a name may be the surname."""
    if _CJK.fullmatch(surname):
        return any(sorted(name.replace(" ", "")) == sorted(surname) for name in names)
    wanted = normalize(surname).split()
    return bool(wanted) and any(wanted[-1] in normalize(name).split() for name in names)


def _cut_short(ref: ParsedRef, cand: Candidate) -> bool:
    """The parser can stop a title at a question mark that a subtitle follows ("...for weight loss?
    A systematic review..."). Then the record's full title starts with the parsed one and appears
    whole in the reference."""
    parsed, full = normalize(ref.title or ""), normalize(cand.title)
    return (len(full.split()) > len(parsed.split()) >= 4 and full.startswith(parsed + " ")
            and f" {full} " in f" {normalize(ref.text)} ")


def score(ref: ParsedRef, cand: Candidate) -> Scored:
    if ref.title:
        value, via = title_similarity(ref.title, cand.title), "title"
        if value < 1.0 and _cut_short(ref, cand):
            value = 1.0
    else:
        value, via = partial_similarity(cand.title, ref.text), "text"
    year_ok = None if ref.year is None or cand.year is None else abs(ref.year - cand.year) <= 1
    author_ok = None
    if ref.first_author and cand.authors:
        author_ok = author_matches(ref.first_author, cand.authors[:3])
    doi_match = ref.doi.lower() == cand.doi.lower() if ref.doi and cand.doi else None
    return Scored(cand, value, via, year_ok, author_ok, doi_match)


def _doi_elsewhere(ref: ParsedRef, scored: list[Scored]) -> str | None:
    """Says so when the reference's DOI leads to a clearly different paper: made-up references
    often pair a real title with some other paper's DOI."""
    other = next((s.cand for s in scored if s.doi_match and s.via == "title" and s.score < RELATED), None)
    if other is None:
        return None
    return f"the DOI {ref.doi} leads to a different paper, “{other.title}”" + (f" ({other.year})" if other.year else "")


def _ranking(ref: ParsedRef):
    """How decide() picks a record: the same paper first, then the version of it that the reference cites.
    A preprint and its published version share a title, and indexes list them in no fixed order."""
    wants_preprint = bool(_PREPRINT.search(ref.text))

    def rank(s: Scored) -> tuple:
        same = s.score >= SAME_PAPER  # the version preferences only choose among records of the same paper
        return (same,
                same and s.doi_match is True,  # the version with the cited DOI
                s.year_ok is not False,
                s.author_ok is not False,
                same and s.cand.year == ref.year,  # the version from the cited year
                same and (s.cand.venue_type == "repository") == wants_preprint,  # a preprint only when one is cited
                s.score)
    return rank


def decide(ref: ParsedRef, scored: list[Scored]) -> tuple[str, str, Scored | None]:
    if not scored:
        return NOT_FOUND, "No index returned any record for this reference.", None
    best = max(scored, key=_ranking(ref))
    wrong_doi = _doi_elsewhere(ref, scored)
    if best.score >= SAME_PAPER:
        problems = [wrong_doi] if wrong_doi else []
        if best.year_ok is False:
            problems.append(f"the year is {ref.year} here but {best.cand.year} in {best.cand.source}")
        if best.author_ok is False:
            problems.append(f"first author {ref.first_author} is not among {', '.join(best.cand.authors[:3])}")
        if best.via == "text" and best.author_ok is not True and best.doi_match is not True:
            problems.append("the title was only found loosely and the authors could not be confirmed")
        if best.cand.retracted:
            problems.append("the paper is marked as retracted")
        if problems:
            return SUSPICIOUS, "Paper found, but " + "; ".join(problems) + ".", best
        where = f"DOI {best.cand.doi}" if best.cand.doi else (best.cand.url or "no link")
        return VERIFIED, f"Found in {best.cand.source} ({where}).", best
    tail = f"; {wrong_doi}." if wrong_doi else "."
    if best.score >= RELATED:
        return SUSPICIOUS, f"The closest record only partly matches the title (similarity {best.score:.2f}){tail}", best
    return NOT_FOUND, f"No record with a matching title (closest similarity {best.score:.2f}){tail}", best


def _lookup(ref: ParsedRef, label: str, fn, query: str) -> tuple[Lookup, list[Scored]]:
    step = Lookup(source=label, query=query)
    started = time.monotonic()
    try:
        found = fn(query)
    except Exception as err:  # one failing index must not sink the whole check
        step.error, found = str(err) or type(err).__name__, []
    step.ms = int((time.monotonic() - started) * 1000)
    scored = [score(ref, c) for c in found]
    step.results = len(scored)
    if scored:
        top = max(scored, key=lambda s: s.score)
        step.best_title, step.best_score = top.cand.title, round(top.score, 3)
    return step, scored


def _run(ref: ParsedRef, tasks: list, trace: list[Lookup], scored: list[Scored]) -> None:
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        for step, found in pool.map(lambda task: _lookup(ref, *task), tasks):
            trace.append(step)
            scored.extend(found)


def check_reference(raw: str) -> ExistenceResult:
    started = time.monotonic()
    ref = parse_reference(raw)
    trace: list[Lookup] = []
    scored: list[Scored] = []

    # Round 1: OpenAlex (and Semantic Scholar, with a key) by title, and OpenAlex by DOI when the reference
    # gives one, which costs no credits. Crossref allows only one request per second, so it joins round 1
    # only when no title could be parsed and the whole string is needed.
    if ref.title:
        first = [("openalex", sources.openalex, ref.title)]
        if sources.has_semantic_scholar_key():
            first.append(("semantic_scholar", sources.semantic_scholar, ref.title))
    else:
        first = [("crossref", sources.crossref, ref.text), ("openalex", sources.openalex, ref.text[:200])]
    if ref.doi:
        first.append(("openalex-doi", sources.openalex_doi, ref.doi))
    _run(ref, first, trace, scored)
    verdict, reason, match = decide(ref, scored)

    # Round 2, only without a clean match: Crossref with the whole reference, arXiv, and OpenAlex
    # limited to the cited year, which surfaces the right paper when a later one shares its title.
    if verdict != VERIFIED and ref.title:
        second = [("crossref", sources.crossref, ref.text), ("arxiv", sources.arxiv, ref.title)]
        if ref.year:
            span = (ref.year - 1, ref.year + 1)
            second.append(("openalex-year", partial(sources.openalex, years=span), ref.title))
        words = ref.title.split()
        if len(words) > 8:
            second.append(("openalex-short", sources.openalex, " ".join(words[:8])))
        _run(ref, second, trace, scored)
        verdict, reason, match = decide(ref, scored)

    abstract, abstract_source = _pick_abstract(match, scored, trace)
    return ExistenceResult(raw, ref, verdict, reason, match, trace, round(time.monotonic() - started, 2),
                           abstract, abstract_source)


def _pubmed(doi: str, title: str, trace: list[Lookup]) -> str | None:
    """The abstract PubMed holds for this DOI, if its record has the matched paper's title."""
    step = Lookup(source="pubmed", query=doi)
    started = time.monotonic()
    try:
        found = sources.pubmed_abstract(doi)
    except Exception as err:  # a failing lookup only means no abstract from here
        step.error, found = str(err) or type(err).__name__, None
    step.ms = int((time.monotonic() - started) * 1000)
    if found:
        step.results, step.best_title = 1, found[0]
        step.best_score = round(title_similarity(found[0], title), 3)
    trace.append(step)
    return found[1] if found and step.best_score >= SAME_PAPER and plausible_abstract(found[0], found[1]) else None


def _pick_abstract(match: Scored | None, scored: list[Scored], trace: list[Lookup]) -> tuple[str | None, str | None]:
    """The matched paper's abstract, from whichever index has one, then from PubMed by DOI;
    arXiv by title as a last resort."""
    if not match or match.score < SAME_PAPER:
        return None, None
    year = match.cand.year
    versions = [s for s in (match, *scored) if s.score >= SAME_PAPER
                and (year is None or s.cand.year is None or abs(s.cand.year - year) <= 1)]
    # An index sometimes holds a README or the acknowledgments as the abstract; skip those.
    same = [s for s in versions if plausible_abstract(s.cand.title, s.cand.abstract)]
    if same:
        best = max(same, key=lambda s: s.score)
        return best.cand.abstract, best.cand.source
    title = match.cand.title
    # PubMed has no arXiv DOIs (10.48550/...), so those are not worth asking about.
    dois = [s.cand.doi for s in versions if s.cand.doi and not s.cand.doi.lower().startswith("10.48550/")]
    for doi in list(dict.fromkeys(d.lower() for d in dois))[:2]:
        abstract = _pubmed(doi, title, trace)
        if abstract:
            return abstract, "pubmed"
    if any(step.source == "arxiv" and normalize(step.query) == normalize(title) for step in trace):
        return None, None  # already asked arXiv for exactly this title
    try:
        for cand in sources.arxiv(title):
            if title_similarity(cand.title, title) >= SAME_PAPER and plausible_abstract(cand.title, cand.abstract):
                return cand.abstract, "arxiv"
    except Exception:
        pass
    return None, None


def check_many(references: list[str], workers: int = 3) -> list[ExistenceResult]:
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(check_reference, references))
