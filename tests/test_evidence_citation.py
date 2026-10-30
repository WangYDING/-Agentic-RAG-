import unittest

from src.evidence import (
    build_evidence_context,
    build_evidence_list,
    format_evidence_citation,
    validate_citations,
)


ARTICLE_RESULT = {
    "text": "10.3.3 地上车站应符合下列规定。",
    "source": "spec.pdf",
    "chunk_id": 7,
    "page_start": 61,
    "page_end": 61,
    "chapter_id": "10",
    "chapter_title": "车站总体布局",
    "article_id": "10.3.3",
    "display_ref": "第10.3.3条",
    "content_type": "text",
    "score": 0.91,
}

TABLE_RESULT = {
    "text": "表号: 表10.3.5\n第1行: 体育馆 | 50",
    "source": "spec.pdf",
    "chunk_id": 8,
    "page_start": 61,
    "page_end": 61,
    "chapter_id": "10",
    "chapter_title": "车站总体布局",
    "article_id": "10.3.5",
    "display_ref": "表10.3.5",
    "content_type": "table",
    "table_id": "表10.3.5",
    "table_title": "出入口离建、构筑物的进出口边缘最小间距",
    "score": 0.88,
    "rerank_score": 0.72,
}


class EvidenceCitationTest(unittest.TestCase):
    def test_build_evidence_list_preserves_article_and_table_metadata(self):
        evidences = build_evidence_list([ARTICLE_RESULT, TABLE_RESULT])

        self.assertEqual([e.evidence_id for e in evidences], ["E1", "E2"])
        self.assertEqual(evidences[0].article_id, "10.3.3")
        self.assertEqual(evidences[0].page_start, 61)
        self.assertEqual(evidences[1].content_type, "table")
        self.assertEqual(evidences[1].table_id, "表10.3.5")
        self.assertEqual(evidences[1].table_title, "出入口离建、构筑物的进出口边缘最小间距")

    def test_context_builder_uses_structured_evidence_ids(self):
        context = build_evidence_context(build_evidence_list([ARTICLE_RESULT, TABLE_RESULT]))

        self.assertIn("[E1]", context)
        self.assertIn("条文: 10.3.3", context)
        self.assertIn("[E2]", context)
        self.assertIn("类型: table", context)
        self.assertIn("表格: 表10.3.5", context)

    def test_validator_rejects_unknown_evidence_id(self):
        evidences = build_evidence_list([ARTICLE_RESULT])

        validation = validate_citations("结论来自 [E1] 和 [E2]。", evidences)

        self.assertFalse(validation.valid)
        self.assertEqual(validation.cited_ids, ["E1", "E2"])
        self.assertIn("UNKNOWN_EVIDENCE_ID:E2", validation.errors)

    def test_validator_rejects_answer_without_any_citation(self):
        evidences = build_evidence_list([ARTICLE_RESULT])

        validation = validate_citations("这是一个没有引用的结论。", evidences)

        self.assertFalse(validation.valid)
        self.assertIn("MISSING_CITATION", validation.errors)

    def test_validator_only_requires_metadata_for_cited_evidence(self):
        unresolved = ARTICLE_RESULT.copy()
        unresolved["page_start"] = None
        evidences = build_evidence_list([ARTICLE_RESULT, unresolved])

        validation = validate_citations("结论来自 [E1]。", evidences)

        self.assertTrue(validation.valid)

    def test_validator_rejects_unresolved_metadata(self):
        result = ARTICLE_RESULT.copy()
        result["page_start"] = None
        evidences = build_evidence_list([result])

        validation = validate_citations("结论来自 [E1]。", evidences)

        self.assertFalse(validation.valid)
        self.assertIn("UNRESOLVED_PAGE:E1", validation.errors)

    def test_validator_rejects_missing_source_on_cited_evidence(self):
        result = ARTICLE_RESULT.copy()
        result["source"] = ""
        evidences = build_evidence_list([result])

        validation = validate_citations("结论来自 [E1]。", evidences)

        self.assertFalse(validation.valid)
        self.assertIn("UNRESOLVED_SOURCE:E1", validation.errors)

    def test_format_evidence_citation_contains_resolvable_metadata(self):
        article, table = build_evidence_list([ARTICLE_RESULT, TABLE_RESULT])

        self.assertEqual(
            format_evidence_citation(article),
            "[E1] spec.pdf - p.61 - 第10.3.3条",
        )
        self.assertIn("[E2] spec.pdf - p.61 - 第10.3.5条 - 表10.3.5", format_evidence_citation(table))


if __name__ == "__main__":
    unittest.main()
