"""Measure step 1 (does the cited paper exist?) on a labelled set of references.

Labels: real = exists and the details are right; real_error = exists but a detail is wrong;
fabricated = made up for testing.

    python eval/run_existence.py [--data FILE] [--workers N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from citefix import sources  # noqa: E402
from citefix.existence import NOT_FOUND, SUSPICIOUS, VERIFIED, check_many  # noqa: E402
from citefix.sources import key_hint  # noqa: E402

EXPECTED = {"real": {VERIFIED}, "real_error": {SUSPICIOUS}, "fabricated": {SUSPICIOUS, NOT_FOUND}}


def rate(hits: int, total: int) -> str:
    return f"{hits}/{total} ({hits / total:.0%})" if total else "n/a"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if os.environ.get("CITEFIX_EVAL_CACHE") != "0":  # look each reference up once a week, not once a run
        sources.use_disk_cache(ROOT / "eval" / ".cache" / "lookups.jsonl")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", default=str(ROOT / "eval" / "data" / "existence_sample.jsonl"))
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()

    lines = Path(args.data).read_text(encoding="utf-8").splitlines()
    items = [json.loads(line) for line in lines if line.strip()]
    started = time.monotonic()
    results = check_many([item["reference"] for item in items], workers=args.workers)
    wall = time.monotonic() - started

    rows = []
    for item, result in zip(items, results):
        match = result.match
        rows.append({
            "id": item["id"],
            "label": item["label"],
            "style": item.get("style"),
            "verdict": result.verdict,
            "reason": result.reason,
            "match_title": match.cand.title if match else None,
            "match_source": match.cand.source if match else None,
            "similarity": round(match.score, 3) if match else None,
            "parsed_title": result.parsed.title,
            "seconds": result.seconds,
            "failed_lookups": [f"{s.source}: {s.error}" for s in result.trace if s.error],
        })

    for row in rows:
        mark = "ok  " if row["verdict"] in EXPECTED[row["label"]] else "MISS"
        print(f"{mark} {row['id']:<4} {row['label']:<10} -> {row['verdict']:<10} {row['reason']}")

    real = [r for r in rows if r["label"] == "real"]
    wrong = [r for r in rows if r["label"] == "real_error"]
    fake = [r for r in rows if r["label"] == "fabricated"]
    print()
    print("fabricated caught (not verified):  ", rate(sum(r["verdict"] != VERIFIED for r in fake), len(fake)))
    print("real verified:                     ", rate(sum(r["verdict"] == VERIFIED for r in real), len(real)))
    print("real wrongly called NOT FOUND:     ", rate(sum(r["verdict"] == NOT_FOUND for r in real), len(real)))
    print("real_error flagged (not verified): ", rate(sum(r["verdict"] != VERIFIED for r in wrong), len(wrong)))
    print(f"time: {sum(r['seconds'] for r in rows) / len(rows):.1f} s per reference, {wall:.0f} s in total")
    failures = Counter(f.split(":")[0] for r in rows for f in r["failed_lookups"])
    if failures:
        print("failed lookups:", ", ".join(f"{name} x{count}" for name, count in failures.most_common()))
    hint = key_hint(set(failures))
    if hint:
        print(hint)

    out_dir = ROOT / "eval" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"existence-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"saved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
