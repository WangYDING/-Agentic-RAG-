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
from src.query_decomposition import decompose_retrieval_targets, focused_query_variants
from src.retrieval_fusion import chunk_identity, reciprocal_rank_fusion
from src.retriever import Retriever


class ScopeBoundaryError(RuntimeError):
    """Raised if any retrieval stage produces evidence outside its request scope."""


@dataclass(frozen=True)
class _DocumentRetriever:
    business_id: str
    standard_code: str
    title: str
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
        catalog_by_id = {item.business_id: item for item in self.catalog.documents}
        documents = []
        for item in self.snapshot.documents:
            if item.manifest.business_id not in allowed:
                continue
            documents.append(
                _DocumentRetriever(
                    item.manifest.business_id,
                    catalog_by_id[item.manifest.business_id].standard_code,
                    catalog_by_id[item.manifest.business_id].title,
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
        focused_queries = focused_query_variants(decompose_retrieval_targets(query))
        query_runs = []
        all_rankings = []
        for retrieval_query in [query, *focused_queries]:
            run_top_k = top_k
            fused, per_document = self._retrieve_once(retrieval_query, run_top_k)
            all_rankings.append(fused)
            query_runs.append(
                {
                    "query": retrieval_query,
                    "top_k": run_top_k,
                    "documents": per_document,
                    "fused_candidates": len(fused),
                }
            )
        fused = reciprocal_rank_fusion(*all_rankings, top_k=None)
        query_ranks: dict[tuple[object, ...], dict[str, int]] = {}
        document_query_ranks: dict[tuple[object, ...], dict[str, int]] = {}
        for run, ranking in zip(query_runs, all_rankings, strict=True):
            document_positions: dict[str, int] = {}
            for rank, item in enumerate(ranking, start=1):
                query_ranks.setdefault(chunk_identity(item), {})[run["query"]] = rank
                business_id = f"{item.get('spec_id')}@{item.get('edition_id')}"
                document_positions[business_id] = document_positions.get(business_id, 0) + 1
                document_query_ranks.setdefault(chunk_identity(item), {})[
                    run["query"]
                ] = document_positions[business_id]
        for item in fused:
            ranks = query_ranks.get(chunk_identity(item), {})
            focused_ranks = [
                rank for focused in focused_queries if (rank := ranks.get(focused)) is not None
            ]
            item["retrieval_query_ranks"] = ranks
            item["document_query_ranks"] = document_query_ranks.get(
                chunk_identity(item), {}
            )
            item["focused_best_rank"] = min(focused_ranks) if focused_ranks else None
            item["focused_rank_sum"] = sum(focused_ranks) if focused_ranks else None
        self._assert_in_scope(fused)
        self.calls.append(
            {
                "query": query,
                "snapshot_id": self.scope.snapshot_id,
                "scope": list(self.scope.business_ids),
                "focused_queries": focused_queries,
                "query_runs": query_runs,
                "fused_candidates": len(fused),
            }
        )
        return fused

    def _retrieve_once(self, query: str, top_k: int) -> tuple[list[dict], list[dict]]:
        ranked_lists = []
        per_document = []
        requested_articles = set(re.findall(r"(?<!\d)(\d+(?:\.\d+){2,})(?!\d)", query))
        for document in self.documents:
            dense = self._decorate(document.dense.retrieve(query, top_k=top_k), document)
            bm25 = self._decorate(document.bm25.retrieve(query, top_k=top_k), document)
            exact_articles = [
                {
                    **self._decorate_record(record, document),
                    "score": 1.0,
                    "match_type": "exact_article",
                }
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
        return fused, per_document

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

    @staticmethod
    def _decorate(results: list[dict], document: _DocumentRetriever) -> list[dict]:
        return [
            ScopedSnapshotRetriever._decorate_record(item, document)
            for item in results
        ]

    @staticmethod
    def _decorate_record(record: dict, document: _DocumentRetriever) -> dict:
        return {
            **record,
            "standard_code": document.standard_code,
            "spec_title": document.title,
            "pdf_page_start": record.get("page_start"),
            "pdf_page_end": record.get("page_end"),
        }
