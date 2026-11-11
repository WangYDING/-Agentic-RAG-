"""Export the provisional cases for independent human source review."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "eval/datasets"
OUT = ROOT / "eval/reviews/independent_120_human_review.csv"


def main() -> None:
    cases = [json.loads(line) for line in (DATA / "independent_120_provisional_review.jsonl").read_text(encoding="utf-8").splitlines()]
    fields = ["case_id", "main_category", "question", "query_scope", "expected_action", "reference_answer",
              "necessary_facts", "evidence_locations", "numeric_constraints", "refusal_or_clarification_reason",
              "fact_group_id", "reviewer_type", "human_reviewer", "human_decision", "reviewed_at",
              "source_page_and_quote_check", "semantic_overlap_check", "modification_reason"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            refs = {json.dumps(ref, ensure_ascii=False, sort_keys=True) for group in case["evidence_groups"] for alternative in group["alternatives"] for ref in alternative["all_of"]}
            refs.update(json.dumps(ref, ensure_ascii=False, sort_keys=True) for ref in case.get("supported_source_references", []))
            writer.writerow({
                "case_id": case["case_id"], "main_category": case["main_category"], "question": case["question"],
                "query_scope": json.dumps(case["query_scope"], ensure_ascii=False),
                "expected_action": case["expected_action"], "reference_answer": case["reference_answer"],
                "necessary_facts": json.dumps(case["necessary_facts"], ensure_ascii=False),
                "evidence_locations": "\n".join(sorted(refs)),
                "numeric_constraints": json.dumps(case.get("numeric_constraints", []), ensure_ascii=False),
                "refusal_or_clarification_reason": case.get("reason_for_refusal_or_clarification", ""),
                "fact_group_id": case.get("fact_group_id", ""), "reviewer_type": "human (pending)",
                "human_decision": "pending", "source_page_and_quote_check": "pending",
                "semantic_overlap_check": "pending",
            })
    print(f"{len(cases)} pending rows -> {OUT}")


if __name__ == "__main__":
    main()
