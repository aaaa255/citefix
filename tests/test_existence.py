"""Offline tests of how candidate records are scored and judged (no network)."""

import unittest

from citefix.existence import NOT_FOUND, SUSPICIOUS, VERIFIED, decide, score
from citefix.sources import Candidate
from citefix.textutil import parse_reference

GPT3 = parse_reference("Brown, T., Mann, B., & Ryder, N. (2020). Language models are few-shot learners. NeurIPS.")
GAN = parse_reference("Goodfellow, I., & Bengio, Y. (2014). Generative adversarial nets. NeurIPS, 27.")
BERT = parse_reference("Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). BERT: Pre-training of deep "
                       "bidirectional transformers for language understanding. Proceedings of NAACL-HLT, 4171–4186. "
                       "https://doi.org/10.18653/v1/N19-1423")
BERT_TITLE = "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding"


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


if __name__ == "__main__":
    unittest.main()
