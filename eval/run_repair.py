"""Measure step 3 (the agent that finds a real supporting paper) on claims that cite the wrong paper.

An item with an expected_title succeeds when the agent suggests that paper. An item whose
expected_title is null has a false claim, and succeeds when the agent suggests no paper for it.

    python eval/run_repair.py [--data FILE]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from citefix import llm  # noqa: E402
from citefix.repair import REPLACE, find_support  # noqa: E402
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
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda item: find_support(item["claim"], item["cited"], PROBLEM), items))

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
        print(f"{'ok  ' if right else 'MISS'} {item['id']:<4} -> {result.decision:<16} {shown}")
        print(f"       {len(searches)} searches: {' | '.join(searches)}")
        for objection in rejected:
            print(f"       rejected: {objection}")
        rows.append({"id": item["id"], "decision": result.decision, "suggested": suggested,
                     "expected": expected, "right": right, "check": result.check,
                     "revised_claim": result.revised_claim, "searches": searches, "rejected": rejected})

    print(f"\nsucceeded: {sum(r['right'] for r in rows)}/{len(rows)}")
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
