"""Offline tests of how candidate records are scored and judged (no network)."""

import unittest
from unittest import mock

from citefix import sources
from citefix.existence import NOT_FOUND, SUSPICIOUS, VERIFIED, _pick_abstract, check_reference, decide, score
from citefix.sources import Candidate
from citefix.textutil import parse_reference

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
