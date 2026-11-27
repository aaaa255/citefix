"""Text helpers: normalising titles, comparing them, and pulling fields out of a reference."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

_TAG = re.compile(r"<[^>]+>")
_NON_WORD = re.compile(r"[^\w\s]")
_NUMBERING = re.compile(r"^\s*(?:\[\d{1,3}\]|\(\d{1,3}\)|\d{1,3}[.)])\s+")

# Title patterns, tried in order: IEEE, MLA and Chicago put the title in quotes (Harvard in single ones), APA
# after "(2017)." (Springer after "(2017)"), ACM after "Author. 2017.", and GB/T 7714 before a type tag such as
# [J], [C] or [EB/OL]. Then the title after a list of authors: full names ("Joon Sung Park, Michael S. Bernstein.
# Generative agents: ..."), surname and initials (Vancouver and AMA: "LeCun Y, Bengio Y, Hinton G. Deep
# learning."; Nature and ACS: "LeCun, Y., Bengio, Y. & Hinton, G. Deep learning."), initials and surname
# (Science: "Y. LeCun, Y. Bengio, G. Hinton, Deep learning.") or Chinese names ("周志华. 机器学习. ...").
_UP = "[A-ZÀ-ÖØ-ÞĀ-ſ]"  # a capital, accented ones too ("Ö." in "Türeci, Ö.", "Ł" in "Łukasz")
# A surname may open with a lower-case particle: "de Man, F. M.", "van Schaik R", "van der Maaten, L."
_PARTICLE = r"(?:(?:van|von|de|da|di|du|del|della|den|der|le|la|ten|ter|dos|das)\s+)"
_NAME_WORD = rf"{_PARTICLE}*{_UP}[\w'’-]+"
_INITIALS = rf"(?:{_UP}\.\s?-?\s?)+"
_TITLE = r"(.+?(?:[.?!](?=[\s,]|$)|$))"  # up to the end of its sentence, or of the reference
_QUOTED_TITLE = re.compile(r"[\"“”](\S.+?)[,.]?[\"“”]")  # not from a stray closing quote: `Topic." Journal ...`
_SINGLE_QUOTED_TITLE = re.compile(r"‘(.+?)[,.]?’(?=[\s,.:;]|$)")  # the ’ of "Don’t" does not end it
_APA_TITLE = re.compile(r"\((?:19|20)\d{2}[a-z]?(?:,[^)]*)?\)[.:]?\s+" + _TITLE)
_ACM_TITLE = re.compile(r"(?:^|[.,]\s)(?:19|20)\d{2}[a-z]?\.\s+(.+?[.?!])(?=\s|$)")
_GBT_TITLE = re.compile(r"[.．]\s*([^.．\[\]]+?)\s*\[(?:J|M|C|D|R|S|N|P|Z|A|G|K|EB|DB|CP)(?:/OL)?\]")
# Lists of authors in the styles above, each followed by the title (the group the pattern captures).
_SURNAME_INITIALS_LIST = re.compile(  # Vancouver, AMA: "LeCun Y, Bengio Y, Hinton G." or "..., et al."
    rf"^(?:{_NAME_WORD}(?:\s{_NAME_WORD})?\s{_UP}{{1,3}},\s)*{_NAME_WORD}(?:\s{_NAME_WORD})?\s{_UP}{{1,3}}"
    r"(?:,?\s+et\s+al)?\.\s+" + _TITLE)
_SURNAME_COMMA_INITIALS_LIST = re.compile(  # Nature, ACS, APA without a year: "LeCun, Y., Bengio, Y. & Hinton, G."
    rf"^(?:{_NAME_WORD}(?:\s{_NAME_WORD})?,\s{_INITIALS}(?:,\s|;\s|,?\s(?:&|and)\s)?)+"
    r"(?:et\s+al\.\s+)?(?=[A-Z0-9])" + _TITLE)
_INITIALS_SURNAME_LIST = re.compile(  # Science, AIP, IEEE without quotes: "Y. LeCun, Y. Bengio, and G. Hinton,"
    rf"^(?:{_INITIALS}{_NAME_WORD}(?:\s{_NAME_WORD})?,\s(?:and\s)?)+(?:et\s+al\.,?\s+)?(?=[A-Z0-9])" + _TITLE)
_SURNAME_GIVEN_LIST = re.compile(  # MLA books: "Hastie, Trevor, et al. The Elements of Statistical Learning."
    rf"^{_NAME_WORD},\s{_NAME_WORD}(?:\s(?:{_NAME_WORD}|{_UP}\.))*"
    rf"(?:,\s+et\s+al|,?\s+and\s+{_NAME_WORD}(?:\s(?:{_NAME_WORD}|{_UP}\.))*)?\.\s+(?=[A-Z0-9])" + _TITLE)
# A venue, volume and pages, not a title: "Nature 521, 436 (2015)" in styles that leave the title out.
_VENUE_NUMBERS = re.compile(r"\b\d+\s*[,:]\s*\d+|\((?:19|20)\d{2}\)")
# What styles add after a title: "(Version 7)", "[Internet]", a book's "(Springer New York, 2009)", or the
# translation of a title in another language: "Update Chemoperfusion [Update on chemoinfusion]".
_TITLE_TAIL = re.compile(r"\s*(?:[\[(](?:version\s*\d+|v\d+|internet|online|preprint|e-?print|pdf)[\])]"
                         r"|\([^()]*\b(?:19|20)\d{2}\)|\[[^\[\]]{3,}\])\s*$", re.IGNORECASE)
# The year right after the authors, as physics journals write it ("Namiki T 1999 IEEE Trans. Microw. Theory Tech.
# 47 2003"), where a later number can look like a year.
_YEAR_AFTER_NAMES = re.compile(
    rf"^(?:{_NAME_WORD}(?:\s{_NAME_WORD})?\s(?:{_UP}{{1,3}}\s?)+,\s)*{_NAME_WORD}(?:\s{_NAME_WORD})?"
    rf"\s(?:{_UP}{{1,3}}\s?)+(?:,?\s*et\s+al\.?)?\s+((?:19|20)\d{{2}})\b")
# The volume and first page (or article number) that close a reference: "Phys. Rev. E 87 042123",
# "Nature 521, 436 (2015).", "Sci. Adv. 8 eabk3160", "Theory Tech.47 2003".
_VOLUME_PAGE = re.compile(r"(?<!\d)(\d{1,4})\s*(?:\(\d{1,4}\))?\s*[,:]?\s+(?:pp?\.?\s*)?([A-Za-z]{0,4}\d{2,7})"
                          r"(?:\s*[-–]\s*\d+)?\s*(?:\((?:19|20)\d{2}\))?\s*\.?$")
_BIBTEX_FIELD = r"\b{}\s*=\s*(?:\{{((?:[^{{}}]|\{{[^{{}}]*\}})*)\}}|\"([^\"]*)\"|(\d+))"
# A reference that opens with a full name: "Joon Sung Park,", "Theodore R. Sumers,", "Takuma Yoneda et al." or a
# Chinese name. (APA's "Vaswani, A." and GB/T's "He K," are not full names.)
_OPENS_WITH_FULL_NAME = re.compile(rf"^(?:{_NAME_WORD}\s+(?:{_NAME_WORD}\s+|{_UP}\.\s*){{0,2}}{_NAME_WORD}"
                                   r"\s*(?:,|\s+et\s+al\b|\s+and\b|\s*&)|[一-鿿]{2,4}\s*[,，、.．])")
# "C." in "Joseph C. O'Brien", "M.-W." in "M.-W. Chang", "J." and "S." in "Park, J.S."
_INITIAL = re.compile(rf"(?<![\w'’]){_UP}\.(?=[\s,;-]|{_UP}|$)")
# A list number with neither brackets nor a stop, as AIP writes it: "1 Y. LeCun, ...".
_BARE_NUMBER = re.compile(rf"^\d{{1,3}}\s+(?={_UP})")
# A note's date is not the publication year: "Accessed 12 March 2026."
_NOTE_DATE = re.compile(r"\b(?:accessed|retrieved|viewed|visited|cited|downloaded)\b[^.]*", re.IGNORECASE)
_SENTENCE_END = re.compile(r"[.．。!?](?=\s|$)")
# Not a title: what some styles write after the year, such as a DOI or a link.
_NOT_A_TITLE = re.compile(r"^(?:doi\b|arxiv\b|https?:|www\.|url\b|available\b|retrieved\b|accessed\b)", re.IGNORECASE)
# An arXiv identifier, new style (2304.03442) or old (hep-th/9901001), with or without its version.
_ARXIV_ID = re.compile(r"(?:arXiv:\s?|arxiv\.org/(?:abs|pdf)/|10\.48550/arXiv\.)"
                       r"(\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?", re.IGNORECASE)
# PubMed's ids, which medical references often give, and an ACL Anthology paper's address, whose id is
# also its DOI's suffix (10.18653/v1/2024.acl-long.747).
_PMID = re.compile(r"\bPMID:?\s*(\d{4,9})\b", re.IGNORECASE)
_PMCID = re.compile(r"\b(PMC\d{4,9})\b")
_ACL_ID = re.compile(r"aclanthology\.org/((?:\d{4}\.[a-z\-]+\.\d+|[A-Z]\d{2}-\d{4}))(?:\.pdf)?/?", re.IGNORECASE)

_PAREN_YEAR = re.compile(r"\(((?:19|20)\d{2})[a-z]?(?:,[^)]*)?\)")
# A bare year, but not one end of a page range (1929–1958) or part of an arXiv id (2010.11929).
_ANY_YEAR = re.compile(r"(?<![\d–—-])((?:19|20)\d{2})[a-z]?(?![\d–—-]|\.\d)")

# A DOI, bare or inside a doi.org link: "10.", the registrant's number, "/", then a suffix that may hold
# almost any character, parentheses included (10.1016/S0140-6736(20)30183-5).
_DOI = re.compile(r"\b10\.\d{4,9}/\S+")

_SURNAME_FIRST = re.compile(rf"^({_NAME_WORD}(?:\s+{_NAME_WORD})?)\s*,")  # "Vaswani, A." / "Ashish Vaswani,"
_INITIALS_FIRST = re.compile(rf"^(?:{_UP}\.\s*-?\s*)+({_NAME_WORD})")  # "K. He," / "M.-W. Chang"
# "Joon Sung Park,", "Theodore R. Sumers,", "Takuma Yoneda et al.", and alone before an ACM year:
# "Albert Bandura. 1977.": given names or initials, then the surname.
_FULL_NAME_FIRST = re.compile(rf"^(?:{_NAME_WORD}\s+|{_UP}\.\s*){{1,3}}({_NAME_WORD})"
                              r"\s*(?:,|\s+et\s+al\b|\s+and\b|\s*&|\.\s+(?=(?:19|20)\d{2}\b))")
# "He K, Zhang X", "PARK J S,", and alone before a physics-style year: "Namiki T 1999 ..."
_SURNAME_INITIALS = re.compile(rf"^({_NAME_WORD})\s+(?:{_UP}{{1,3}}\s?){{1,3}}(?:[,.]|(?=(?:19|20)\d{{2}}\b))")
_CJK_AUTHOR = re.compile(r"^([一-鿿]{2,4})\s*[,，.．、]")  # "周志华." (GB/T, Chinese)


@dataclass
class ParsedRef:
    raw: str
    text: str  # the reference on one line, list numbering removed
    title: str | None
    year: int | None
    first_author: str | None  # surname
    doi: str | None = None
    arxiv_id: str | None = None  # "2304.03442", without its version
    other_ids: list[str] = field(default_factory=list)  # OpenAlex lookups: "pmid:123", "pmcid:PMC1", "doi:10.18653/..."


def normalize(text: str) -> str:
    """Lower-case and strip markup, accents and punctuation."""
    text = _TAG.sub(" ", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(_NON_WORD.sub(" ", text.lower()).split())


def _only_names(text: str) -> bool:
    """Is this the start of a reference up to its year in ACM style, an author list with no sentence in it?
    "Ashish Vaswani, Noam Shazeer, and Illia Polosukhin" is; "Joon Sung Park, ... Michael S. Bernstein.
    Generative Agents: Interactive Simulacra of Human Behavior" is not: the title came before the year.
    "et al." may end the list, but a title after it ("Wenyue Hua et al. War and Peace ...") is a sentence."""
    stripped = _INITIAL.sub(" ", re.sub(r"\bet\s+al\.?\s*$", "", text.strip()))
    return not _SENTENCE_END.search(stripped)


def _title_after_names(text: str) -> str | None:
    """The title of a reference that opens with full names: the sentence after the first full stop that does
    not end an initial."""
    if not _OPENS_WITH_FULL_NAME.match(text):
        return None
    for stop in _SENTENCE_END.finditer(text):
        if text[stop.start()] in ".．" and _INITIAL.match(text, stop.start() - 1):
            continue  # "C." in "Joseph C. O'Brien"
        rest = text[stop.end():].lstrip()
        end = _SENTENCE_END.search(rest)
        title = (rest[:end.end()] if end else rest).rstrip(".．。").strip()
        return title or None
    return None


def _plausible_title(title: str | None) -> str | None:
    """A title found after an author list, unless it is really a note, a link or a venue with its numbers."""
    if not title:
        return None
    title = re.split(r",\s+[Ii]n\s", title)[0].rstrip(".．。,").strip()  # "..., in Proc. CVPR" (IEEE without quotes)
    if not title or _NOT_A_TITLE.match(title) or _VENUE_NUMBERS.search(title) or not re.search(r"[^\W\d_]{2}", title):
        return None
    return title


def bibtex_field(text: str, name: str) -> str | None:
    found = re.search(_BIBTEX_FIELD.format(name), text, re.IGNORECASE)
    if not found:
        return None
    value = next(group for group in found.groups() if group is not None)
    return " ".join(value.replace("{", "").replace("}", "").split()) or None


def extract_title(text: str) -> str | None:
    title = _find_title(text)
    return _TITLE_TAIL.sub("", title).strip() or None if title else None


def _find_title(text: str) -> str | None:
    if text.startswith("@"):  # a BibTeX entry
        return bibtex_field(text, "title")
    quoted = _QUOTED_TITLE.search(text)
    if quoted and len(quoted.group(1).split()) >= 2:
        return quoted.group(1).strip()
    single = _SINGLE_QUOTED_TITLE.search(text)
    if single and len(single.group(1).split()) >= 2:
        return single.group(1).strip()
    for pattern in (_APA_TITLE, _ACM_TITLE, _GBT_TITLE):
        found = pattern.search(text)
        if found and pattern is _ACM_TITLE and not _only_names(text[:found.start()]):
            continue  # the year came after the title, and what follows it is a note, a venue or a link
        if found and not _NOT_A_TITLE.match(found.group(1)):
            return found.group(1).rstrip(".").strip()
    title = _plausible_title(_title_after_names(text))  # full names first: "Theodore R." is not Vancouver's "Hinton G."
    if title:
        return title
    for pattern in (_SURNAME_INITIALS_LIST, _SURNAME_COMMA_INITIALS_LIST, _INITIALS_SURNAME_LIST, _SURNAME_GIVEN_LIST):
        found = pattern.match(text)
        title = _plausible_title(found.group(1)) if found else None
        if title:
            return title
    return None


def volume_and_page(text: str) -> tuple[str, str] | None:
    """The volume and first page a reference ends with, for finding one that gives no title."""
    found = _VOLUME_PAGE.search(text.strip())
    return (found.group(1), found.group(2)) if found else None


def extract_year(text: str) -> int | None:
    text = _NOTE_DATE.sub(" ", text)
    after_names = _YEAR_AFTER_NAMES.match(text)
    if after_names:
        return int(after_names.group(1))
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
        if doi[-1] in ".,;:'\"”’]>}":
            doi = doi[:-1]
        elif doi[-1] == ")" and doi.count(")") > doi.count("("):
            doi = doi[:-1]
        else:
            break
    return doi or None


def extract_arxiv_id(text: str) -> str | None:
    found = _ARXIV_ID.search(text)
    return found.group(1) if found else None


def extract_other_ids(text: str, doi: str | None) -> list[str]:
    """PubMed ids and an ACL Anthology DOI, written as OpenAlex looks works up by them."""
    found = [f"pmid:{m.group(1)}" for m in _PMID.finditer(text)][:1]
    found += [f"pmcid:{m.group(1)}" for m in _PMCID.finditer(text)][:1]
    acl = _ACL_ID.search(text)
    if acl and not doi:
        found.append(f"doi:10.18653/v1/{acl.group(1)}")
    return found


def first_author_surname(text: str) -> str | None:
    found = _SURNAME_FIRST.match(text)
    if found:
        words = found.group(1).split()
        # "Park JS," is a surname and its initials (Vancouver), "Ashish Vaswani," a given name and a surname.
        return words[0] if len(words) == 2 and words[1].isupper() and len(words[1]) <= 3 else words[-1]
    for pattern in (_INITIALS_FIRST, _FULL_NAME_FIRST, _SURNAME_INITIALS, _CJK_AUTHOR):
        found = pattern.match(text)
        if found:
            return found.group(1)
    return None


def _parse_bibtex(raw: str, text: str) -> ParsedRef:
    """A BibTeX entry, as LaTeX users keep their references: the fields say what each part is."""
    authors = bibtex_field(text, "author") or ""
    first = authors.split(" and ")[0].strip()
    surname = first.split(",")[0].strip() if "," in first else (first.split() or [None])[-1]
    year = bibtex_field(text, "year")
    doi = bibtex_field(text, "doi")
    eprint = bibtex_field(text, "eprint")
    return ParsedRef(raw=raw, text=text, title=extract_title(text),
                     year=int(year) if year and year[:4].isdigit() else extract_year(text),
                     first_author=surname or None, doi=extract_doi(doi) if doi else None,
                     arxiv_id=extract_arxiv_id(f"arXiv:{eprint}") if eprint else extract_arxiv_id(text),
                     other_ids=extract_other_ids(text, doi))


def parse_reference(raw: str) -> ParsedRef:
    text = _NUMBERING.sub("", " ".join(raw.split()), count=1)
    text = _BARE_NUMBER.sub("", text, count=1)
    if text.startswith("@"):
        return _parse_bibtex(raw, text)
    doi = extract_doi(text)
    return ParsedRef(
        raw=raw,
        text=text,
        title=extract_title(text),
        year=extract_year(text),
        first_author=first_author_surname(text),
        doi=doi,
        arxiv_id=extract_arxiv_id(text),
        other_ids=extract_other_ids(text, doi),
    )


# A long reference pasted from a PDF or a word processor can wrap onto several lines.
_BIBTEX_START = re.compile(r"^@\w+\s*\{")  # "@article{lecun2015deep," opens a BibTeX entry
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
# A group author ("World Health Organization. (2020). ...") has no initials, but APA puts its year in
# brackets right after its name, which opens with a whole word. "D. (2006). ..." is the rest of a person's
# name that a line break cut off.
_GROUP_AUTHOR = re.compile(r"^[A-Z][a-z]+(?:[\s,&]+[A-Za-z][\w'’-]*){0,14}\.\s*\((?:19|20)\d{2}[a-z]?(?:,[^)]*)?\)\.")


def _continues(above: str, line: str, numbered: bool) -> bool:
    """Does this line carry on the reference above it rather than start a new one?"""
    if _NUMBERING.match(line) or _BIBTEX_START.match(line):
        return False
    if above.startswith("@"):  # the fields of a BibTeX entry, until its next entry
        return True
    if numbered:
        return True  # in a numbered list every reference has its number; an IEEE author list can break anywhere
    if _STARTS_LINK.match(line) or _ENDS_MIDWAY.search(above):
        return True
    if line[0].islower() and not _NAME_PARTICLE.match(line):
        return True
    ref = parse_reference(line)
    author = bool(ref.first_author or _NAME_PARTICLE.match(line))
    looks_new = ((author and (ref.year is not None or "n.d." in line)) or bool(_AUTHOR_START.match(line))
                 or bool(_GROUP_AUTHOR.match(line)))
    if looks_new and _ENDS_REFERENCE.search(above):
        return False
    return not looks_new or not _ENDS_REFERENCE.search(above)


def join_wrapped(lines: list[str]) -> list[str]:
    """One entry per reference from pasted lines. A blank line always ends a reference and a numbered
    line always starts one. When the list's first reference is numbered, a line without a number carries
    on the one above. Otherwise a line carries on the one above when that one stops midway (on "&" or a
    comma), when it starts with a link or a lower-case word, or when it does not look like the start of a
    reference (an author and a year, an author list, or a group author followed by its year)."""
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


# Indexes sometimes store something other than an abstract in the abstract field: a software README,
# a paper's acknowledgments, or a line of publication details. Two signs of a README or of
# acknowledgments are needed, since one alone can turn up in a real abstract. Only phrases a real abstract
# hardly uses count: "installation", "usage" or "funded by" do turn up in real ones.
_README_SIGNS = re.compile(r"\b(?:in this repository|docker|git clone|pip install|npm install|readme|requirements\.txt)\b",
                           re.IGNORECASE)
_THANKS_SIGNS = re.compile(r"\b(?:referees?|we thank|we are grateful|grateful to|for help|helpful comments|"
                           r"originally supported by)\b", re.IGNORECASE)
_PUBLICATION_DETAILS = re.compile(r"\bpublished in volume \d+", re.IGNORECASE)


def plausible_abstract(title: str, abstract: str | None) -> bool:
    """False when the text an index holds as a paper's abstract is clearly something else: too short,
    a README, acknowledgments, publication details, or text sharing no word with the title."""
    if not abstract or len(abstract.split()) < 20 or _PUBLICATION_DETAILS.search(abstract):
        return False
    if len(set(m.lower() for m in _README_SIGNS.findall(abstract))) >= 2:
        return False
    if len(set(m.lower() for m in _THANKS_SIGNS.findall(abstract))) >= 2:
        return False
    def stems(text: str) -> set[str]:
        return {w.removesuffix("s") for w in normalize(text).split() if len(w) > 3 and w.isascii()}
    words = stems(title)
    return not words or bool(words & stems(abstract))


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
