"""Offline tests of how candidate records are scored and judged (no network)."""

import unittest

from citefix.existence import NOT_FOUND, SUSPICIOUS, VERIFIED, decide, score
from citefix.sources import Candidate
from citefix.textutil import parse_reference

GPT3 = parse_reference("Brown, T., Mann, B., & Ryder, N. (2020). Language models are few-shot learners. NeurIPS.")
GAN = parse_reference("Goodfellow, I., & Bengio, Y. (2014). Generative adversarial nets. NeurIPS, 27.")


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


if __name__ == "__main__":
    unittest.main()
