import unittest
from types import SimpleNamespace

from src.hybrid_retriever import HybridRetriever


class EmptyRetriever:
    def retrieve(self, query, top_k):
        return []


class HybridRetrieverNeighborTest(unittest.TestCase):
    def test_expands_only_adjacent_chunks_from_same_article_and_source(self):
        records = [
            {"source": "spec.pdf", "chunk_id": 9, "article_id": "7.1.9", "text": "previous article"},
            {"source": "spec.pdf", "chunk_id": 10, "article_id": "7.2.1", "text": "first half"},
            {"source": "spec.pdf", "chunk_id": 11, "article_id": "7.2.1", "text": "second half"},
            {"source": "spec.pdf", "chunk_id": 12, "article_id": "7.2.2", "text": "next article"},
            {"source": "other.pdf", "chunk_id": 11, "article_id": "7.2.1", "text": "other source"},
        ]
        bm25 = SimpleNamespace(chunk_records=records)
        retriever = HybridRetriever(EmptyRetriever(), bm25)

        expanded = retriever.expand_neighbors([dict(records[1])])

        self.assertEqual(
            [(item["source"], item["chunk_id"]) for item in expanded],
            [("spec.pdf", 10), ("spec.pdf", 11)],
        )


if __name__ == "__main__":
    unittest.main()
