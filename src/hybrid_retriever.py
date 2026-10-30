from __future__ import annotations

from src.retrieval_fusion import reciprocal_rank_fusion


class HybridRetriever:
    """Fuse dense and BM25 result lists with equal-weight RRF."""

    def __init__(self, dense, bm25):
        self.dense = dense
        self.bm25 = bm25
        self.calls = []

    def retrieve(self, query: str, top_k: int = 10) -> list[dict]:
        dense_results = self.dense.retrieve(query, top_k=top_k)
        bm25_results = self.bm25.retrieve(query, top_k=top_k)
        union = reciprocal_rank_fusion(dense_results, bm25_results, top_k=None)
        self.calls.append(
            {
                "query": query,
                "dense": dense_results,
                "bm25": bm25_results,
                "union": union,
            }
        )
        return union
