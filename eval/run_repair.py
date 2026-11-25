"""Measure step 3 (the agent that finds a real supporting paper) on claims that cite the wrong paper.

An item with an expected_title succeeds when the agent suggests that paper. An item whose
expected_title is null has a false claim, and succeeds when the agent suggests no paper for the
claim as written; a rewrite of the claim, with the paper that supports the rewrite, is fine.

    python eval/run_repair.py [--data FILE]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from citefix import llm  # noqa: E402
from citefix.existence import SAME_PAPER, check_many  # noqa: E402
from citefix.repair import REPLACE, REVISE, find_support  # noqa: E402
from citefix.textutil import title_similarity  # noqa: E402

PROBLEM = "The cited paper's abstract does not support this claim."


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", default=str(ROOT / "eval" / "data" / "repair_sample.jsonl"))
    args = parser.parse_args()
    lines = Path(args.data).read_text(encoding="utf-8").splitlines()
    items = [json.loads(line) for line in lines if line.strip()]

    before, started = llm.balance(), time.monotonic()
    # As in the web app, the agent gets the cited paper's record and abstract when an index has it.
    cited = {}
    for ref in check_many(sorted({item["cited"] for item in items})):
        if ref.match and ref.match.score >= SAME_PAPER:
            cited[ref.reference] = dataclasses.replace(ref.match.cand, abstract=ref.abstract)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda item: find_support(item["claim"], item["cited"], PROBLEM,
                                                          cited_paper=cited.get(item["cited"])), items))

    rows = []
    for item, result in zip(items, results):
        suggested = result.paper.title if result.paper else None
        expected = item.get("expected_title")
        if expected:
            right = result.decision == REPLACE and bool(suggested) and title_similarity(suggested, expected) >= 0.9
        else:
            right = result.decision != REPLACE
        searches = [s.detail for s in result.steps if s.action == "search"]
        rejected = [s.detail for s in result.steps if s.action == "rejected"]
        shown = suggested if result.decision == REPLACE else (result.revised_claim or result.explanation)
        if result.decision == REVISE:
            shown += " | keeps the citation" if result.keeps_citation else f" | cites {suggested}"
        print(f"{'ok  ' if right else 'MISS'} {item['id']:<4} -> {result.decision:<16} {shown}")
        print(f"       {len(searches)} searches: {' | '.join(searches)}")
        for objection in rejected:
            print(f"       rejected: {objection}")
        version = result.paper.venue_type if result.paper else None
        if result.paper:
            print(f"       version: {version or 'unknown'}, {result.paper.venue or 'no venue'}, doi {result.paper.doi}")
        rows.append({"id": item["id"], "decision": result.decision, "suggested": suggested,
                     "suggested_venue": result.paper.venue if result.paper else None, "suggested_version": version,
                     "expected": expected, "right": right, "check": result.check,
                     "revised_claim": result.revised_claim, "keeps_citation": result.keeps_citation,
                     "searches": searches, "rejected": rejected})

    print(f"\nsucceeded: {sum(r['right'] for r in rows)}/{len(rows)}")
    papers = [r for r in rows if r["suggested"]]
    print(f"suggested papers that are preprints: {sum(r['suggested_version'] == 'repository' for r in papers)}"
          f"/{len(papers)}")
    print(f"searches per claim: {sum(len(r['searches']) for r in rows) / len(rows):.1f}")
    print(llm.usage_summary(before))
    print(f"time: {time.monotonic() - started:.0f} s")

    out = ROOT / "eval" / "results" / f"repair-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"saved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
