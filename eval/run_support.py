"""Measure step 2 (does the cited paper support the claim?) on labelled claim/reference pairs.

Labels: supported; unsupported (contradicted or off-topic); partial (only part of it is supported).

    python eval/run_support.py [--data FILE]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from citefix import sources  # noqa: E402
from citefix import llm  # noqa: E402
from citefix.existence import check_many  # noqa: E402
from citefix.support import PARTIAL, SUPPORTED, judge_support  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if os.environ.get("CITEFIX_EVAL_CACHE") != "0":  # look each reference up once a week, not once a run
        sources.use_disk_cache(ROOT / "eval" / ".cache" / "lookups.jsonl")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", default=str(ROOT / "eval" / "data" / "support_sample.jsonl"))
    args = parser.parse_args()
    lines = Path(args.data).read_text(encoding="utf-8").splitlines()
    items = [json.loads(line) for line in lines if line.strip()]

    before, started = llm.balance(), time.monotonic()
    references = sorted({item["reference"] for item in items})
    papers = dict(zip(references, check_many(references)))

    def judge(item):
        paper = papers[item["reference"]]
        if not paper.abstract:
            return None
        return judge_support(item["claim"], paper.match.cand.title, paper.abstract, paper.match.cand.year)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(judge, items))

    rows = []
    for item, result in zip(items, results):
        verdict = result.verdict if result else "no_abstract"
        if item["label"] == "supported":
            right = verdict == SUPPORTED
        else:
            right = verdict not in (SUPPORTED, "no_abstract")
        why = result.explanation if result else papers[item["reference"]].reason
        print(f"{'ok  ' if right else 'MISS'} {item['id']:<4} {item['label']:<11} -> {verdict:<22} {why}")
        rows.append({
            "id": item["id"], "label": item["label"], "verdict": verdict, "right": right,
            "quote": result.quote if result else None,
            "quote_found": result.quote_found if result else None,
            "explanation": why,
            "abstract_source": papers[item["reference"]].abstract_source,
        })

    print()
    for label, text in (("supported", "supported claims judged supported:"),
                        ("unsupported", "unsupported claims flagged:       "),
                        ("partial", "partly supported claims flagged:  ")):
        group = [r for r in rows if r["label"] == label]
        print(text, f"{sum(r['right'] for r in group)}/{len(group)}")
    partial = [r for r in rows if r["label"] == "partial"]
    print("partly supported called partial:  ", f"{sum(r['verdict'] == PARTIAL for r in partial)}/{len(partial)}")
    quoted = [r for r in rows if r["quote"]]
    print("quotes found in the abstract:      ", f"{sum(bool(r['quote_found']) for r in quoted)}/{len(quoted)}")
    print("pairs without an abstract:         ", sum(r["verdict"] == "no_abstract" for r in rows))
    print(llm.usage_summary(before))
    print(f"time: {time.monotonic() - started:.0f} s")

    out = ROOT / "eval" / "results" / f"support-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"saved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
