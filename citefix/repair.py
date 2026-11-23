"""Step 3: an agent that looks for a real paper supporting a claim.

The model decides what to search for and which paper to suggest, but it can only suggest a paper
that its own searches returned, its quote must appear in that paper's abstract, and a separate
judge call has to agree that the abstract supports the claim. Otherwise the suggestion goes back
to the agent with the reason.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import llm, sources
from .sources import Candidate
from .support import PARTIAL, SUPPORTED, judge_support, quote_in
from .textutil import normalize

REPLACE = "replace"
REVISE = "revise_claim"
NONE_FOUND = "no_support_found"

MAX_TURNS = 10
MAX_SEARCHES = 5
MAX_REJECTIONS = 3

SYSTEM = """You help a student fix a citation. A sentence in their manuscript cites a paper that does not support it, or a reference that does not exist. Find a real paper that supports the claim.

Rules:
- Use search_papers to find papers. You may search up to 5 times, with different keywords each time.
- You may only suggest a paper that search_papers returned, by its id (P1, P2, ...).
- Prefer the paper that introduced the method or first reported the finding over later papers that use it.
- Back the suggestion with one sentence copied word for word from that paper's abstract.
- If what you find contradicts the claim, or nothing supports it, do not force a citation: submit "revise_claim" with a corrected claim, or "no_support_found".
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
            "paper_id": {"type": "string", "description": "Id of the suggested paper (for replace)."},
            "quote": {"type": "string", "description": "Supporting sentence copied from that paper's abstract."},
            "explanation": {"type": "string", "description": "One or two sentences for the student."},
            "revised_claim": {"type": "string", "description": "The corrected claim (for revise_claim)."},
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
    check: str | None = None  # the independent judge's verdict on the suggested paper
    steps: list[Step] = field(default_factory=list)


class Library:
    """Papers the agent has been shown, under short ids, so it cannot suggest a paper it invented."""

    def __init__(self) -> None:
        self.papers: dict[str, Candidate] = {}
        self._by_title: dict[str, str] = {}

    def add(self, cand: Candidate) -> str:
        key = normalize(cand.title)
        pid = self._by_title.get(key)
        if pid is None:
            pid = f"P{len(self.papers) + 1}"
            self._by_title[key] = pid
            self.papers[pid] = cand
        elif cand.abstract and not self.papers[pid].abstract:
            self.papers[pid] = cand
        return pid


def search(library: Library, query: str, years: sources.Years | None) -> tuple[list[dict], list[str]]:
    lookups = {
        "openalex": lambda: sources.openalex(query, years=years, per_page=6),
        "arxiv": lambda: sources.arxiv(query, max_results=6, field="all"),
        "crossref": lambda: sources.crossref(query, years=years, rows=6),  # has abstracts for some papers
    }
    found: list[Candidate] = []
    errors: list[str] = []

    def run(name):
        try:
            return lookups[name](), None
        except Exception as err:
            return [], f"{name}: {err}"

    with ThreadPoolExecutor(max_workers=len(lookups)) as pool:
        for cands, error in pool.map(run, lookups):
            found += cands
            if error:
                errors.append(error)
    results: list[dict] = []
    for cand in found:
        if not cand.abstract:
            continue  # the agent cannot judge a paper without its abstract
        if years and cand.year and not years[0] <= cand.year <= years[1]:
            continue
        pid = library.add(cand)
        if any(r["id"] == pid for r in results):
            continue
        results.append({"id": pid, "title": cand.title, "year": cand.year, "authors": cand.authors[:3],
                        "venue": cand.venue, "abstract": cand.abstract[:1500]})
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
    if decision == REPLACE:
        paper = library.papers.get(str(args.get("paper_id") or ""))
        if paper is None:
            return None, "paper_id is not one of the ids that search_papers returned."
        quote = str(args.get("quote") or "")
        if not quote_in(quote, paper.abstract or ""):
            return None, f"That quote is not in the abstract of {args.get('paper_id')}. Copy a sentence exactly."
        verdict = judge_support(claim, paper.title, paper.abstract or "", paper.year)
        if verdict.verdict not in (SUPPORTED, PARTIAL):
            return None, f"An independent check found that {args.get('paper_id')} does not support the claim: {verdict.explanation}"
        return RepairResult(REPLACE, paper, quote, explanation, check=verdict.verdict), ""
    if decision == REVISE:
        revised = str(args.get("revised_claim") or "").strip()
        if not revised:
            return None, "revise_claim needs a revised_claim."
        paper = library.papers.get(str(args.get("paper_id") or ""))
        quote = str(args.get("quote") or "")
        if paper is not None and not quote_in(quote, paper.abstract or ""):
            paper, quote = None, ""
        return RepairResult(REVISE, paper, quote, explanation, revised), ""
    if decision == NONE_FOUND:
        return RepairResult(NONE_FOUND, None, "", explanation), ""
    return None, "decision must be replace, revise_claim or no_support_found."


def find_support(claim: str, cited: str, problem: str,
                 on_step: Callable[[Step], None] | None = None) -> RepairResult:
    """Run the agent. on_step, when given, is called with each step as it happens."""
    library = Library()
    steps: list[Step] = []
    searches = rejections = 0

    def record(step: Step) -> None:
        steps.append(step)
        if on_step:
            on_step(step)
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Claim: {claim}\nCurrently cited: {cited}\nProblem: {problem}"},
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
                    shown = outcome.paper.title if outcome.paper else outcome.revised_claim or outcome.explanation
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
