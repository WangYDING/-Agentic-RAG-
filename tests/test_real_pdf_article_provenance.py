import re
import unittest
from pathlib import Path

from src.loader import load_pdf_pages
from src.splitter import split_pages_with_ref


PDF_PATH = Path("data/raw/城市轨道交通工程设计标准.pdf")


@unittest.skipUnless(PDF_PATH.exists(), "real PDF fixture is not available")
class RealPdfArticleProvenanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        document, pages = load_pdf_pages(str(PDF_PATH))
        cls.chunks = split_pages_with_ref(document, pages)

    def test_known_article_samples_have_correct_provenance(self):
        samples = [
            (32, "4.3.1", "城市轨道交通列车运行应采用双线线路"),
            (45, "7.2.1", "车站站台宜设在直线上"),
            (59, "10.1.4", "客流动态仿真模拟评价结果"),
            (61, "10.3.4", "地下车站跨路口设置时"),
            (50, "8.2.2", "钢轨标准轨距应为1435mm"),
        ]

        for page, article, phrase in samples:
            with self.subTest(page=page, article=article):
                matches = [
                    chunk for chunk in self.chunks
                    if chunk["content_type"] == "text"
                    and chunk["page_start"] == page
                    and phrase in chunk["text"]
                ]
                self.assertTrue(matches)
                self.assertEqual({chunk["article_id"] for chunk in matches}, {article})

    def test_no_text_chunk_contains_multiple_articles(self):
        pattern = re.compile(r"(?m)^\s*((?:\d+\.){2,}\d+)\s*$")
        crossing = [
            chunk for chunk in self.chunks
            if chunk["content_type"] == "text"
            and len(set(pattern.findall(chunk["text"]))) > 1
        ]

        self.assertEqual(crossing, [])

    def test_table_chunks_are_not_bound_to_articles(self):
        table_chunks = [chunk for chunk in self.chunks if chunk["content_type"] == "table"]

        self.assertTrue(table_chunks)
        self.assertTrue(all(chunk["article_id"] is None for chunk in table_chunks))


if __name__ == "__main__":
    unittest.main()
