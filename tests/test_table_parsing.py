import unittest

from src.document_schema import DocumentMetadata, Page, PageMetadata, Table, TableMetadata
from src.loader import (
    _clean_table_cell,
    _extract_table_captions,
    build_table_retrieval_text,
)
from src.splitter import split_pages_with_ref


class TableParsingTest(unittest.TestCase):
    def test_extracts_table_caption_and_title(self):
        captions = _extract_table_captions(
            "表7.2.2\n缓和曲线长度（m）\n正文",
            repeated_noise=set(),
        )

        self.assertEqual(captions, [("表7.2.2", "缓和曲线长度（m）")])

    def test_table_cell_cleaning_removes_watermark_noise(self):
        cell = _clean_table_cell("市\n京\n90", repeated_noise=set())
        mixed = _clean_table_cell("65 然\n自", repeated_noise=set())

        self.assertEqual(cell, "90")
        self.assertEqual(mixed, "65")

    def test_build_table_retrieval_text_keeps_headers_and_rows(self):
        metadata = TableMetadata(
            document_id="spec",
            source="spec.pdf",
            page_number=46,
            table_id="表7.2.2",
            title="缓和曲线长度（m）",
        )

        text = build_table_retrieval_text(
            metadata,
            headers=[["R", "130", "125"]],
            rows=[["12000", "20", "20"], ["11500", "20", "20"]],
        )

        self.assertIn("表号: 表7.2.2", text)
        self.assertIn("表题: 缓和曲线长度（m）", text)
        self.assertIn("表头: R | 130 | 125", text)
        self.assertIn("第1行: 12000 | 20 | 20", text)

    def test_split_pages_emits_table_chunk_with_structured_representation(self):
        document = DocumentMetadata("spec", "spec.pdf", 1)
        table = Table(
            metadata=TableMetadata(
                document_id="spec",
                source="spec.pdf",
                page_number=46,
                table_id="表7.2.2",
                title="缓和曲线长度（m）",
            ),
            headers=[["R", "130"]],
            rows=[["12000", "20"]],
            cells=[["R", "130"], ["12000", "20"]],
            retrieval_text="表号: 表7.2.2\n表题: 缓和曲线长度（m）\n第1行: 12000 | 20",
        )
        page = Page(
            text="7.2.2\n正文",
            raw_text="raw",
            tables=[table],
            metadata=PageMetadata("spec", "spec.pdf", 46, 3, 8),
        )

        records = split_pages_with_ref(document, [page], chunk_size=300, overlap=50)
        table_records = [record for record in records if record["content_type"] == "table"]

        self.assertEqual(len(table_records), 1)
        self.assertEqual(table_records[0]["table_id"], "表7.2.2")
        self.assertEqual(table_records[0]["table_title"], "缓和曲线长度（m）")
        self.assertEqual(table_records[0]["page_start"], 46)
        self.assertIsNone(table_records[0]["article_id"])
        self.assertEqual(table_records[0]["extra"]["table"]["rows"], [["12000", "20"]])
        self.assertIn("表号: 表7.2.2", table_records[0]["text"])


if __name__ == "__main__":
    unittest.main()
