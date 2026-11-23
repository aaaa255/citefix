"""Step 2: does the cited paper support the sentence that cites it?

The judgement uses only the paper's abstract, and a "supported" verdict needs a quote that
really appears in that abstract: the model is not trusted to remember papers correctly.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import llm
from .textutil import normalize, partial_similarity

SUPPORTED = "supported"
PARTIAL = "partially_supported"
UNSUPPORTED = "not_supported"
UNCLEAR = "insufficient_evidence"
VERDICTS = {SUPPORTED, PARTIAL, UNSUPPORTED, UNCLEAR}

SYSTEM = """You check whether a cited paper supports the claim that cites it.
You are given a claim from a manuscript and the title and abstract of the cited paper.
Judge only from the abstract. Do not use anything you remember about the paper.

Verdicts:
- supported: the abstract states the claim or directly implies it.
- partially_supported: the abstract supports part of the claim, but another part is missing from it or goes beyond it.
- not_supported: the abstract contradicts the claim, or is about something else.
- insufficient_evidence: the abstract is on the right topic but says too little to decide; the full paper might settle it.

Copy, word for word, the one abstract sentence that best supports or contradicts the claim. Leave "quote" empty if there is none.
Answer in json, for example:
{"verdict": "supported", "quote": "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.", "explanation": "The abstract says the model uses only attention, which is what the claim says."}"""


@dataclass
class SupportResult:
    verdict: str
    quote: str
    quote_found: bool  # the quote really appears in the abstract
    explanation: str


def quote_in(quote: str, text: str) -> bool:
    """True when the quote appears in the text, allowing small copying differences."""
    q, t = normalize(quote), normalize(text)
    if not q or not t:
        return False
    return q in t or (len(q.split()) >= 4 and partial_similarity(quote, text) >= 0.9)


def judge_support(claim: str, title: str, abstract: str, year: int | None = None) -> SupportResult:
    paper = f"{title} ({year})" if year else title
    answer = llm.ask_json(SYSTEM, f"Claim: {claim}\n\nCited paper: {paper}\nAbstract: {abstract}")
    verdict = answer.get("verdict") if answer.get("verdict") in VERDICTS else UNCLEAR
    quote = str(answer.get("quote") or "").strip()
    explanation = str(answer.get("explanation") or "").strip()
    found = quote_in(quote, abstract)
    if verdict in (SUPPORTED, PARTIAL) and not found:
        verdict = UNCLEAR
        explanation = "The model's supporting quote is not in the abstract, so its verdict was not accepted. " + explanation
    return SupportResult(verdict, quote, found, explanation)
