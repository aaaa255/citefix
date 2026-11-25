"""Text helpers: normalising titles, comparing them, and pulling fields out of a reference."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

_TAG = re.compile(r"<[^>]+>")
_NON_WORD = re.compile(r"[^\w\s]")
_NUMBERING = re.compile(r"^\s*(?:\[\d{1,3}\]|\(\d{1,3}\)|\d{1,3}[.)])\s+")

# Title patterns, tried in order: IEEE puts the title in quotes, APA after "(2017).",
# ACM after "Author. 2017.", and GB/T 7714 before a type tag such as [J] or [C].
_QUOTED_TITLE = re.compile(r"[\"“”](.+?)[,.]?[\"“”]")
_APA_TITLE = re.compile(r"\((?:19|20)\d{2}[a-z]?(?:,[^)]*)?\)\.\s*(.+?[.?!])(?=\s|$)")
_ACM_TITLE = re.compile(r"(?:^|[.,]\s)(?:19|20)\d{2}[a-z]?\.\s+(.+?[.?!])(?=\s|$)")
_GBT_TITLE = re.compile(r"[.．]\s*([^.．\[\]]+?)\s*\[(?:J|M|C|D|R|S|N|P|Z|A|G|EB/OL|J/OL|M/OL|DB/OL)\]")

_PAREN_YEAR = re.compile(r"\(((?:19|20)\d{2})[a-z]?(?:,[^)]*)?\)")
# A bare year, but not one end of a page range (1929–1958) or part of an arXiv id (2010.11929).
_ANY_YEAR = re.compile(r"(?<![\d–—-])((?:19|20)\d{2})[a-z]?(?![\d–—-]|\.\d)")

# A DOI, bare or inside a doi.org link: "10.", the registrant's number, "/", then a suffix that may hold
# almost any character, parentheses included (10.1016/S0140-6736(20)30183-5).
_DOI = re.compile(r"\b10\.\d{4,9}/\S+")

_SURNAME_FIRST = re.compile(r"^([A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+)?)\s*,")  # "Vaswani, A." / "Ashish Vaswani,"
_INITIALS_FIRST = re.compile(r"^(?:[A-Z]\.\s*-?\s*)+([A-Z][\w'’-]+)")  # "K. He," / "M.-W. Chang"
_SURNAME_INITIALS = re.compile(r"^([A-Z][\w'’-]+)\s+[A-Z]{1,3}\s*[,.]")  # "He K, Zhang X" (GB/T)
_CJK_AUTHOR = re.compile(r"^([一-鿿]{2,4})\s*[,，.．、]")  # "周志华." (GB/T, Chinese)


@dataclass
class ParsedRef:
    raw: str
    text: str  # the reference on one line, list numbering removed
    title: str | None
    year: int | None
    first_author: str | None  # surname
    doi: str | None = None


def normalize(text: str) -> str:
    """Lower-case and strip markup, accents and punctuation."""
    text = _TAG.sub(" ", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(_NON_WORD.sub(" ", text.lower()).split())


def extract_title(text: str) -> str | None:
    quoted = _QUOTED_TITLE.search(text)
    if quoted and len(quoted.group(1).split()) >= 3:
        return quoted.group(1).strip()
    for pattern in (_APA_TITLE, _ACM_TITLE, _GBT_TITLE):
        found = pattern.search(text)
        if found:
            return found.group(1).rstrip(".").strip()
    return None


def extract_year(text: str) -> int | None:
    paren = _PAREN_YEAR.search(text)
    if paren:
        return int(paren.group(1))
    years = _ANY_YEAR.findall(text)
    return int(years[-1]) if years else None


def extract_doi(text: str) -> str | None:
    """The first DOI in a reference, without the punctuation that a citation style puts after it."""
    found = _DOI.search(text)
    doi = found.group(0) if found else ""
    while doi:
        if doi[-1] in ".,;:'\"”’]>":
            doi = doi[:-1]
        elif doi[-1] == ")" and doi.count(")") > doi.count("("):
            doi = doi[:-1]
        else:
            break
    return doi or None


def first_author_surname(text: str) -> str | None:
    found = _SURNAME_FIRST.match(text)
    if found:
        return found.group(1).split()[-1]
    for pattern in (_INITIALS_FIRST, _SURNAME_INITIALS, _CJK_AUTHOR):
        found = pattern.match(text)
        if found:
            return found.group(1)
    return None


def parse_reference(raw: str) -> ParsedRef:
    text = _NUMBERING.sub("", " ".join(raw.split()), count=1)
    return ParsedRef(
        raw=raw,
        text=text,
        title=extract_title(text),
        year=extract_year(text),
        first_author=first_author_surname(text),
        doi=extract_doi(text),
    )


# A long reference pasted from a PDF or a word processor can wrap onto several lines.
_ENDS_REFERENCE = re.compile(r"(?:[.。]|\d|https?://\S+|\b10\.\d{4,9}/\S+)$")
_ENDS_MIDWAY = re.compile(r"(?:[&,:;–-]|\band)$")
_STARTS_LINK = re.compile(r"(?:https?://|doi\b)", re.IGNORECASE)
_LINK_CUT = re.compile(r"(?:https?://|\b10\.\d{4,9}/)\S*[./-]$")  # a link the line break cut in two
_PARTICLES = r"(?:(?:van|von|de|da|di|du|del|della|den|der|le|la|ten|ter)\s+)"
_NAME_PARTICLE = re.compile(rf"^{_PARTICLES}+[A-Z]")  # van der Maaten
# A line that opens like an author list starts a reference even when a long list pushed its year onto
# the next line: "Wadden, D., Lin, S., ...", "K. He, X. Zhang, ...", "He K, ...", "Ashish Vaswani, Noam ...".
_FULL_NAME = r"[A-Z][a-z]+(?:\s+[A-Z]\.)*\s+[A-Z][\w'’-]+"
_AUTHOR_START = re.compile(rf"^{_PARTICLES}*(?:[A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+)?,\s*[A-Z]\."
                           r"|(?:[A-Z]\.\s*-?\s*)+[A-Z][\w'’-]+,|[A-Z][\w'’-]+\s+[A-Z]{1,3}\s*[,.]"
                           rf"|{_FULL_NAME},\s+(?:and\s+)?{_FULL_NAME}[,.])")


def _continues(above: str, line: str, numbered: bool) -> bool:
    """Does this line carry on the reference above it rather than start a new one?"""
    if _NUMBERING.match(line):
        return False
    if _STARTS_LINK.match(line) or _ENDS_MIDWAY.search(above):
        return True
    if line[0].islower() and not _NAME_PARTICLE.match(line):
        return True
    ref = parse_reference(line)
    author = bool(ref.first_author or _NAME_PARTICLE.match(line))
    looks_new = (author and (ref.year is not None or "n.d." in line)) or bool(_AUTHOR_START.match(line))
    if looks_new and _ENDS_REFERENCE.search(above):
        return False
    return numbered or not looks_new or not _ENDS_REFERENCE.search(above)


def join_wrapped(lines: list[str]) -> list[str]:
    """One entry per reference from pasted lines. A blank line always ends a reference and a numbered
    line always starts one. A line carries on the one above when that one stops midway (on "&" or a
    comma), when it starts with a link or a lower-case word, or when it does not look like the start of
    a reference (an author and a year). In a numbered list, a line without a number carries on unless it
    looks like a new reference and the one above looks finished."""
    entries: list[str] = []
    numbered: bool | None = None
    after_blank = True
    for raw in lines:
        line = raw.strip()
        if not line:
            after_blank = True
            continue
        if numbered is None:
            numbered = bool(_NUMBERING.match(line))
        if entries and not after_blank and _continues(entries[-1], line, numbered):
            joiner = "" if entries[-1].endswith("-") or _LINK_CUT.search(entries[-1]) else " "
            entries[-1] += joiner + line
        else:
            entries.append(line)
        after_blank = False
    return entries


def title_similarity(a: str, b: str) -> float:
    """Similarity of two titles from 0 to 1, after normalisation."""
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    return 1.0 if na == nb else SequenceMatcher(None, na, nb).ratio()


def partial_similarity(title: str, text: str) -> float:
    """Best similarity between the title and any run of the same number of words in text.

    Used only when no title could be parsed out of a reference. Titles under four words
    return 0, because they turn up inside too many unrelated references.
    """
    target = normalize(title).split()
    words = normalize(text).split()
    if len(target) < 4 or len(words) < len(target):
        return 0.0
    joined, size = " ".join(target), len(target)
    return max(
        SequenceMatcher(None, joined, " ".join(words[i:i + size])).ratio()
        for i in range(len(words) - size + 1)
    )
