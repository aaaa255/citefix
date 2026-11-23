"""Offline tests for steps 2 and 3 and the passage pipeline (no network, no model calls)."""

import unittest

from citefix.repair import NONE_FOUND, Library, check_submission
from citefix.review import split_passage
from citefix.sources import Candidate, _clean_markup, _inverted_to_text
from citefix.support import quote_in

ABSTRACT = ("We propose a new simple network architecture, the Transformer, based solely on attention "
            "mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine "
            "translation tasks show these models to be superior in quality.")


class QuoteTest(unittest.TestCase):
    def test_exact_and_near_copies_count(self):
        self.assertTrue(quote_in("based solely on attention mechanisms, dispensing with recurrence", ABSTRACT))
        self.assertTrue(quote_in("We propose a new simple network architecture the Transformer based solely "
                                 "on attention mechanism", ABSTRACT))

    def test_invented_quote_does_not_count(self):
        self.assertFalse(quote_in("Transformers outperform convolutional networks on ImageNet.", ABSTRACT))
        self.assertFalse(quote_in("", ABSTRACT))


class AbstractParsingTest(unittest.TestCase):
    def test_openalex_inverted_index(self):
        self.assertEqual(_inverted_to_text({"attention": [0], "all": [2], "is": [1]}), "attention is all")

    def test_crossref_jats(self):
        jats = "<jats:title>Abstract</jats:title><jats:p>Deep networks &amp; residual learning.</jats:p>"
        self.assertEqual(_clean_markup(jats), "Deep networks & residual learning.")


class SubmissionTest(unittest.TestCase):
    def setUp(self):
        self.library = Library()
        self.pid = self.library.add(Candidate("arxiv", "Attention Is All You Need", 2017, ["Ashish Vaswani"],
                                              abstract=ABSTRACT))

    def test_same_title_gets_same_id(self):
        self.assertEqual(self.library.add(Candidate("openalex", "Attention is all you need.", 2017)), self.pid)

    def test_unknown_paper_is_rejected(self):
        outcome, objection = check_submission({"decision": "replace", "paper_id": "P9", "quote": "x",
                                               "explanation": ""}, self.library, "claim")
        self.assertIsNone(outcome)
        self.assertIn("paper_id", objection)

    def test_made_up_quote_is_rejected(self):
        outcome, objection = check_submission({"decision": "replace", "paper_id": self.pid,
                                               "quote": "Transformers beat CNNs on ImageNet.",
                                               "explanation": ""}, self.library, "claim")
        self.assertIsNone(outcome)
        self.assertIn("quote", objection)

    def test_no_support_found_is_accepted(self):
        outcome, _ = check_submission({"decision": NONE_FOUND, "explanation": "Nothing fits."}, self.library, "c")
        self.assertEqual(outcome.decision, NONE_FOUND)


class SplitPassageTest(unittest.TestCase):
    def test_splits_at_heading(self):
        body, refs = split_passage("Claim one [1].\n\nReferences\n[1] A. (2020). T.\n\n[2] B. (2021). U.\n")
        self.assertEqual(body, "Claim one [1].")
        self.assertEqual(refs, ["[1] A. (2020). T.", "[2] B. (2021). U."])

    def test_chinese_heading(self):
        _, refs = split_passage("正文。\n参考文献\n周志华. 机器学习[M]. 2016.")
        self.assertEqual(refs, ["周志华. 机器学习[M]. 2016."])


if __name__ == "__main__":
    unittest.main()
