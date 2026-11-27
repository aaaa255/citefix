"""Build eval/data/real_refs.jsonl: references as real published papers print them, each with the DOI it
points to, for testing step 1 on what authors actually write.

Publishers deposit their papers' reference lists with Crossref, and some deposit each reference as printed
(Crossref's "unstructured" field) together with its DOI, asserted by the publisher or matched by Crossref.
This takes recent papers from journals that do, in several fields and house styles, keeps the references
with a DOI, and cuts the DOI and links out of the string, so a reference must be found by what it says.
Acta Physica Sinica prints each reference in English and then in Chinese; the English line is kept.

    python eval/make_real_refs.py [--per-paper 20] [--out FILE]
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from make_styles_sample import strip_identifiers  # noqa: E402

UA = {"User-Agent": "citefix-eval/0.1"}
# Journal, ISSN, how many papers. All deposit printed references with DOIs (checked 2026-11-27).
JOURNALS = [
    ("Scientific Reports", "2045-2322", 2),
    ("Humanities and Social Sciences Communications", "2662-9992", 2),
    ("Acta Physica Sinica", "1000-3290", 2),
    ("Sustainability", "2071-1050", 2),
    ("ACM Computing Surveys", "0360-0300", 2),
    ("Journal of Economic Perspectives", "0895-3309", 2),
]
_DOI = re.compile(r"\b10\.\d{4,9}/[^\s,;<>\"]+")


def get(url: str) -> dict | None:
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as response:
                return json.load(response)
        except (urllib.error.URLError, OSError, ValueError) as err:
            if attempt == 2:
                print(f"  {url[:80]}: {err}", file=sys.stderr)
                return None
            time.sleep(5)
    return None


def printed(raw: str, journal: str) -> str:
    """The reference as a reader sees it: no markup, one line; the English line of a bilingual one."""
    if journal == "Acta Physica Sinica":
        raw = re.split(r"<br\s*/?>", raw)[0]
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw)).split())


def title_of(doi: str) -> str | None:
    work = get("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/:()"))
    time.sleep(1)
    title = ((work or {}).get("message") or {}).get("title") or []
    subtitle = ((work or {}).get("message") or {}).get("subtitle") or []
    if not title:
        return None
    return f"{title[0].rstrip(':')}: {subtitle[0]}" if subtitle and subtitle[0] not in title[0] else title[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--per-paper", type=int, default=20)
    parser.add_argument("--out", default=str(ROOT / "eval" / "data" / "real_refs.jsonl"))
    args = parser.parse_args()
    rows = []
    for journal, issn, papers in JOURNALS:
        found = get(f"https://api.crossref.org/journals/{issn}/works?" + urllib.parse.urlencode({
            "filter": "has-references:true,from-pub-date:2024-01-01", "rows": 20,
            "select": "DOI,reference", "sort": "published", "order": "desc"}))
        time.sleep(1)
        taken = 0
        for work in ((found or {}).get("message") or {}).get("items") or []:
            usable = []
            for ref in work.get("reference") or []:
                raw = ref.get("unstructured")
                if not raw:
                    continue
                text = printed(raw, journal)
                doi = ref.get("DOI") or (_DOI.search(text).group(0).rstrip(".") if _DOI.search(text) else None)
                reference = strip_identifiers(text)
                if doi and len(reference) >= 25:
                    usable.append({"source": work["DOI"], "journal": journal, "reference": reference,
                                   "doi": doi.lower(), "asserted_by": ref.get("doi-asserted-by") or "printed"})
            if len(usable) < 5:
                continue
            rows += usable[:args.per_paper]
            print(f"{journal}: {work['DOI']}, {len(usable[:args.per_paper])} references")
            taken += 1
            if taken == papers:
                break
    for row in rows:
        row["title"] = title_of(row["doi"])
    Path(args.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)} references written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
