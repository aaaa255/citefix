import unittest

from citefix.textutil import parse_reference, partial_similarity, title_similarity


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
