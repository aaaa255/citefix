"""Offline tests for steps 2 and 3 and the passage pipeline (no network, no model calls)."""

import unittest
from unittest import mock

from citefix.repair import CITED, NONE_FOUND, REVISE, Library, check_submission
from citefix.review import apa_reference, split_passage
from citefix.sources import Candidate, _clean_markup, _inverted_to_text, _openalex_work
from citefix.support import PARTIAL, SUPPORTED, SupportResult, quote_in

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


QUOTE = "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms."
REWRITE = "The Transformer is based solely on attention."


def judged(verdict):
    """Stands in for the judge model, so these tests make no model calls."""
    return mock.patch("citefix.repair.judge_support", return_value=SupportResult(verdict, QUOTE, True, "why"))


class RewriteTest(unittest.TestCase):
    """A rewrite carries a citation, so it must name the paper that supports it."""

    def setUp(self):
        self.cited = Candidate("openalex", "Attention Is All You Need", 2017, ["Ashish Vaswani"], abstract=ABSTRACT)
        self.library = Library(self.cited)
        self.other = self.library.add(Candidate("arxiv", "Another paper", 2020, ["Ann Author"], abstract=ABSTRACT))

    def submit(self, pid, revised=REWRITE):
        return check_submission({"decision": REVISE, "paper_id": pid, "quote": QUOTE, "revised_claim": revised,
                                 "explanation": ""}, self.library, "The Transformer uses recurrence.")

    def test_cited_paper_is_c_and_searches_count_from_p1(self):
        self.assertEqual(self.other, "P1")
        self.assertEqual(self.library.add(Candidate("crossref", "Attention is all you need.", 2017)), CITED)

    def test_rewrite_supported_by_the_cited_paper_keeps_the_citation(self):
        with judged(SUPPORTED):
            outcome, _ = self.submit(CITED)
        self.assertTrue(outcome.keeps_citation)
        self.assertEqual(outcome.revised_claim, REWRITE)

    def test_rewrite_supported_by_a_searched_paper_cites_that_paper(self):
        with judged(SUPPORTED):
            outcome, _ = self.submit(self.other)
        self.assertFalse(outcome.keeps_citation)
        self.assertEqual(outcome.paper.title, "Another paper")

    def test_rewrite_without_a_paper_is_rejected(self):
        outcome, objection = self.submit("")
        self.assertIsNone(outcome)
        self.assertIn("C or one of the ids", objection)

    def test_rewrite_the_paper_only_partly_supports_is_rejected(self):
        with judged(PARTIAL):
            outcome, objection = self.submit(CITED)
        self.assertIsNone(outcome)
        self.assertIn("does not fully support", objection)

    def test_reference_not_found_cannot_keep_its_citation(self):
        library = Library()  # no index had the cited reference
        outcome, objection = check_submission({"decision": REVISE, "paper_id": CITED, "quote": QUOTE,
                                               "revised_claim": REWRITE, "explanation": ""}, library, "claim")
        self.assertIsNone(outcome)
        self.assertNotIn("C or", objection)

    def test_cited_paper_without_an_abstract_cannot_back_a_rewrite(self):
        library = Library(Candidate("openalex", "Attention Is All You Need", 2017))
        outcome, objection = check_submission({"decision": REVISE, "paper_id": CITED, "quote": QUOTE,
                                               "revised_claim": REWRITE, "explanation": ""}, library, "claim")
        self.assertIsNone(outcome)
        self.assertIn("no abstract", objection)

    def test_replacing_a_citation_with_itself_is_rejected(self):
        outcome, objection = check_submission({"decision": "replace", "paper_id": CITED, "quote": QUOTE,
                                               "explanation": ""}, self.library, "claim")
        self.assertIsNone(outcome)
        self.assertIn("already cited", objection)


class SplitPassageTest(unittest.TestCase):
    def test_splits_at_heading(self):
        body, refs = split_passage("Claim one [1].\n\nReferences\n[1] A. (2020). T.\n\n[2] B. (2021). U.\n")
        self.assertEqual(body, "Claim one [1].")
        self.assertEqual(refs, ["[1] A. (2020). T.", "[2] B. (2021). U."])

    def test_heading_at_the_end_of_the_last_sentence(self):
        body, refs = split_passage("Intro. Claim two [2]. References\n[1] A. (2020). T.\n[2] B. (2021). U.")
        self.assertEqual(body, "Intro. Claim two [2].")
        self.assertEqual(refs, ["[1] A. (2020). T.", "[2] B. (2021). U."])

    def test_heading_at_the_end_before_an_unnumbered_list(self):
        _, refs = split_passage("Claim (Smith, 2020). References:\nSmith, J. (2020). A title. Journal, 1.")
        self.assertEqual(refs, ["Smith, J. (2020). A title. Journal, 1."])

    def test_the_word_at_the_end_of_prose_is_not_a_heading(self):
        text = "We read them all. References\nThis is more of the passage, not a list."
        self.assertEqual(split_passage(text), (text, []))

    def test_chinese_heading(self):
        _, refs = split_passage("正文。\n参考文献\n周志华. 机器学习[M]. 2016.")
        self.assertEqual(refs, ["周志华. 机器学习[M]. 2016."])


if __name__ == "__main__":
    unittest.main()
