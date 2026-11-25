"""Build test passages from the introductions of open-access papers, whose citations are mostly right.

For each PubMed Central id, the script fetches the article's XML, keeps it only if its licence is CC BY
or CC0, takes the first introduction paragraph that cites 4 to 8 different references, renumbers those
citations [1], [2] ... in order of appearance, and writes the references in APA style. The passages go to
eval/data/oa_passages.json with empty label lists, to be labelled by hand before citefix runs on them.

    python eval/make_oa_passages.py PMCID [PMCID ...] [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"
XLINK = "{http://www.w3.org/1999/xlink}href"


def text(element: ET.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def licence(article: ET.Element) -> str | None:
    """"CC BY" or "CC0" when the article may be reused with attribution, else None."""
    for lic in article.iter("license"):
        words = (lic.get(XLINK) or "") + " " + text(lic)
        if re.search(r"creativecommons\.org/publicdomain/zero|\bCC0\b|public domain", words, re.I):
            return "CC0"
        if re.search(r"creativecommons\.org/licenses/by/|Creative Commons Attribution License", words, re.I):
            return "CC BY"
    return None


def paragraph_with_markers(par: ET.Element) -> tuple[str, list[str]]:
    """The paragraph's text with each citation turned into {{rid}}, and the cited ids in order."""
    parts, cited = [], []

    def walk(node: ET.Element) -> None:
        if node.tag == "xref" and node.get("ref-type") == "bibr":
            for rid in (node.get("rid") or "").split():
                parts.append("{{" + rid + "}}")
                cited.append(rid)
        else:
            parts.append(node.text or "")
            for child in node:
                walk(child)
                parts.append(child.tail or "")
    walk(par)
    return " ".join("".join(parts).split()), cited


GROUP = re.compile(r"\[((?:\s*\{\{[^}]+\}\}\s*(?:[,–-]\s*)?)+)\]")  # "[{{r1}}–{{r3}}, {{r7}}]"


def group_ids(inner: str, ref_ids: list[str]) -> list[str]:
    """The reference ids one bracketed citation names; a range takes in every reference between its ends."""
    ids = []
    for piece in re.split(r"\s*,\s*", inner):
        ends = re.findall(r"\{\{([^}]+)\}\}", piece)
        if len(ends) == 2 and re.search(r"[–-]", piece) and all(end in ref_ids for end in ends):
            ids.extend(ref_ids[ref_ids.index(ends[0]):ref_ids.index(ends[1]) + 1])
        else:
            ids.extend(ends)
    return list(dict.fromkeys(ids))


def cited_in_order(body: str, ref_ids: list[str]) -> list[str]:
    return list(dict.fromkeys(rid for m in GROUP.finditer(body) for rid in group_ids(m.group(1), ref_ids)))


def renumber(body: str, order: list[str], ref_ids: list[str]) -> str:
    """Each bracketed citation as [1], [2, 3] ..., numbered in order of first appearance."""
    numbers = {rid: n for n, rid in enumerate(order, 1)}
    return GROUP.sub(lambda m: "[" + ", ".join(str(numbers[rid]) for rid in group_ids(m.group(1), ref_ids)
                                               if rid in numbers) + "]", body)


def apa(ref: ET.Element) -> str:
    cite = next((c for c in (ref.find("element-citation"), ref.find("mixed-citation"), ref.find("citation"))
                 if c is not None), None)
    if cite is None:
        return text(ref)
    names = []
    for name in cite.iter("name"):
        surname, given = text(name.find("surname")), text(name.find("given-names"))
        initials = " ".join(f"{g[0]}." for g in re.split(r"[\s.]+", given) if g)
        names.append(f"{surname}, {initials}".strip(", "))
    if not names:
        names = [text(c) for c in cite.iter("collab")]
    authors = names[0] if len(names) == 1 else ", ".join(names[:-1]) + ", & " + names[-1] if names else ""
    year = text(cite.find("year")) or "n.d."
    title = text(cite.find("article-title")) or text(cite.find("chapter-title"))
    source = text(cite.find("source"))
    if not names or not (title or source):
        return text(cite)  # a citation kept as plain text: use it as it is
    volume, issue = text(cite.find("volume")), text(cite.find("issue"))
    first, last = text(cite.find("fpage")), text(cite.find("lpage"))
    doi = next((text(p) for p in cite.iter("pub-id") if p.get("pub-id-type") == "doi"), "")
    parts = [f"{authors} ({year}).".strip()]
    if title:
        parts.append(title.rstrip(".") + ".")
    where = source
    if volume:
        where += f", {volume}" + (f"({issue})" if issue else "")
    if first:
        where += f", {first}" + (f"–{last}" if last and last != first else "")
    if where:
        parts.append(where + ".")
    if doi:
        parts.append(f"https://doi.org/{doi}")
    return " ".join(parts)


def passage(pmcid: str) -> dict | None:
    query = urllib.parse.urlencode({"db": "pmc", "id": pmcid.removeprefix("PMC"), "retmode": "xml", "tool": "citefix"})
    request = urllib.request.Request(EFETCH + query, headers={"User-Agent": "citefix-eval/0.1"})
    with urllib.request.urlopen(request, timeout=60) as reply:
        root = ET.fromstring(reply.read())
    article = root.find(".//article")
    if article is None or not licence(article):
        print(f"{pmcid}: no CC BY or CC0 licence, skipped", file=sys.stderr)
        return None
    ref_ids = [ref.get("id") for ref in article.iter("ref")]
    refs = {ref.get("id"): ref for ref in article.iter("ref")}
    intro = next((sec for sec in article.iter("sec")
                  if re.match(r"(introduction|background)", text(sec.find("title")), re.I)), None)
    for par in (intro.iter("p") if intro is not None else []):
        body, _ = paragraph_with_markers(par)
        order = [rid for rid in cited_in_order(body, ref_ids) if rid in refs]
        if 4 <= len(order) <= 8 and "{{" not in renumber(body, order, ref_ids):
            meta = article.find(".//article-meta")
            title = text(meta.find(".//article-title"))
            doi = next((text(i) for i in meta.iter("article-id") if i.get("pub-id-type") == "doi"), "")
            year = text(meta.find(".//pub-date/year"))
            journal = text(article.find(".//journal-title"))
            references = "\n".join(f"[{n}] {apa(refs[rid])}" for n, rid in enumerate(order, 1))
            return {"id": "", "topic": title, "source": {"pmcid": pmcid, "title": title, "journal": journal,
                                                         "year": year, "doi": doi, "licence": licence(article)},
                    "text": f"{renumber(body, order, ref_ids)}\n\nReferences\n{references}", "references": [], "citations": []}
    print(f"{pmcid}: no introduction paragraph citing 4 to 8 references", file=sys.stderr)
    return None


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pmcids", nargs="+")
    parser.add_argument("--out", default=str(ROOT / "eval" / "data" / "oa_passages.json"))
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists():
        print(f"{out} already exists and holds hand-made labels, so it is not overwritten.", file=sys.stderr)
        return 1
    passages = []
    for pmcid in args.pmcids:
        found = passage(pmcid)
        time.sleep(0.5)  # NCBI allows 3 requests a second without a key
        if found:
            found["id"] = f"oa{len(passages) + 1:02d}"
            passages.append(found)
            print(f"--- {found['id']} {pmcid} ({found['source']['licence']})\n{found['text']}\n")
    about = ("Introduction paragraphs of open-access papers (CC BY or CC0, attributed in each passage's source), "
             "with their citations renumbered; label each reference and citation by hand before running citefix.")
    out.write_text(json.dumps({"about": about, "passages": passages}, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"saved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
