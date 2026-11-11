from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "eval/datasets/phase1_cross_spec_independent_v1.jsonl"
RESULT = ROOT / "eval/reports/phase1_cross_spec_independent_v1_20261106.json"


def evidence_key(item: dict) -> tuple[str, str]:
    return f"{item.get('spec_id')}@{item.get('edition_id')}", str(item.get("article_id"))


def main() -> None:
    dataset = {
        row["id"]: row
        for row in (json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines())
    }
    run = json.loads(RESULT.read_text(encoding="utf-8"))
    for result in run["questions"]:
        gold = dataset[result["id"]]
        candidates = [
            item
            for call in result["retrieval_calls"]
            for item in call["candidates"]
        ]
        candidate_keys = {evidence_key(item) for item in candidates}
        final_keys = {evidence_key(item) for item in result["final_evidence"]}
        required = {
            (business_id, article)
            for business_id, articles in gold["expected_articles_by_spec"].items()
            for article in articles
        }
        allowed = set(result["bound_scope"])
        escaped = sorted({key[0] for key in candidate_keys | final_keys if key[0] not in allowed})
        metrics = result["request_metrics"] or {}
        summary = {
            "id": result["id"],
            "expected": gold["expected_behavior"],
            "actual": result["result_type"],
            "candidate_complete": required <= candidate_keys,
            "candidate_missing": sorted(required - candidate_keys),
            "final_complete": required <= final_keys,
            "final_missing": sorted(required - final_keys),
            "escaped": escaped,
            "retrieval_calls": len(result["retrieval_calls"]),
            "token_usage": metrics.get("token_usage"),
            "duration_ms": metrics.get("duration_ms"),
            "model_calls": metrics.get("model_calls"),
        }
        print(json.dumps(summary, ensure_ascii=False))
        print("ANSWER", (result["answer"] or "").replace("\n", " "))


if __name__ == "__main__":
    main()
