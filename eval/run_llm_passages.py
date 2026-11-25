"""Run the whole check (steps 1 to 3) on labelled passages and compare it with the labels: by default the
literature-review paragraphs a language model wrote (eval/data/llm_passages.json); with --data, any file in
the same format, such as eval/data/oa_passages.json (introductions of open-access papers).

- Step 1: real references should be verified; fabricated ones should not.
- Finding citations: every labelled citation should be found in its passage.
- Step 2: a verdict is right when it is in the citation's accept list. A citation whose list holds only
  "supported" should pass; one whose list lacks "supported" should be flagged; the rest are borderline.
- Step 3: every suggestion is printed and saved, to be checked by reading the suggested paper's abstract.

    python eval/run_llm_passages.py [--data FILE] [--no-repair]
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
from citefix.existence import NOT_FOUND, SUSPICIOUS, VERIFIED  # noqa: E402
from citefix.repair import REPLACE, REVISE  # noqa: E402
from citefix.review import review_passage  # noqa: E402
from citefix.support import SUPPORTED  # noqa: E402
from citefix.textutil import title_similarity  # noqa: E402

# real_error: a detail of the reference is wrong; unindexed: a report or web page the indexes do not hold.
EXPECTED = {"real": {VERIFIED}, "real_error": {SUSPICIOUS}, "fabricated": {SUSPICIOUS, NOT_FOUND},
            "unindexed": {SUSPICIOUS, NOT_FOUND}}


def rate(hits: int, total: int) -> str:
    return f"{hits}/{total}" if total else "n/a"


def check(passage: dict, repair: bool):
    try:
        return review_passage(passage["text"], repair=repair), None
    except (ValueError, llm.LLMError) as err:
        return None, str(err)


def support_verdict(claim) -> str:
    if claim is None:
        return "missed"  # the citation was not found in the passage
    if claim.support:
        return claim.support.verdict
    if claim.existence == NOT_FOUND:
        return "reference_not_found"
    return "no_abstract" if claim.note else "error"


def group(accept: list[str]) -> str:
    if accept == [SUPPORTED]:
        return "pass"
    return "borderline" if SUPPORTED in accept else "flag"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if os.environ.get("CITEFIX_EVAL_CACHE") != "0":  # look each reference up once a week, not once a run
        sources.use_disk_cache(ROOT / "eval" / ".cache" / "lookups.jsonl")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", default=str(ROOT / "eval" / "data" / "llm_passages.json"))
    parser.add_argument("--no-repair", action="store_true", help="skip step 3")
    args = parser.parse_args()
    passages = json.loads(Path(args.data).read_text(encoding="utf-8"))["passages"]

    before, started = llm.balance(), time.monotonic()
    with ThreadPoolExecutor(max_workers=2) as pool:  # the web app also runs two checks at a time
        outcomes = list(pool.map(lambda p: check(p, not args.no_repair), passages))

    rows = []
    for passage, (review, error) in zip(passages, outcomes):
        pid = passage["id"]
        if error:
            print(f"FAIL {pid}: {error}")
            rows.append({"kind": "passage", "id": pid, "error": error})
        for ref in passage["references"]:
            result = review.references[ref["n"] - 1] if review else None
            verdict = result.verdict if result else "not_checked"
            right = verdict in EXPECTED[ref["label"]]
            reason = result.reason if result else error
            print(f"{'ok  ' if right else 'MISS'} {pid} [{ref['n']}] {ref['label']:<10} -> {verdict:<11} {reason}")
            rows.append({"kind": "reference", "id": pid, "n": ref["n"], "label": ref["label"], "verdict": verdict,
                         "right": right, "reason": reason,
                         "match": result.match.cand.title if result and result.match else None,
                         "abstract_source": result.abstract_source if result else None})

        claims = review.claims if review else []
        used = set()
        for cite in passage["citations"]:
            options = [i for i, c in enumerate(claims) if c.ref_number == cite["ref"] and i not in used]
            # Two citations of one reference in one sentence are told apart by their claims.
            if cite.get("claim"):
                best = max(options, key=lambda i: title_similarity(claims[i].claim, cite["claim"]), default=None)
            else:
                best = max(options, key=lambda i: title_similarity(claims[i].sentence, cite["sentence"]), default=None)
            if best is not None:
                used.add(best)
            claim = claims[best] if best is not None else None
            verdict = support_verdict(claim)
            row = {"kind": "citation", "id": pid, "ref": cite["ref"], "accept": cite["accept"], "verdict": verdict,
                   "explanation": claim.support.explanation if claim and claim.support else (claim.note if claim else ""),
                   "quote": claim.support.quote if claim and claim.support else None}
            if cite["accept"] is None:
                # the reference does not exist: right when no paper was judged to support the sentence
                row["group"], row["right"] = "no_paper", verdict in ("reference_not_found", "no_abstract")
            else:
                row["group"], row["right"] = group(cite["accept"]), verdict in cite["accept"]
            fix = claim.repair if claim else None
            if fix:
                row["repair"] = {"decision": fix.decision, "check": fix.check, "quote": fix.quote,
                                 "explanation": fix.explanation, "revised_claim": fix.revised_claim,
                                 "keeps_citation": fix.keeps_citation,
                                 "paper": {"title": fix.paper.title, "year": fix.paper.year, "doi": fix.paper.doi,
                                           "authors": fix.paper.authors[:3]} if fix.paper else None,
                                 "searches": [s.detail for s in fix.steps if s.action == "search"]}
            rows.append(row)
            mark = "ok  " if row["right"] else "MISS"
            print(f"{mark} {pid} cites [{cite['ref']}] {row['group']:<10} -> {verdict:<21} {row['explanation'][:150]}")
            if fix:
                cites = (f"keeps [{cite['ref']}]" if fix.keeps_citation else
                         f"cites {fix.paper.title} ({fix.paper.year})" if fix.paper else "")
                shown = (f"{fix.paper.title} ({fix.paper.year})" if fix.decision == REPLACE and fix.paper
                         else f"{fix.revised_claim} | {cites}" if fix.decision == REVISE else fix.explanation)
                print(f"       step 3 {fix.decision}: {shown}, check: {fix.check}")
        for i, claim in enumerate(claims):
            if i not in used:
                print(f"EXTRA {pid} cites [{claim.ref_number}]: {claim.sentence[:120]}")
                rows.append({"kind": "extra_citation", "id": pid, "ref": claim.ref_number, "sentence": claim.sentence})

    refs = [r for r in rows if r["kind"] == "reference"]
    cites = [r for r in rows if r["kind"] == "citation"]
    judged = [r for r in cites if r["group"] != "no_paper" and r["verdict"] not in
              ("missed", "no_abstract", "reference_not_found", "error")]
    print()
    print("passages that could not be checked:  ", sum(r["kind"] == "passage" for r in rows), "of", len(passages))
    for label, text in (("real", "real references verified:           "),
                        ("real_error", "references with a wrong detail flagged:"),
                        ("unindexed", "reports and pages not verified:     "),
                        ("fabricated", "fabricated references caught:       ")):
        if not any(r["label"] == label for r in refs):
            continue
        group_rows = [r for r in refs if r["label"] == label]
        print(text, rate(sum(r["right"] for r in group_rows), len(group_rows)))
    print("real references called not found:   ",
          rate(sum(r["verdict"] == NOT_FOUND for r in refs if r["label"] == "real"), sum(r["label"] == "real" for r in refs)))
    print("citations found in the passages:     ", rate(sum(r["verdict"] != "missed" for r in cites), len(cites)),
          f"(extra: {sum(r['kind'] == 'extra_citation' for r in rows)})")
    on_papers = [r for r in cites if r["group"] != "no_paper"]
    print("citations of real papers:            ", len(on_papers))
    for reason in ("no_abstract", "reference_not_found", "missed", "error"):
        count = sum(r["verdict"] == reason for r in on_papers)
        if count:
            print(f"  not judged ({reason}):".ljust(38), count)
    print("  judged, verdict in the accept list:", rate(sum(r["right"] for r in judged), len(judged)))
    for name, text in (("pass", "  should pass, passed:               "),
                       ("flag", "  should be flagged, flagged:        ")):
        group_rows = [r for r in judged if r["group"] == name]
        print(text, rate(sum((r["verdict"] == SUPPORTED) == (name == "pass") for r in group_rows), len(group_rows)))
    borderline = [r for r in judged if r["group"] == "borderline"]
    print("  borderline, passed / flagged:      ",
          f"{sum(r['verdict'] == SUPPORTED for r in borderline)} / {sum(r['verdict'] != SUPPORTED for r in borderline)}")
    fixes = [r["repair"] for r in cites if r.get("repair")]
    if fixes:
        print("step 3 runs:                         ", len(fixes), "-",
              ", ".join(f"{name} {sum(f['decision'] == name for f in fixes)}"
                        for name in (REPLACE, REVISE, "no_support_found")))
        rewrites = [f for f in fixes if f["decision"] == REVISE]
        print("  rewrites keeping the citation:     ", sum(f["keeps_citation"] for f in rewrites), "of", len(rewrites))
    print(llm.usage_summary(before))
    print(f"time: {time.monotonic() - started:.0f} s")

    out = ROOT / "eval" / "results" / f"llm-passages-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"saved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
