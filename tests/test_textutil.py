import unittest

from citefix.textutil import (extract_doi, join_wrapped, normalize, parse_reference, partial_similarity,
                              plausible_abstract, title_similarity)


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


class FullNamesFirstTest(unittest.TestCase):
    """Full names, the title, then the venue and year, perhaps a note and an identifier. The sentence after the
    year is a note here, not the title as in ACM style."""

    def test_title_after_the_names(self):
        ref = parse_reference("[6]\tJoon Sung Park, Joseph C. O'Brien, Carrie J. Cai, Meredith Ringel Morris, Percy Liang, "
                              "Michael S. Bernstein. Generative Agents: Interactive Simulacra of Human Behavior. 2023. "
                              "Read version: v2. DOI: 10.48550/arXiv.2304.03442.")
        self.assertEqual(ref.title, "Generative Agents: Interactive Simulacra of Human Behavior")
        self.assertEqual((ref.first_author, ref.year, ref.arxiv_id), ("Park", 2023, "2304.03442"))

    def test_venue_and_year_after_the_title(self):
        ref = parse_reference("Zhenyu Guan, Xiangyu Kong, Fangwei Zhong, Yizhou Wang. Richelieu: Self-Evolving LLM-Based "
                              "Agents for AI Diplomacy. NeurIPS, 2024. Main track.")
        self.assertEqual(ref.title, "Richelieu: Self-Evolving LLM-Based Agents for AI Diplomacy")
        self.assertEqual(ref.first_author, "Guan")

    def test_et_al_then_the_title(self):
        ref = parse_reference("Wenyue Hua et al. War and Peace (WarAgent): Large Language Model-based Multi-Agent "
                              "Simulation of World Wars. 2023. Read: method and results. arXiv:2311.17227.")
        self.assertEqual(ref.title, "War and Peace (WarAgent): Large Language Model-based Multi-Agent Simulation of World Wars")
        self.assertEqual((ref.first_author, ref.arxiv_id), ("Hua", "2311.17227"))

    def test_middle_initial_is_not_the_end_of_the_names(self):
        ref = parse_reference("Theodore R. Sumers, Shunyu Yao, Karthik Narasimhan, Thomas L. Griffiths. Cognitive "
                              "Architectures for Language Agents. 2023. arXiv:2309.02427.")
        self.assertEqual(ref.title, "Cognitive Architectures for Language Agents")
        self.assertEqual(ref.first_author, "Sumers")

    def test_chinese_without_a_type_tag(self):
        ref = parse_reference("周志华. 机器学习. 北京: 清华大学出版社, 2016.")
        self.assertEqual((ref.title, ref.first_author, ref.year), ("机器学习", "周志华", 2016))

    def test_acm_year_still_follows_the_names(self):
        ref = parse_reference("Wenyue Hua, Lizhou Fan, et al. 2023. War and peace (WarAgent): Large language model-based "
                              "multi-agent simulation of world wars. arXiv.")
        self.assertEqual(ref.title, "War and peace (WarAgent): Large language model-based multi-agent simulation of world wars")

    def test_a_doi_is_never_the_title(self):
        self.assertIsNone(parse_reference("Doe, J. 2020. DOI: 10.1234/abcd.5678.").title)


class StylesTest(unittest.TestCase):
    """One paper as the common citation styles write it (rendered by the DOI system's CSL styles)."""

    def test_title_in_each_style(self):
        for style, text in (
            ("vancouver", "LeCun Y, Bengio Y, Hinton G. Deep learning. Nature. 2015;521(7553):436-444."),
            ("nature", "LeCun, Y., Bengio, Y. & Hinton, G. Deep learning. Nature 521, 436–444 (2015)."),
            ("acs", "LeCun, Y.; Bengio, Y.; Hinton, G. Deep Learning. Nature 2015, 521 (7553), 436–444."),
            ("science", "Y. LeCun, Y. Bengio, G. Hinton, Deep learning. Nature 521, 436–444 (2015)."),
            ("springer", "LeCun Y, Bengio Y, Hinton G (2015) Deep learning. Nature 521:436–444."),
            ("harvard", "LeCun, Y., Bengio, Y. and Hinton, G. (2015) ‘Deep learning’, Nature, 521(7553), pp. 436–444."),
            ("mla", "LeCun, Yann, et al. “Deep Learning.” Nature, vol. 521, no. 7553, 2015, pp. 436–44."),
            ("elsevier", "LeCun, Y., Bengio, Y., Hinton, G., 2015. Deep learning. Nature 521, 436–444."),
            ("ieee, no quotes", "Y. LeCun, Y. Bengio, and G. Hinton, Deep learning, in Proc. Nature, 2015, pp. 436–444."),
        ):
            with self.subTest(style=style):
                ref = parse_reference(text)
                self.assertEqual(normalize(ref.title or ""), "deep learning")
                self.assertEqual((ref.first_author, ref.year), ("LeCun", 2015))

    def test_details_of_real_lists(self):
        for text, title, author in (
            ("1 Y. LeCun, Y. Bengio, and G. Hinton, “Deep learning,” Nature 521(7553), 436–444 (2015).",
             "Deep learning", "LeCun"),  # AIP numbers its list without brackets
            ("Park JS, O’Brien J, Cai CJ, et al (2023) Generative Agents: Interactive Simulacra of Human Behavior. "
             "Proceedings of UIST.", "Generative Agents: Interactive Simulacra of Human Behavior", "Park"),
            ("PARK J S, O’BRIEN J, CAI C J, et al. Generative Agents: Interactive Simulacra of Human Behavior[C]. "
             "UIST, 2023.", "Generative Agents: Interactive Simulacra of Human Behavior", "PARK"),
            ("Park, J.S., O’Brien, J., Cai, C.J., Bernstein, M.S., 2023. Generative Agents: Interactive Simulacra of "
             "Human Behavior. Proceedings of UIST.", "Generative Agents: Interactive Simulacra of Human Behavior", "Park"),
            ("Polack, F. P.; Pérez Marc, G.; Türeci, Ö.; Gruber, W. C. Safety and Efficacy of the BNT162b2 mRNA "
             "Covid-19 Vaccine. N. Engl. J. Med. 2020, 383 (27), 2603–2615.",
             "Safety and Efficacy of the BNT162b2 mRNA Covid-19 Vaccine", "Polack"),
            ("Albert Bandura. 1977. Self-efficacy: Toward a unifying theory of behavioral change. Psychological "
             "Review 84, 2 (1977), 191–215.", "Self-efficacy: Toward a unifying theory of behavioral change", "Bandura"),
            ("Vaswani, A., Shazeer, N., & Polosukhin, I. (2017). Attention Is All You Need (Version 7). arXiv.",
             "Attention Is All You Need", "Vaswani"),
            ("Vaswani A, Shazeer N, Parmar N, et al (2017) Attention Is All You Need", "Attention Is All You Need",
             "Vaswani"),
            ("Hastie, Trevor, et al. The Elements of Statistical Learning. Springer Series in Statistics, 2009.",
             "The Elements of Statistical Learning", "Hastie"),
            ("1 T. Hastie, R. Tibshirani, and J. Friedman, The Elements of Statistical Learning (Springer New York, 2009).",
             "The Elements of Statistical Learning", "Hastie"),
        ):
            with self.subTest(text=text[:40]):
                ref = parse_reference(text)
                self.assertEqual((ref.title, ref.first_author), (title, author))

    def test_a_note_date_is_not_the_year(self):
        ref = parse_reference("K. He et al., “Deep residual learning for image recognition,” in Proc. CVPR, 2016, "
                              "pp. 770–778. Accessed 12 March 2026.")
        self.assertEqual(ref.year, 2016)

    def test_gbt_with_any_type_tag(self):
        ref = parse_reference("VASWANI A, SHAZEER N, PARMAR N, et al. Attention Is All You Need[A/OL]. arXiv, 2017.")
        self.assertEqual(ref.title, "Attention Is All You Need")

    def test_a_venue_with_numbers_is_not_a_title(self):
        ref = parse_reference("Y. LeCun, Y. Bengio, and G. Hinton, Nature 521, 436 (2015).")  # AIP leaves out titles
        self.assertIsNone(ref.title)
        self.assertEqual(ref.first_author, "LeCun")

    def test_bibtex(self):
        ref = parse_reference("@article{LeCun_2015, title={Deep {L}earning}, volume={521}, journal={Nature}, "
                              "author={LeCun, Yann and Bengio, Yoshua}, year={2015}, doi={10.1038/nature14539}}")
        self.assertEqual((ref.title, ref.first_author, ref.year, ref.doi),
                         ("Deep Learning", "LeCun", 2015, "10.1038/nature14539"))

    def test_bibtex_entries_over_several_lines(self):
        lines = ["@article{a,", "  title={Deep learning},", "  author={LeCun, Yann},", "}",
                 "@inproceedings{b,", "  title = {Attention is all you need},", "}"]
        self.assertEqual(len(join_wrapped(lines)), 2)


class OtherIdsTest(unittest.TestCase):
    def test_pubmed_ids_and_acl_anthology(self):
        ref = parse_reference("Polack FP, et al. Safety and efficacy. N Engl J Med. 2020;383(27):2603-15. "
                              "PMID: 33301246; PMCID: PMC7745181.")
        self.assertEqual(ref.other_ids, ["pmid:33301246", "pmcid:PMC7745181"])
        ref = parse_reference("Devlin, J. et al. BERT. In NAACL, 2019. https://aclanthology.org/N19-1423/")
        self.assertEqual(ref.other_ids, ["doi:10.18653/v1/N19-1423"])


class ArxivIdTest(unittest.TestCase):
    def test_written_in_several_ways(self):
        for text in ("arXiv:2309.02427.", "arXiv: 2309.02427v3", "https://arxiv.org/abs/2309.02427v2",
                     "DOI: 10.48550/arXiv.2309.02427.", "arxiv.org/pdf/2309.02427"):
            with self.subTest(text=text):
                self.assertEqual(parse_reference("Sumers, T. (2023). Cognitive architectures. " + text).arxiv_id,
                                 "2309.02427")

    def test_old_style_and_none(self):
        self.assertEqual(parse_reference("Maldacena, J. (1997). The large N limit. arXiv:hep-th/9711200.").arxiv_id,
                         "hep-th/9711200")
        self.assertIsNone(parse_reference("He, K. (2016). Deep residual learning. CVPR, 770–778.").arxiv_id)


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

    def test_a_group_author_starts_a_reference(self):
        lines = ["Smith, J. (2019). A study of children's asthma. Journal of Asthma, 1, 1–2.",
                 "World Health Organization. (2020). Global report on asthma. WHO.",
                 "Organisation for Economic Co-operation and Development. (2018). Education at a glance. OECD."]
        self.assertEqual(join_wrapped(lines), lines)

    def test_a_line_that_opens_with_the_year_carries_on(self):
        refs = join_wrapped(["Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N.,",
                             "Kaiser, Ł., Polosukhin, I.",
                             "(2017). Attention is all you need. Advances in Neural Information Processing Systems, 30."])
        self.assertEqual(len(refs), 1)

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
        refs = join_wrapped(["He, K., & Sun, J. (2016). Deep residual learning. In Proc. CVPR (pp. 770–778).",
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
        lists = [split_passage(p["text"])[1] for name in ("llm_passages.json", "oa_passages.json")
                 for p in json.loads((data / name).read_text(encoding="utf-8"))["passages"]]
        lists.append([json.loads(line)["reference"] for line in
                      (data / "existence_sample.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()])
        for width in (40, 75, 110):
            for refs in lists:
                lines = [w for r in refs for w in textwrap.wrap(r, width, break_long_words=False, break_on_hyphens=False)]
                self.assertEqual(join_wrapped(lines), refs, f"width {width}")


class PlausibleAbstractTest(unittest.TestCase):
    """Indexes sometimes hold something else in a paper's abstract field."""

    ATTENTION = ("We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, "
                 "dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks "
                 "show these models to be superior in quality.")

    def test_a_real_abstract(self):
        self.assertTrue(plausible_abstract("Attention Is All You Need", self.ATTENTION))

    def test_a_real_abstract_that_links_to_its_code(self):
        text = self.ATTENTION + " Code and trained models are released at https://github.com/example/transformer."
        self.assertTrue(plausible_abstract("Attention Is All You Need", text))

    def test_a_software_readme(self):
        text = ("DiffuCpG. In this repository we deposit the code used to build the diffusion models with example "
                "datasets for methylation imputation. Docker usage: install Docker from the link below; a machine "
                "with 16 GB of memory is recommended.")
        self.assertFalse(plausible_abstract("Denoising Diffusion Probabilistic Models", text))

    def test_acknowledgments(self):
        text = ("We thank two referees for help at various stages of this work, which was originally supported by a "
                "study commission and has been revised substantially for this survey of the evidence.")
        self.assertFalse(plausible_abstract("The Effect of the Minimum Wage on Employment and Unemployment", text))

    def test_publication_details(self):
        text = ("Minimum Wages and Employment: A Case Study of the Fast-Food Industry in New Jersey and Pennsylvania: "
                "Reply by David Card and Alan B. Krueger. Published in volume 90, issue 5, pages 1397-1420 of "
                "American Economic Review, December 2000")
        self.assertFalse(plausible_abstract("Minimum Wages and Employment: Reply", text))

    def test_an_abstract_about_installing_things(self):
        text = ("We studied the installation and usage of rooftop solar panels in 300 households and found that "
                "installation costs, not usage habits, explained most of the variation in adoption.")
        self.assertTrue(plausible_abstract("Rooftop solar adoption in households", text))

    def test_an_abstract_with_a_funding_note(self):
        text = ("Our results are supported by a randomized trial of 139 patients with obesity, in which weight loss "
                "did not differ between groups after 12 months. (Funded by the National Key Research Project.)")
        self.assertTrue(plausible_abstract("Time-restricted eating for weight loss", text))

    def test_text_about_something_else(self):
        self.assertFalse(plausible_abstract("Deep Residual Learning for Image Recognition", self.ATTENTION))

    def test_too_short(self):
        self.assertFalse(plausible_abstract("Attention Is All You Need", "Attention matters a great deal."))

    def test_a_title_in_chinese_skips_the_shared_word_check(self):
        self.assertTrue(plausible_abstract("机器学习", self.ATTENTION))

    def test_an_ieee_author_list_broken_after_an_initial(self):
        refs = join_wrapped(["[1] D. K. Duvenaud, D. Maclaurin, J.",
                             "Iparraguirre, R. Gomez-Bombarelli, and R. P. Adams, \"Convolutional networks on graphs,\"",
                             "in Advances in Neural Information Processing Systems 28, 2015, pp. 2224-2232.",
                             "[2] S. Kearnes and P. Riley, \"Molecular graph convolutions,\" J. Comput.-Aided Mol. Des., 2016."])
        self.assertEqual(len(refs), 2)
