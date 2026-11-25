"""Judge every labelled claim several times with each judge model, to see how often step 2 flags a
citation it should pass, lets through one it should flag, and changes its mind between runs.

The claims are the cited sentences in eval/data/llm_passages.json, citation numbers removed, and the
pairs in eval/data/support_sample.jsonl. Each reference is looked up once; only the judging repeats.

- should pass: labelled "supported" only. Any other verdict is a false alarm.
- should be flagged: labelled without "supported". A "supported" verdict lets it through.
- borderline: "supported" or another verdict both count as right.

    python eval/run_judge_repeats.py [--models deepseek-flash deepseek-v4-pro] [--runs 3]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from citefix import llm  # noqa: E402
from citefix.existence import check_many  # noqa: E402
from citefix.review import split_passage  # noqa: E402
from citefix.support import SUPPORTED, judge_support  # noqa: E402

MARKER = re.compile(r"\s*\[\d+(?:\s*[,–-]\s*\d+)*\]")
GROUPS = ("pass", "flag", "borderline")


def labelled_claims() -> list[dict]:
    claims = []
    data = json.loads((ROOT / "eval" / "data" / "llm_passages.json").read_text(encoding="utf-8"))
    for passage in data["passages"]:
        _, references = split_passage(passage["text"])
        for cite in passage["citations"]:
            accept = cite["accept"]
            if accept is None:
                continue  # the reference does not exist, so there is nothing to judge
            group = "pass" if accept == [SUPPORTED] else "borderline" if SUPPORTED in accept else "flag"
            claims.append({"id": f"{passage['id']}-{cite['ref']}", "claim": MARKER.sub("", cite["sentence"]),
                           "reference": references[cite["ref"] - 1], "group": group, "accept": accept})
    for line in (ROOT / "eval" / "data" / "support_sample.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            claims.append({"id": item["id"], "claim": item["claim"], "reference": item["reference"],
                           "group": "pass" if item["label"] == "supported" else "flag", "accept": None})
    return claims


def rate(hits: int, total: int) -> str:
    return f"{hits}/{total} ({hits / total:.0%})" if total else "n/a"


def summarize(model: str, rows: list[dict]) -> None:
    mine = [r for r in rows if r["model"] == model and r["verdict"] != "error"]
    print(f"\n== {model}: {len({r['id'] for r in mine})} claims, {len({r['run'] for r in mine})} runs")
    for group, text in (("pass", "should pass, flagged (false alarms):"),
                        ("flag", "should be flagged, passed (misses):  "),
                        ("borderline", "borderline, flagged:                 ")):
        judged = [r for r in mine if r["group"] == group]
        wrong = [r for r in judged if (r["verdict"] == SUPPORTED) == (group == "flag")]
        if group == "borderline":
            wrong = [r for r in judged if r["verdict"] != SUPPORTED]
        print(text, rate(len(wrong), len(judged)), dict(Counter(r["verdict"] for r in judged)))
    exact = [r for r in mine if r["accept"]]
    print("verdict among the accepted ones:     ", rate(sum(r["verdict"] in r["accept"] for r in exact), len(exact)))
    by_claim: dict[str, list[dict]] = {}
    for r in mine:
        by_claim.setdefault(r["id"], []).append(r)
    same_call = sum(len({r["verdict"] == SUPPORTED for r in rs}) == 1 for rs in by_claim.values())
    same_verdict = sum(len({r["verdict"] for r in rs}) == 1 for rs in by_claim.values())
    print("same pass/flag call in every run:    ", rate(same_call, len(by_claim)))
    print("same verdict in every run:           ", rate(same_verdict, len(by_claim)))
    # Majority of the runs, as if the judge were asked several times and the most common call kept.
    for group, text in (("pass", "majority vote, false alarms:         "), ("flag", "majority vote, misses:               ")):
        claims = [rs for rs in by_claim.values() if rs[0]["group"] == group]
        flagged = [rs for rs in claims if sum(r["verdict"] != SUPPORTED for r in rs) * 2 > len(rs)]
        wrong = len(flagged) if group == "pass" else len(claims) - len(flagged)
        print(text, rate(wrong, len(claims)))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", nargs="+", default=["deepseek-flash", "deepseek-v4-pro"])
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    claims = labelled_claims()
    references = sorted({c["reference"] for c in claims})
    papers = dict(zip(references, check_many(references)))
    usable = [c for c in claims if papers[c["reference"]].abstract]
    print(f"{len(usable)} of {len(claims)} claims have an abstract to judge against: "
          + ", ".join(f"{g} {sum(c['group'] == g for c in usable)}" for g in GROUPS))

    rows = []
    for model in args.models:
        before, calls, started = llm.balance(), llm.usage.calls, time.monotonic()

        def judge(job, model=model):
            claim, run = job
            paper = papers[claim["reference"]]
            try:
                verdict = judge_support(claim["claim"], paper.match.cand.title, paper.abstract,
                                        paper.match.cand.year, model=model).verdict
            except llm.LLMError:
                verdict = "error"
            return {"model": model, "run": run, "id": claim["id"], "group": claim["group"],
                    "accept": claim["accept"], "verdict": verdict}

        with ThreadPoolExecutor(max_workers=6) as pool:
            rows += pool.map(judge, [(c, run) for run in range(1, args.runs + 1) for c in usable])
        after = llm.balance()
        spent = f"{before[0] - after[0]:.2f} {after[1]}" if before and after else "unknown"
        errors = sum(r["model"] == model and r["verdict"] == "error" for r in rows)
        print(f"{model}: {llm.usage.calls - calls} calls, {spent}, {time.monotonic() - started:.0f} s, "
              f"{errors} failed calls")

    for model in args.models:
        summarize(model, rows)
    out = ROOT / "eval" / "results" / f"judges-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"\nsaved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
