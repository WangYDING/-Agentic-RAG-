from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.bm25_retriever import BM25Retriever
from src.agent_workflow import AgentWorkflow
from src.embedder import Embedder
from src.knowledge_base import KnowledgeBaseManager
from src.query_scope import QueryScope
from src.query_decomposition import decompose_retrieval_targets, focused_query_variants
from src.reranker import Reranker
from src.retriever import Retriever
from src.retrieval_fusion import reciprocal_rank_fusion
from src.snapshot_retriever import SnapshotRetriever
from src.spec_catalog import SpecCatalog


def _article_rank(results: list[dict], article: str) -> int | None:
    return next(
        (index for index, item in enumerate(results, start=1) if item.get("article_id") == article),
        None,
    )


def _scoped_article_rank(
    results: list[dict], business_id: str, article: str
) -> int | None:
    return next(
        (
            index
            for index, item in enumerate(results, start=1)
            if f"{item.get('spec_id')}@{item.get('edition_id')}" == business_id
            and item.get("article_id") == article
        ),
        None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose Phase 1 Slice 4 retrieval misses")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--slice3-report", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--knowledge-base-root", type=Path, required=True)
    parser.add_argument("--embedding-model", default="BAAI/bge-small-zh-v1.5")
    parser.add_argument("--reranker-model", default="BAAI/bge-reranker-base")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    rows = {
        row["id"]: row
        for row in (
            json.loads(line)
            for line in args.dataset.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    baseline = json.loads(args.slice3_report.read_text(encoding="utf-8"))
    baseline_by_id = {item["id"]: item for item in baseline["questions"]}
    corrected = []
    for question_id, row in rows.items():
        expected = row["expected_articles_by_spec"]
        baseline_item = baseline_by_id[question_id]
        hits = baseline_item.get("expected_article_hits", {})
        corrected.append(
            {
                "id": question_id,
                "all_expected_articles": expected,
                "hit_expected_articles": hits,
                "missing_expected_articles": {
                    business_id: sorted(set(articles) - set(hits.get(business_id, [])))
                    for business_id, articles in expected.items()
                },
            }
        )

    snapshot = KnowledgeBaseManager(args.knowledge_base_root).load_active()
    catalog = SpecCatalog.load(
        args.catalog, repository_root=args.catalog.resolve().parent.parent
    )
    embedder = Embedder(args.embedding_model)
    reranker = Reranker(args.reranker_model)
    facade = SnapshotRetriever(snapshot, catalog, embedder)
    diagnostics = []
    for question_id in ("P1-Q009", "P1-Q011"):
        row = rows[question_id]
        scope = QueryScope.from_request_payload(row["requested_scope"])
        scoped = facade.for_scope(scope)
        fused = scoped.retrieve(row["question"], top_k=args.top_k)
        top3 = reranker.rerank(row["question"], fused, top_n=3)
        proposed = AgentWorkflow._select_scope_target_coverage(
            object.__new__(AgentWorkflow),
            fused,
            focused_query_variants(decompose_retrieval_targets(row["question"])),
            scoped.scope.business_ids,
            top_n=8,
            score_cache={},
            preferred=top3,
        )
        documents = {
            item.manifest.business_id: item
            for item in snapshot.documents
            if item.manifest.business_id in scoped.scope.business_ids
        }
        expected_positions = {}
        for business_id, articles in row["expected_articles_by_spec"].items():
            document = documents[business_id]
            dense = Retriever(document.vector_store, embedder).retrieve(
                row["question"], top_k=args.top_k
            )
            bm25 = BM25Retriever(document.vector_store.chunk_records).retrieve(
                row["question"], top_k=args.top_k
            )
            per_document_fused = reciprocal_rank_fusion(dense, bm25, top_k=None)
            expected_positions[business_id] = {
                article: {
                    "dense_rank": _article_rank(dense, article),
                    "bm25_rank": _article_rank(bm25, article),
                    "per_document_fused_rank": _article_rank(per_document_fused, article),
                    "cross_document_fused_rank": _scoped_article_rank(
                        fused, business_id, article
                    ),
                    "final_top3_rank": _scoped_article_rank(
                        top3, business_id, article
                    ),
                }
                for article in articles
            }
        diagnostics.append(
            {
                "id": question_id,
                "question": row["question"],
                "expected_positions": expected_positions,
                "fused_candidate_count": len(fused),
                "top3": [
                    {
                        "business_id": f"{item.get('spec_id')}@{item.get('edition_id')}",
                        "article_id": item.get("article_id"),
                        "page": item.get("page_start"),
                    }
                    for item in top3
                ],
                "proposed_evidence": [
                    {
                        "business_id": f"{item.get('spec_id')}@{item.get('edition_id')}",
                        "article_id": item.get("article_id"),
                        "page": item.get("page_start"),
                        "focused_best_rank": item.get("focused_best_rank"),
                    }
                    for item in proposed
                ],
            }
        )

    payload = {
        "snapshot_id": snapshot.snapshot_id,
        "top_k_per_document_per_route": args.top_k,
        "corrected_gold_accounting": corrected,
        "failure_diagnostics": diagnostics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(diagnostics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
