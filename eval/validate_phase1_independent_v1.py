"""Validate the frozen Phase 1 independent dataset and its source review."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "eval/datasets/phase1_cross_spec_independent_v1.jsonl"
REVIEW = ROOT / "eval/reviews/phase1_cross_spec_independent_v1_source_review.json"


def main() -> None:
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line]
    review = json.loads(REVIEW.read_text(encoding="utf-8"))

    assert len(rows) == 30
    assert len({row["id"] for row in rows}) == 30
    assert len(review["cases"]) == 30
    assert review["candidate_system_answers_run_or_inspected"] is False
    assert review["dataset_sha256"] == hashlib.sha256(DATASET.read_bytes()).hexdigest()
    assert {row["id"] for row in rows} == {case["id"] for case in review["cases"]}
    assert all(row["annotation_review"]["status"] == "approved" for row in rows)
    assert all(row["requested_scope"] or row["expected_behavior"] == "clarify_scope" for row in rows)
    assert all(row["source_references"] or not row["answerable"] for row in rows)

    behaviors = Counter(row["expected_behavior"] for row in rows)
    assert behaviors == {"answer": 25, "clarify_scope": 2, "refuse": 3}
    print(f"validated {len(rows)} cases: {dict(behaviors)}")


if __name__ == "__main__":
    main()
