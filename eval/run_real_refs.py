"""Step 1 on references as real papers print them (eval/data/real_refs.jsonl, made by eval/make_real_refs.py):
per journal, how many are found right (the matched record has the reference's DOI, or the title of that DOI's
paper, as another version such as its preprint does), verified as another paper, or not verified.

    python eval/run_real_refs.py [--model]

Lookups are kept in eval/.cache/ like the other evaluations (CITEFIX_EVAL_CACHE=0 for fresh ones).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from citefix import sources  # noqa: E402
from citefix.existence import NOT_FOUND, SUSPICIOUS, VERIFIED, check_many  # noqa: E402
from citefix.textutil import title_similarity  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", action="store_true", help="let the model read what the rules cannot")
    args = parser.parse_args()
    rows = [json.loads(line) for line in (ROOT / "eval" / "data" / "real_refs.jsonl").read_text(encoding="utf-8")
            .splitlines() if line.strip()]
    if os.environ.get("CITEFIX_EVAL_CACHE") != "0":
        sources.use_disk_cache(ROOT / "eval" / ".cache" / "lookups.jsonl")
    started = time.monotonic()
    extra = {"model": True} if args.model else {}
    results = check_many([r["reference"] for r in rows], workers=3, **extra)
    for r, result in zip(rows, results):
        cand = result.match.cand if result.match else None
        same = cand is not None and ((cand.doi or "").lower() == r["doi"]
                                     or bool(r["title"]) and title_similarity(cand.title, r["title"]) >= 0.9)
        r.update(verdict=result.verdict, reason=result.reason, matched=cand.title if cand else None,
                 matched_doi=cand.doi if cand else None, right=result.verdict == VERIFIED and same,
                 wrong=result.verdict == VERIFIED and not same)
    print(f"lookups: {time.monotonic() - started:.0f} s for {len(rows)} references\n")

    by_journal: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_journal[r["journal"]].append(r)
    print(f"{'journal':<48} {'n':>3} {'right':>6} {'wrong':>6} {'suspicious':>10} {'not found':>9}")
    for journal, rs in sorted(by_journal.items()):
        print(f"{journal:<48} {len(rs):>3} {sum(r['right'] for r in rs):>6} {sum(r['wrong'] for r in rs):>6} "
              f"{sum(r['verdict'] == SUSPICIOUS for r in rs):>10} {sum(r['verdict'] == NOT_FOUND for r in rs):>9}")
    print(f"\nall: {len(rows)}; found right {sum(r['right'] for r in rows)}, verified as another paper "
          f"{sum(r['wrong'] for r in rows)}, suspicious {sum(r['verdict'] == SUSPICIOUS for r in rows)}, "
          f"not found {sum(r['verdict'] == NOT_FOUND for r in rows)}\n")
    for r in rows:
        if not r["right"]:
            print(f"{'WRONG' if r['wrong'] else r['verdict'].upper()} [{r['journal']}] {r['reference'][:150]}\n"
                  f"    want {r['doi']} {str(r['title'])[:70]!r}\n    got  {r['matched_doi']} {str(r['matched'])[:70]!r}: "
                  f"{r['reason'][:110]}")
    out = ROOT / "eval" / "results" / f"real-refs-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"\nsaved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
