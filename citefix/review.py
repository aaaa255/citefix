"""The whole check for a passage: find its citations, then run steps 1 to 3 on each one.

review_passage() can report progress through an emit(kind, data) callback; the web app streams
those events to the browser as they happen.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass

from . import llm
from .existence import NOT_FOUND, ExistenceResult, check_reference
from .repair import RepairResult, find_support
from .sources import Candidate
from .support import SUPPORTED, SupportResult, judge_support

Emit = Callable[[str, dict], None]

_HEADING = re.compile(r"^\s*(references|bibliography|works cited|参考文献)\s*[:：]?\s*$", re.IGNORECASE)

EXTRACT_SYSTEM = """You find the citations in a passage from a manuscript.
You are given the passage and its numbered reference list. For every place where the passage cites
references, give the sentence exactly as it appears in the passage, the specific claim those references
are cited for, and the numbers of those references in the list. Map author-year citations such as
(Vaswani et al., 2017) to their numbers. Write each claim as a standalone statement without citation markers.
Answer in json, for example:
{"citations": [{"sentence": "Transformers rely only on attention [1].", "claim": "Transformers rely only on attention.", "refs": [1]}]}"""


@dataclass
class ClaimCheck:
    sentence: str
    claim: str
    ref_number: int
    reference: str
    existence: str  # step 1 verdict for the cited reference
    support: SupportResult | None = None
    repair: RepairResult | None = None
    note: str = ""


@dataclass
class Review:
    references: list[ExistenceResult]
    claims: list[ClaimCheck]

    def to_dict(self) -> dict:
        return asdict(self)


def split_passage(text: str) -> tuple[str, list[str]]:
    """Split at a "References" (or "参考文献") line: body above, one reference per line below."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if _HEADING.match(line):
            return "\n".join(lines[:i]).strip(), [r.strip() for r in lines[i + 1:] if r.strip()]
    return text.strip(), []


def find_citations(body: str, references: list[str]) -> list[dict]:
    numbered = "\n".join(f"[{i}] {ref}" for i, ref in enumerate(references, 1))
    answer = llm.ask_json(EXTRACT_SYSTEM, f"Passage:\n{body}\n\nReference list:\n{numbered}", max_tokens=8000)
    citations = []
    for item in answer.get("citations") or []:
        refs = [r for r in item.get("refs") or [] if isinstance(r, int) and 1 <= r <= len(references)]
        claim = str(item.get("claim") or "").strip()
        if refs and claim:
            citations.append({"sentence": str(item.get("sentence") or claim).strip(), "claim": claim,
                              "refs": list(dict.fromkeys(refs))})
    return citations


# --- formatting papers for people -------------------------------------------------------------

def _surname(name: str) -> str:
    return name.split(",")[0].strip() if "," in name else (name.split() or [""])[-1]


def _initials(name: str) -> str:
    """"Hu, Edward J." gives "E. J."; a hyphenated given name keeps its hyphen, "Ming-Wei" giving "M.-W."."""
    given = name.split(",", 1)[1] if "," in name else " ".join(name.split()[:-1])
    initials = []
    for part in given.replace(".-", "-").replace(".", " ").split():
        letters = [f"{piece[0]}." for piece in part.split("-") if piece and piece[0].isalpha()]
        if letters:
            initials.append("-".join(letters))
    return " ".join(initials)


def short_cite(authors: list[str], year: int | None) -> str:
    """In-text form, e.g. (Ioffe & Szegedy, 2015) or (Lewis et al., 2020)."""
    names = [_surname(a) for a in authors if a.strip()]
    if not names:
        lead = "Unknown"
    elif len(names) == 1:
        lead = names[0]
    elif len(names) == 2:
        lead = f"{names[0]} & {names[1]}"
    else:
        lead = f"{names[0]} et al."
    return f"({lead}, {year})" if year else f"({lead})"


def _published_in(cand: Candidate) -> str | None:
    """Where the paper appeared, with volume, issue and pages when the index has them:
    "Journal of Machine Learning Research, 15(1), 1929–1958." or "In <proceedings> (pp. 4171–4186)."."""
    if not cand.venue:
        return None
    venue = cand.venue.rstrip(".")
    if cand.venue_type == "conference":  # a proceedings "volume" is often just the year, so leave it out
        pages = f" ({'pp.' if '–' in cand.pages else 'p.'} {cand.pages})" if cand.pages else ""
        return f"In {venue}{pages}."
    volume = f"{cand.volume}({cand.issue})" if cand.volume and cand.issue else cand.volume
    return ", ".join(part for part in (venue, volume, cand.pages) if part) + "."


def apa_reference(cand: Candidate) -> str:
    people = [f"{_surname(a)}, {_initials(a)}".rstrip(", ") for a in cand.authors[:20] if a.strip()]
    if len(people) > 1:
        authors = ", ".join(people[:-1]) + ", & " + people[-1]
    else:
        authors = people[0] if people else "Unknown author"
    parts = [f"{authors} ({cand.year or 'n.d.'}). {cand.title.rstrip('.')}."]
    published_in = _published_in(cand)
    if published_in:
        parts.append(published_in)
    if cand.doi:
        parts.append(f"https://doi.org/{cand.doi}")
    elif cand.url:
        parts.append(cand.url)
    return " ".join(parts)


def paper_info(cand: Candidate | None) -> dict | None:
    if cand is None:
        return None
    return {
        "title": cand.title, "year": cand.year, "authors": cand.authors[:6], "venue": cand.venue,
        "source": cand.source, "doi": cand.doi,
        "url": f"https://doi.org/{cand.doi}" if cand.doi else cand.url,
        "short": short_cite(cand.authors, cand.year), "apa": apa_reference(cand),
    }


# --- the check ---------------------------------------------------------------------------------

def _check_claim(index: int, cite: dict, number: int, ref: ExistenceResult, repair: bool, emit: Emit) -> ClaimCheck:
    key = {"index": index, "ref": number}
    result = ClaimCheck(cite["sentence"], cite["claim"], number, ref.reference, ref.verdict)
    try:
        problem = None
        if ref.verdict == NOT_FOUND:
            problem = "The cited reference was not found in any scholarly index; it may not exist."
            emit("note", {**key, "kind": "reference_not_found",
                          "text": "This reference was not found in OpenAlex, Crossref or arXiv, so it may not exist."})
        elif not ref.abstract:
            result.note = "No abstract is available for the cited paper, so support could not be checked."
            emit("note", {**key, "kind": "no_abstract", "text": result.note})
        else:
            paper = ref.match.cand
            result.support = judge_support(cite["claim"], paper.title, ref.abstract, paper.year)
            emit("support", {**key, "verdict": result.support.verdict, "quote": result.support.quote,
                             "quote_found": result.support.quote_found,
                             "explanation": result.support.explanation,
                             "paper": paper_info(paper), "abstract_source": ref.abstract_source})
            if result.support.verdict != SUPPORTED:
                problem = (f"The cited paper's abstract does not clearly support the claim "
                           f"({result.support.verdict}): {result.support.explanation}")
        if problem and repair:
            emit("agent_start", key)
            fix = find_support(cite["claim"], ref.reference, problem, on_step=lambda step: emit(
                "agent_step", {**key, "action": step.action, "detail": step.detail, "results": step.results,
                               "errors": step.errors}))
            result.repair = fix
            emit("repair", {**key, "decision": fix.decision, "paper": paper_info(fix.paper), "quote": fix.quote,
                            "explanation": fix.explanation, "revised_claim": fix.revised_claim, "check": fix.check})
    except llm.LLMError as err:
        emit("claim_error", {**key, "message": str(err)})
    return result


def _reference_event(number: int, ref: ExistenceResult) -> dict:
    return {"number": number, "verdict": ref.verdict, "reason": ref.reason,
            "paper": paper_info(ref.match.cand if ref.match else None), "has_abstract": bool(ref.abstract)}


def review_passage(text: str, repair: bool = True, emit: Emit | None = None,
                   max_references: int = 60, max_checks: int = 40) -> Review:
    emit = emit or (lambda kind, data: None)
    body, references = split_passage(text)
    if not references:
        raise ValueError("No reference list found. Put the references after a line that says "
                         "References (or 参考文献), one per line.")
    if len(references) > max_references:
        raise ValueError(f"This check takes at most {max_references} references at a time; "
                         f"the text has {len(references)}.")
    emit("start", {"body": body, "references": references})

    existence: list[ExistenceResult | None] = [None] * len(references)
    citations: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        pending = {pool.submit(check_reference, ref): i for i, ref in enumerate(references)}
        if body:
            pending[pool.submit(find_citations, body, references)] = "citations"
        for future in as_completed(pending):
            tag = pending[future]
            if tag == "citations":
                citations = future.result()
                emit("citations", {"items": [{"index": n, **c} for n, c in enumerate(citations)]})
            else:
                existence[tag] = future.result()
                emit("reference", _reference_event(tag + 1, existence[tag]))

    pairs = [(n, cite, number) for n, cite in enumerate(citations) for number in cite["refs"]]
    if len(pairs) > max_checks:
        emit("notice", {"text": f"Only the first {max_checks} of {len(pairs)} citations were checked."})
        pairs = pairs[:max_checks]
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(
            lambda p: _check_claim(p[0], p[1], p[2], existence[p[2] - 1], repair, emit), pairs))
    return Review(existence, claims)
