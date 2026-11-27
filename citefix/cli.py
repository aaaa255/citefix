"""Command line entry point.

    python -m citefix check FILE [--trace] [--json]     step 1 on a reference list
    python -m citefix review FILE [--no-repair] [--json] steps 1-3 on a passage with references
    python -m citefix serve [--host H] [--port P]        the web app
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import llm
from .existence import NOT_FOUND, SUSPICIOUS, VERIFIED, check_many
from .repair import REPLACE, REVISE
from .sources import key_hint
from .support import PARTIAL, SUPPORTED, UNCLEAR, UNSUPPORTED
from .textutil import join_wrapped

LABELS = {VERIFIED: "VERIFIED", SUSPICIOUS: "SUSPICIOUS", NOT_FOUND: "NOT FOUND"}
SUPPORT_LABELS = {SUPPORTED: "SUPPORTED", PARTIAL: "PARTLY SUPPORTED", UNSUPPORTED: "NOT SUPPORTED",
                  UNCLEAR: "UNCLEAR"}


def read_text(path: str) -> str:
    return sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")


def read_references(path: str) -> list[str]:
    """One reference per line; a reference wrapped onto several lines is joined back up."""
    return join_wrapped([line for line in read_text(path).splitlines() if not line.lstrip().startswith("#")])


def print_check(results, trace: bool) -> None:
    for number, result in enumerate(results, 1):
        print(f"[{number}] {LABELS[result.verdict]:<10} {result.reason}")
        print(f"     {result.reference}")
        if result.match:
            found = result.match.cand
            kind = "match" if result.verdict == VERIFIED else "closest"
            print(f"     {kind}: {found.title} ({found.year}, {found.source}), similarity {result.match.score:.2f}")
        if trace:
            for step in result.trace:
                outcome = f"error: {step.error}" if step.error else f"{step.results} results, best {step.best_score}"
                print(f"       - {step.source:<17} {outcome} ({step.ms} ms)")
        print()
    print("   ".join(f"{label}: {sum(r.verdict == v for r in results)}" for v, label in LABELS.items()))


def print_review(review) -> None:
    print("References")
    for number, ref in enumerate(review.references, 1):
        print(f"  [{number}] {LABELS[ref.verdict]:<10} {ref.reason}")
    print("\nCitations")
    for i, claim in enumerate(review.claims, 1):
        print(f"\n  {i}. {claim.claim}  -> [{claim.ref_number}]")
        if claim.support:
            print(f"     support: {SUPPORT_LABELS[claim.support.verdict]}. {claim.support.explanation}")
            if claim.support.quote:
                missing = "" if claim.support.quote_found else "  (not found in the abstract)"
                print(f'     quote: "{claim.support.quote}"{missing}')
        elif claim.note:
            print(f"     {claim.note}")
        elif claim.existence == NOT_FOUND:
            print("     support: not checked, the reference itself was not found")
        fix = claim.repair
        if fix:
            for step in fix.steps:
                extra = f" ({step.results} results)" if step.action == "search" else ""
                print(f"       agent {step.action}: {step.detail}{extra}")
            if fix.decision == REPLACE and fix.paper:
                authors = ", ".join(fix.paper.authors[:3])
                print(f'     suggestion: cite "{fix.paper.title}" ({authors}, {fix.paper.year}), checked: {fix.check}')
                print(f'       evidence: "{fix.quote}"')
            elif fix.decision == REVISE:
                print(f"     suggestion: rewrite the claim as: {fix.revised_claim}")
                if fix.keeps_citation:
                    print(f"       keep [{claim.ref_number}]: its abstract supports the rewrite, checked: {fix.check}")
                elif fix.paper:
                    authors = ", ".join(fix.paper.authors[:3])
                    print(f'       and cite "{fix.paper.title}" ({authors}, {fix.paper.year}) instead of '
                          f"[{claim.ref_number}], checked: {fix.check}")
                if fix.quote:
                    print(f'       evidence: "{fix.quote}"')
                print(f"       why: {fix.explanation}")
            else:
                print(f"     no supporting paper found: {fix.explanation}")
    print("\n" + llm.usage_summary())


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="citefix", description="Check citations.")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="step 1 on a file with one reference per line ('-' reads stdin)")
    check.add_argument("file")
    check.add_argument("--trace", action="store_true", help="list every lookup made for each reference")
    check.add_argument("--json", action="store_true", help="print the full results as JSON")
    review = commands.add_parser("review", help="steps 1-3 on a passage followed by a References list")
    review.add_argument("file")
    review.add_argument("--no-repair", action="store_true", help="skip step 3, finding replacements")
    review.add_argument("--json", action="store_true", help="print the full results as JSON")
    serve = commands.add_parser("serve", help="run the web app")
    serve.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to accept other machines")
    serve.add_argument("--port", type=int, default=int(os.environ.get("PORT") or 8765),
                       help="defaults to $PORT when a host sets it, otherwise 8765")
    serve.add_argument("--record", metavar="FILE", help="dev: save each check's events to FILE")
    serve.add_argument("--replay", metavar="FILE", help="dev: answer every check by replaying FILE (labelled)")
    args = parser.parse_args(argv)

    if args.command == "serve":
        from .web import serve as run_server

        run_server(args.host, args.port, record=args.record, replay=args.replay)
        return 0
    if args.command == "review":
        from .review import review_passage  # needs DeepSeek, so only loaded for this command

        try:
            result = review_passage(read_text(args.file), repair=not args.no_repair)
        except (ValueError, llm.LLMError) as err:
            print(err, file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print_review(result)
        failed = {step.source for r in result.references for step in r.trace if step.error}
    else:
        references = read_references(args.file)
        if not references:
            print("No references found in the input.", file=sys.stderr)
            return 1
        results = check_many(references, model=llm.available())
        if args.json:
            print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
            return 0
        print_check(results, args.trace)
        failed = {step.source for r in results for step in r.trace if step.error}
    hint = key_hint(failed)
    if hint and not args.json:
        print("\n" + hint)
    return 0
