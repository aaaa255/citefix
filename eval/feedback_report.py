"""Summarise tester feedback as Markdown, ready to paste into the test record.

    python eval/feedback_report.py [PATH ...] [--all]

Each PATH is a folder of feedback files (default: feedback/; a clone of the private feedback repository
works too) or a saved server log, where every send is a line containing "FEEDBACK {...}".
When a check was sent more than once, only its latest send counts. Replayed checks and sends signed
"test" are left out unless --all is given.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERDICTS = {
    "supported": "supported",
    "partially_supported": "partly supported",
    "not_supported": "not supported",
    "insufficient_evidence": "can't tell from the abstract",
    "reference_not_found": "reference not found",
    "no_abstract": "no abstract to check",
}
FIXES = {"replace": "agent suggested another paper", "rewrite": "agent suggested a rewrite",
         "none": "agent found nothing"}


def _records_in(path: Path) -> tuple[list[dict], int]:
    """Records in one file, and how many entries could not be read."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".json":
        chunks = [text]
    else:
        chunks = [line[line.index("FEEDBACK {") + len("FEEDBACK "):] for line in text.splitlines()
                  if "FEEDBACK {" in line]
    found, broken = [], 0
    for chunk in chunks:
        try:
            record = json.loads(chunk)
        except ValueError:
            broken += 1
            continue
        if isinstance(record, dict) and record.get("id"):
            found.append(record)
    return found, broken


def load(paths: list[Path]) -> tuple[list[dict], int]:
    by_id, broken = {}, 0
    for path in paths:
        files = sorted(path.rglob("*.json")) if path.is_dir() else [path]
        for file in files:
            found, bad = _records_in(file)
            broken += bad
            for record in found:
                by_id[record["id"]] = record  # the same send can be both in a log and in a file
    latest = {}
    for record in sorted(by_id.values(), key=lambda r: r.get("time", "")):
        latest[record.get("check") or record["id"]] = record
    return sorted(latest.values(), key=lambda r: r.get("time", "")), broken


def outcome(citation: dict) -> str:
    verdict = VERDICTS.get(citation.get("verdict"), citation.get("verdict") or "unknown")
    fix = FIXES.get(citation.get("fix"))
    return f"{verdict}, {fix}" if fix else verdict


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def percent(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "-"


def mean(values: list[int]) -> str:
    return f"{sum(values) / len(values):.1f}" if values else "-"


def report(records: list[dict]) -> str:
    marked = [(r, c) for r in records for c in r.get("citations", []) if c.get("vote") in ("right", "wrong")]
    ratings = [r["rating"] for r in records if isinstance(r.get("rating"), int)]
    testers = {r.get("tester") or "(no name)" for r in records}
    lines = ["# Tester feedback", "",
             f"{plural(len(records), 'check')} with feedback from {plural(len(testers), 'tester')} "
             f"({', '.join(sorted(testers))}); {plural(len(marked), 'note')} marked right or wrong.", ""]

    lines += ["## By version", "", "| Version | Checks | Marked notes | Marked right | Mean rating |",
              "|---|---|---|---|---|"]
    by_version = defaultdict(list)
    for record in records:
        by_version[record.get("version") or "unknown"].append(record)
    for version, group in by_version.items():
        votes = [c["vote"] for r in group for c in r.get("citations", []) if c.get("vote")]
        lines.append(f"| {version} | {len(group)} | {len(votes)} | {percent(votes.count('right'), len(votes))} | "
                     f"{mean([r['rating'] for r in group if isinstance(r.get('rating'), int)])} |")

    lines += ["", "## By outcome", "", "| What citefix said | Marked | Right | Wrong | Marked right |",
              "|---|---|---|---|---|"]
    tally = defaultdict(Counter)
    for _, citation in marked:
        tally[outcome(citation)][citation["vote"]] += 1
    for name, votes in sorted(tally.items(), key=lambda item: -sum(item[1].values())):
        total = votes["right"] + votes["wrong"]
        lines.append(f"| {name} | {total} | {votes['right']} | {votes['wrong']} | {percent(votes['right'], total)} |")

    counts = Counter(ratings)
    lines += ["", "## Ratings", "",
              f"Mean {mean(ratings)} from {plural(len(ratings), 'rating')}. "
              + ", ".join(f"{score}: {counts[score]}" for score in range(1, 6)), ""]

    wrong = [(r, c) for r, c in marked if c["vote"] == "wrong"]
    lines += ["## Marked wrong", ""]
    for record, c in wrong:
        lines.append(f"- [{c.get('ref')}] \"{c.get('claim')}\": {outcome(c)}"
                     + (f". Why: \"{c['why']}\"" if c.get("why") else "")
                     + f" ({record.get('tester') or 'no name'}, {record.get('time', '')[:10]})")
        lines.append(f"  - Cited: {c.get('reference') or '-'}")
        if c.get("suggested"):
            lines.append(f"  - Suggested: {c['suggested']}")
    if not wrong:
        lines.append("None.")

    lines += ["", "## Comments", ""]
    commented = [r for r in records if r.get("comment")]
    for record in commented:
        score = f"rated {record['rating']}" if record.get("rating") else "no rating"
        text = record["comment"].replace("\n", " ")
        lines.append(f"- \"{text}\" ({record.get('tester') or 'no name'}, {score}, {record.get('time', '')[:10]})")
    if not commented:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Summarise tester feedback as Markdown.")
    parser.add_argument("paths", nargs="*", type=Path, default=[ROOT / "feedback"],
                        help="folders of feedback files or saved server logs (default: feedback/)")
    parser.add_argument("--all", action="store_true", help="also count replayed checks and sends signed 'test'")
    args = parser.parse_args(argv)
    missing = [str(p) for p in args.paths if not p.exists()]
    if missing:
        print(f"Not found: {', '.join(missing)}", file=sys.stderr)
        return 1
    records, broken = load(args.paths)
    if not args.all:
        records = [r for r in records if not r.get("replay") and (r.get("tester") or "").lower() != "test"]
    if not records:
        print("No feedback to report." + ("" if args.all else " (Replays and 'test' sends are skipped; add --all.)"))
        return 0
    print(report(records), end="")
    if broken:
        print(f"\n{broken} entries could not be read (a log line may have been cut off).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
