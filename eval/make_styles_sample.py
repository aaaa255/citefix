"""Build eval/data/styles_sample.jsonl: well-known papers written out in many citation styles, for testing
how step 1 reads and finds references whatever their format.

Each paper's DOI is rendered by the DOI system's content negotiation (citeproc-js with the official CSL styles,
the same styles reference managers use), and its record is kept as the expected answer. The DOI and any link
are then cut from the string, as in Crossref's own matching tests, so a reference must be found by what it
says. A few hand-made "messy" variants of two styles cover what students also write: typos, no punctuation,
all lower case, no year, a note after the reference.

    python eval/make_styles_sample.py [--out FILE]
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from citefix.textutil import normalize  # noqa: E402

# Journal articles, conference papers, a book chapter, a book and preprints, in several fields.
DOIS = [
    "10.1038/nature14539",                  # LeCun et al., Deep learning, Nature 2015
    # Not 10.1126/science.ade9097: the formatter drops its group author and starts the reference with ", Bakhtin".
    "10.1109/cvpr.2016.90",                 # He et al., ResNet, CVPR 2016
    "10.18653/v1/N19-1423",                 # Devlin et al., BERT, NAACL 2019
    "10.1145/3586183.3606763",              # Park et al., Generative agents, UIST 2023
    "10.1016/S0140-6736(20)30183-5",        # Huang et al., Lancet 2020
    "10.1056/NEJMoa2034577",                # Polack et al., NEJM 2020
    "10.1111/j.1467-9280.2006.01693.x",     # Roediger & Karpicke, Psychological Science 2006
    "10.1371/journal.pone.0000308",         # Piwowar et al., PLoS ONE 2007
    "10.1007/978-3-319-24574-4_28",         # Ronneberger et al., U-Net, MICCAI 2015 (book chapter)
    "10.1162/neco.1997.9.8.1735",           # Hochreiter & Schmidhuber, LSTM, Neural Computation 1997
    "10.1038/s41586-021-03819-2",           # Jumper et al., AlphaFold, Nature 2021
    "10.1037/0033-295X.84.2.191",           # Bandura, Self-efficacy, Psychological Review 1977
    "10.1145/544862.544867",                # Yolum & Singh, AAMAS 2002
    "10.1023/A:1008319631231",              # Singh, AI and Law 1999 (single author)
    "10.1093/qje/qjz014",                   # Cengiz et al., minimum wages, QJE 2019
    "10.1007/978-0-387-84858-7",            # Hastie et al., Elements of Statistical Learning (book)
    "10.48550/arXiv.1706.03762",            # Vaswani et al., Attention is all you need (arXiv, DataCite)
    "10.48550/arXiv.2310.08560",            # Packer et al., MemGPT (arXiv, DataCite)
    "10.1145/3065386",                      # Krizhevsky et al., ImageNet classification, CACM 2017
]

STYLES = [
    "apa", "modern-language-association", "chicago-author-date", "chicago-note-bibliography",
    "harvard-cite-them-right", "ieee", "vancouver", "american-medical-association", "nature", "science", "cell",
    "american-chemical-society", "american-institute-of-physics", "association-for-computing-machinery",
    "springer-basic-author-date", "elsevier-harvard", "china-national-standard-gb-t-7714-2015-numeric", "bibtex",
]

UA = {"User-Agent": "citefix-eval/0.1"}
_DOI = re.compile(r"(?:https?://(?:dx\.)?doi\.org/|doi:\s*|DOI:\s*)?\b10\.\d{4,9}/\S+", re.IGNORECASE)
_LINK = re.compile(r"(?:Available (?:at|from):?\s*|Retrieved from\s*|\[Online\]\.?\s*)?https?://\S+", re.IGNORECASE)


def negotiate(doi: str, accept: str) -> str | None:
    request = urllib.request.Request("https://doi.org/" + urllib.parse.quote(doi, safe="/:()"),
                                     headers={**UA, "Accept": accept})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                return response.read().decode("utf-8", "replace").strip()
        except urllib.error.HTTPError as err:
            if err.code in (429, 500, 502, 503, 504) and attempt == 1:
                time.sleep(5)
                continue
            print(f"  {doi} {accept[:40]}: HTTP {err.code}", file=sys.stderr)
            return None
        except OSError as err:
            if attempt == 1:
                time.sleep(5)
                continue
            print(f"  {doi} {accept[:40]}: {err}", file=sys.stderr)
            return None
    return None


def plain(text: str) -> str:
    """What a student copying the reference from a page gets: no markup, one line, no list number. Also without
    what the formatter writes for an empty editor field (", edited by,", "Edited by.", "., ed.") and MLA's
    closing "Crossref", which come from the record, not the style."""
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", "", text)).split())
    text = re.sub(r",\s*edited by,", ",", text)
    text = re.sub(r"\.\s*Edited by,", ",", text)
    text = re.sub(r"\.,\s*ed\.", ".", text)
    text = re.sub(r"\s+Crossref$", "", text)
    return re.sub(r"^\s*(?:\[\d+\]|\(\d+\)|\d+\.)\s*", "", text)


def strip_identifiers(text: str) -> str:
    """The reference without its DOI or links, and without what is left dangling: "doi:", "Available from:"."""
    if text.startswith("@"):  # bibtex: drop whole fields, so the braces stay balanced
        text = re.sub(r"\b(?:url|doi|abstractNote|ISSN|ISBN|note)\s*=\s*\{(?:[^{}]|\{[^{}]*\})*\},?\s*", "", text,
                      flags=re.IGNORECASE)
        return text
    text = _LINK.sub("", text)
    text = _DOI.sub("", text)
    text = re.sub(r"\b(?:doi|DOI|https?)\s*[:.]?\s*(?=[.,;]?\s*$)", "", text.strip())
    text = re.sub(r"(?:,\s*)?(?:doi|url)\s*=\s*\{\s*\}", "", text)  # bibtex fields left empty
    return re.sub(r"\s+([.,;])", r"\1", " ".join(text.split())).rstrip(" ,;")


def expected(csl: dict) -> dict:
    authors = csl.get("author") or []
    first = authors[0] if authors else {}
    issued = (csl.get("issued") or {}).get("date-parts") or [[None]]
    title = csl.get("title")
    title = title[0] if isinstance(title, list) else title
    subtitle = csl.get("subtitle")  # Crossref keeps "Taking Memory Tests Improves ..." apart from "Test-Enhanced Learning"
    subtitle = subtitle[0] if isinstance(subtitle, list) and subtitle else subtitle
    if title and subtitle and normalize(subtitle) not in normalize(title):
        title = f"{title.rstrip(':')}: {subtitle}"
    return {"title": title,
            "first_author": first.get("family") or first.get("literal"),
            "year": issued[0][0] if issued and issued[0] else None,
            "type": csl.get("type")}


def messy(text: str, rng: random.Random) -> dict[str, str]:
    """Ways students write references that no style intended."""
    words = text.split()
    typo = list(words)
    long_words = [i for i, w in enumerate(words) if len(w) > 6 and w.isalpha()]
    for i in rng.sample(long_words, min(2, len(long_words))):
        w = typo[i]
        j = rng.randrange(1, len(w) - 2)
        typo[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]  # two letters swapped
    return {
        "typos": " ".join(typo),
        "lower_case": text.lower(),
        "no_punctuation": re.sub(r"[.,:;()\[\]\"“”']", " ", text),
        "no_year": re.sub(r"\(?\b(?:19|20)\d{2}[a-z]?\b\)?[.,]?", "", text),
        "note_after": text + " Accessed 12 March 2026. Read for the related-work chapter.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "eval" / "data" / "styles_sample.jsonl"))
    args = parser.parse_args()
    rng = random.Random(7)
    rows = []
    for doi in DOIS:
        record = negotiate(doi, "application/vnd.citationstyles.csl+json")
        time.sleep(1)
        if not record:
            continue
        truth = expected(json.loads(record))
        print(f"{doi}: {truth['title']}")
        for style in STYLES:
            written = negotiate(doi, f"text/x-bibliography; style={style}; locale=en-US")
            time.sleep(1)
            if not written:
                continue
            reference = strip_identifiers(plain(written))
            rows.append({"doi": doi, "style": style, "variant": "as written", "reference": reference, **truth})
            if style in ("apa", "ieee"):
                for variant, text in messy(reference, rng).items():
                    rows.append({"doi": doi, "style": style, "variant": variant, "reference": text, **truth})
    Path(args.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)} references written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
