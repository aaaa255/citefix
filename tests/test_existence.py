"""Offline tests of how candidate records are scored and judged (no network)."""

import dataclasses
import unittest
from unittest import mock

from citefix import sources
from citefix.existence import NOT_FOUND, SUSPICIOUS, VERIFIED, _pick_abstract, check_reference, decide, score
from citefix.sources import Candidate
from citefix.textutil import parse_reference


def _no_network(*args, **kwargs):
    raise AssertionError("a test tried to reach the network")


# Every lookup a test does not mock fails loudly, and Open Library, which the tests below mostly leave alone,
# finds nothing.
_OFFLINE = [mock.patch("citefix.sources.urllib.request.urlopen", side_effect=_no_network),
            mock.patch.object(sources._NO_REDIRECTS, "open", side_effect=_no_network),
            mock.patch("citefix.sources.openlibrary", return_value=[]),
            mock.patch("citefix.sources.openlibrary_isbn", return_value=[])]


def setUpModule():
    for patcher in _OFFLINE:
        patcher.start()


def tearDownModule():
    for patcher in _OFFLINE:
        patcher.stop()

GPT3 = parse_reference("Brown, T., Mann, B., & Ryder, N. (2020). Language models are few-shot learners. NeurIPS.")
GAN = parse_reference("Goodfellow, I., & Bengio, Y. (2014). Generative adversarial nets. NeurIPS, 27.")
BERT = parse_reference("Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). BERT: Pre-training of deep "
                       "bidirectional transformers for language understanding. Proceedings of NAACL-HLT, 4171–4186. "
                       "https://doi.org/10.18653/v1/N19-1423")
BERT_TITLE = "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding"
SEIMON = parse_reference("Seimon, R. V., Roekenes, J. A., & Sainsbury, A. (2015). Do intermittent diets provide "
                         "physiological benefits over continuous diets for weight loss? A systematic review of "
                         "clinical trials. Molecular and Cellular Endocrinology, 418, 153–172.")
SEIMON_TITLE = ("Do intermittent diets provide physiological benefits over continuous diets for weight loss? "
                "A systematic review of clinical trials")


class CutShortTitleTest(unittest.TestCase):
    """The parser stops a title at a question mark, so it loses the subtitle that follows."""

    def test_the_full_title_in_the_reference_is_the_same_paper(self):
        self.assertTrue(SEIMON.title.endswith("weight loss?"))
        found = score(SEIMON, Candidate("openalex", SEIMON_TITLE, 2015, ["Radhika V. Seimon"]))
        self.assertEqual(found.score, 1.0)
        self.assertEqual(decide(SEIMON, [found])[0], VERIFIED)

    def test_another_subtitle_is_not_taken_for_it(self):
        other = SEIMON_TITLE.split("?")[0] + "? A randomised trial in older adults living with type 2 diabetes"
        self.assertLess(score(SEIMON, Candidate("openalex", other, 2015, ["Radhika V. Seimon"])).score, 0.9)


class PubMedAbstractTest(unittest.TestCase):
    ESEARCH = b'{"esearchresult": {"idlist": ["26384657"]}}'
    EFETCH = ("<PubmedArticleSet><PubmedArticle><MedlineCitation><Article>"
              f"<ArticleTitle>{SEIMON_TITLE}.</ArticleTitle><Abstract>"
              '<AbstractText Label="BACKGROUND">Energy restriction <i>hinders</i> weight loss.</AbstractText>'
              '<AbstractText Label="RESULTS">Intermittent fasting is not superior.</AbstractText>'
              "</Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>").encode()

    def test_reads_a_structured_abstract(self):
        with mock.patch("citefix.sources._get", side_effect=[self.ESEARCH, self.EFETCH]):
            title, abstract = sources.pubmed_abstract("10.1016/j.mce.2015.09.014")
        self.assertEqual(title, SEIMON_TITLE + ".")
        self.assertEqual(abstract, "BACKGROUND: Energy restriction hinders weight loss. "
                                   "RESULTS: Intermittent fasting is not superior.")

    def test_used_when_no_index_has_the_abstract(self):
        record = Candidate("openalex", SEIMON_TITLE, 2015, ["Radhika V. Seimon"], doi="10.1016/j.mce.2015.09.014")
        match = score(SEIMON, record)
        abstract = ("We reviewed trials of intermittent diets and found that they reduce body weight about as much as "
                    "continuous diets, without clear physiological benefits for weight loss beyond that.")
        with mock.patch("citefix.sources.pubmed_abstract", return_value=(SEIMON_TITLE, abstract)) as lookup:
            self.assertEqual(_pick_abstract(match, [match], []), (abstract, "pubmed"))
        lookup.assert_called_once_with("10.1016/j.mce.2015.09.014")

    def test_a_pubmed_record_with_another_title_is_ignored(self):
        record = Candidate("openalex", SEIMON_TITLE, 2015, ["Radhika V. Seimon"], doi="10.1016/j.mce.2015.09.014")
        match = score(SEIMON, record)
        with mock.patch("citefix.sources.pubmed_abstract", return_value=("Erratum", "Not this.")), \
                mock.patch("citefix.sources.arxiv", return_value=[]):
            self.assertEqual(_pick_abstract(match, [match], []), (None, None))


class ScoreTest(unittest.TestCase):
    def test_author_written_surname_first(self):
        found = Candidate("openalex", "Language Models are Few-Shot Learners", 2020,
                          ["Brown, Tom B.", "Benjamin Mann", "Nick Ryder"])
        scored = score(GPT3, found)
        self.assertEqual(scored.score, 1.0)
        self.assertTrue(scored.year_ok)
        self.assertTrue(scored.author_ok)

    def test_chinese_author_in_any_order(self):
        ref = parse_reference("周志华. 机器学习[M]. 北京: 清华大学出版社, 2016.")
        self.assertTrue(score(ref, Candidate("openalex", "机器学习", 2016, ["志华 周"])).author_ok)
        self.assertFalse(score(ref, Candidate("openalex", "机器学习", 2018, ["丰 郭"])).author_ok)


class DecideTest(unittest.TestCase):
    def test_prefers_the_record_from_the_cited_year(self):
        later = Candidate("crossref", "Generative adversarial networks", 2020, ["Ian Goodfellow"])
        original = Candidate("openalex", "Generative Adversarial Networks", 2014, ["Ian Goodfellow"])
        verdict, _, match = decide(GAN, [score(GAN, later), score(GAN, original)])
        self.assertEqual(verdict, VERIFIED)
        self.assertEqual(match.cand.year, 2014)

    def test_wrong_first_author_is_suspicious(self):
        found = Candidate("openalex", "Language Models are Few-Shot Learners", 2020, ["Someone Else"])
        verdict, reason, _ = decide(GPT3, [score(GPT3, found)])
        self.assertEqual(verdict, SUSPICIOUS)
        self.assertIn("first author", reason)

    def test_unrelated_records_mean_not_found(self):
        found = Candidate("openalex", "Block Pruning For Faster Transformers", 2021, ["F. Lagunas"])
        verdict, _, _ = decide(GPT3, [score(GPT3, found)])
        self.assertEqual(verdict, NOT_FOUND)

    def test_prefers_the_version_the_doi_names(self):
        preprint = Candidate("openalex", BERT_TITLE, 2018, ["Devlin, Jacob"], doi="10.48550/arxiv.1810.04805")
        published = Candidate("openalex", BERT_TITLE, 2019, ["Jacob Devlin"], doi="10.18653/v1/n19-1423")
        verdict, _, match = decide(BERT, [score(BERT, preprint), score(BERT, published)])
        self.assertEqual(verdict, VERIFIED)
        self.assertEqual(match.cand.year, 2019)

    def test_without_a_doi_prefers_the_cited_version(self):
        title = "Deep Residual Learning for Image Recognition"
        preprint = Candidate("openalex", title, 2015, ["He, Kaiming"], venue_type="repository")
        published = Candidate("openalex", title, 2016, ["Kaiming He"], venue_type="conference")
        for text, year in (("He, K. (2016). Deep residual learning for image recognition. In Proc. CVPR (pp. 770–778).", 2016),
                           ("He, K. (2015). Deep residual learning for image recognition. arXiv:1512.03385.", 2015),
                           ("He, K. (2012). Deep residual learning for image recognition. In Proc. CVPR (pp. 770–778).", 2016)):
            ref = parse_reference(text)
            with self.subTest(text=text):
                self.assertEqual(decide(ref, [score(ref, preprint), score(ref, published)])[2].cand.year, year)

    def test_a_doi_that_leads_to_another_paper_is_suspicious(self):
        ref = parse_reference("Brown, T., Mann, B., & Ryder, N. (2020). Language models are few-shot learners. "
                              "NeurIPS. https://doi.org/10.1145/3065386")
        real = Candidate("openalex", "Language Models are Few-Shot Learners", 2020, ["Tom B. Brown"],
                         doi="10.48550/arxiv.2005.14165")
        other = Candidate("openalex", "ImageNet classification with deep convolutional neural networks", 2017,
                          ["Alex Krizhevsky"], doi="10.1145/3065386")
        verdict, reason, match = decide(ref, [score(ref, real), score(ref, other)])
        self.assertEqual(verdict, SUSPICIOUS)
        self.assertIn("DOI 10.1145/3065386 leads to a different paper", reason)
        self.assertEqual(match.cand.doi, "10.48550/arxiv.2005.14165")

    def test_a_matching_doi_confirms_a_title_found_loosely(self):
        ref = parse_reference("Deep residual learning for image recognition. CVPR 2016. https://doi.org/10.1109/CVPR.2016.90")
        found = Candidate("openalex", "Deep Residual Learning for Image Recognition", 2016, ["Kaiming He"],
                          doi="10.1109/cvpr.2016.90")
        self.assertEqual(decide(ref, [score(ref, found)])[0], VERIFIED)
        found.doi = None
        self.assertEqual(decide(ref, [score(ref, found)])[0], SUSPICIOUS)


MEMGPT = ("Charles Packer, Sarah Wooders, Kevin Lin, Vivian Fang, Shishir G. Patil, Ion Stoica, Joseph E. Gonzalez. "
          "MemGPT: Towards LLMs as Operating Systems. 2023. arXiv:2310.08560.")
MEMGPT_RECORD = Candidate("arxiv", "MemGPT: Towards LLMs as Operating Systems", 2023, ["Charles Packer", "Sarah Wooders"],
                          arxiv_id="2310.08560")


class IdentifierTest(unittest.TestCase):
    """A record that the reference's own DOI or arXiv id leads to."""

    def test_an_arxiv_id_names_the_record_in_either_form(self):
        ref = parse_reference(MEMGPT)
        self.assertTrue(score(ref, MEMGPT_RECORD).doi_match)
        openalex = Candidate("openalex", MEMGPT_RECORD.title, 2023, ["Charles Packer"], doi="10.48550/arxiv.2310.08560")
        self.assertTrue(score(ref, openalex).doi_match)

    def test_the_title_written_out_in_the_reference_outweighs_a_wrongly_parsed_one(self):
        ref = parse_reference(MEMGPT)
        ref.title = "Read version: v2"  # what the parser once took for the title
        found = score(ref, MEMGPT_RECORD)
        self.assertEqual((found.via, found.score), ("text", 1.0))
        verdict, reason, _ = decide(ref, [found])
        self.assertEqual(verdict, VERIFIED)
        self.assertNotIn("different paper", reason)

    def test_without_the_id_or_the_author_it_stays_a_different_title(self):
        ref = parse_reference(MEMGPT)
        ref.title = "Read version: v2"
        other = Candidate("openalex", MEMGPT_RECORD.title, 2023, ["Someone Else"])
        self.assertLess(score(ref, other).score, 0.75)

    def test_a_longer_cited_title_is_another_paper(self):
        ref = parse_reference("Vaswani, A., & Parmar, N. (2019). Attention is all you need for graph reasoning. "
                              "In International Conference on Machine Learning (pp. 6123–6132).")
        real = Candidate("openalex", "Attention Is All You Need", 2017, ["Ashish Vaswani"])
        self.assertLess(score(ref, real).score, 0.9)

    def test_an_arxiv_id_that_leads_to_another_paper(self):
        ref = parse_reference(MEMGPT.replace("2310.08560", "2310.08561"))
        other = Candidate("arxiv", "Graph Neural Networks for Weather", 2023, ["A. Person"], arxiv_id="2310.08561")
        verdict, reason, _ = decide(ref, [score(ref, MEMGPT_RECORD), score(ref, other)])
        self.assertIn("the arXiv id 2310.08561 leads to a different paper", reason)
        self.assertEqual(verdict, SUSPICIOUS)


DEEP_LEARNING = Candidate("crossref", "Deep learning", 2015, ["Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"],
                          doi="10.1038/nature14539", volume="521", issue="7553", pages="436–444")


class FieldsTest(unittest.TestCase):
    """Crossref's check without parsing: the record's author, year and volume and page, or most of its title,
    are in the reference."""

    def test_a_style_without_titles(self):
        ref = parse_reference("Y. LeCun, Y. Bengio, and G. Hinton, Nature 521, 436 (2015).")
        found = score(ref, DEEP_LEARNING)
        self.assertEqual((found.via, found.score), ("fields", 0.9))
        self.assertEqual(decide(ref, [found])[0], VERIFIED)

    def test_a_title_with_typos(self):
        ref = parse_reference("LeCun Y, Bengio Y, Hinton G. Deep lerning by representaton. Nature. 2015;521:436-44.")
        self.assertEqual(score(ref, DEEP_LEARNING).via, "fields")

    def test_another_page_and_title_by_the_same_author_is_not_it(self):
        ref = parse_reference("LeCun, Y. (2015). Self-supervised folding of protein graphs. Nature, 521, 1203–1210.")
        self.assertLess(score(ref, DEEP_LEARNING).score, 0.9)

    def test_another_first_author_is_not_it(self):
        ref = parse_reference("Y. Bengio, Y. LeCun, and G. Hinton, Nature 521, 436 (2015).")
        self.assertLess(score(ref, DEEP_LEARNING).score, 0.9)

    def test_physics_style_by_year_volume_and_article_number(self):
        raw = "Alicki R, Fannes M 2013 Phys. Rev. E 87 042123"
        record = Candidate("openalex", "Entanglement boost for extractable work from ensembles of quantum batteries",
                           2013, ["Robert Alicki", "Mark Fannes"], doi="10.1103/physreve.87.042123", volume="87",
                           pages="042123")
        with mock.patch("citefix.sources.openalex", return_value=[]), \
                mock.patch("citefix.sources.crossref", return_value=[]), \
                mock.patch("citefix.sources.arxiv", return_value=[]), \
                mock.patch("citefix.sources.pubmed_abstract", return_value=None), \
                mock.patch("citefix.sources.openalex_by_numbers", return_value=[record]) as by_numbers:
            result = check_reference(raw)
        by_numbers.assert_called_once_with(2013, "87", "042123")
        self.assertEqual((result.verdict, result.match.via), (VERIFIED, "fields"))

    def test_print_year_after_online_year(self):
        ref = parse_reference("Clarke, R. I., Lee, J. H., & Clark, N. (2017). Why video game genres fail: A "
                              "classificatory analysis. Games and Culture, 12(5), 445–465.")
        online = Candidate("openalex", "Why Video Game Genres Fail: A Classificatory Analysis", 2015,
                           ["Rachel Ivy Clarke"])
        self.assertEqual(decide(ref, [score(ref, online)])[0], VERIFIED)
        early = Candidate("openalex", online.title, 2019, ["Rachel Ivy Clarke"])  # cited before it came out
        self.assertEqual(decide(ref, [score(ref, early)])[0], SUSPICIOUS)

    def test_a_record_named_by_a_pubmed_id(self):
        ref = parse_reference("Polack FP, et al. Safety and efficacy. N Engl J Med. 2020;383:2603-15. PMID: 33301246.")
        record = Candidate("openalex", "Safety and Efficacy of the BNT162b2 mRNA Covid-19 Vaccine", 2020,
                           ["Fernando P. Polack"])
        with mock.patch("citefix.sources.openalex", return_value=[]), \
                mock.patch("citefix.sources.crossref", return_value=[]), \
                mock.patch("citefix.sources.arxiv", return_value=[]), \
                mock.patch("citefix.sources.pubmed_abstract", return_value=None), \
                mock.patch("citefix.sources.openalex_by_id", return_value=[record]) as by_id:
            result = check_reference(ref.raw)
        by_id.assert_any_call("pmid:33301246")
        self.assertTrue(result.match.doi_match)


ASHWAL = Candidate("crossref", "Risk factors for postpartum hemorrhage following cesarean delivery", 2022,
                   ["Eran Ashwal", "Ron Bergel Bson", "Amir Aviram"], doi="10.1080/14767058.2020.1834533",
                   volume="35", issue="18", pages="3626-3630")
# A real paper's authors, year, journal, volume and pages under another paper's title.
MIXED = parse_reference("Ashwal E, Bergel Bson R, Aviram A, Hadar E, Yogev Y, Hiersch L. Heart transplantation in "
                        "the cyclosporine era. J Matern Fetal Neonatal Med. 2022;35(18):3626-30.")


class MixedDetailsTest(unittest.TestCase):
    """The record's author, year, volume and page vouch for a reference only when it gives no title of its own
    that is clearly another: made-up references are often a real paper's details under another title."""

    def test_another_title_on_a_real_papers_details_is_suspicious(self):
        found = score(MIXED, ASHWAL)
        self.assertEqual(found.via, "details")
        self.assertLess(found.score, 0.9)
        verdict, reason, match = decide(MIXED, [found])
        self.assertEqual(verdict, SUSPICIOUS)
        self.assertIn("Risk factors for postpartum hemorrhage following cesarean delivery", reason)
        self.assertIs(match, found)

    def test_the_paper_with_that_title_is_named_too(self):
        titled = Candidate("openalex", "Heart transplantation in the cyclosporine era", 1988, ["Philip E. Oyer"])
        verdict, reason, match = decide(MIXED, [score(MIXED, ASHWAL), score(MIXED, titled)])
        self.assertEqual(verdict, SUSPICIOUS)
        self.assertIn("Risk factors for postpartum hemorrhage", reason)
        self.assertIn("Philip E. Oyer", reason)
        self.assertIs(match.cand, titled)

    def test_the_papers_own_title_verifies(self):
        ref = parse_reference(MIXED.raw.replace("Heart transplantation in the cyclosporine era", ASHWAL.title))
        self.assertEqual(decide(ref, [score(ref, ASHWAL)])[0], VERIFIED)

    def test_a_short_misread_title_does_not_count_as_another(self):
        # The parser can take a journal's name for the title; a few words are not another paper's title.
        ref = dataclasses.replace(parse_reference("I. Aref’eva, K. Rannu, and P. Slepov, Phys. Lett. B 792, 470 "
                                                  "(2019)."), title="Phys")
        record = Candidate("crossref", "Orientation dependence of confinement-deconfinement phase transition in "
                           "anisotropic media", 2019, ["Irina Aref’eva", "Kristina Rannu", "Pavel Slepov"],
                           volume="792", pages="470-475")
        self.assertEqual(decide(ref, [score(ref, record)])[0], VERIFIED)


def checked_book(raw: str, books=(), by_isbn=(), found=()):
    """check_reference with OpenAlex, Crossref and arXiv finding `found` (or nothing) and Open Library `books`."""
    with mock.patch("citefix.sources.openalex", return_value=list(found)), \
            mock.patch("citefix.sources.crossref", return_value=[]), \
            mock.patch("citefix.sources.arxiv", return_value=[]), \
            mock.patch("citefix.sources.openlibrary", return_value=list(books)) as library, \
            mock.patch("citefix.sources.openlibrary_isbn", return_value=list(by_isbn)) as isbn:
        return check_reference(raw), library, isbn


SUTTON_BARTO = Candidate("openlibrary", "Reinforcement Learning: An Introduction", 2018,
                         ["Richard S. Sutton", "Andrew G. Barto"], venue_type="book")


class BookTest(unittest.TestCase):
    """Textbooks and monographs, many without a DOI, from Open Library."""

    def test_a_textbook_in_its_cited_edition(self):
        first_edition = Candidate("crossref", "Reinforcement Learning: An Introduction", 1998,
                                  ["Richard S. Sutton", "Andrew G. Barto"])
        result, library, _ = checked_book("Sutton, R. S., & Barto, A. G. (2018). Reinforcement learning: An "
                                          "introduction (2nd ed.). MIT Press.", [SUTTON_BARTO], found=[first_edition])
        library.assert_called_once_with("Reinforcement learning", author="Sutton", year=2018)
        self.assertEqual((result.verdict, result.match.cand.source), (VERIFIED, "openlibrary"))
        self.assertIsNone(result.abstract)

    def test_an_isbn(self):
        book = Candidate("openlibrary", "Deep Learning", 2016, ["Ian Goodfellow"], venue_type="book")
        result, _, isbn = checked_book("Goodfellow, I. (2016). Deep learning. MIT Press. ISBN 978-0-262-03561-3",
                                       by_isbn=[book])
        isbn.assert_called_once_with("9780262035613", year=2016)
        self.assertEqual(result.verdict, VERIFIED)

    def test_another_book_with_the_same_title(self):
        other = Candidate("openalex", "机器学习", 2018, ["郭丰"])
        result, _, _ = checked_book("周志华. 机器学习[M]. 北京: 清华大学出版社, 2016.", found=[other])
        self.assertEqual(result.verdict, SUSPICIOUS)  # it may well exist; no index has it
        self.assertIn("probably another work with the same title", result.reason)

    def test_a_journal_article_asks_open_library_only_when_nothing_else_finds_it(self):
        result, library, _ = checked_book(
            "LeCun Y, Bengio Y, Hinton G. Deep learning. Nature. 2015;521(7553):436-444.",
            found=[Candidate("openalex", "Deep learning", 2015, ["Yann LeCun"])])
        self.assertEqual(result.verdict, VERIFIED)
        library.assert_not_called()


MESSY = "lecun yann / bengio y / hinton g -- deep learning -- nature vol 521 2015 pp 436"


def read_by_model(answer: dict, title_search=()):
    """check_reference with the model's reading given, and OpenAlex answering a title search with title_search."""
    searched = []

    def openalex(query, **kwargs):  # only a search for the title itself finds the paper
        searched.append(query)
        return list(title_search) if query.strip().lower() == "deep learning" else []
    with mock.patch("citefix.existence.llm.ask_json", return_value=answer), \
            mock.patch("citefix.sources.openalex", side_effect=openalex), \
            mock.patch("citefix.sources.crossref", return_value=[]), \
            mock.patch("citefix.sources.arxiv", return_value=[]), \
            mock.patch("citefix.sources.pubmed_abstract", return_value=None):
        return check_reference(MESSY, model=True), searched


class ModelReadingTest(unittest.TestCase):
    """A reference in no style the rules know: the model copies out its parts, which steer the search."""

    def test_the_copied_title_finds_the_paper(self):
        result, searched = read_by_model({"title": "deep learning", "first_author_surname": "lecun", "year": "2015"},
                                         [DEEP_LEARNING])
        self.assertIn("deep learning", searched)
        self.assertEqual(result.verdict, VERIFIED)

    def test_a_title_not_in_the_reference_is_ignored(self):
        result, searched = read_by_model({"title": "Deep Learning: Methods and Applications", "year": "2015"},
                                         [DEEP_LEARNING])
        self.assertNotIn("Deep Learning: Methods and Applications", searched)
        self.assertNotEqual(result.verdict, VERIFIED)
        self.assertEqual(result.trace[-1].source, "model-reading")


CHINESE = "余晨, 王立. 大语言模型的引文核查方法研究. 计算机工程, 2026, 52(5): 1–12. DOI: 10.19678/j.issn.1000-3428.0000001."


def checked(raw: str, registration, page=None, by_doi=()):
    """check_reference with no index holding the paper (or only the records by_doi gives for its DOI),
    and the DOI system's answer given."""
    with mock.patch("citefix.sources.openalex", return_value=[]), \
            mock.patch("citefix.sources.openalex_doi", return_value=list(by_doi)), \
            mock.patch("citefix.sources.crossref", return_value=[]), \
            mock.patch("citefix.sources.arxiv", return_value=[]), \
            mock.patch("citefix.sources.arxiv_by_id", return_value=[]), \
            mock.patch("citefix.sources.pubmed_abstract", return_value=None), \
            mock.patch("citefix.sources.doi_registration", return_value=registration), \
            mock.patch("citefix.sources.doi_record_page", return_value=page):
        return check_reference(raw)


class DoiSystemTest(unittest.TestCase):
    """A DOI that no index holds, such as one from China's DOI agency."""

    def test_the_agency_page_shows_the_title(self):
        result = checked(CHINESE, (True, "https://www.chndoi.org/Resolution/Handler?doi=10.19678/x"),
                         "题名 大语言模型的引文核查方法研究 作者 余晨 王立 计算机工程 2026")
        self.assertEqual(result.verdict, VERIFIED)
        self.assertIn("doi.org", result.reason)

    def test_the_agency_page_shows_another_title(self):
        result = checked(CHINESE, (True, "https://www.chndoi.org/Resolution/Handler?doi=10.19678/x"), "题名 另一篇论文")
        self.assertEqual(result.verdict, NOT_FOUND)
        self.assertIn("does not show this title", result.reason)

    def test_an_agency_page_that_cannot_be_read_still_counts_the_registration(self):
        with mock.patch("citefix.sources.openalex", return_value=[]), \
                mock.patch("citefix.sources.openalex_doi", return_value=[]), \
                mock.patch("citefix.sources.crossref", return_value=[]), \
                mock.patch("citefix.sources.arxiv", return_value=[]), \
                mock.patch("citefix.sources.pubmed_abstract", return_value=None), \
                mock.patch("citefix.sources.doi_registration", return_value=(True, "https://www.chndoi.org/x")), \
                mock.patch("citefix.sources.doi_record_page", side_effect=sources.SourceError("HTTP 302")):
            result = check_reference(CHINESE)
        self.assertEqual(result.verdict, SUSPICIOUS)
        self.assertIn("is registered", result.reason)

    def test_an_unregistered_doi(self):
        result = checked(CHINESE, (False, None))
        self.assertEqual(result.verdict, NOT_FOUND)
        self.assertIn("is not registered with any DOI agency", result.reason)

    def test_registered_but_nowhere_to_read_it(self):
        result = checked(CHINESE, (True, "https://journal.example/article/1"))
        self.assertEqual(result.verdict, SUSPICIOUS)
        self.assertIn("is registered, but no index holds its record", result.reason)

    def test_an_english_title_for_the_doi_is_not_another_paper(self):
        ref = parse_reference(CHINESE)
        english = Candidate("openalex", "Research on Citation Checking Methods for Large Language Models", 2026,
                            ["Chen Yu"], doi="10.19678/j.issn.1000-3428.0000001")
        verdict, reason, _ = decide(ref, [score(ref, english)])
        self.assertEqual(verdict, SUSPICIOUS)
        self.assertIn("gives the title in another language", reason)
        self.assertNotIn("different paper", reason)
        # The agency's page, which shows the Chinese title, settles it.
        result = checked(CHINESE, (True, "https://www.chndoi.org/Resolution/Handler?doi=10.19678/x"),
                         "大语言模型的引文核查方法研究", by_doi=[english])
        self.assertEqual(result.verdict, VERIFIED)
        self.assertIn("doi.org", result.reason)


if __name__ == "__main__":
    unittest.main()
