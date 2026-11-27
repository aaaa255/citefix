"""Step 1: does each reference point to a paper that exists?

Existence is decided only from records that scholarly indexes return, never from a
language model's memory: made-up references are exactly what language models produce.
A model may help read a reference the rules cannot (check_reference's model option), but only
by copying parts of it, which then serve as search queries.
"""

from __future__ import annotations

import dataclasses
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from functools import partial

from . import llm, sources
from .sources import Candidate
from .textutil import (ParsedRef, normalize, parse_reference, partial_similarity, plausible_abstract, title_similarity,
                       volume_and_page)

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
    via: str  # "title": compared with the parsed title; "text": found inside the raw reference;
    # "fields": the record's author, year and title or volume and page are in the reference (_fields_agree)
    year_ok: bool | None
    author_ok: bool | None
    doi_match: bool | None = None  # the reference's DOI or arXiv id names this record; None when either has none


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


_WHOLE_NUMBER = re.compile(r"(?<!\d)\d+(?!\d)")


def _numbers_in(ref: ParsedRef) -> set[str]:
    """The whole numbers a reference gives (year, volume, issue, pages), leaving out those inside identifiers."""
    text = ref.text
    for ident in filter(None, (ref.doi, ref.arxiv_id, *ref.other_ids)):
        text = text.replace(ident.split(":", 1)[-1], " ")
    return {n.lstrip("0") or "0" for n in _WHOLE_NUMBER.findall(text)}


def _first_number(value: str | None) -> str | None:
    found = _WHOLE_NUMBER.search(value or "")
    return (found.group(0).lstrip("0") or "0") if found else None


def _fields_agree(ref: ParsedRef, cand: Candidate) -> bool:
    """Crossref's way of confirming a match without parsing the reference: the record's details are in it.
    The record's first author must be the reference's (or, when none was read, open it), and its year must be
    there, with either most of its title or both its volume and first page. This finds references in styles
    that leave the title out (AIP: "Y. LeCun, Y. Bengio, and G. Hinton, Nature 521, 436 (2015).") and ones
    whose title the parser could not tell apart, without letting a made-up title by a real author through."""
    if not cand.authors or not cand.year:
        return False
    first = cand.authors[0]
    surname = normalize(first.split(",")[0] if "," in first else (first.split() or [""])[-1])
    if ref.first_author:
        if not author_matches(ref.first_author, [first]):
            return False
    elif len(surname) < 2 or surname not in normalize(ref.text).split()[:3]:
        return False
    numbers = _numbers_in(ref)
    if not {str(cand.year - 1), str(cand.year), str(cand.year + 1)} & numbers:
        return False
    whole, cited = normalize(cand.title), normalize(ref.title or "")
    # Most of the title: but a record whose title is only the start of the cited one is another paper.
    title_seen = partial_similarity(cand.title, ref.text) >= 0.75 and not (cited and whole != cited and whole in cited)
    volume, page = _first_number(cand.volume), _first_number(cand.pages)
    return title_seen or bool(volume and page and volume != page and {volume, page} <= numbers)


def _identifiers(doi: str | None, arxiv_id: str | None) -> set[str]:
    """A paper's DOI and its arXiv id, the latter in the DOI form arXiv gives it (10.48550/arxiv.<id>)."""
    found = {doi.lower()} if doi else set()
    if arxiv_id:
        found.add(f"10.48550/arxiv.{arxiv_id.lower()}")
    return found


def score(ref: ParsedRef, cand: Candidate, named: bool = False) -> Scored:
    """named: the record came from looking up an identifier the reference gives (its DOI, arXiv id or PubMed id),
    so the reference names it, even when the index filed it under its published version's DOI."""
    # A year off by one, or cited up to two years after the record's: journals put papers online a year or two
    # before the printed issue that references give. A year before the record's cannot be that.
    year_ok = None if ref.year is None or cand.year is None else -1 <= ref.year - cand.year <= 2
    author_ok = None
    if ref.first_author and cand.authors:
        author_ok = author_matches(ref.first_author, cand.authors[:3])
    cited, held = _identifiers(ref.doi, ref.arxiv_id), _identifiers(cand.doi, cand.arxiv_id)
    doi_match = True if named else (bool(cited & held) if cited and held else None)
    if ref.title:
        value, via = title_similarity(ref.title, cand.title), "title"
        if value < 1.0 and _cut_short(ref, cand):
            value = 1.0
        # The parser can take the wrong part of a reference for its title, such as a note after the year. A record
        # that the reference's DOI or arXiv id leads to, or that has its first author, is the same paper when the
        # reference spells out the record's whole title. Not when that title is only the start of the cited one:
        # "Attention is all you need" is another paper than "Attention is all you need for graph reasoning".
        if value < SAME_PAPER and (doi_match or author_ok) and normalize(cand.title) not in normalize(ref.title):
            loose = partial_similarity(cand.title, ref.text)
            if loose >= SAME_PAPER:
                value, via = loose, "text"
    else:
        value, via = partial_similarity(cand.title, ref.text), "text"
    if value < SAME_PAPER and _fields_agree(ref, cand):
        value, via = SAME_PAPER, "fields"
    return Scored(cand, value, via, year_ok, author_ok, doi_match)


def _same_script(ref: ParsedRef, cand: Candidate) -> bool:
    """Can the titles be compared? Indexes often hold a Chinese paper under its English title."""
    return not ref.title or bool(_CJK.search(ref.title)) == bool(_CJK.search(cand.title))


def _doi_elsewhere(ref: ParsedRef, scored: list[Scored]) -> str | None:
    """Says so when the reference's DOI or arXiv id leads to a clearly different paper: made-up references
    often pair a real title with some other paper's DOI."""
    other = next((s.cand for s in scored
                  if s.doi_match and s.via == "title" and s.score < RELATED and _same_script(ref, s.cand)), None)
    if other is None:
        return None
    if ref.doi and (not ref.arxiv_id or (other.doi or "").lower() == ref.doi.lower()):
        named = f"the DOI {ref.doi}"
    elif ref.arxiv_id:
        named = f"the arXiv id {ref.arxiv_id}"
    else:
        named = f"the id {ref.other_ids[0]}" if ref.other_ids else "the identifier"
    return f"{named} leads to a different paper, “{other.title}”" + (f" ({other.year})" if other.year else "")


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


UNREGISTERED = "unregistered"  # no DOI agency registered the cited DOI
OTHER_TITLE = "other_title"  # the agency's page for the DOI shows another title
REGISTERED = "registered"  # registered, but no index or agency page to compare the title with


def _doi_problem(ref: ParsedRef, doi_state: str | None) -> str | None:
    if doi_state == UNREGISTERED:
        return f"the DOI {ref.doi} is not registered with any DOI agency"
    if doi_state == OTHER_TITLE:
        return f"the page the DOI {ref.doi} leads to does not show this title"
    return None


def decide(ref: ParsedRef, scored: list[Scored], doi_state: str | None = None) -> tuple[str, str, Scored | None]:
    """doi_state: what the DOI system said about a DOI that no index holds (see _ask_doi_system)."""
    wrong_doi = _doi_elsewhere(ref, scored) or _doi_problem(ref, doi_state)
    if not scored:
        if doi_state == REGISTERED:
            return (SUSPICIOUS, f"The DOI {ref.doi} is registered, but no index holds its record, "
                                "so its title could not be compared.", None)
        tail = f"; {wrong_doi}." if wrong_doi else "."
        return NOT_FOUND, "No index returned any record for this reference" + tail, None
    best = max(scored, key=_ranking(ref))
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
    translated = next((s for s in scored if s.doi_match and not _same_script(ref, s.cand)), None)
    if translated:
        return (SUSPICIOUS, f"Found by its DOI in {translated.cand.source}, which gives the title in another language "
                            f"(“{translated.cand.title}”), so the titles could not be compared.", translated)
    tail = f"; {wrong_doi}." if wrong_doi else "."
    if best.score >= RELATED:
        return SUSPICIOUS, f"The closest record only partly matches the title (similarity {best.score:.2f}){tail}", best
    if doi_state == REGISTERED:
        return (SUSPICIOUS, f"The DOI {ref.doi} is registered, but no index holds its record, "
                            "so its title could not be compared.", None)
    return NOT_FOUND, f"No record with a matching title (closest similarity {best.score:.2f}){tail}", best


def _lookup(ref: ParsedRef, label: str, fn, query: str, named: bool = False) -> tuple[Lookup, list[Scored]]:
    step = Lookup(source=label, query=query)
    started = time.monotonic()
    try:
        found = fn(query)
    except Exception as err:  # one failing index must not sink the whole check
        step.error, found = str(err) or type(err).__name__, []
    step.ms = int((time.monotonic() - started) * 1000)
    scored = [score(ref, c, named) for c in found]
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


def check_reference(raw: str, model: bool = False) -> ExistenceResult:
    """model: when the rules find no record, let a language model read the reference (_reread_with_model)."""
    started = time.monotonic()
    ref = parse_reference(raw)
    trace: list[Lookup] = []
    scored: list[Scored] = []
    doi_state = None

    # Round 1: OpenAlex (and Semantic Scholar, with a key) by title, and OpenAlex by DOI when the reference
    # gives one, which costs no credits. Crossref allows only one request per second, so it joins round 1
    # only when no title could be parsed and the whole string is needed.
    if ref.title:
        first = [("openalex", sources.openalex, ref.title)]
        if sources.has_semantic_scholar_key():
            first.append(("semantic_scholar", sources.semantic_scholar, ref.title))
    else:
        first = [("crossref", sources.crossref, ref.text), ("openalex", sources.openalex, ref.text[:200])]
    # Lookups by an identifier the reference gives cost no OpenAlex credits, and their record is the one it names.
    if ref.doi:
        first.append(("openalex-doi", sources.openalex_doi, ref.doi, True))
    # OpenAlex holds arXiv's papers under the DOI arXiv gives them.
    arxiv_doi = f"10.48550/arXiv.{ref.arxiv_id}" if ref.arxiv_id else None
    if arxiv_doi and (ref.doi or "").lower() != arxiv_doi.lower():
        first.append(("openalex-arxiv", sources.openalex_doi, arxiv_doi, True))
    for key in ref.other_ids:  # PubMed ids, an ACL Anthology address
        first.append((f"openalex-{key.split(':')[0]}", sources.openalex_by_id, key, True))
    _run(ref, first, trace, scored)
    verdict, reason, match = decide(ref, scored)

    # Round 2, only without a clean match: Crossref with the whole reference, arXiv, and OpenAlex
    # limited to the cited year, which surfaces the right paper when a later one shares its title;
    # and arXiv by the cited id when OpenAlex does not have that paper yet.
    if verdict != VERIFIED:
        second = []
        if ref.title:
            second = [("crossref", sources.crossref, ref.text), ("arxiv", sources.arxiv, ref.title)]
            if ref.year:
                span = (ref.year - 1, ref.year + 1)
                second.append(("openalex-year", partial(sources.openalex, years=span), ref.title))
            words = ref.title.split()
            if len(words) > 8:
                second.append(("openalex-short", sources.openalex, " ".join(words[:8])))
        if ref.arxiv_id and not any(s.doi_match for s in scored):
            second.append(("arxiv-id", sources.arxiv_by_id, ref.arxiv_id, True))
        # A reference without a title, as physics journals write them, still gives its year, volume and first
        # page, which together pick out one paper.
        numbers = volume_and_page(ref.text) if ref.year and not ref.title else None
        if numbers:
            second.append(("openalex-numbers", partial(sources.openalex_by_numbers, ref.year, numbers[0]), numbers[1]))
        if second:
            _run(ref, second, trace, scored)
            verdict, reason, match = decide(ref, scored)

    # Last, a DOI that no index holds, or holds under a title in another language: the DOI system knows
    # whether any agency registered it, and China's agency shows the paper's own title.
    if verdict != VERIFIED and ref.doi and not any(s.doi_match and _same_script(ref, s.cand) for s in scored):
        doi_state = _ask_doi_system(ref, trace, scored)
        verdict, reason, match = decide(ref, scored, doi_state)

    # A reference written in no style the rules know: a language model reads it, copying its parts, and the
    # title it copied is searched for. Records are scored against the reference as always.
    if verdict != VERIFIED and model:
        reread = _reread_with_model(ref, trace)
        if reread:
            ref = reread
            scored = [score(ref, s.cand, s.doi_match is True) for s in scored]
            query = " ".join(str(part) for part in (ref.first_author, ref.title, ref.year) if part)
            _run(ref, [("openalex", sources.openalex, ref.title), ("crossref", sources.crossref, query)], trace, scored)
            verdict, reason, match = decide(ref, scored, doi_state)

    abstract, abstract_source = _pick_abstract(match, scored, trace)
    return ExistenceResult(raw, ref, verdict, reason, match, trace, round(time.monotonic() - started, 2),
                           abstract, abstract_source)


READ_SYSTEM = """You read one bibliographic reference, which may be badly formatted, and copy out its parts.
Copy each part exactly as the reference writes it. Do not correct, complete, translate or guess anything;
leave a part empty when the reference does not give it.
Answer in json, for example:
{"title": "Deep learning", "first_author_surname": "LeCun", "year": "2015"}"""


def _reread_with_model(ref: ParsedRef, trace: list[Lookup]) -> ParsedRef | None:
    """A language model's reading of a reference the rules found no record for. Only parts it copied from the
    reference are kept, so it can steer the search but never supply a title, author or year of its own.
    None when it read nothing new."""
    step = Lookup(source="model-reading", query=ref.text[:200])
    started = time.monotonic()
    try:
        answer = llm.ask_json(READ_SYSTEM, f"Reference: {ref.text}", effort="none", max_tokens=600)
    except llm.LLMError as err:
        step.error, answer = str(err), {}
    step.ms = int((time.monotonic() - started) * 1000)
    trace.append(step)
    within = normalize(ref.text)

    def copied(value) -> str | None:
        value = str(value or "").strip()
        return value if normalize(value) and normalize(value) in within else None

    title = copied(answer.get("title"))
    if not title or len(normalize(title)) < 6 or normalize(title) == normalize(ref.title or ""):
        return None
    step.results, step.best_title = 1, title
    surname = copied(answer.get("first_author_surname"))
    year = copied(answer.get("year"))
    return dataclasses.replace(ref, title=title, first_author=surname or ref.first_author,
                               year=int(year[:4]) if year and year[:4].isdigit() else ref.year)


def _ask_doi_system(ref: ParsedRef, trace: list[Lookup], scored: list[Scored]) -> str | None:
    """Asks the DOI system about a DOI that no index holds. An agency's own page that shows the cited title
    confirms the paper (China's DOI agency, whose records the indexes lack); a DOI that no agency registered
    is a mistake. Returns a doi_state for decide(), or None when the page confirmed the title."""
    step = Lookup(source="doi.org", query=ref.doi)
    started = time.monotonic()
    state = page = None
    try:
        registered, url = sources.doi_registration(ref.doi)
    except Exception as err:  # the DOI system being unreachable only means no answer from it
        step.error, registered, url = str(err) or type(err).__name__, None, None
    if registered:
        try:
            page = sources.doi_record_page(url)
        except Exception as err:  # nor does an agency page that cannot be read
            step.error = str(err) or type(err).__name__
    if registered is False:
        state = UNREGISTERED
    elif registered and page is not None:
        title = ref.title if ref.title and len(normalize(ref.title)) >= 6 else None
        wanted, text = (normalize(title), normalize(page)) if title else ("", "")
        # Chinese is written without spaces, so a Chinese title is looked for anywhere in the page.
        if title and (wanted in text if _CJK.search(title) else f" {wanted} " in f" {text} "):
            found = score(ref, Candidate("doi.org", title, ref.year, [], doi=ref.doi, url=url))
            scored.append(found)
            step.results, step.best_title, step.best_score = 1, title, round(found.score, 3)
        else:
            state = OTHER_TITLE if title else REGISTERED
    elif registered:
        state = REGISTERED
    step.ms = int((time.monotonic() - started) * 1000)
    trace.append(step)
    return state


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


def check_many(references: list[str], workers: int = 3, model: bool = False) -> list[ExistenceResult]:
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(lambda ref: check_reference(ref, model), references))
