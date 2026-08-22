import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from eval.bm25 import BM25Retriever
from eval.rrf import reciprocal_rank_fusion
from eval.schema import load_eval_dataset, matched_gold_indices
from src.embedder import Embedder
from src.index_manager import IndexManager
from src.reranker import Reranker
from src.retriever import Retriever


def summarize(values: list[float]) -> dict:
    array = np.asarray(values, dtype=float)
    return {
        "count": len(values),
        "min": float(np.min(array)),
        "p25": float(np.percentile(array, 25)),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p75": float(np.percentile(array, 75)),
        "max": float(np.max(array)),
    }


THRESHOLDS = (0.90, 0.95, 0.97, 0.98, 0.99, 0.995)


def _threshold_metrics(labels: list[int], scores: list[float], threshold: float) -> dict:
    predicted = [int(score >= threshold) for score in scores]
    tp = sum(actual == 1 and guess == 1 for actual, guess in zip(labels, predicted))
    fp = sum(actual == 0 and guess == 1 for actual, guess in zip(labels, predicted))
    tn = sum(actual == 0 and guess == 0 for actual, guess in zip(labels, predicted))
    fn = sum(actual == 1 and guess == 0 for actual, guess in zip(labels, predicted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "threshold": threshold,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "false_accept_rate": fp / (fp + tn) if fp + tn else 0.0,
        "false_refusal_rate": fn / (fn + tp) if fn + tp else 0.0,
    }


def run_diagnostic(*, dataset_path, pdf_path, index_dir=".rag_index", negative_dataset_path=None) -> dict:
    positives = [
        example for example in load_eval_dataset(dataset_path)
        if example.answerable and example.question_type != "context_dependent"
    ]
    if negative_dataset_path:
        negatives = load_eval_dataset(negative_dataset_path)
    else:
        negatives = [
            example for example in load_eval_dataset(dataset_path)
            if not example.answerable and example.question_type != "context_dependent"
        ]
    examples = positives + negatives
    embedder = Embedder()
    managed = IndexManager(index_dir).build_or_load(pdf_path, embedder=embedder)
    dense = Retriever(managed.vector_store, embedder)
    bm25 = BM25Retriever(managed.vector_store.chunk_records)
    reranker = Reranker()

    cases = []
    for example in examples:
        dense_results = dense.retrieve(example.question, top_k=10)
        bm25_results = bm25.retrieve(example.question, top_k=10)
        candidates = reciprocal_rank_fusion(dense_results, bm25_results, top_k=None)
        results = reranker.rerank(example.question, candidates, top_n=10)
        scores = [float(item["rerank_score"]) for item in results[:3]]
        top1 = results[0]
        cases.append({
            "id": example.id,
            "question": example.question,
            "label": "answerable" if example.answerable else "unanswerable",
            "hard_negative_type": example.hard_negative_type,
            "top1_rerank_score": scores[0],
            "top2_rerank_score": scores[1],
            "top3_rerank_score": scores[2],
            "top1_top2_gap": scores[0] - scores[1],
            "top1_gold_hit": bool(matched_gold_indices(top1, example.gold_evidence)) if example.answerable else None,
            "top1_evidence": top1["text"],
            "top1_provenance": {
                "source": top1.get("source"),
                "page_start": top1.get("page_start"),
                "page_end": top1.get("page_end"),
                "article_id": top1.get("article_id"),
                "table_id": top1.get("table_id"),
                "content_type": top1.get("content_type", "text"),
                "chunk_id": top1.get("chunk_id"),
                "display_ref": top1.get("display_ref"),
            },
        })

    summary = {}
    for label in ("answerable", "unanswerable"):
        selected = [case for case in cases if case["label"] == label]
        summary[label] = {
            field: summarize([case[field] for case in selected])
            for field in ("top1_rerank_score", "top2_rerank_score", "top3_rerank_score", "top1_top2_gap")
        }
    unanswerable_by_type = {}
    for negative_type in sorted({case["hard_negative_type"] for case in cases if case["hard_negative_type"]}):
        selected = [case for case in cases if case["hard_negative_type"] == negative_type]
        unanswerable_by_type[negative_type] = {
            field: summarize([case[field] for case in selected])
            for field in ("top1_rerank_score", "top2_rerank_score", "top3_rerank_score", "top1_top2_gap")
        }
    labels = [int(case["label"] == "answerable") for case in cases]
    top1_scores = [case["top1_rerank_score"] for case in cases]
    return {
        "dataset_path": str(dataset_path),
        "negative_dataset_path": str(negative_dataset_path) if negative_dataset_path else None,
        "pipeline": "Dense10 + BM25-10 union + equal RRF metadata + BAAI/bge-reranker-base",
        "excluded_question_types": ["context_dependent"],
        "summary": summary,
        "unanswerable_by_hard_negative_type": unanswerable_by_type,
        "auroc": float(roc_auc_score(labels, top1_scores)),
        "auprc": float(average_precision_score(labels, top1_scores)),
        "threshold_diagnostics": [_threshold_metrics(labels, top1_scores, threshold) for threshold in THRESHOLDS],
        "cases": cases,
    }


def write_markdown(report: dict, path) -> None:
    lines = ["# Answerable vs Unanswerable Retrieval Score Diagnostic", ""]
    for label, fields in report["summary"].items():
        lines.extend([f"## {label.title()}", "", "| field | min | p25 | mean | median | p75 | max |", "|---|---:|---:|---:|---:|---:|---:|"])
        for field, stats in fields.items():
            lines.append(f"| {field} | {stats['min']:.6f} | {stats['p25']:.6f} | {stats['mean']:.6f} | {stats['median']:.6f} | {stats['p75']:.6f} | {stats['max']:.6f} |")
        lines.append("")
    lines.extend([
        "## Discrimination", "",
        f"- AUROC: {report['auroc']:.6f}",
        f"- AUPRC: {report['auprc']:.6f}", "",
        "| threshold | precision | recall | F1 | false accept rate | false refusal rate |",
        "|---:|---:|---:|---:|---:|---:|",
    ])
    for item in report["threshold_diagnostics"]:
        lines.append(f"| {item['threshold']:.3f} | {item['precision']:.6f} | {item['recall']:.6f} | {item['f1']:.6f} | {item['false_accept_rate']:.6f} | {item['false_refusal_rate']:.6f} |")
    lines.extend(["", "## Unanswerable By Hard-Negative Type", ""])
    for negative_type, fields in report["unanswerable_by_hard_negative_type"].items():
        lines.extend([f"### {negative_type}", "", "| field | min | p25 | mean | median | p75 | max |", "|---|---:|---:|---:|---:|---:|---:|"])
        for field, stats in fields.items():
            lines.append(f"| {field} | {stats['min']:.6f} | {stats['p25']:.6f} | {stats['mean']:.6f} | {stats['median']:.6f} | {stats['p75']:.6f} | {stats['max']:.6f} |")
        lines.append("")
    lines.extend(["## Unanswerable Cases", ""])
    for case in report["cases"]:
        if case["label"] == "unanswerable":
            lines.extend([
                f"### {case['id']}", "",
                f"- Question: {case['question']}",
                f"- Top scores: {case['top1_rerank_score']:.6f} / {case['top2_rerank_score']:.6f} / {case['top3_rerank_score']:.6f}",
                f"- Gap: {case['top1_top2_gap']:.6f}",
                f"- Hard-negative type: {case['hard_negative_type']}",
                f"- Provenance: `{json.dumps(case['top1_provenance'], ensure_ascii=False)}`", "",
                case["top1_evidence"], "",
            ])
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare answerable and unanswerable retrieval scores.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--negative-dataset")
    parser.add_argument("--index-dir", default=".rag_index")
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    args = parser.parse_args()
    report = run_diagnostic(dataset_path=args.dataset, negative_dataset_path=args.negative_dataset, pdf_path=args.pdf, index_dir=args.index_dir)
    Path(args.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, args.md_out)
    print(f"Wrote {args.json_out} and {args.md_out}")


if __name__ == "__main__":
    main()
