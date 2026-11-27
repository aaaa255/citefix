"""Step 1 on books that theses often cite (eval/data/books_sample.jsonl): classic textbooks and monographs in
several fields, many without a DOI, two of them Chinese. A book counts as found when the record verified has
the book's title (its main title, before any subtitle) and the cited first author.

    python eval/run_books.py

Lookups are kept in eval/.cache/ like the other evaluations (CITEFIX_EVAL_CACHE=0 for fresh ones).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from citefix import sources  # noqa: E402
from citefix.existence import VERIFIED, author_matches, check_many  # noqa: E402
from citefix.textutil import normalize  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = [json.loads(line) for line in (ROOT / "eval" / "data" / "books_sample.jsonl").read_text(encoding="utf-8")
            .splitlines() if line.strip()]
    if os.environ.get("CITEFIX_EVAL_CACHE") != "0":
        sources.use_disk_cache(ROOT / "eval" / ".cache" / "lookups.jsonl")
    started = time.monotonic()
    results = check_many([r["reference"] for r in rows], workers=3)
    found = 0
    for r, result in zip(rows, results):
        cand = result.match.cand if result.match else None
        # The record's title may be the book's main title alone ("Self-efficacy") or carry its subtitle.
        held, wanted = (normalize(cand.title), normalize(r["title"])) if cand else ("", "")
        right = (result.verdict == VERIFIED and cand is not None and bool(held)
                 and (held.startswith(wanted) or wanted.startswith(held))
                 and author_matches(r["first_author"], cand.authors[:3]))
        found += right
        where = f"{cand.source}: {cand.title[:50]!r} ({cand.year})" if cand else "-"
        print(f"{'ok  ' if right else 'MISS'} {result.verdict:<10} {r['reference'][:60]:<60} | {where}")
        r.update(verdict=result.verdict, reason=result.reason, matched=cand.title if cand else None,
                 matched_source=cand.source if cand else None, right=right)
    print(f"\nbooks found: {found}/{len(rows)} ({time.monotonic() - started:.0f} s)")
    out = ROOT / "eval" / "results" / f"books-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"saved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
