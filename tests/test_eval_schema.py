import unittest

from eval.schema import ConversationMessage, EvalExample, GoldEvidence, is_gold_hit


class EvalSchemaTest(unittest.TestCase):
    def test_loads_optional_refusal_fields(self):
        item = EvalExample.from_dict({
            "id": "ua1",
            "question": "question",
            "question_type": "unanswerable",
            "answerable": False,
            "gold_evidence": [],
            "hard_negative_type": "missing_fact",
            "why_unanswerable": "missing",
        })

        self.assertEqual(item.hard_negative_type, "missing_fact")
        self.assertEqual(item.why_unanswerable, "missing")

    def test_loads_example_from_dict(self):
        example = EvalExample.from_dict({
            "id": "q1",
            "question": "问题",
            "question_type": "article_lookup",
            "answerable": True,
            "gold_answer": "答案",
            "gold_evidence": [
                {
                    "document": "spec.pdf",
                    "page": 61,
                    "article": "10.3.3",
                    "table": None,
                }
            ],
        })

        self.assertEqual(example.id, "q1")
        self.assertEqual(example.gold_evidence[0].page, 61)
        self.assertEqual(example.conversation_history, [])
        self.assertIsNone(example.rewritten_query_reference)

    def test_loads_optional_conversation_fields(self):
        example = EvalExample.from_dict({
            "id": "ctx1",
            "question": "那后者呢？",
            "question_type": "context_dependent",
            "answerable": True,
            "gold_answer": "答案",
            "gold_evidence": [],
            "conversation_history": [
                {"role": "user", "content": "前一个问题"},
                {"role": "assistant", "content": "前一个答案"},
            ],
            "rewritten_query_reference": "完整问题",
        })

        self.assertEqual(example.conversation_history, [
            ConversationMessage("user", "前一个问题"),
            ConversationMessage("assistant", "前一个答案"),
        ])
        self.assertEqual(example.rewritten_query_reference, "完整问题")
        self.assertEqual(example.to_dict()["conversation_history"][0]["role"], "user")

    def test_rejects_invalid_conversation_role(self):
        with self.assertRaisesRegex(ValueError, "Invalid conversation role"):
            EvalExample.from_dict({
                "id": "ctx1",
                "question": "问题",
                "question_type": "context_dependent",
                "answerable": True,
                "gold_answer": "答案",
                "conversation_history": [{"role": "tool", "content": "内容"}],
            })

    def test_rejects_non_string_rewritten_query_reference(self):
        with self.assertRaisesRegex(ValueError, "must be a string or null"):
            EvalExample.from_dict({
                "id": "ctx1",
                "question": "问题",
                "question_type": "context_dependent",
                "answerable": True,
                "gold_answer": "答案",
                "rewritten_query_reference": ["不是字符串"],
            })

    def test_false_premise_question_type_is_supported(self):
        example = EvalExample.from_dict({
            "id": "fp1",
            "question": "错误前提问题",
            "question_type": "false_premise",
            "answerable": True,
            "gold_answer": "纠正答案",
            "gold_evidence": [{"document": "spec.pdf", "article": "1.0.1"}],
        })

        self.assertEqual(example.question_type, "false_premise")
        self.assertTrue(example.answerable)

    def test_gold_hit_matches_document_page_article_and_table(self):
        retrieved = {
            "source": "spec.pdf",
            "page_start": 60,
            "page_end": 62,
            "article_id": "10.3.5",
            "table_id": "表10.3.5",
        }
        gold = [GoldEvidence("spec.pdf", page=61, article="10.3.5", table="表10.3.5")]

        self.assertTrue(is_gold_hit(retrieved, gold))
        self.assertFalse(is_gold_hit(retrieved, [GoldEvidence("spec.pdf", page=63)]))
        self.assertFalse(is_gold_hit(retrieved, [GoldEvidence("other.pdf", page=61)]))


if __name__ == "__main__":
    unittest.main()
