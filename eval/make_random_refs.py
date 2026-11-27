"""Build eval/data/random_refs.jsonl: references from published papers drawn at random, as the papers print them,
for testing step 1 on papers nobody picked.

Crossref draws random journal articles (its `sample` parameter) among those whose publisher deposited the
reference list with each reference as printed (Crossref's "unstructured" field). At most --per-publisher papers
come from one publisher, so a few large ones do not fill the set. From each paper, drawn at random:
  - up to --with-doi references that carry a DOI, the answer key. The DOI and links are cut out of the string,
    so a reference must be found by what it says;
  - up to --without-doi references that carry none: books, reports, web pages, theses, papers the publisher
    did not match. No answer key, so these are checked by hand.
Then --fakes made-up references: one reference with the title of another paper's reference put in, so its
authors, year and journal are real but that paper does not exist. No paper already in real_refs.jsonl is used.

    python eval/make_random_refs.py [--papers 25] [--with-doi 10] [--without-doi 4] [--fakes 30] [--seed 7]
    python eval/make_random_refs.py --refake    # the same papers, the made-up references made again
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from citefix.textutil import normalize, parse_reference, title_similarity  # noqa: E402
from make_styles_sample import strip_identifiers  # noqa: E402

UA = {"User-Agent": "citefix-eval/0.1"}
_DOI = re.compile(r"\b10\.\d{4,9}/[^\s,;<>\"]+")


def get(url: str) -> dict | None:
    for attempt in (1, 2, 3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as response:
                return json.load(response)
        except (urllib.error.URLError, OSError, ValueError) as err:
            if attempt == 3:
                print(f"  {url[:90]}: {err}", file=sys.stderr)
                return None
            time.sleep(5 * attempt)
    return None


def printed(raw: str) -> str:
    """The reference as a reader sees it: no markup, one line; the first line of a bilingual one."""
    raw = re.split(r"<br\s*/?>", raw)[0]
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw)).split())


def titles_of(dois: list[str]) -> dict[str, str]:
    """Crossref's title (with subtitle) for each DOI it holds, 40 at a time."""
    found: dict[str, str] = {}
    for start in range(0, len(dois), 40):
        batch = [d for d in dois[start:start + 40] if "," not in d]
        body = get("https://api.crossref.org/works?" + urllib.parse.urlencode({
            "filter": ",".join(f"doi:{d}" for d in batch), "rows": 100, "select": "DOI,title,subtitle"}))
        time.sleep(1)
        for work in ((body or {}).get("message") or {}).get("items") or []:
            title, subtitle = (work.get("title") or [None])[0], (work.get("subtitle") or [None])[0]
            if title:
                if subtitle and normalize(subtitle) not in normalize(title):
                    title = f"{title.rstrip(':')}: {subtitle}"
                found[work["DOI"].lower()] = title
    return found


def chimera(a: dict, b: dict) -> str | None:
    """a's reference with b's title in place of its own, or None unless the parser reads both titles right (as
    their DOIs' records give them), so that a's own title is gone and b's is a real paper's."""
    ra, rb = parse_reference(a["reference"]), parse_reference(b["reference"])
    if not (ra.title and rb.title and ra.first_author and rb.first_author and a["title"] and b["title"]):
        return None
    if (title_similarity(ra.title, a["title"]) < 0.9 or title_similarity(rb.title, b["title"]) < 0.9
            or len(rb.title.split()) < 4 or ra.title not in a["reference"]
            or normalize(ra.first_author) == normalize(rb.first_author)):
        return None
    return a["reference"].replace(ra.title, rb.title, 1)


def make_fakes(rows: list[dict], count: int, rng: random.Random) -> list[dict]:
    pool = [r for r in rows if r["kind"] == "doi"]
    fakes: list[dict] = []
    for _ in range(5000):
        if len(fakes) == count:
            break
        a, b = rng.sample(pool, 2)
        if a["source"] == b["source"] or any(f["made_from"][0] == a["reference"] or f["made_from"][1] == b["reference"]
                                             for f in fakes):
            continue
        made = chimera(a, b)
        if made:
            fakes.append({"source": a["source"], "journal": a["journal"], "publisher": a["publisher"],
                          "reference": made, "doi": None, "title": None, "kind": "fake",
                          "made_from": [a["reference"], b["reference"]]})
    return fakes


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--papers", type=int, default=25)
    parser.add_argument("--with-doi", type=int, default=10)
    parser.add_argument("--without-doi", type=int, default=4)
    parser.add_argument("--fakes", type=int, default=30)
    parser.add_argument("--per-publisher", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default=str(ROOT / "eval" / "data" / "random_refs.jsonl"))
    parser.add_argument("--refake", action="store_true", help="keep the file's papers, make its made-up ones again")
    args = parser.parse_args()
    rng = random.Random(args.seed)
    if args.refake:
        rows = [r for r in (json.loads(line) for line in Path(args.out).read_text(encoding="utf-8").splitlines()
                            if line.strip()) if r["kind"] != "fake"]
        rows += make_fakes(rows, args.fakes, rng)
        Path(args.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        print(f"{sum(r['kind'] == 'fake' for r in rows)} made-up references written to {args.out}")
        return 0
    used = {json.loads(line)["source"].lower() for line in
            (ROOT / "eval" / "data" / "real_refs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()}
    rows: list[dict] = []
    publishers: Counter = Counter()
    journals: set[str] = set()
    papers = draws = 0
    while papers < args.papers and draws < 15:
        draws += 1
        body = get("https://api.crossref.org/works?" + urllib.parse.urlencode({
            "sample": 100, "filter": "type:journal-article,has-references:true,from-pub-date:2015-01-01",
            "select": "DOI,reference,container-title,publisher"}))
        time.sleep(1)
        for work in ((body or {}).get("message") or {}).get("items") or []:
            publisher = work.get("publisher") or "?"
            journal = (work.get("container-title") or ["?"])[0]
            refs = work.get("reference") or []
            printed_refs = [r for r in refs if r.get("unstructured")]
            if (papers >= args.papers or work["DOI"].lower() in used or journal in journals
                    or publishers[publisher] >= args.per_publisher or len(printed_refs) < max(8, len(refs) // 2)):
                continue
            with_doi, without_doi = [], []
            for ref in printed_refs:
                text = printed(ref["unstructured"])
                doi = ref.get("DOI") or (_DOI.search(text).group(0).rstrip(".") if _DOI.search(text) else None)
                reference = strip_identifiers(text)
                if len(reference) < 25:
                    continue
                row = {"source": work["DOI"], "journal": journal, "publisher": publisher, "reference": reference,
                       "doi": doi.lower() if doi else None, "asserted_by": ref.get("doi-asserted-by")}
                (with_doi if doi else without_doi).append(row)
            if len(with_doi) < 5:
                continue
            for row in rng.sample(with_doi, min(args.with_doi, len(with_doi))):
                rows.append(dict(row, kind="doi"))
            for row in rng.sample(without_doi, min(args.without_doi, len(without_doi))):
                rows.append(dict(row, kind="no-doi"))
            papers += 1
            publishers[publisher] += 1
            journals.add(journal)
            print(f"{papers:>2}. {publisher[:38]:<38} | {journal[:45]:<45} | {len(with_doi)} with DOI, "
                  f"{len(without_doi)} without", flush=True)
    titles = titles_of(sorted({r["doi"] for r in rows if r["doi"]}))
    for row in rows:
        row["title"] = titles.get(row["doi"]) if row["doi"] else None

    # Made-up references: real authors, year and journal, with the title of a reference from another paper.
    rows += make_fakes(rows, args.fakes, rng)
    Path(args.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    kinds = Counter(r["kind"] for r in rows)
    print(f"\n{papers} papers from {len(publishers)} publishers; {kinds['doi']} references with a DOI, "
          f"{kinds['no-doi']} without, {kinds['fake']} made up -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
