"""Offline, read-only compatibility audit; never invokes the RAG workflow."""
import json
from collections import Counter
from pathlib import Path

from eval.contract_v1 import make_rag_input, validate_rag_input, validate_test_case

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "datasets" / "independent_120_user_reviewed.jsonl"
REPORT = ROOT / "reviews" / "independent_120_contract_alignment.json"


def main():
    cases = [json.loads(s) for s in DATA.read_text(encoding="utf-8").splitlines() if s.strip()]
    issues = []
    for case in cases:
        cid = case["case_id"]
        validate_test_case(case)
        validate_rag_input(make_rag_input(case))
        if case.get("numeric_constraints") and not any("numeric" in f for f in case["necessary_facts"]):
            issues.append({"case_id": cid, "code": "NUMERIC_FACT_MAPPING", "count": len(case["numeric_constraints"]),
                           "resolution": "Retain original top-level constraints; review allocation to necessary_facts[].numeric before numeric scoring."})
        if case["expected_action"] == "refuse" and case.get("supported_source_references"):
            issues.append({"case_id": cid, "code": "PARTIAL_SUPPORT_MAPPING",
                           "resolution": "Retain source references as annotation; decide whether known premise is a scored fact or only refusal rationale."})
        if case["expected_action"] == "clarify" and case.get("ambiguity_source_pages"):
            issues.append({"case_id": cid, "code": "CLARIFICATION_EVIDENCE_MAPPING",
                           "resolution": "Retain alternative-condition pages; decide whether to model as evidence groups or rubric metadata."})
        if case.get("overlap_review", {}).get("status") == "pending_semantic_review":
            issues.append({"case_id": cid, "code": "OVERLAP_STATUS_CONFLICT",
                           "resolution": "User asserted completed review, but original per-case overlap status is pending; record actual disposition without overwriting original."})
        if case["expected_action"] == "clarify" and not case["query_scope"].get("edition_ids"):
            issues.append({"case_id": cid, "code": "SCOPE_BEHAVIOR", "resolution": "Verify public QueryScope edition-only clarification path on frozen interface; no model call."})
    result = {"contract": "rag-eval.test-case.v1", "input_contract": "rag-eval.rag-input.v1",
              "schema_path": "eval/contract_v1.py", "example_path": "eval/examples/synthetic_contract_v1.json",
              "interface_docs": ["docs/EVALUATION_INTERFACE_V1.md", "docs/EVALUATION_GOVERNANCE_V1.md"],
              "dataset": DATA.name, "cases_valid": len(cases), "public_inputs_valid": len(cases),
              "distribution": dict(Counter(c["main_category"] for c in cases)),
              "necessary_facts": sum(len(c["necessary_facts"]) for c in cases),
              "evidence_groups": sum(len(c["evidence_groups"]) for c in cases),
              "issue_counts": dict(Counter(i["code"] for i in issues)), "issues": issues,
              "semantic_changes_made": False, "rag_invoked": False, "formal_run_started": False}
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(cases)} cases and public inputs valid; {len(issues)} mapping issues; report={REPORT}")


if __name__ == "__main__":
    main()
