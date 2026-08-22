import unittest

from src.chat_memory import ChatMemory
from src.rag_service import RAGService


RESULTS = [
    {"text": "片段一", "source": "spec.pdf", "display_ref": "chunk_0", "chunk_id": 0, "page_start": 1},
    {"text": "片段二", "source": "spec.pdf", "display_ref": "chunk_1", "chunk_id": 1, "page_start": 2},
    {"text": "片段三", "source": "spec.pdf", "display_ref": "chunk_2", "chunk_id": 2, "page_start": 3},
]


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def retrieve(self, query, top_k):
        self.calls.append((query, top_k))
        return [item.copy() for item in RESULTS]


class FakeReranker:
    def __init__(self):
        self.calls = []

    def rerank(self, query, results, top_n):
        self.calls.append((query, results, top_n))
        return list(reversed(results))[:top_n]


class FakeGenerator:
    def __init__(self):
        self.calls = []

    def generate_answer(self, query, evidences, chat_history):
        self.calls.append((query, evidences, list(chat_history)))
        return "baseline answer [E1]"


class FakeRewriter:
    def __init__(self, rewritten="改写后的问题"):
        self.rewritten = rewritten
        self.calls = []

    def rewrite(self, query, chat_history):
        self.calls.append((query, list(chat_history)))
        return self.rewritten


class RAGServiceTest(unittest.TestCase):
    def build_service(self, rewriter=None):
        self.retriever = FakeRetriever()
        self.reranker = FakeReranker()
        self.generator = FakeGenerator()
        return RAGService(
            retriever=self.retriever,
            reranker=self.reranker,
            generator=self.generator,
            rewriter=rewriter,
        )

    def test_cli_baseline_uses_history_query_then_reranks_original_query(self):
        memory = ChatMemory(max_turns=3)
        memory.add_user_message("上一问")
        memory.add_assistant_message("上一答")
        service = self.build_service()

        response = service.answer(
            "当前问题",
            memory,
            query_mode="history",
            top_k=10,
            top_n=3,
            use_rerank=True,
        )

        expected_query = "用户之前问：上一问\n系统之前回答：上一答\n当前问题：当前问题"
        self.assertEqual(self.retriever.calls, [(expected_query, 10)])
        self.assertEqual(self.reranker.calls[0][0], "当前问题")
        self.assertEqual(self.reranker.calls[0][2], 3)
        self.assertEqual(
            [(self.generator.calls[0][0], [e.text for e in self.generator.calls[0][1]], self.generator.calls[0][2])],
            [("当前问题", ["片段三", "片段二", "片段一"], [
                {"role": "user", "content": "上一问"},
                {"role": "assistant", "content": "上一答"},
            ])],
        )
        self.assertEqual(response.answer, "baseline answer [E1]")
        self.assertEqual([e.evidence_id for e in response.evidences], ["E1", "E2", "E3"])
        self.assertTrue(response.citation_validation.valid)
        self.assertEqual(memory.get_recent_history()[-2:], [
            {"role": "user", "content": "当前问题"},
            {"role": "assistant", "content": "baseline answer [E1]"},
        ])

    def test_web_baseline_rewrites_before_retrieval(self):
        memory = ChatMemory(max_turns=3)
        rewriter = FakeRewriter()
        service = self.build_service(rewriter)

        response = service.answer(
            "那验收标准呢",
            memory,
            query_mode="rewrite",
            top_k=8,
            top_n=2,
            use_rerank=True,
        )

        self.assertEqual(rewriter.calls, [("那验收标准呢", [])])
        self.assertEqual(self.retriever.calls, [("改写后的问题", 8)])
        self.assertEqual(self.reranker.calls[0][0], "那验收标准呢")
        self.assertEqual(response.retrieval_query, "改写后的问题")
        self.assertEqual([item["text"] for item in response.results], ["片段三", "片段二"])
        self.assertEqual([e.evidence_id for e in response.evidences], ["E1", "E2"])

    def test_web_baseline_can_skip_reranker_and_slice_dense_results(self):
        service = self.build_service(FakeRewriter())

        response = service.answer(
            "问题",
            ChatMemory(),
            query_mode="rewrite",
            top_k=5,
            top_n=2,
            use_rerank=False,
        )

        self.assertEqual(self.reranker.calls, [])
        self.assertEqual(response.results, RESULTS[:2])
        self.assertEqual([e.text for e in self.generator.calls[0][1]], ["片段一", "片段二"])

    def test_rewrite_mode_requires_rewriter(self):
        service = self.build_service()
        with self.assertRaisesRegex(RuntimeError, "requires a query rewriter"):
            service.answer("问题", ChatMemory(), query_mode="rewrite")


if __name__ == "__main__":
    unittest.main()
