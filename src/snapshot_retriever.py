from __future__ import annotations

from dataclasses import dataclass
import re

from src.bm25_retriever import BM25Retriever
from src.query_scope import (
    QueryScope,
    ResolvedQueryScope,
    resolve_query_scope,
    versions_from_catalog,
    versions_from_snapshot,
)
from src.retrieval_fusion import chunk_identity, reciprocal_rank_fusion
from src.retriever import Retriever


class ScopeBoundaryError(RuntimeError):
    """Raised if any retrieval stage produces evidence outside its request scope."""


@dataclass(frozen=True)
class _DocumentRetriever:
    business_id: str
    dense: object
    bm25: BM25Retriever


class SnapshotRetriever:
    """Immutable snapshot facade that creates request-local scoped retrievers."""

    def __init__(self, snapshot, catalog, embedder):
        self.snapshot = snapshot
        self.catalog = catalog
        self.embedder = embedder
        self.snapshot_id = snapshot.snapshot_id

    def for_scope(self, scope: QueryScope) -> ScopedSnapshotRetriever:
        resolved = resolve_query_scope(
            scope,
            snapshot_id=self.snapshot_id,
            snapshot_versions=versions_from_snapshot(self.snapshot),
            catalog_versions=versions_from_catalog(self.catalog),
        )
        allowed = set(resolved.business_ids)
        documents = []
        for item in self.snapshot.documents:
            if item.manifest.business_id not in allowed:
                continue
            documents.append(
                _DocumentRetriever(
                    item.manifest.business_id,
                    Retriever(item.vector_store, self.embedder),
                    BM25Retriever(item.vector_store.chunk_records),
                )
            )
        return ScopedSnapshotRetriever(resolved, tuple(documents))


class ScopedSnapshotRetriever:
    def __init__(
        self,
        scope: ResolvedQueryScope,
        documents: tuple[_DocumentRetriever, ...],
    ):
        self.scope = scope
        self.documents = documents
        self.calls: list[dict] = []
        self._chunk_records = {
            chunk_identity(record): record
            for document in documents
            for record in document.bm25.chunk_records
        }

    def retrieve(self, query: str, top_k: int = 10) -> list[dict]:
        ranked_lists = []
        per_document = []
        requested_articles = set(re.findall(r"(?<!\d)(\d+(?:\.\d+){2,})(?!\d)", query))
        for document in self.documents:
            dense = document.dense.retrieve(query, top_k=top_k)
            bm25 = document.bm25.retrieve(query, top_k=top_k)
            exact_articles = [
                {**record, "score": 1.0, "match_type": "exact_article"}
                for record in document.bm25.chunk_records
                if record.get("article_id") in requested_articles
            ]
            self._assert_in_scope([*dense, *bm25, *exact_articles])
            ranked_lists.extend((exact_articles, dense, bm25))
            per_document.append(
                {
                    "business_id": document.business_id,
                    "dense_candidates": len(dense),
                    "bm25_candidates": len(bm25),
                    "exact_article_candidates": len(exact_articles),
                }
            )
        fused = reciprocal_rank_fusion(*ranked_lists, top_k=None)
        self._assert_in_scope(fused)
        self.calls.append(
            {
                "query": query,
                "snapshot_id": self.scope.snapshot_id,
                "scope": list(self.scope.business_ids),
                "documents": per_document,
                "fused_candidates": len(fused),
            }
        )
        return fused

    def expand_neighbors(self, results: list[dict]) -> list[dict]:
        self._assert_in_scope(results)
        expanded = list(results)
        seen = {chunk_identity(item) for item in results}
        for result in results:
            chunk_id = result.get("chunk_id")
            article_id = result.get("article_id")
            if not isinstance(chunk_id, int) or not article_id:
                continue
            for neighbor_id in (chunk_id - 1, chunk_id + 1):
                identity = chunk_identity({**result, "chunk_id": neighbor_id})
                neighbor = self._chunk_records.get(identity)
                if (
                    neighbor is None
                    or identity in seen
                    or neighbor.get("article_id") != article_id
                ):
                    continue
                seen.add(identity)
                expanded.append({**neighbor, "score": 0.0})
        self._assert_in_scope(expanded)
        return expanded

    def _assert_in_scope(self, results: list[dict]) -> None:
        escaped = [
            chunk_identity(item)
            for item in results
            if not self.scope.allows(item.get("spec_id"), item.get("edition_id"))
        ]
        if escaped:
            raise ScopeBoundaryError(f"retrieval produced out-of-scope evidence: {escaped}")
