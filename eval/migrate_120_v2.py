"""Stage a v2 annotation migration; never asserts renewed human approval."""
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from eval.contract_v1 import make_rag_input, validate_rag_input, validate_test_case

ROOT = Path(__file__).resolve().parent
DATA, REV = ROOT / "datasets", ROOT / "reviews"
MANUAL = {
    ("I120-N001", 1): ["F1"], ("I120-N001", 2): ["F2"],
    ("I120-N012", 1): ["F1"], ("I120-N016", 1): ["F1"],
    ("I120-T002", 1): ["F1"], ("I120-T002", 3): ["F3"],
    ("I120-T007", 1): ["F1", "F2", "F3"],
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    src = DATA / "independent_120_alignment_staging.jsonl"
    cases = [json.loads(x) for x in src.read_text(encoding="utf-8").splitlines() if x.strip()]
    alignment = json.loads((REV / "independent_120_alignment_resolution.json").read_text(encoding="utf-8"))
    pending = set(alignment["requires_re_review_case_ids"])
    issues = []
    mapping = []
    for case in cases:
        cid = case["case_id"]
        case["schema_version"] = "rag-eval.test-case.v2"
        if case["expected_action"] == "answer":
            rows = []
            for n, old in enumerate(case.get("numeric_constraints", []), 1):
                matches = [f["fact_id"] for f in case["necessary_facts"] if re.search(r"(?<![0-9.])" + re.escape(str(old["value"])) + r"(?![0-9.])", f["description"])]
                fact_ids = MANUAL.get((cid, n), matches)
                if len(fact_ids) != 1 and (cid, n) not in MANUAL:
                    issues.append({"case_id": cid, "code": "NUMERIC_LINK_REQUIRES_DECISION", "index": n, "candidates": matches})
                    continue
                row = {"constraint_id": f"N{n}", "value": str(old["value"]), "unit": str(old["unit"]),
                       "comparison": str(old["comparison"]), "conditions": [old["condition"]],
                       "fact_ids": fact_ids, "link_semantics": "all_facts"}
                rows.append(row)
                mapping.append({"case_id": cid, "index": n, "fact_ids": fact_ids,
                                "basis": "manual semantic disambiguation" if (cid, n) in MANUAL else "unique value in fact description; pending renewed review"})
            case["numeric_constraints_v2"] = rows
        elif case["expected_action"] == "refuse":
            refs = case.get("supported_source_references", [])
            reason = case.get("reason_for_refusal_or_clarification") or "缺少所问事实的独立依据"
            case["refusal_annotation_v2"] = {
                "supported_facts": [{"fact_id": f"S{n}", "description": f"原标注支持的规范前提：{r.get('article', '规范位置')}"} for n, r in enumerate(refs, 1)],
                "missing_facts": [{"fact_id": "M1", "description": reason}],
                "allowed_explanation": ["可解释原标注列出的规范前提及缺失的项目或外部资料，不得给出未经证实的项目结论"],
            }
            if refs:
                # v2 does not attach evidence to supported behavior facts.
                issues.append({"case_id": cid, "code": "SUPPORTED_PREMISE_EVIDENCE_UNSCORED", "count": len(refs)})
        else:
            reason = case.get("reason_for_refusal_or_clarification") or "需明确适用条件"
            case["clarification_annotation_v2"] = {"required_fields": [reason], "branches": []}
            if case.get("ambiguity_source_pages"):
                issues.append({"case_id": cid, "code": "BRANCH_PAGES_NOT_EVIDENCE_REFS", "pages": case["ambiguity_source_pages"]})
        if cid in pending:
            case["annotation_review"]["status"] = "requires_re_review_for_v2"
            case["annotation_review"]["human_approved"] = False
        validate_test_case(case)
        public = make_rag_input(case)
        validate_rag_input(public)
        assert set(public) == {"schema_version", "case_id", "question", "query_scope"}
    out = DATA / "independent_120_v2_pending_review.jsonl"
    out.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases), encoding="utf-8")
    report = {"protocol": "rag-eval.test-case.v2", "public_input": "rag-eval.rag-input.v1",
              "source_sha256": sha(src), "output_sha256": sha(out), "cases": len(cases),
              "distribution": dict(Counter(c["main_category"] for c in cases)),
              "numeric_constraint_mappings": mapping, "numeric_constraint_count": len(mapping),
              "issues": issues, "unresolved_case_ids": sorted({i["case_id"] for i in issues}),
              "renewed_human_review_required_case_ids": sorted(pending),
              "review_history_preserved": True, "schema_valid": True, "public_input_isolated": True,
              "rag_invoked": False, "independent_run_started": False}
    path = REV / "independent_120_v2_migration.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(len(cases), len(mapping), len(issues), len(pending), sha(out))


if __name__ == "__main__":
    main()
