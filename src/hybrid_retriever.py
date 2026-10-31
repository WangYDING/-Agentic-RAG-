from __future__ import annotations

from src.retrieval_fusion import reciprocal_rank_fusion


class HybridRetriever:
    """Fuse dense and BM25 result lists with equal-weight RRF."""

    def __init__(self, dense, bm25):
        self.dense = dense
        self.bm25 = bm25
        self.calls = []
        self._chunk_records = {
            (record.get("source"), record.get("chunk_id")): record
            for record in getattr(bm25, "chunk_records", [])
        }

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

    def expand_neighbors(self, results: list[dict]) -> list[dict]:
        """Add only adjacent chunks that belong to the same source and article."""
        expanded = list(results)
        seen = {
            (result.get("source"), result.get("chunk_id")) for result in results
        }
        for result in results:
            chunk_id = result.get("chunk_id")
            article_id = result.get("article_id")
            source = result.get("source")
            if not isinstance(chunk_id, int) or not article_id:
                continue
            for neighbor_id in (chunk_id - 1, chunk_id + 1):
                record = self._chunk_records.get((source, neighbor_id))
                if not record or record.get("article_id") != article_id:
                    continue
                identity = (source, neighbor_id)
                if identity in seen:
                    continue
                seen.add(identity)
                neighbor = dict(record)
                neighbor.setdefault("content_type", "text")
                neighbor.setdefault("extra", {})
                neighbor.setdefault("display_ref", f"chunk_{neighbor_id}")
                neighbor["score"] = 0.0
                expanded.append(neighbor)
        return expanded
