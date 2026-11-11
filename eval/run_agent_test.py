import argparse
import json
import logging
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from eval.schema import load_eval_dataset, matched_gold_indices
from eval.dataset_manifest import validate_manifest, file_sha256
from eval.metrics import compute_retrieval_metrics
from eval.provenance import capture_provenance
from eval.review import review_template
from src.application import build_agent_workflow
from src.config import AppConfig



class RequestMetricsCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        if getattr(record, "event", None) == "request_completed":
            self.records.append(dict(record.fields))


def run_observed(workflow, question):
    logger = logging.getLogger("rag.request")
    handler = RequestMetricsCapture()
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    started = time.monotonic()
    try:
        response = workflow.run(question)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
    record = next((r for r in handler.records if r.get("request_id") == response.request_id), {})
    return response, {
        "wall_time_ms": (time.monotonic() - started) * 1000,
        "stage_timings_ms": record.get("stage_timings_ms"),
        "token_usage": record.get("token_usage"),
        "estimated_cost": record.get("estimated_cost"),
        "model_calls": record.get("model_calls"),
        "model_retries": record.get("model_retries"),
        "usage_note": "null means unobserved; zero tokens may also mean provider omitted usage; costs are estimates",
        "deployment_baseline": False,
    }


class ObservedReranker:
    def __init__(self, reranker):
        self.reranker = reranker
        self.calls = []
        self.supports_score_cache = bool(
            getattr(reranker, "supports_score_cache", False)
            and callable(getattr(reranker, "score_candidates", None))
            and callable(getattr(reranker, "select_top", None))
        )
        self._scoring_query = None

    def rerank(self, query, results, top_n=3):
        top10 = self.reranker.rerank(query, results, top_n=max(10, top_n))
        self.calls.append({"query": query, "candidate_count": len(results), "top10": top10})
        return top10[:top_n]

    def score_candidates(self, query, results):
        self._scoring_query = query
        return self.reranker.score_candidates(query, results)

    def select_top(self, scored_results, top_n=3):
        top10 = self.reranker.select_top(scored_results, top_n=max(10, top_n))
        self.calls.append(
            {"query": self._scoring_query, "candidate_count": len(scored_results), "top10": top10}
        )
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
    if not examples:
        raise ValueError("dataset must not be empty")
    ids = [example.id for example in examples]
    if len(ids) != len(set(ids)):
        raise ValueError("dataset IDs must be unique")
    for example in examples:
        if example.answerable and not example.gold_evidence:
            raise ValueError(f"{example.id}: answerable case requires gold evidence")
        if example.conversation_history:
            raise ValueError(f"{example.id}: current Agent does not support conversation history")


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def evaluate(dataset_path, pdf_path, index_dir, *, manifest_path=None, config=None, workflow=None):
    examples = load_eval_dataset(dataset_path)
    if manifest_path is None:
        raise ValueError("manifest_path is required for every evaluation")
    manifest = None
    if manifest_path:
        manifest, _ = validate_manifest(manifest_path)
        if manifest.get("data_format", "agent") != "agent" or file_sha256(dataset_path) != manifest["sha256"]:
            raise ValueError("manifest does not describe supplied dataset")
    if manifest and manifest["role"] == "independent" and manifest["status"] != "frozen":
        raise ValueError("independent evaluation requires frozen criteria and human-approved annotations")
    _validate_dataset(examples)
    config = config or AppConfig.from_sources(pdf_path=str(pdf_path), index_dir=str(index_dir))
    if str(config.pdf_path) != str(pdf_path) or str(config.index_dir) != str(index_dir):
        raise ValueError("evaluation paths must match application configuration")
    root = Path(__file__).resolve().parent.parent
    provenance = capture_provenance(config, root=root, dataset_path=dataset_path, pdf_path=pdf_path)
    provenance["dataset_manifest"] = manifest
    # Capture configuration before any model calls; then observe the real application.
    injected = workflow is not None
    if config.evidence_top_n > 10:
        raise ValueError("evaluation evidence_top_n must be <=10 for fixed Recall@10 observation")
    workflow = workflow or build_agent_workflow(config)
    if not injected:
        from types import SimpleNamespace
        from src.index_manager import IndexManager
        identity = SimpleNamespace(model_name=config.embedding_model, model_revision=config.embedding_revision)
        index_manifest = IndexManager(config.index_dir).check(config.pdf_path, embedder=identity)
        if index_manifest.version_id != workflow.index_version_id:
            raise ValueError("index version changed during evaluation initialization")
        provenance["index_manifest"] = asdict(index_manifest)
    provenance["index_version_id"] = workflow.index_version_id
    provenance["runtime_workflow"] = {
        name: getattr(workflow, name, None) for name in (
            "retrieval_top_k", "evidence_top_n", "max_model_calls", "total_timeout_seconds", "max_retries")
    }
    provenance["retrieval_constants"] = {"rrf_k": 60, "bounded_retrieval_retries": 1}
    observed_reranker = ObservedReranker(workflow.reranker)
    workflow.reranker = observed_reranker

    try:
        cases = []
        for example in examples:
            observed_reranker.calls.clear()
            response, measurements = run_observed(workflow, example.question)
            grades = [step for step in response.state.trace if step["step"] == "grade"]
            first_top10 = observed_reranker.calls[0]["top10"] if observed_reranker.calls else []
            final_top10 = observed_reranker.calls[-1]["top10"] if observed_reranker.calls else []
            final_top_n = [item.to_dict() for item in response.state.evidences]
            cases.append({
                "id": example.id,
                "measurements": measurements,
                "initial_retrieval_metric_case": {
                    "hits": [bool(matched_gold_indices(item, example.gold_evidence)) for item in first_top10],
                    "gold_hit_ids_by_rank": [matched_gold_indices(item, example.gold_evidence) for item in first_top10],
                    "gold_count": len(example.gold_evidence),
                    "metric_eligible": example.answerable,
                },
                "category": example.question_type,
                "question": example.question,
                "expected_answerability": example.answerable,
                "gold_answer": example.gold_answer,
                "required_requirements": example.required_requirements,
                "key_answer_points": example.key_answer_points,
                "numeric_expectations": [asdict(x) for x in example.numeric_expectations],
                "request_id": response.request_id,
                "error_code": response.error_code,
                "human_review": {"status": "pending", "reviewer": None, "reviewed_at": None,
                    "evidence_support": None, "completeness": None, "numeric_conditions": None,
                    "unsupported_facts": None, "notes": ""},
                "gold_evidence": [asdict(item) for item in example.gold_evidence],
                "final_action": response.state.final_action,
                "retry_count": response.state.retry_count,
                "rewritten_query": response.state.rewritten_query,
                "final_answer_or_refusal": response.answer,
                "first_grade": grades[0] if grades else None,
                "second_grade": grades[1] if len(grades) > 1 else None,
                "trace": response.state.trace,
                "initial_candidate_count": observed_reranker.calls[0]["candidate_count"] if observed_reranker.calls else 0,
                "retry_candidate_count": observed_reranker.calls[1]["candidate_count"] if len(observed_reranker.calls) > 1 else None,
                "initial_top_n_coverage": _coverage(first_top10[:config.evidence_top_n], example.gold_evidence),
                "initial_top10_coverage": _coverage(first_top10, example.gold_evidence),
                "final_top_n_coverage": _coverage(final_top_n, example.gold_evidence),
                "final_top10_coverage": _coverage(final_top10, example.gold_evidence),
                "final_evidence_refs": [_serialize_result(item) for item in final_top_n],
                "citation_validation": asdict(response.state.citation_validation) if response.state.citation_validation else None,
            })
    finally:
        workflow.reranker = observed_reranker.reranker

    answerable = [case for case in cases if case["expected_answerability"]]
    unanswerable = [case for case in cases if not case["expected_answerability"]]
    retried = [case for case in cases if case["retry_count"] == 1]
    first_sufficient = sum(bool(case["first_grade"] and case["first_grade"]["decision"] == "sufficient") for case in cases)
    retry_sufficient = sum(bool(case["second_grade"] and case["second_grade"]["decision"] == "sufficient") for case in cases)
    report = {
        "report_schema_version": 2,
        "provenance": provenance,
        "evidence_top_n": config.evidence_top_n,
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
        "category_counts": {
            category: {
                "count": len(group),
                "answer": sum(x["final_action"] == "answer" for x in group),
                "refuse": sum(x["final_action"] == "refuse" for x in group),
                "error": sum(x["final_action"] == "error" for x in group),
            }
            for category in sorted({x["category"] for x in cases})
            for group in [[x for x in cases if x["category"] == category]]
        },
        "initial_rank_metrics": compute_retrieval_metrics(case["initial_retrieval_metric_case"] for case in cases),
        "retrieval_evidence": {
            "initial_hit_rate_at_n": _ratio(sum(case["initial_top_n_coverage"]["hit"] for case in answerable), len(answerable)),
            "initial_recall_at_n": _ratio(sum(len(case["initial_top_n_coverage"]["matched_gold_indices"]) for case in answerable), sum(case["initial_top_n_coverage"]["gold_count"] for case in answerable)),
            "initial_recall_at_10": _ratio(sum(len(case["initial_top10_coverage"]["matched_gold_indices"]) for case in answerable), sum(case["initial_top10_coverage"]["gold_count"] for case in answerable)),
            "final_hit_rate_at_n": _ratio(sum(case["final_top_n_coverage"]["hit"] for case in answerable), len(answerable)),
            "final_recall_at_n": _ratio(sum(len(case["final_top_n_coverage"]["matched_gold_indices"]) for case in answerable), sum(case["final_top_n_coverage"]["gold_count"] for case in answerable)),
            "multi_evidence_complete_at_n": sum(case["final_top_n_coverage"]["complete"] for case in answerable if len(case["gold_evidence"]) > 1),
            "multi_evidence_count": sum(len(case["gold_evidence"]) > 1 for case in answerable),
        },
        "agent_decision": {
            "first_sufficient": first_sufficient,
            "first_insufficient_retry": len(retried),
            "retry_sufficient": retry_sufficient,
            "retry_still_insufficient": sum(bool(case["second_grade"] and case["second_grade"]["decision"] == "insufficient") for case in cases),
            "final_answer": sum(case["final_action"] == "answer" for case in cases),
            "final_error": sum(case["final_action"] == "error" for case in cases),
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
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "human_review_status": "pending",
        "release_decision": "blocked_pending_human_review_and_real_deployment_baselines",
        "cases": cases,
    }
    report["agent_decision"]["false_accept_rate"] = _ratio(report["agent_decision"]["false_accept"], len(unanswerable))
    report["agent_decision"]["false_refusal_rate"] = _ratio(report["agent_decision"]["false_refusal"], len(answerable))
    report["input_integrity_at_finish"] = {
        "dataset_unchanged": file_sha256(dataset_path) == provenance["dataset_sha256"],
        "pdf_unchanged": file_sha256(pdf_path) == provenance["pdf_sha256"],
    }
    return report


def write_report(report, json_out, md_out):
    if Path(json_out).exists() or Path(md_out).exists():
        raise FileExistsError("Use new report paths; existing reports must remain unchanged")
    Path(json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(md_out).parent.mkdir(parents=True, exist_ok=True)
    with open(json_out, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    n = report["evidence_top_n"]
    a = report["agent_decision"]
    r = report["retrieval_evidence"]
    lines = [
        "# Agent Evaluation", "",
        f"- Cases: {report['dataset']['count']} ({report['dataset']['answerable']} answerable, {report['dataset']['unanswerable']} unanswerable)",
        f"- Model: `{report['model']}`", "",
        f"- Release: {report['release_decision']}",
        f"- Provenance and category denominators: `{Path(json_out).name}`", "",
        "## Retrieval / Evidence", "",
        f"- Initial HitRate@{n}: {r['initial_hit_rate_at_n']}",
        f"- Initial Recall@{n}: {r['initial_recall_at_n']}",
        f"- Initial Recall@10: {r['initial_recall_at_10']}",
        f"- Final HitRate@{n}: {r['final_hit_rate_at_n']}",
        f"- Final Recall@{n}: {r['final_recall_at_n']}",
        f"- Multi-evidence complete@{n}: {r['multi_evidence_complete_at_n']}/{r['multi_evidence_count']}", "",
        "## Agent Decision", "",
        f"- First sufficient: {a['first_sufficient']}",
        f"- Retried: {a['first_insufficient_retry']}",
        f"- Retry sufficient: {a['retry_sufficient']}",
        f"- Retry still insufficient: {a['retry_still_insufficient']}",
        f"- Final answer/refuse/error: {a['final_answer']}/{a['final_refuse']}/{a['final_error']}",
        f"- Correct unanswerable refusal: {a['correct_unanswerable_refusal']}",
        f"- False accept/refusal: {a['false_accept']}/{a['false_refusal']}", "",
        "## Per Case", "",
        f"| ID | Expected | First grade | Retry | Second grade | Action | Gold Top{n} | Citation |",
        "|---|---:|---|---:|---|---|---|---|",
    ]
    for case in report["cases"]:
        second = case["second_grade"]["decision"] if case["second_grade"] else "-"
        citation = case["citation_validation"]["valid"] if case["citation_validation"] else "-"
        complete = case["final_top_n_coverage"]["complete"]
        lines.append(f"| {case['id']} | {case['expected_answerability']} | {case['first_grade']['decision'] if case['first_grade'] else '-'} | {case['retry_count']} | {second} | {case['final_action']} | {complete} | {citation} |")
    with open(md_out, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Run a manifest-validated Agent evaluation (explicit model/API calls).")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--index-dir", default=".rag_index")
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    parser.add_argument("--manifest", required=True, help="Dataset identity, distribution and freeze manifest")
    parser.add_argument("--review-out", required=True)
    args = parser.parse_args()
    if any(Path(path).exists() for path in (args.json_out, args.md_out, args.review_out)):
        parser.error("report paths already exist; choose new paths before invoking models")
    report = evaluate(args.dataset, args.pdf, args.index_dir, manifest_path=args.manifest)
    write_report(report, args.json_out, args.md_out)
    Path(args.review_out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.review_out, "x", encoding="utf-8") as stream:
        json.dump(review_template(report), stream, ensure_ascii=False, indent=2)
    print(f"Wrote {args.json_out} and {args.md_out}")


if __name__ == "__main__":
    main()
