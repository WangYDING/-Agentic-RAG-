from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.embedder import Embedder
from src.knowledge_base import KnowledgeBaseManager
from src.query_scope import QueryScope, QueryScopeClarificationRequired
from src.snapshot_retriever import SnapshotRetriever
from src.spec_catalog import SpecCatalog


def run_retrieval_check(
    *,
    dataset_path: Path,
    catalog_path: Path,
    knowledge_base_root: Path,
    embedding_model: str,
    top_k: int,
) -> dict:
    snapshot = KnowledgeBaseManager(knowledge_base_root).load_active()
    catalog = SpecCatalog.load(
        catalog_path, repository_root=catalog_path.resolve().parent.parent
    )
    facade = SnapshotRetriever(snapshot, catalog, Embedder(embedding_model))
    rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    results = []
    for row in rows:
        scope = QueryScope.from_request_payload(row["requested_scope"])
        started = time.perf_counter()
        try:
            scoped = facade.for_scope(scope)
        except QueryScopeClarificationRequired as exc:
            results.append(
                {
                    "id": row["id"],
                    "behavior": "clarify_scope",
                    "message": str(exc),
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            )
            continue
        candidates = scoped.retrieve(row["question"], top_k=top_k)
        actual_articles: dict[str, list[str]] = {}
        out_of_scope = []
        for item in candidates:
            business_id = f"{item.get('spec_id')}@{item.get('edition_id')}"
            if business_id not in scoped.scope.business_ids:
                out_of_scope.append(business_id)
            article = item.get("article_id")
            if article:
                actual_articles.setdefault(business_id, []).append(article)
        expected = row["expected_articles_by_spec"]
        hits = {
            business_id: sorted(set(articles) & set(actual_articles.get(business_id, [])))
            for business_id, articles in expected.items()
        }
        results.append(
            {
                "id": row["id"],
                "behavior": "retrieve",
                "scope": list(scoped.scope.business_ids),
                "candidate_count": len(candidates),
                "per_document_candidates": scoped.calls[-1]["documents"],
                "expected_article_hits": hits,
                "all_expected_articles_recalled": all(
                    set(articles).issubset(actual_articles.get(business_id, []))
                    for business_id, articles in expected.items()
                ),
                "out_of_scope": out_of_scope,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        )
    retrievals = [item for item in results if item["behavior"] == "retrieve"]
    return {
        "snapshot_id": snapshot.snapshot_id,
        "embedding_model": embedding_model,
        "top_k_per_document_per_route": top_k,
        "questions": results,
        "summary": {
            "question_count": len(results),
            "clarification_count": len(results) - len(retrievals),
            "retrieval_count": len(retrievals),
            "out_of_scope_count": sum(len(item["out_of_scope"]) for item in retrievals),
            "all_expected_articles_recalled_count": sum(
                bool(item["all_expected_articles_recalled"]) for item in retrievals
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 1 scope/retrieval checks")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--knowledge-base-root", type=Path, required=True)
    parser.add_argument("--embedding-model", default="BAAI/bge-small-zh-v1.5")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run_retrieval_check(
        dataset_path=args.dataset,
        catalog_path=args.catalog,
        knowledge_base_root=args.knowledge_base_root,
        embedding_model=args.embedding_model,
        top_k=args.top_k,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
