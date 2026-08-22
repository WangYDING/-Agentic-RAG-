import unittest

from src.chat_memory import ChatMemory
from src.splitter import extract_article_id, split_text_with_ref


class BaselineComponentsTest(unittest.TestCase):
    def test_splitter_keeps_300_50_sliding_window_contract(self):
        chunks = split_text_with_ref(
            "A" * 600,
            source="spec.pdf",
            chunk_size=300,
            overlap=50,
        )
        self.assertEqual([len(chunk["text"]) for chunk in chunks], [300, 300, 100])
        self.assertEqual([chunk["chunk_id"] for chunk in chunks], [0, 1, 2])
        self.assertTrue(all(chunk["source"] == "spec.pdf" for chunk in chunks))

    def test_article_reference_extraction_contract(self):
        self.assertEqual(extract_article_id("13.1.1 条文内容"), "13.1.1")
        self.assertIsNone(extract_article_id("0.25 数值"))

    def test_memory_keeps_three_turns(self):
        memory = ChatMemory(max_turns=3)
        for index in range(4):
            memory.add_user_message(f"q{index}")
            memory.add_assistant_message(f"a{index}")
        self.assertEqual(len(memory.get_recent_history()), 6)
        self.assertEqual(memory.get_recent_history()[0]["content"], "q1")


if __name__ == "__main__":
    unittest.main()
