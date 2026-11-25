"""Step 3: an agent that looks for a real paper supporting a claim.

The model decides what to search for and which paper to suggest, but it can only suggest a paper
that its own searches returned, its quote must appear in that paper's abstract, and a separate
judge call has to agree that the abstract supports the claim. Otherwise the suggestion goes back
to the agent with the reason.

A rewritten claim goes through the same checks: it must name the paper whose abstract supports it,
either the paper already cited (then the sentence keeps its citation) or one from the searches
(then that paper replaces the citation), and the judge must find the rewrite fully supported.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from dataclasses import dataclass, field

from . import llm, sources
from .sources import Candidate
from .support import PARTIAL, SUPPORTED, judge_support, quote_in
from .textutil import normalize, plausible_abstract, title_similarity

REPLACE = "replace"
REVISE = "revise_claim"
NONE_FOUND = "no_support_found"

CITED = "C"  # the agent's id for the paper the sentence already cites

MAX_TURNS = 10
MAX_SEARCHES = 5
MAX_REJECTIONS = 3

SYSTEM = """You help a student fix a citation. A sentence in their manuscript cites a paper that does not support it, or a reference that does not exist. Find a real paper that supports the claim.

Rules:
- Use search_papers to find papers. You may search up to 5 times, with different keywords each time.
- You may only suggest a paper that search_papers returned, by its id (P1, P2, ...), or the paper already cited, whose id is C when an index has it.
- Prefer the paper that introduced the method or first reported the finding over later papers that use it.
- Back the suggestion with one sentence copied word for word from that paper's abstract.
- If what you find contradicts the claim, or nothing supports it, do not force a citation: submit "revise_claim" with a corrected claim that says no more than one paper's abstract supports, and that paper's id, or "no_support_found". With C the sentence keeps its current citation; with a paper from your searches, that paper replaces it.
- Finish by calling submit."""

TOOLS = [
    {"type": "function", "function": {
        "name": "search_papers",
        "description": "Search scholarly indexes. Returns papers with an id, title, year, authors and abstract.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "A few keywords, e.g. a method name and what it does."},
            "year_from": {"type": "integer", "description": "Optional earliest publication year."},
            "year_to": {"type": "integer", "description": "Optional latest publication year."},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "submit",
        "description": "Give the final answer.",
        "parameters": {"type": "object", "properties": {
            "decision": {"type": "string", "enum": [REPLACE, REVISE, NONE_FOUND]},
            "paper_id": {"type": "string", "description": "Id of the paper the answer rests on: for replace, one "
                         "that search_papers returned; for revise_claim, C or one that search_papers returned."},
            "quote": {"type": "string", "description": "Supporting sentence copied from that paper's abstract."},
            "explanation": {"type": "string", "description": "One or two sentences for the student."},
            "revised_claim": {"type": "string", "description": "The corrected claim (for revise_claim), saying no "
                              "more than that paper's abstract supports."},
        }, "required": ["decision", "explanation"]},
    }},
]


@dataclass
class Step:
    action: str  # search, submit, rejected
    detail: str
    results: int = 0
    errors: list[str] = field(default_factory=list)  # sources that failed during a search


@dataclass
class RepairResult:
    decision: str
    paper: Candidate | None
    quote: str
    explanation: str
    revised_claim: str = ""
    check: str | None = None  # the independent judge's verdict on the suggested paper or the rewrite
    steps: list[Step] = field(default_factory=list)
    keeps_citation: bool = False  # a rewrite that the cited paper itself supports


class Library:
    """Papers the agent has been shown, under short ids, so it cannot suggest a paper it invented.
    The paper already cited, when an index has it, is C, and keeps that id when a search finds it again."""

    def __init__(self, cited: Candidate | None = None) -> None:
        self.papers: dict[str, Candidate] = {}
        self._by_title: dict[str, str] = {}
        self._found = 0
        if cited is not None:
            self.add(cited, CITED)

    def add(self, cand: Candidate, pid: str | None = None) -> str:
        """The id of this paper, merging it with a record of the same paper already here (see _merge)."""
        key = normalize(cand.title)
        known = self._by_title.get(key)
        if known is not None and _same_work(self.papers[known], cand):
            self.papers[known] = _merge(self.papers[known], cand)
            return known
        if pid is None:
            self._found += 1
            pid = f"P{self._found}"
        self._by_title.setdefault(key, pid)
        self.papers[pid] = cand
        return pid


def _published(cand: Candidate) -> bool:
    return cand.venue_type in ("journal", "conference")


def _same_work(a: Candidate, b: Candidate) -> bool:
    """Two records with one title are one paper when their first authors share a name."""
    if not a.authors or not b.authors:
        return True
    names = [{w for w in normalize(c.authors[0]).split() if len(w) > 1} for c in (a, b)]
    return bool(names[0] & names[1])


def _merge(kept: Candidate, new: Candidate) -> Candidate:
    """One record for two versions of a paper: the published version's details, so that a suggestion
    names the journal or proceedings rather than a preprint, and the abstract the agent may already have
    seen, else the other version's when it is a real one."""
    details = new if _published(new) and not _published(kept) else kept
    abstract = next((c.abstract for c in (kept, new) if plausible_abstract(c.title, c.abstract)), details.abstract)
    return dataclasses.replace(details, abstract=abstract)


ARXIV_FILL = 2  # at most this many records are looked up on arXiv per search
ENOUGH = 3  # OpenAlex results with an abstract that make asking Crossref as well unnecessary


def _maybe_on_arxiv(cand: Candidate) -> bool:
    """A preprint, or conference proceedings, whose papers are often on arXiv too."""
    return (cand.venue_type in ("repository", "conference") or "arxiv" in (cand.venue or "").lower()
            or (cand.doi or "").lower().startswith("10.48550/"))


def _arxiv_copies(cands: list[Candidate]) -> tuple[list[Candidate], list[str]]:
    """arXiv's copies of the leading preprint or proceedings records that came without a usable abstract.
    OpenAlex covers arXiv, so a full arXiv search is not needed, but arXiv's own copy has the real abstract
    where OpenAlex holds none or the wrong text. arXiv asks for 3 s between calls, which made a full search
    there the slowest part of every search. Journal papers without an abstract are seldom on arXiv, so they
    are not looked up."""
    missing = [c for c in cands if _maybe_on_arxiv(c) and not plausible_abstract(c.title, c.abstract)][:ARXIV_FILL]
    copies: list[Candidate] = []
    for cand in missing:
        try:
            copies += [a for a in sources.arxiv(cand.title, max_results=2)
                       if title_similarity(a.title, cand.title) >= 0.9]
        except Exception as err:
            return copies, [f"arxiv: {err}"]
    return copies, []


def search(library: Library, query: str, years: sources.Years | None) -> tuple[list[dict], list[str]]:
    """OpenAlex first. Crossref (one request a second) only when OpenAlex gives fewer than ENOUGH papers
    with an abstract, and arXiv only for the leading records that lack one; but a full arXiv search when
    OpenAlex fails or the two together still come up short, since OpenAlex is where arXiv's papers are
    otherwise found."""
    found: list[Candidate] = []
    errors: list[str] = []

    def usable() -> int:
        return sum(plausible_abstract(c.title, c.abstract) for c in found)
    for name, lookup in (("openalex", lambda: sources.openalex(query, years=years, per_page=6)),
                         ("crossref", lambda: sources.crossref(query, years=years, rows=6))):
        if name == "crossref" and usable() >= ENOUGH:
            break
        try:
            found += lookup()
        except Exception as err:
            errors.append(f"{name}: {err}")
    if usable() < ENOUGH or any(e.startswith("openalex") for e in errors):
        try:
            found += sources.arxiv(query, max_results=6, field="all")
        except Exception as err:
            errors.append(f"arxiv: {err}")
    copies, arxiv_errors = _arxiv_copies(found)
    found += copies
    errors += arxiv_errors
    results: list[dict] = []
    for cand in found:
        if years and cand.year and not years[0] <= cand.year <= years[1]:
            continue
        pid = library.add(cand)  # a preprint and its published version become one record
        paper = library.papers[pid]
        if not plausible_abstract(paper.title, paper.abstract):
            continue  # no abstract, or one that is really a README or acknowledgments: nothing to judge
        if any(r["id"] == pid for r in results):
            continue
        results.append({"id": pid, "title": paper.title, "year": paper.year, "authors": paper.authors[:3],
                        "venue": paper.venue, "abstract": paper.abstract[:1500]})
    return results[:8], errors


def _years(args: dict) -> sources.Years | None:
    low, high = args.get("year_from"), args.get("year_to")
    if isinstance(low, int) or isinstance(high, int):
        return (low if isinstance(low, int) else 1900, high if isinstance(high, int) else 2100)
    return None


def check_submission(args: dict, library: Library, claim: str) -> tuple[RepairResult | None, str]:
    """Accept the agent's answer only if it holds up; otherwise say what is wrong with it."""
    decision = args.get("decision")
    explanation = str(args.get("explanation") or "")
    if decision == NONE_FOUND:
        return RepairResult(NONE_FOUND, None, "", explanation), ""
    if decision not in (REPLACE, REVISE):
        return None, "decision must be replace, revise_claim or no_support_found."
    pid = str(args.get("paper_id") or "")
    if decision == REPLACE and pid == CITED:
        return None, "C is the paper already cited. To keep it, rewrite the claim to fit its abstract with revise_claim."
    paper = library.papers.get(pid)
    if paper is None:
        allowed = "C or " if decision == REVISE and CITED in library.papers else ""
        return None, f"paper_id must be {allowed}one of the ids that search_papers returned."
    if not paper.abstract:
        return None, f"{pid} has no abstract, so the answer cannot be checked against it."
    quote = str(args.get("quote") or "")
    if not quote_in(quote, paper.abstract):
        return None, f"That quote is not in the abstract of {pid}. Copy a sentence exactly."
    if decision == REPLACE:
        verdict = judge_support(claim, paper.title, paper.abstract, paper.year)
        if verdict.verdict not in (SUPPORTED, PARTIAL):
            return None, f"An independent check found that {pid} does not support the claim: {verdict.explanation}"
        return RepairResult(REPLACE, paper, quote, explanation, check=verdict.verdict), ""
    revised = str(args.get("revised_claim") or "").strip()
    if not revised:
        return None, "revise_claim needs a revised_claim."
    # The rewrite will carry this paper's citation, so this paper has to support all of it.
    verdict = judge_support(revised, paper.title, paper.abstract, paper.year)
    if verdict.verdict != SUPPORTED:
        return None, (f"An independent check found that the abstract of {pid} does not fully support the corrected "
                      f"claim: {verdict.explanation} Say no more than that abstract supports.")
    return RepairResult(REVISE, paper, quote, explanation, revised, check=verdict.verdict,
                        keeps_citation=pid == CITED), ""


def _brief(claim: str, cited: str, cited_paper: Candidate | None, problem: str) -> str:
    if cited_paper is None:
        paper = "No index has the cited paper, so the sentence cannot keep its current citation."
    else:
        abstract = cited_paper.abstract[:1500] if cited_paper.abstract else "none available"
        paper = f"The cited paper is C: {cited_paper.title} ({cited_paper.year or 'n.d.'}). Its abstract: {abstract}"
    return f"Claim: {claim}\nCurrently cited: {cited}\n{paper}\nProblem: {problem}"


def find_support(claim: str, cited: str, problem: str,
                 on_step: Callable[[Step], None] | None = None,
                 cited_paper: Candidate | None = None) -> RepairResult:
    """Run the agent. on_step, when given, is called with each step as it happens. cited_paper is the
    index record of the cited reference, with its abstract, when the reference was found."""
    library = Library(cited_paper)
    steps: list[Step] = []
    searches = rejections = 0

    def record(step: Step) -> None:
        steps.append(step)
        if on_step:
            on_step(step)
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": _brief(claim, cited, cited_paper, problem)},
    ]
    for _ in range(MAX_TURNS):
        message, _finish = llm.chat(messages, model=llm.AGENT_MODEL, tools=TOOLS,
                                    effort=llm.AGENT_EFFORT, max_tokens=8000)
        # In thinking mode DeepSeek needs reasoning_content passed back on every later request.
        messages.append({"role": "assistant", **{k: message[k] for k in
                         ("content", "reasoning_content", "tool_calls") if message.get(k) is not None}})
        calls = message.get("tool_calls") or []
        if not calls:
            messages.append({"role": "user", "content": "Call submit to give your answer."})
            continue
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except ValueError:
                args = None
            if not isinstance(args, dict):
                reply: dict = {"error": "The arguments were not valid JSON."}
            elif name == "search_papers":
                query = str(args.get("query") or "")
                if searches >= MAX_SEARCHES:
                    reply = {"error": "Search limit reached. Call submit now."}
                else:
                    searches += 1
                    results, errors = search(library, query, _years(args))
                    record(Step("search", query, len(results), errors))
                    reply = {"results": results, **({"errors": errors} if errors else {})}
            elif name == "submit":
                outcome, objection = check_submission(args, library, claim)
                if outcome is not None:
                    shown = outcome.revised_claim or (outcome.paper.title if outcome.paper else outcome.explanation)
                    record(Step("submit", f"{outcome.decision}: {shown}"))
                    outcome.steps = steps
                    return outcome
                rejections += 1
                record(Step("rejected", objection))
                if rejections >= MAX_REJECTIONS:
                    return RepairResult(NONE_FOUND, None, "", "Every suggestion failed verification.", steps=steps)
                reply = {"error": objection}
            else:
                reply = {"error": f"Unknown tool {name}."}
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(reply, ensure_ascii=False)})
    return RepairResult(NONE_FOUND, None, "", "The agent ran out of turns without an answer.", steps=steps)
