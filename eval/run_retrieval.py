import argparse
import time
from pathlib import Path

from eval.metrics import compute_grouped_metrics, compute_retrieval_metrics
from eval.report import write_json_report, write_markdown_report
from eval.schema import load_eval_dataset, matched_gold_indices
from src.bm25_retriever import BM25Retriever
from src.embedder import Embedder
from src.index_manager import IndexManager
from src.retrieval_fusion import reciprocal_rank_fusion
from src.reranker import Reranker
from src.retriever import Retriever


def evaluate_retrieval(
    *,
    dataset_path,
    pdf_path,
    index_dir=".rag_index",
    mode="dense",
    top_k=10,
    rerank_top_n=10,
    embedder=None,
    reranker=None,
) -> dict:
    examples = load_eval_dataset(dataset_path)
    embedder = embedder or Embedder()
    managed_index = IndexManager(index_dir).build_or_load(pdf_path, embedder=embedder)
    retriever = Retriever(managed_index.vector_store, embedder) if mode != "bm25" else None
    bm25 = BM25Retriever(managed_index.vector_store.chunk_records) if mode in {"bm25", "rrf", "hybrid_rerank"} else None
    reranker = reranker or (Reranker() if mode in {"dense_rerank", "hybrid_rerank"} else None)

    cases = []
    for example in examples:
        candidate_pool_size = 10 if mode == "hybrid_rerank" else max(top_k, 10)
        dense_results = retriever.retrieve(example.question, top_k=candidate_pool_size) if retriever is not None else None
        bm25_results = bm25.retrieve(example.question, top_k=candidate_pool_size) if bm25 is not None else None
        fused_candidates = None
        rerank_latency_ms = None
        gold_ranks_before = []
        gold_ranks_after = []
        if mode == "dense":
            final_results = dense_results
        elif mode == "dense_rerank":
            final_results = reranker.rerank(
                example.question,
                dense_results,
                top_n=max(rerank_top_n, 10),
            )
        elif mode == "bm25":
            final_results = bm25_results
        elif mode == "rrf":
            final_results = reciprocal_rank_fusion(dense_results, bm25_results, top_k=10)
        elif mode == "hybrid_rerank":
            fused_candidates = reciprocal_rank_fusion(dense_results, bm25_results, top_k=None)
            for rank, result in enumerate(fused_candidates, start=1):
                for gold_index in matched_gold_indices(result, example.gold_evidence):
                    gold_ranks_before.append({"gold_index": gold_index, "rank": rank})
            started = time.perf_counter()
            final_results = reranker.rerank(example.question, fused_candidates, top_n=10)
            rerank_latency_ms = (time.perf_counter() - started) * 1000
            for rank, result in enumerate(final_results, start=1):
                for gold_index in matched_gold_indices(result, example.gold_evidence):
                    gold_ranks_after.append({"gold_index": gold_index, "rank": rank})
        else:
            raise ValueError("mode must be 'dense', 'dense_rerank', 'bm25', 'rrf', or 'hybrid_rerank'")

        retrieved = []
        hits = []
        gold_hit_ids_by_rank = []
        for rank, result in enumerate(final_results[:10], start=1):
            matched_ids = matched_gold_indices(result, example.gold_evidence)
            hit = bool(matched_ids)
            hits.append(hit)
            gold_hit_ids_by_rank.append(matched_ids)
            retrieved.append(_serialize_retrieved(rank, result, hit, matched_ids))

        cases.append({
            "id": example.id,
            "question": example.question,
            "question_type": example.question_type,
            "answerable": example.answerable,
            "gold_answer": example.gold_answer,
            "gold_evidence": [item.__dict__ for item in example.gold_evidence],
            "gold_count": len(example.gold_evidence),
            "metric_eligible": example.answerable or bool(example.gold_evidence),
            "hits": hits,
            "gold_hit_ids_by_rank": gold_hit_ids_by_rank,
            "retrieved": retrieved,
        })
        if mode == "hybrid_rerank":
            cases[-1].update({
                "fused_candidate_count": len(fused_candidates),
                "rerank_latency_ms": rerank_latency_ms,
                "gold_ranks_before_rerank": gold_ranks_before,
                "gold_ranks_after_rerank": gold_ranks_after,
            })

    return {
        "dataset_path": str(dataset_path),
        "pdf_path": str(pdf_path),
        "index_dir": str(index_dir),
        "mode": mode,
        "top_k": top_k,
        "candidate_pool_size": max(top_k, 10),
        "rerank_top_n": max(rerank_top_n, 10) if mode in {"dense_rerank", "hybrid_rerank"} else None,
        "overall": compute_retrieval_metrics(cases),
        "by_question_type": compute_grouped_metrics(cases),
        "cases": cases,
    }


def _serialize_retrieved(rank: int, result: dict, hit: bool, matched_gold_indices_: list[int]) -> dict:
    return {
        "rank": rank,
        "hit": hit,
        "matched_gold_indices": matched_gold_indices_,
        "text": result.get("text"),
        "source": result.get("source"),
        "page_start": result.get("page_start"),
        "page_end": result.get("page_end"),
        "chapter_id": result.get("chapter_id"),
        "chapter_title": result.get("chapter_title"),
        "article_id": result.get("article_id"),
        "table_id": result.get("table_id"),
        "table_title": result.get("table_title"),
        "content_type": result.get("content_type", "text"),
        "chunk_id": result.get("chunk_id"),
        "score": result.get("score"),
        "rrf_score": result.get("rrf_score"),
        "rerank_score": result.get("rerank_score"),
        "display_ref": result.get("display_ref"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run retrieval evaluation.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--index-dir", default=".rag_index")
    parser.add_argument("--mode", choices=["dense", "dense_rerank", "bm25", "rrf", "hybrid_rerank"], default="dense")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--rerank-top-n", type=int, default=10)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    args = parser.parse_args()

    report = evaluate_retrieval(
        dataset_path=args.dataset,
        pdf_path=args.pdf,
        index_dir=args.index_dir,
        mode=args.mode,
        top_k=args.top_k,
        rerank_top_n=args.rerank_top_n,
    )
    write_json_report(report, args.json_out)
    write_markdown_report(report, args.md_out)
    print(f"Wrote {Path(args.json_out)} and {Path(args.md_out)}")


if __name__ == "__main__":
    main()
