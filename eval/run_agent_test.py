import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from eval.schema import load_eval_dataset, matched_gold_indices
from src.agent_workflow import AgentWorkflow
from src.bm25_retriever import BM25Retriever
from src.embedder import Embedder
from src.evidence_sufficiency import EvidenceSufficiencyGrader
from src.generator import Generator
from src.index_manager import IndexManager
from src.hybrid_retriever import HybridRetriever
from src.query_rewriter import QueryRewriter
from src.reranker import Reranker
from src.retriever import Retriever


class ObservedReranker:
    def __init__(self, reranker):
        self.reranker = reranker
        self.calls = []

    def rerank(self, query, results, top_n=3):
        top10 = self.reranker.rerank(query, results, top_n=10)
        self.calls.append({"query": query, "candidate_count": len(results), "top10": top10})
        return top10[:top_n]


def _serialize_result(result):
    keys = (
        "text", "source", "page_start", "page_end", "article_id", "table_id",
        "content_type", "chunk_id", "score", "rrf_score", "rerank_score", "display_ref",
    )
    return {key: result.get(key) for key in keys}


def _coverage(results, gold_evidence):
    matched = set()
    for result in results:
        matched.update(matched_gold_indices(result, gold_evidence))
    return {
        "matched_gold_indices": sorted(matched),
        "gold_count": len(gold_evidence),
        "hit": bool(matched),
        "complete": len(matched) == len(gold_evidence) if gold_evidence else None,
    }


def _validate_dataset(examples):
    if len(examples) != 20:
        raise ValueError(f"test_v1 must contain 20 cases, got {len(examples)}")
    ids = [example.id for example in examples]
    if len(ids) != len(set(ids)):
        raise ValueError("test_v1 IDs must be unique")
    expected = {
        "ordinary_single_turn_answerable": 6,
        "hard_numeric": 2,
        "hard_table": 1,
        "hard_table_numeric": 1,
        "multi_evidence": 3,
        "agent_challenge": 3,
        "hard_negative_unanswerable": 4,
    }
    actual = Counter(example.question_type for example in examples)
    if actual != Counter(expected):
        raise ValueError(f"Unexpected type distribution: {dict(actual)}")
    for example in examples:
        if example.answerable and not example.gold_evidence:
            raise ValueError(f"{example.id}: answerable case requires gold evidence")
        if not example.answerable and example.gold_evidence:
            raise ValueError(f"{example.id}: unanswerable case must not have gold evidence")


def evaluate(dataset_path, pdf_path, index_dir):
    examples = load_eval_dataset(dataset_path)
    _validate_dataset(examples)
    embedder = Embedder()
    managed = IndexManager(index_dir).build_or_load(pdf_path, embedder=embedder)
    hybrid = HybridRetriever(
        Retriever(managed.vector_store, embedder),
        BM25Retriever(managed.vector_store.chunk_records),
    )
    observed_reranker = ObservedReranker(Reranker())
    workflow = AgentWorkflow(
        hybrid,
        observed_reranker,
        EvidenceSufficiencyGrader(),
        Generator(),
        QueryRewriter(),
    )

    cases = []
    for example in examples:
        hybrid.calls.clear()
        observed_reranker.calls.clear()
        response = workflow.run(example.question)
        grades = [step for step in response.state.trace if step["step"] == "grade"]
        first_top10 = observed_reranker.calls[0]["top10"]
        final_top10 = observed_reranker.calls[-1]["top10"]
        final_top3 = final_top10[:3]
        cases.append({
            "id": example.id,
            "category": example.question_type,
            "question": example.question,
            "expected_answerability": example.answerable,
            "gold_answer": example.gold_answer,
            "gold_evidence": [asdict(item) for item in example.gold_evidence],
            "final_action": response.state.final_action,
            "retry_count": response.state.retry_count,
            "rewritten_query": response.state.rewritten_query,
            "final_answer_or_refusal": response.answer,
            "first_grade": grades[0],
            "second_grade": grades[1] if len(grades) > 1 else None,
            "trace": response.state.trace,
            "initial_candidate_count": observed_reranker.calls[0]["candidate_count"],
            "retry_candidate_count": observed_reranker.calls[1]["candidate_count"] if len(observed_reranker.calls) > 1 else None,
            "initial_top3_coverage": _coverage(first_top10[:3], example.gold_evidence),
            "initial_top10_coverage": _coverage(first_top10, example.gold_evidence),
            "final_top3_coverage": _coverage(final_top3, example.gold_evidence),
            "final_top10_coverage": _coverage(final_top10, example.gold_evidence),
            "final_evidence_refs": [_serialize_result(item) for item in final_top3],
            "citation_validation": asdict(response.state.citation_validation) if response.state.citation_validation else None,
        })

    answerable = [case for case in cases if case["expected_answerability"]]
    unanswerable = [case for case in cases if not case["expected_answerability"]]
    retried = [case for case in cases if case["retry_count"] == 1]
    first_sufficient = sum(case["first_grade"]["decision"] == "sufficient" for case in cases)
    retry_sufficient = sum(bool(case["second_grade"] and case["second_grade"]["decision"] == "sufficient") for case in cases)
    report = {
        "dataset_path": str(dataset_path),
        "pdf_path": str(pdf_path),
        "index_dir": str(index_dir),
        "model": workflow.grader.model,
        "dataset": {
            "count": len(cases),
            "type_distribution": dict(Counter(case["category"] for case in cases)),
            "answerable": len(answerable),
            "unanswerable": len(unanswerable),
        },
        "retrieval_evidence": {
            "initial_hit_rate_at_3": sum(case["initial_top3_coverage"]["hit"] for case in answerable) / len(answerable),
            "initial_recall_at_3": sum(len(case["initial_top3_coverage"]["matched_gold_indices"]) for case in answerable) / sum(case["initial_top3_coverage"]["gold_count"] for case in answerable),
            "initial_recall_at_10": sum(len(case["initial_top10_coverage"]["matched_gold_indices"]) for case in answerable) / sum(case["initial_top10_coverage"]["gold_count"] for case in answerable),
            "final_hit_rate_at_3": sum(case["final_top3_coverage"]["hit"] for case in answerable) / len(answerable),
            "final_recall_at_3": sum(len(case["final_top3_coverage"]["matched_gold_indices"]) for case in answerable) / sum(case["final_top3_coverage"]["gold_count"] for case in answerable),
            "multi_evidence_complete_at_3": sum(case["final_top3_coverage"]["complete"] for case in answerable if case["category"] == "multi_evidence"),
            "multi_evidence_count": sum(case["category"] == "multi_evidence" for case in answerable),
        },
        "agent_decision": {
            "first_sufficient": first_sufficient,
            "first_insufficient_retry": len(cases) - first_sufficient,
            "retry_sufficient": retry_sufficient,
            "retry_still_insufficient": len(retried) - retry_sufficient,
            "final_answer": sum(case["final_action"] == "answer" for case in cases),
            "final_refuse": sum(case["final_action"] == "refuse" for case in cases),
            "correct_unanswerable_refusal": sum(case["final_action"] == "refuse" for case in unanswerable),
            "false_accept": sum(case["final_action"] == "answer" for case in unanswerable),
            "false_refusal": sum(case["final_action"] == "refuse" for case in answerable),
        },
        "citation_validation": {
            "answered": sum(case["final_action"] == "answer" for case in cases),
            "valid": sum(bool(case["citation_validation"] and case["citation_validation"]["valid"]) for case in cases),
            "invalid_ids": [case["id"] for case in cases if case["citation_validation"] and not case["citation_validation"]["valid"]],
        },
        "cases": cases,
    }
    return report


def write_report(report, json_out, md_out):
    Path(json_out).parent.mkdir(parents=True, exist_ok=True)
    with open(json_out, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    a = report["agent_decision"]
    r = report["retrieval_evidence"]
    lines = [
        "# Final Test v1 Agent Evaluation", "",
        f"- Cases: {report['dataset']['count']} ({report['dataset']['answerable']} answerable, {report['dataset']['unanswerable']} unanswerable)",
        f"- Model: `{report['model']}`", "",
        "## Retrieval / Evidence", "",
        f"- Initial HitRate@3: {r['initial_hit_rate_at_3']:.4f}",
        f"- Initial Recall@3: {r['initial_recall_at_3']:.4f}",
        f"- Initial Recall@10: {r['initial_recall_at_10']:.4f}",
        f"- Final HitRate@3: {r['final_hit_rate_at_3']:.4f}",
        f"- Final Recall@3: {r['final_recall_at_3']:.4f}",
        f"- Multi-evidence complete@3: {r['multi_evidence_complete_at_3']}/{r['multi_evidence_count']}", "",
        "## Agent Decision", "",
        f"- First sufficient: {a['first_sufficient']}",
        f"- Retried: {a['first_insufficient_retry']}",
        f"- Retry sufficient: {a['retry_sufficient']}",
        f"- Retry still insufficient: {a['retry_still_insufficient']}",
        f"- Final answer/refuse: {a['final_answer']}/{a['final_refuse']}",
        f"- Correct unanswerable refusal: {a['correct_unanswerable_refusal']}",
        f"- False accept/refusal: {a['false_accept']}/{a['false_refusal']}", "",
        "## Per Case", "",
        "| ID | Expected | First grade | Retry | Second grade | Action | Gold Top3 | Citation |",
        "|---|---:|---|---:|---|---|---|---|",
    ]
    for case in report["cases"]:
        second = case["second_grade"]["decision"] if case["second_grade"] else "-"
        citation = case["citation_validation"]["valid"] if case["citation_validation"] else "-"
        complete = case["final_top3_coverage"]["complete"]
        lines.append(f"| {case['id']} | {case['expected_answerability']} | {case['first_grade']['decision']} | {case['retry_count']} | {second} | {case['final_action']} | {complete} | {citation} |")
    with open(md_out, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Run the frozen final Agent evaluation once.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--index-dir", default=".rag_index")
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    args = parser.parse_args()
    report = evaluate(args.dataset, args.pdf, args.index_dir)
    write_report(report, args.json_out, args.md_out)
    print(f"Wrote {args.json_out} and {args.md_out}")


if __name__ == "__main__":
    main()
