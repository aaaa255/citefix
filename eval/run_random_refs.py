"""Step 1 on references from randomly drawn papers (eval/data/random_refs.jsonl, made by eval/make_random_refs.py).

  - with a DOI: found right when the record verified has that DOI, or the title of that DOI's paper (as another
    version such as its preprint does); "verified as another paper" when it has neither;
  - without a DOI: verdicts and matched records are listed for checking by hand;
  - made up: caught when not verified.

    python eval/run_random_refs.py [--model] [--no-openalex-search]

--no-openalex-search leaves out OpenAlex's searches (10 credits each), keeping its lookups by identifier, which
are free: for a run on a day the key's credits are needed by the live site. Lookups are kept in eval/.cache/
like the other evaluations (CITEFIX_EVAL_CACHE=0 for fresh ones).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
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
    parser.add_argument("--no-openalex-search", action="store_true")
    parser.add_argument("--data", default=str(ROOT / "eval" / "data" / "random_refs.jsonl"))
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.data).read_text(encoding="utf-8").splitlines() if line.strip()]
    if os.environ.get("CITEFIX_EVAL_CACHE") != "0":
        sources.use_disk_cache(ROOT / "eval" / ".cache" / "lookups.jsonl")
    if args.no_openalex_search:
        sources.openalex = sources.openalex_by_numbers = lambda *a, **k: []
    started = time.monotonic()
    results = check_many([r["reference"] for r in rows], workers=3, **({"model": True} if args.model else {}))
    for r, result in zip(rows, results):
        cand = result.match.cand if result.match else None
        # The DOI, the arXiv id that DOI is made of (10.48550/arxiv.<id>), or the title of that DOI's paper.
        held = {(cand.doi or "").lower(), f"10.48550/arxiv.{cand.arxiv_id}".lower() if cand.arxiv_id else ""} if cand else set()
        same = cand is not None and r["doi"] is not None and (
            r["doi"] in held or bool(r["title"]) and title_similarity(cand.title, r["title"]) >= 0.9)
        r.update(verdict=result.verdict, reason=result.reason, matched=cand.title if cand else None,
                 matched_doi=cand.doi if cand else None, matched_source=cand.source if cand else None,
                 right=result.verdict == VERIFIED and same,
                 wrong=r["kind"] == "doi" and result.verdict == VERIFIED and not same,
                 failed=sorted({step.source for step in result.trace if step.error}))
    failures = Counter(source for r in rows for source in r["failed"])
    print(f"lookups: {time.monotonic() - started:.0f} s for {len(rows)} references"
          f"{' (no OpenAlex searches)' if args.no_openalex_search else ''}; references with a failed lookup, "
          f"by source: {dict(failures) or 'none'}\n")

    def count(rs: list[dict], verdict: str) -> int:
        return sum(r["verdict"] == verdict for r in rs)

    with_doi = [r for r in rows if r["kind"] == "doi"]
    without = [r for r in rows if r["kind"] == "no-doi"]
    fakes = [r for r in rows if r["kind"] == "fake"]
    by_publisher: dict[str, list[dict]] = defaultdict(list)
    for r in with_doi:
        by_publisher[f"{r['publisher'][:30]} | {r['journal'][:30]}"].append(r)
    print(f"{'with a DOI: publisher | journal':<63} {'n':>3} {'right':>6} {'wrong':>6} {'susp.':>6} {'not f.':>6}")
    for name, rs in sorted(by_publisher.items()):
        print(f"{name:<63} {len(rs):>3} {sum(r['right'] for r in rs):>6} {sum(r['wrong'] for r in rs):>6} "
              f"{count(rs, SUSPICIOUS):>6} {count(rs, NOT_FOUND):>6}")
    print(f"\nwith a DOI: {len(with_doi)}; found right {sum(r['right'] for r in with_doi)}, verified as another "
          f"paper {sum(r['wrong'] for r in with_doi)}, suspicious {count(with_doi, SUSPICIOUS)}, "
          f"not found {count(with_doi, NOT_FOUND)}")
    print(f"without a DOI: {len(without)}; verified {count(without, VERIFIED)}, suspicious "
          f"{count(without, SUSPICIOUS)}, not found {count(without, NOT_FOUND)}")
    print(f"made up: {len(fakes)}; caught {len(fakes) - count(fakes, VERIFIED)} (suspicious {count(fakes, SUSPICIOUS)}, "
          f"not found {count(fakes, NOT_FOUND)}), verified {count(fakes, VERIFIED)}\n")

    for r in with_doi:
        if not r["right"]:
            print(f"{'WRONG' if r['wrong'] else r['verdict'].upper()} [{r['journal'][:30]}] {r['reference'][:160]}\n"
                  f"    want {r['doi']} {str(r['title'])[:80]!r}\n    got  {r['matched_doi']} "
                  f"{str(r['matched'])[:80]!r}: {r['reason'][:120]}")
    print("\n--- without a DOI")
    for r in without:
        print(f"{r['verdict'].upper()} [{r['journal'][:30]}] {r['reference'][:160]}\n"
              f"    got {r['matched_source']} {r['matched_doi']} {str(r['matched'])[:90]!r}")
    print("\n--- made up")
    for r in fakes:
        print(f"{'PASSED' if r['verdict'] == VERIFIED else 'caught'} {r['verdict']}: {r['reference'][:150]}\n"
              f"    {r['reason'][:150]}")
    out = ROOT / "eval" / "results" / f"random-refs-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"\nsaved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
