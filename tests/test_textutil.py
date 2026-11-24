import unittest

from citefix.textutil import extract_doi, parse_reference, partial_similarity, title_similarity


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
