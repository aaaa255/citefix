"""Offline tests for steps 2 and 3 and the passage pipeline (no network, no model calls)."""

import unittest

from citefix.repair import NONE_FOUND, Library, check_submission
from citefix.review import apa_reference, split_passage
from citefix.sources import Candidate, _clean_markup, _inverted_to_text, _openalex_work
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


class OpenAlexRecordTest(unittest.TestCase):
    def test_keeps_author_names_as_printed(self):
        cand = _openalex_work({"display_name": "LoRA: Low-Rank Adaptation of Large Language Models", "authorships": [
            {"author": {"display_name": "J. Edward Hu"}, "raw_author_name": "Hu, Edward J."},
            {"author": {"display_name": "Yelong Shen"}, "raw_author_name": "SHEN, YELONG"},
            {"author": {"display_name": "Phillip Wallis"}}]})
        self.assertEqual(cand.authors, ["Hu, Edward J.", "Shen, Yelong", "Phillip Wallis"])

    def test_reads_pages_and_links_to_the_publisher(self):
        cand = _openalex_work({
            "id": "https://openalex.org/W2095705004", "display_name": "Dropout", "publication_year": 2014,
            "primary_location": {"landing_page_url": "https://jmlr.org/papers/v15/srivastava14a.html",
                                 "source": {"display_name": "Journal of Machine Learning Research", "type": "journal"}},
            "biblio": {"volume": "15", "issue": "1", "first_page": "1929", "last_page": "1958"}})
        self.assertEqual((cand.venue_type, cand.volume, cand.issue, cand.pages), ("journal", "15", "1", "1929–1958"))
        self.assertEqual(cand.url, "https://jmlr.org/papers/v15/srivastava14a.html")
        self.assertEqual(_openalex_work({"id": "https://openalex.org/W1", "display_name": "T"}).url,
                         "https://openalex.org/W1")


class ApaReferenceTest(unittest.TestCase):
    def test_journal_article_with_volume_issue_and_pages(self):
        cand = Candidate("openalex", "Dropout: a simple way to prevent neural networks from overfitting", 2014,
                         ["Nitish Srivastava", "Geoffrey E. Hinton"], url="https://jmlr.org/papers/v15/srivastava14a.html",
                         venue="Journal of Machine Learning Research", venue_type="journal", volume="15", issue="1",
                         pages="1929–1958")
        self.assertEqual(apa_reference(cand), "Srivastava, N., & Hinton, G. E. (2014). Dropout: a simple way to prevent "
                                              "neural networks from overfitting. Journal of Machine Learning Research, "
                                              "15(1), 1929–1958. https://jmlr.org/papers/v15/srivastava14a.html")

    def test_conference_paper_gives_pages_and_no_volume(self):
        cand = Candidate("openalex", "BERT: Pre-training of deep bidirectional transformers for language understanding",
                         2019, ["Jacob Devlin", "Ming-Wei Chang"], doi="10.18653/v1/n19-1423", venue="NAACL-HLT",
                         venue_type="conference", volume="2019", pages="4171–4186")
        self.assertEqual(apa_reference(cand), "Devlin, J., & Chang, M.-W. (2019). BERT: Pre-training of deep "
                                              "bidirectional transformers for language understanding. In NAACL-HLT "
                                              "(pp. 4171–4186). https://doi.org/10.18653/v1/n19-1423")

    def test_initials_of_a_name_written_surname_first(self):
        cand = Candidate("openalex", "LoRA", 2021, ["Hu, Edward J.", "Shen, Yelong", "Chang, M.-W."])
        self.assertTrue(apa_reference(cand).startswith("Hu, E. J., Shen, Y., & Chang, M.-W. (2021)."))


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
