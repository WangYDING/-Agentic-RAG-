import unittest

from src.document_schema import DocumentMetadata, Page, PageMetadata
from src.loader import clean_page_text, detect_repeated_page_noise
from src.splitter import parse_structural_lines, split_pages_with_ref


class IngestionMetadataTest(unittest.TestCase):
    def test_repeated_header_footer_and_watermark_are_removed_conservatively(self):
        pages = [
            "DB11/T 995-2025\n1\n1 总则\n北京市规划和自然资源委\n北京市\n",
            "DB11/T 995-2025\n2\n正文 保留规划和自然资源委作为句子的一部分\n北京市规划和自然资源委\n北京市\n",
            "DB11/T 995-2025\n3\n3.0.1\n条文正文\n源委\n北京市\n",
        ]
        noise = detect_repeated_page_noise(pages)

        cleaned = clean_page_text(pages[1], noise)

        self.assertNotIn("DB11/T 995-2025", cleaned)
        self.assertNotIn("\n北京市\n", f"\n{cleaned}\n")
        self.assertNotIn("\n2\n", f"\n{cleaned}\n")
        self.assertIn("正文保留规划和自然资源委作为句子的一部分", cleaned)

    def test_article_id_can_be_standalone_line_before_body(self):
        parsed = parse_structural_lines("10.3.3\n地上车站应符合下列规定：\n1\n设置要求")

        article_ids = [item["article_id"] for item in parsed]

        self.assertEqual(article_ids[0], "10.3.3")
        self.assertEqual(article_ids[1], "10.3.3")

    def test_chapter_can_be_inferred_from_split_title_and_first_article(self):
        parsed = parse_structural_lines("总\n则\n1.0.1\n制定本标准。")

        self.assertEqual(parsed[0]["chapter_id"], "1")
        self.assertEqual(parsed[0]["chapter_title"], "总则")
        self.assertEqual(parsed[2]["article_id"], "1.0.1")

    def test_split_pages_adds_page_chapter_article_metadata(self):
        document = DocumentMetadata(
            document_id="spec",
            source="spec.pdf",
            page_count=1,
        )
        page = Page(
            text="10\n车站建筑\n10.3.2\n站厅公共区及出入口宜与相邻建筑地下空间衔接。",
            raw_text="raw",
            metadata=PageMetadata(
                document_id="spec",
                source="spec.pdf",
                page_number=35,
                char_count_raw=3,
                char_count_cleaned=40,
            ),
        )

        chunks = split_pages_with_ref(document, [page], chunk_size=300, overlap=50)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["document_id"], "spec")
        self.assertEqual(chunks[0]["source"], "spec.pdf")
        self.assertEqual(chunks[0]["page_start"], 35)
        self.assertEqual(chunks[0]["page_end"], 35)
        self.assertEqual(chunks[0]["chapter_id"], "10")
        self.assertEqual(chunks[0]["chapter_title"], "车站建筑")
        self.assertEqual(chunks[0]["article_id"], "10.3.2")
        self.assertEqual(chunks[0]["display_ref"], "第10.3.2条")

    def test_chunks_do_not_cross_article_boundaries(self):
        document = DocumentMetadata("spec", "spec.pdf", 1)
        page = Page(
            text="4.3.1\n第一条正文。\n4.3.2\n第二条正文。",
            raw_text="raw",
            metadata=PageMetadata("spec", "spec.pdf", 1, 30, 30),
        )

        chunks = split_pages_with_ref(document, [page], chunk_size=300, overlap=50)

        self.assertEqual([chunk["article_id"] for chunk in chunks], ["4.3.1", "4.3.2"])
        self.assertNotIn("4.3.2", chunks[0]["text"])

    def test_long_article_children_keep_the_same_article_id(self):
        document = DocumentMetadata("spec", "spec.pdf", 1)
        page = Page(
            text="7.2.1\n" + "长条文内容" * 100,
            raw_text="raw",
            metadata=PageMetadata("spec", "spec.pdf", 1, 500, 500),
        )

        chunks = split_pages_with_ref(document, [page], chunk_size=100, overlap=20)

        self.assertGreater(len(chunks), 1)
        self.assertEqual({chunk["article_id"] for chunk in chunks}, {"7.2.1"})


if __name__ == "__main__":
    unittest.main()
