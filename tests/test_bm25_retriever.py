import unittest

from src.bm25_retriever import BM25Retriever


class BM25RetrieverTest(unittest.TestCase):
    def test_ranks_matching_chunk_and_preserves_provenance(self):
        records = [
            {
                "text": "station lighting system design requirements",
                "source": "spec.pdf",
                "chunk_id": 1,
                "page_start": 10,
            },
            {
                "text": "table10.3.5 stadium entrance minimum spacing is 50m",
                "source": "spec.pdf",
                "chunk_id": 2,
                "page_start": 61,
                "table_id": "table10.3.5",
            },
            {
                "text": "track power supply safety requirements",
                "source": "spec.pdf",
                "chunk_id": 3,
                "page_start": 20,
            },
        ]

        result = BM25Retriever(records).retrieve("stadium entrance spacing", top_k=1)[0]

        self.assertEqual(result["chunk_id"], 2)
        self.assertEqual(result["page_start"], 61)
        self.assertEqual(result["table_id"], "table10.3.5")
        self.assertIsInstance(result["score"], float)


if __name__ == "__main__":
    unittest.main()
