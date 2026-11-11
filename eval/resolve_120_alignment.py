"""Resolve metadata conflicts and stage semantic changes without invoking RAG."""
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from eval.contract_v1 import make_rag_input, validate_rag_input, validate_test_case
from src.query_scope import QueryScope, QueryScopeClarificationRequired, SpecEdition, resolve_query_scope

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "datasets"
REVIEWS = ROOT / "reviews"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = DATA / "independent_120_user_reviewed.jsonl"
    cases = [json.loads(s) for s in source.read_text(encoding="utf-8").splitlines() if s.strip()]
    original = {c["case_id"]: c for c in cases}
    old = json.loads((REVIEWS / "independent_120_contract_alignment.json").read_text(encoding="utf-8"))["issues"]
    by_case = defaultdict(list)
    for issue in old:
        by_case[issue["case_id"]].append(issue["code"])
    decisions = []
    numeric_links = []
    scope = QueryScope.from_request_payload(original["I120-Q007"]["query_scope"])
    catalog = [SpecEdition("cn.beijing.db11t995", "2025")]
    try:
        resolve_query_scope(scope, snapshot_id="offline-scope-check", snapshot_versions=catalog, catalog_versions=catalog)
    except QueryScopeClarificationRequired:
        scope_result = "clarify"
    else:
        scope_result = "not_clarify"
    assert scope_result == "clarify"
    for case in cases:
        cid = case["case_id"]
        codes = by_case.get(cid, [])
        for index, constraint in enumerate(case.get("numeric_constraints", []), 1):
            needle = str(constraint["value"])
            candidates = [f["fact_id"] for f in case["necessary_facts"] if re.search(r"(?<![0-9.])" + re.escape(needle) + r"(?![0-9.])", f["description"])]
            numeric_links.append({"case_id": cid, "constraint_index": index, "constraint": constraint,
                                  "candidate_fact_ids": candidates, "allocation_status": "needs_semantic_adjudication"})
        for code in codes:
            if code == "OVERLAP_STATUS_CONFLICT":
                case.setdefault("overlap_review_history", []).append(case["overlap_review"].copy())
                case["overlap_review"] = {"status": "user_review_asserted_complete", "known_overlap_ids": case["overlap_review"].get("known_overlap_ids", []),
                                          "basis": "User confirmed review of all 120 cases in conversation; original pending status retained in history."}
                decision = "resolved_metadata"
            elif code == "SCOPE_BEHAVIOR":
                case["scope_policy_check"] = {"result": scope_result, "source": "src/query_scope.py resolve_query_scope; offline call with catalog/snapshot identity", "rag_invoked": False}
                decision = "resolved_offline_policy"
            else:
                decision = "pending_semantic_adjudication"
                # The existing v1 scorer only reads fact.numeric. Do not guess a mapping
                # where the same number applies to several facts or a fact has several values.
                case["annotation_review"]["status"] = "requires_re_review_for_scoring_mapping"
                case["annotation_review"]["human_approved"] = False
            decisions.append({"case_id": cid, "code": code, "decision": decision})
        validate_test_case(case)
        validate_rag_input(make_rag_input(case))
    out = DATA / "independent_120_alignment_staging.jsonl"
    out.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases), encoding="utf-8")
    resolved = sorted({d["case_id"] for d in decisions if d["decision"].startswith("resolved")})
    pending = sorted({d["case_id"] for d in decisions if d["decision"] == "pending_semantic_adjudication"})
    report = {
        "source_sha256": sha(source), "staging_sha256": sha(out), "schema": "rag-eval.test-case.v1",
        "total_records": len(decisions), "unique_affected_cases": len(by_case),
        "record_decisions": dict(Counter(d["decision"] for d in decisions)),
        "resolved_case_ids": resolved, "pending_adjudication_case_ids": pending,
        "requires_re_review_case_ids": pending,
        "issues": decisions,
        "numeric_fact_link_candidates": numeric_links,
        "interface_gaps": [
            "v1 numeric scoring reads necessary_facts[].numeric only; top-level numeric_constraints may express multiple values, comparison directions and distinct conditions. A lossless multi-constraint-per-fact rubric is needed or explicit per-case allocation and renewed approval.",
            "v1 refusal and clarification cases with empty necessary_facts/evidence_groups cannot score supported premise or competing branch evidence. Need typed, non-gold-leaking behavior premise/branch annotations and a scoring rule before mapping these references.",
        ],
        "scope_check": {"case_id": "I120-Q007", "result": scope_result, "frozen_interface_still_unverified": True},
        "all_cases_schema_valid": len(cases) == 120, "all_public_inputs_valid": True,
        "rag_invoked": False, "formal_run_started": False,
    }
    path = REVIEWS / "independent_120_alignment_resolution.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(len(decisions), len(by_case), len(pending), sha(out))


if __name__ == "__main__":
    main()
