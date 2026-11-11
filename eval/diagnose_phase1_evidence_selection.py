from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "eval/datasets/phase1_cross_spec_independent_v1.jsonl"
RESULT = ROOT / "eval/reports/phase1_seen_regression_evidence_selection_final_20261106.json"
TARGETS = {
    "P1-IND-011", "P1-IND-012", "P1-IND-016", "P1-IND-017",
    "P1-IND-018", "P1-IND-020", "P1-IND-025",
}


def identity(item: dict) -> str:
    return f"{item.get('spec_id')}@{item.get('edition_id')}:{item.get('article_id')}#{item.get('chunk_id')}"


def main() -> None:
    dataset = {row["id"]: row for row in map(json.loads, DATASET.read_text(encoding="utf-8").splitlines())}
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    for case in result["questions"]:
        if case["id"] not in TARGETS:
            continue
        gold = dataset[case["id"]]
        required = {(business_id, article) for business_id, articles in gold["expected_articles_by_spec"].items() for article in articles}
        print(f"\n## {case['id']} {gold['question']}")
        print("required", sorted(required))
        for call_index, call in enumerate(case["retrieval_calls"], start=1):
            print(f"call {call_index}: {call['query']}")
            for rank, item in enumerate(call["candidates"], start=1):
                key = (f"{item.get('spec_id')}@{item.get('edition_id')}", str(item.get("article_id")))
                if key in required:
                    print("  REQUIRED", rank, identity(item), item.get("score"), item.get("focused_best_rank"))
        print("final", [identity(item) for item in case["final_evidence"]])
        print("trace", json.dumps(case["trace"], ensure_ascii=False))


if __name__ == "__main__":
    main()
