import unittest

from eval.rrf import RRF_K, reciprocal_rank_fusion


class RRFTest(unittest.TestCase):
    def test_equal_rank_fusion_deduplicates_stable_chunk_identity(self):
        dense = [
            {"source": "spec.pdf", "chunk_id": 1, "text": "dense"},
            {"source": "spec.pdf", "chunk_id": 2, "text": "second"},
        ]
        bm25 = [
            {"source": "spec.pdf", "chunk_id": 2, "text": "second"},
            {"source": "spec.pdf", "chunk_id": 3, "text": "third"},
        ]

        fused = reciprocal_rank_fusion(dense, bm25, top_k=3)

        self.assertEqual([item["chunk_id"] for item in fused], [2, 1, 3])
        self.assertEqual(fused[0]["rrf_score"], 1 / (RRF_K + 2) + 1 / (RRF_K + 1))
        self.assertEqual(len({(item["source"], item["chunk_id"]) for item in fused}), 3)


if __name__ == "__main__":
    unittest.main()
