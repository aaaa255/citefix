"""How step 1 reads and finds references in many citation styles (eval/data/styles_sample.jsonl, made by
eval/make_styles_sample.py): per style, how often the title, first author and year are read right, and with
--lookup how often the paper is found, and found right (the matched record has the expected title).

    python eval/run_styles.py [--lookup [--model]] [--styles apa ieee ...] [--variants "as written" typos ...]

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
from citefix.existence import VERIFIED, check_many  # noqa: E402
from citefix.textutil import normalize, parse_reference, title_similarity  # noqa: E402


def title_ok(parsed: str | None, wanted: str | None) -> bool:
    return bool(parsed and wanted) and title_similarity(parsed, wanted) >= 0.9


def author_ok(parsed: str | None, wanted: str | None) -> bool:
    if not parsed or not wanted:
        return False
    return normalize(parsed).split()[-1:] == normalize(wanted).split()[-1:]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lookup", action="store_true", help="also run step 1's lookups")
    parser.add_argument("--model", action="store_true", help="with --lookup: let the model read what the rules cannot")
    parser.add_argument("--styles", nargs="*")
    parser.add_argument("--variants", nargs="*")
    args = parser.parse_args()
    rows = [json.loads(line) for line in (ROOT / "eval" / "data" / "styles_sample.jsonl").read_text(encoding="utf-8")
            .splitlines() if line.strip()]
    rows = [r for r in rows if (not args.styles or r["style"] in args.styles)
            and (not args.variants or r["variant"] in args.variants)]

    for r in rows:
        ref = parse_reference(r["reference"])
        r["parsed"] = {"title": ref.title, "first_author": ref.first_author, "year": ref.year}
        r["title_ok"] = title_ok(ref.title, r["title"])
        r["author_ok"] = author_ok(ref.first_author, r["first_author"])
        r["year_ok"] = None if r["variant"] == "no_year" else ref.year == r["year"]

    if args.lookup:
        if os.environ.get("CITEFIX_EVAL_CACHE") != "0":
            sources.use_disk_cache(ROOT / "eval" / ".cache" / "lookups.jsonl")
        started = time.monotonic()
        extra = {"model": True} if args.model else {}  # so that the script also runs on code from before that option
        results = check_many([r["reference"] for r in rows], workers=3, **extra)
        for r, result in zip(rows, results):
            cand = result.match.cand if result.match else None
            r["verdict"], r["reason"] = result.verdict, result.reason
            r["matched"], r["matched_doi"] = (cand.title, cand.doi) if cand else (None, None)
            # Right: the record has the paper's DOI, or (another version of it, such as the preprint) its title.
            same = cand is not None and ((cand.doi or "").lower() == r["doi"].lower() or title_ok(cand.title, r["title"]))
            r["found_right"] = result.verdict == VERIFIED and same
            r["found_wrong"] = result.verdict == VERIFIED and not same
        print(f"lookups: {time.monotonic() - started:.0f} s for {len(rows)} references\n")

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["style"] if r["variant"] == "as written" else f"{r['style']} / {r['variant']}"].append(r)
    header = f"{'style':<52} {'n':>3} {'title':>6} {'author':>6} {'year':>6}" + (f" {'found':>6} {'wrong':>6}" if args.lookup else "")
    print(header)
    for name in sorted(groups):
        rs = groups[name]
        years = [r for r in rs if r["year_ok"] is not None]
        line = (f"{name:<52} {len(rs):>3} {sum(r['title_ok'] for r in rs):>6} {sum(r['author_ok'] for r in rs):>6} "
                f"{(str(sum(r['year_ok'] for r in years)) if years else '-'):>6}")
        if args.lookup:
            line += f" {sum(r['found_right'] for r in rs):>6} {sum(r['found_wrong'] for r in rs):>6}"
        print(line)
    total = len(rows)
    print(f"\nall: {total} references; title read right {sum(r['title_ok'] for r in rows)}, first author "
          f"{sum(r['author_ok'] for r in rows)}" + (f"; found right {sum(r['found_right'] for r in rows)}, "
                                                    f"verified as the wrong paper {sum(r['found_wrong'] for r in rows)}"
                                                    if args.lookup else ""))
    if args.lookup:
        out = ROOT / "eval" / "results" / f"styles-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        print(f"saved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
