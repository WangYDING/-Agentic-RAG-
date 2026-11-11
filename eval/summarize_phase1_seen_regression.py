from __future__ import annotations

import json
import re
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "eval/datasets/phase1_cross_spec_independent_v1.jsonl"
RESULT = ROOT / "eval/reports/phase1_seen_regression_evidence_selection_final_20261106.json"
OUTPUT = ROOT / "eval/reports/phase1_seen_regression_evidence_selection_final_20261106.summary.json"


def percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * fraction + 0.999999) - 1)]


def main() -> None:
    dataset = {row["id"]: row for row in map(json.loads, DATASET.read_text(encoding="utf-8").splitlines())}
    run = json.loads(RESULT.read_text(encoding="utf-8"))
    cases = []
    for item in run["questions"]:
        gold = dataset[item["id"]]
        candidates = [candidate for call in item["retrieval_calls"] for candidate in call["candidates"]]
        required = {(bid, article) for bid, articles in gold["expected_articles_by_spec"].items() for article in articles}
        candidate_keys = {(f"{x.get('spec_id')}@{x.get('edition_id')}", str(x.get("article_id"))) for x in candidates}
        final_keys = {(f"{x.get('spec_id')}@{x.get('edition_id')}", str(x.get("article_id"))) for x in item["final_evidence"]}
        allowed = set(item["bound_scope"])
        citations = {int(value) for value in re.findall(r"\[E(\d+)\]", item["answer"] or "")}
        cases.append({
            "id": item["id"], "expected": gold["expected_behavior"], "actual": item["result_type"],
            "candidate_complete": required <= candidate_keys, "final_complete": required <= final_keys,
            "candidate_missing": sorted(required - candidate_keys), "final_missing": sorted(required - final_keys),
            "scope_violations": sorted({bid for bid, _ in candidate_keys | final_keys if bid not in allowed}),
            "citation_legal": not citations or max(citations) <= len(item["final_evidence"]),
            "total_ms": item["request_metrics"]["total_ms"], "tokens": item["request_metrics"]["token_usage"]["total"],
            "model_calls": item["request_metrics"]["model_calls"],
        })
    cross = [case for case in cases if len(dataset[case["id"]]["requested_scope"].get("spec_ids", [])) > 1]
    summary = {
        "outcomes": {kind: sum(case["actual"] == kind for case in cases) for kind in ("answer", "refuse", "error")},
        "candidate_complete_answerable": sum(case["candidate_complete"] for case in cases if dataset[case["id"]]["answerable"]),
        "final_complete_answerable": sum(case["final_complete"] for case in cases if dataset[case["id"]]["answerable"]),
        "scope_violations": sum(bool(case["scope_violations"]) for case in cases),
        "citation_errors": sum(not case["citation_legal"] for case in cases if case["actual"] == "answer"),
        "cross_spec_p95_ms": percentile([case["total_ms"] for case in cross], .95),
        "cross_spec_mean_tokens": statistics.mean(case["tokens"] for case in cross),
        "cross_spec_p95_tokens": percentile([case["tokens"] for case in cross], .95),
        "total_tokens": sum(case["tokens"] for case in cases), "model_calls": sum(case["model_calls"] for case in cases),
    }
    payload = {"summary": summary, "cases": cases}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
