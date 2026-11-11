"""Record the user's explicit assertion that all 120 annotations were reviewed."""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from eval.contract_v1 import validate_test_case
from eval.fingerprints_v1 import canonical_hash


BASE = Path(__file__).resolve().parent / "datasets"
SOURCE = BASE / "independent_120_provisional_review.jsonl"
OUT = BASE / "independent_120_user_reviewed.jsonl"
DESCRIPTOR = BASE / "independent_120_user_reviewed.descriptor.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cases = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(cases) == 120 and len({c["case_id"] for c in cases}) == 120
    assert Counter(c["expected_action"] for c in cases) == {"answer": 90, "refuse": 20, "clarify": 10}
    reviewed_at = datetime.now(timezone.utc).isoformat()
    reviewer = {"identity": "User (explicit confirmation in conversation; name not supplied)", "type": "human", "at": reviewed_at}
    approvals = []
    for case in cases:
        case["annotation_review"] = {
            "status": "approved_by_user_assertion", "reviewer_type": "human",
            "reviewer": reviewer["identity"], "reviewed_at": reviewed_at,
            "human_approved": True,
            "notes": "User explicitly confirmed completed human review of all cases in conversation on 2026-11-10; individual review notes and original review times were not supplied. AI did not impersonate the reviewer.",
        }
        case["dataset_role"] = "independent"
        validate_test_case(case)
        approvals.append({"case_id": case["case_id"], "status": "approved",
                          "reviewer": reviewer, "facts_sha256": canonical_hash(case["necessary_facts"]),
                          "schemes_sha256": canonical_hash(case["evidence_groups"])})
    OUT.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases), encoding="utf-8")
    DESCRIPTOR.write_text(json.dumps({
        "dataset_id": "independent_120_user_reviewed", "role": "independent",
        "status": "reviewed_pending_formal_freeze", "sha256": sha(OUT), "count": len(cases),
        "source_sha256": sha(SOURCE), "review_basis": "user assertion in conversation",
        "reviewer_identity_detail": "Name and per-case rationale not provided",
        "used_for_tuning": False, "formal_run_allowed": False,
        "case_approvals": approvals,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(len(cases), sha(OUT), DESCRIPTOR)


if __name__ == "__main__":
    main()
