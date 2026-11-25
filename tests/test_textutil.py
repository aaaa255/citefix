import unittest

from citefix.textutil import extract_doi, join_wrapped, parse_reference, partial_similarity, title_similarity


class ParseReferenceTest(unittest.TestCase):
    def test_apa(self):
        ref = parse_reference("Vaswani, A., Shazeer, N., & Polosukhin, I. (2017). Attention is all you need. "
                              "Advances in Neural Information Processing Systems, 30.")
        self.assertEqual(ref.title, "Attention is all you need")
        self.assertEqual(ref.year, 2017)
        self.assertEqual(ref.first_author, "Vaswani")

    def test_ieee_with_list_number(self):
        ref = parse_reference("[13] K. He, X. Zhang, S. Ren, and J. Sun, “Deep residual learning for image "
                              "recognition,” in Proc. CVPR, 2016, pp. 770–778.")
        self.assertEqual(ref.title, "Deep residual learning for image recognition")
        self.assertEqual(ref.year, 2016)
        self.assertEqual(ref.first_author, "He")

    def test_acm(self):
        ref = parse_reference("Ashish Vaswani, Noam Shazeer, and Illia Polosukhin. 2017. Attention is all you need. "
                              "In Advances in Neural Information Processing Systems 30. 5998–6008.")
        self.assertEqual(ref.title, "Attention is all you need")
        self.assertEqual(ref.year, 2017)
        self.assertEqual(ref.first_author, "Vaswani")

    def test_gbt_7714(self):
        ref = parse_reference("He K, Zhang X, Ren S, et al. Deep residual learning for image recognition[C]//"
                              "Proceedings of CVPR. 2016: 770-778.")
        self.assertEqual(ref.title, "Deep residual learning for image recognition")
        self.assertEqual(ref.year, 2016)
        self.assertEqual(ref.first_author, "He")

    def test_gbt_7714_chinese(self):
        ref = parse_reference("周志华. 机器学习[M]. 北京: 清华大学出版社, 2016.")
        self.assertEqual(ref.title, "机器学习")
        self.assertEqual(ref.year, 2016)
        self.assertEqual(ref.first_author, "周志华")

    def test_page_range_is_not_a_year(self):
        ref = parse_reference("Srivastava, N. Dropout. Journal of Machine Learning Research, 15(1), 1929–1958, 2014.")
        self.assertEqual(ref.year, 2014)


class DoiTest(unittest.TestCase):
    def test_doi_link_without_the_final_stop(self):
        ref = parse_reference("Piwowar, H. A., Day, R. S., & Fridsma, D. B. (2007). Sharing detailed research data is "
                              "associated with increased citation rate. PLoS ONE, 2(3), e308. "
                              "https://doi.org/10.1371/journal.pone.0000308.")
        self.assertEqual(ref.doi, "10.1371/journal.pone.0000308")
        self.assertEqual(ref.year, 2007)

    def test_parentheses_belong_to_the_doi_only_when_they_pair_up(self):
        self.assertEqual(extract_doi("Lancet, 395. doi:10.1016/S0140-6736(20)30183-5"), "10.1016/S0140-6736(20)30183-5")
        self.assertEqual(extract_doi("(NAACL version: 10.18653/v1/N19-1423)."), "10.18653/v1/N19-1423")

    def test_no_doi(self):
        self.assertIsNone(parse_reference("Vaswani, A. (2017). Attention is all you need. arXiv:1706.03762.").doi)


class SimilarityTest(unittest.TestCase):
    def test_title_similarity(self):
        self.assertEqual(title_similarity("Attention Is All You Need", "attention is all you need."), 1.0)
        self.assertLess(title_similarity("Attention is all you need", "Deep residual learning for image recognition"), 0.5)
        self.assertLess(title_similarity("Attention is all you need for graph reasoning", "Attention is all you need"), 0.75)

    def test_partial_similarity(self):
        text = "K. He et al. Deep residual learning for image recognition. CVPR 2016"
        self.assertGreater(partial_similarity("Deep residual learning for image recognition", text), 0.95)
        self.assertEqual(partial_similarity("Deep learning", text), 0.0)


if __name__ == "__main__":
    unittest.main()


class JoinWrappedTest(unittest.TestCase):
    """References pasted from a PDF or a word processor, wrapped onto several lines."""

    def test_numbered_list(self):
        lines = ["[1] Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, Ł., &",
                 "Polosukhin, I. (2017). Attention is all you need. Advances in Neural Information Processing",
                 "Systems, 30.",
                 "[2] He, K., Zhang, X., Ren, S., & Sun, J. (2016). Deep residual learning for image recognition.",
                 "In Proceedings of CVPR (pp. 770–778)."]
        refs = join_wrapped(lines)
        self.assertEqual(len(refs), 2)
        self.assertEqual(parse_reference(refs[0]).title, "Attention is all you need")
        self.assertTrue(refs[0].endswith("Information Processing Systems, 30."))
        self.assertTrue(refs[1].endswith("(pp. 770–778)."))

    def test_unnumbered_list_with_a_doi_on_its_own_line(self):
        lines = ["Roediger, H. L., & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves",
                 "long-term retention. Psychological Science, 17(3), 249–255.",
                 "Butler, A. C. (2010). Repeated testing produces superior transfer of learning relative to",
                 "repeated studying. Journal of Experimental Psychology: Learning, Memory, and Cognition,",
                 "36(5), 1118–1133.",
                 "https://doi.org/10.1037/a0019902"]
        refs = join_wrapped(lines)
        self.assertEqual(len(refs), 2)
        self.assertIn("improves long-term retention", refs[0])
        self.assertEqual(extract_doi(refs[1]), "10.1037/a0019902")

    def test_a_wrap_right_after_the_title(self):
        refs = join_wrapped(["Karpicke, J. D., & Blunt, J. R. (2011). Retrieval practice produces more learning.",
                             "Science, 331(6018), 772–775."])
        self.assertEqual(len(refs), 1)

    def test_a_doi_cut_by_the_line_break(self):
        refs = join_wrapped(["Eerkes-Medrano, D. (2015). Microplastics in freshwater systems. Water Research, 75,",
                             "63–82. https://doi.org/10.1016/j.",
                             "watres.2015.02.012"])
        self.assertEqual(len(refs), 1)
        self.assertEqual(extract_doi(refs[0]), "10.1016/j.watres.2015.02.012")

    def test_complete_lines_stay_apart(self):
        lines = ["Vaswani, A., & Polosukhin, I. (2017). Attention is all you need. NeurIPS, 30",
                 "[2] K. He, X. Zhang, S. Ren, and J. Sun, “Deep residual learning,” in Proc. CVPR, 2016.",
                 "Hinton, G., & Shazeer, N. (2017). Attention is all you need. NeurIPS, 30.",
                 "van der Maaten, L., & Hinton, G. (2008). Visualizing data using t-SNE. JMLR, 9, 2579–2605.",
                 "",
                 "Ioffe, S. Batch normalization (n.d.)."]
        self.assertEqual(join_wrapped(lines), [line for line in lines if line])

    def test_chinese_reference_wrapped(self):
        refs = join_wrapped(["[1] 周志华. 机器学习[M]. 北京:",
                             "清华大学出版社, 2016."])
        self.assertEqual(len(refs), 1)

    def test_a_long_author_list_pushes_the_year_down(self):
        refs = join_wrapped(["Kingma, D. P., & Ba, J. (2015). Adam: A method for stochastic optimization. In ICLR.",
                             "Wadden, D., Lin, S., Lo, K., Wang, L. L., van Zuylen, M.,",
                             "Cohan, A., & Hajishirzi, H. (2020). Fact or fiction: Verifying scientific claims."])
        self.assertEqual(len(refs), 2)

    def test_full_names_first(self):
        refs = join_wrapped(["[13] K. He and J. Sun, “Deep residual learning,” in Proc. CVPR, 2016, pp. 770–778.",
                             "Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones,",
                             "Aidan N. Gomez, Łukasz Kaiser, and Illia Polosukhin. 2017. Attention is all you need."])
        self.assertEqual(len(refs), 2)
        self.assertTrue(refs[1].startswith("Ashish Vaswani"))

    def test_every_test_reference_list_survives_wrapping(self):
        import json
        import textwrap
        from pathlib import Path

        from citefix.review import split_passage
        data = Path(__file__).resolve().parents[1] / "eval" / "data"
        lists = [split_passage(p["text"])[1] for p in
                 json.loads((data / "llm_passages.json").read_text(encoding="utf-8"))["passages"]]
        lists.append([json.loads(line)["reference"] for line in
                      (data / "existence_sample.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()])
        for width in (40, 75, 110):
            for refs in lists:
                lines = [w for r in refs for w in textwrap.wrap(r, width, break_long_words=False, break_on_hyphens=False)]
                self.assertEqual(join_wrapped(lines), refs, f"width {width}")
