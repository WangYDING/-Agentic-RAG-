"""Versioned, offline evaluation contract for RAG adapters.

This module is additive: legacy dataset readers, runners and metric meanings remain
unchanged.  It uses only the standard library and never calls a model or RAG system.
"""

from __future__ import annotations

import json
import copy
import math
from pathlib import Path
from typing import Any


TEST_CASE_VERSION = "rag-eval.test-case.v1"
TEST_CASE_VERSION_V2 = "rag-eval.test-case.v2"
RAG_INPUT_VERSION = "rag-eval.rag-input.v1"
OBSERVATION_VERSION = "rag-eval.observation.v1"
REVIEW_VERSION = "rag-eval.review.v1"
RUN_VERSION = "rag-eval.run.v1"
REPORT_VERSION = "rag-eval.report.v1"

EXPECTED_ACTIONS = {"answer", "refuse", "clarify"}
ACTUAL_ACTIONS = EXPECTED_ACTIONS | {"error"}
SUPPORT_LABELS = {"supported", "unsupported", "contradicted"}
RAG_INPUT_KEYS = {"schema_version", "case_id", "question", "query_scope"}


class ContractError(ValueError):
    """Raised when a v1 artifact violates the evaluation contract."""


def _require(obj: dict[str, Any], keys: set[str], label: str) -> None:
    if not isinstance(obj, dict):
        raise ContractError(f"{label} must be an object")
    missing = sorted(keys - obj.keys())
    if missing:
        raise ContractError(f"{label} missing fields: {', '.join(missing)}")


def _nonempty(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be a non-empty string")


def _nullable_bool(value: Any, label: str) -> None:
    if value is not None and type(value) is not bool:
        raise ContractError(f"{label} must be boolean or null")


def validate_evidence_ref(ref: dict[str, Any]) -> None:
    _require(ref, {"evidence_id", "document_id", "document_version", "page"}, "evidence")
    for key in ("evidence_id", "document_id", "document_version"):
        _nonempty(ref[key], f"evidence.{key}")
    if type(ref["page"]) is not int or ref["page"] < 1:
        raise ContractError("evidence.page must be a 1-based positive integer")
    if not any(ref.get(key) for key in ("article", "table", "locator", "quote")):
        raise ContractError("evidence requires article, table, locator, or quote")
    if "chunk_id" in ref and len(ref) == 5:
        raise ContractError("chunk_id cannot be the sole stable gold locator")


def validate_test_case(case: dict[str, Any]) -> None:
    _require(
        case,
        {
            "schema_version", "case_id", "dataset_role", "question", "query_scope",
            "expected_action", "reference_answer", "necessary_facts", "evidence_groups",
        },
        "test case",
    )
    if case["schema_version"] not in {TEST_CASE_VERSION, TEST_CASE_VERSION_V2}:
        raise ContractError("unsupported test case schema_version")
    if case["schema_version"] == TEST_CASE_VERSION_V2:
        _validate_v2_annotations(case)
    if case["dataset_role"] not in {"synthetic", "development", "historical", "independent"}:
        raise ContractError("invalid dataset_role")
    if case["expected_action"] not in EXPECTED_ACTIONS:
        raise ContractError("invalid expected_action")
    for key in ("case_id", "question"):
        _nonempty(case[key], f"test_case.{key}")
    if not isinstance(case["query_scope"], dict):
        raise ContractError("query_scope must be an object")
    if case["reference_answer"] is not None and not isinstance(case["reference_answer"], str):
        raise ContractError("reference_answer must be string or null")
    for key in ("necessary_facts", "evidence_groups"):
        if not isinstance(case[key], list):
            raise ContractError(f"{key} must be a list")
    if case["expected_action"] == "answer" and not case["necessary_facts"]:
        raise ContractError("answer requires necessary facts")
    fact_ids: set[str] = set()
    for fact in case["necessary_facts"]:
        _require(fact, {"fact_id", "description"}, "necessary fact")
        _nonempty(fact["fact_id"], "fact_id")
        _nonempty(fact["description"], "fact.description")
        if fact["fact_id"] in fact_ids:
            raise ContractError(f"duplicate fact_id: {fact['fact_id']}")
        fact_ids.add(fact["fact_id"])
    group_fact_ids: set[str] = set()
    for group in case["evidence_groups"]:
        _require(group, {"fact_id", "alternatives"}, "evidence group")
        if group["fact_id"] not in fact_ids:
            raise ContractError(f"evidence group references unknown fact: {group['fact_id']}")
        if group["fact_id"] in group_fact_ids:
            raise ContractError(f"duplicate evidence group for fact: {group['fact_id']}")
        group_fact_ids.add(group["fact_id"])
        if not isinstance(group["alternatives"], list) or not group["alternatives"]:
            raise ContractError("evidence alternatives must be a non-empty OR list")
        for alternative in group["alternatives"]:
            _require(alternative, {"scheme_id", "all_of"}, "evidence alternative")
            _nonempty(alternative["scheme_id"], "scheme_id")
            if not isinstance(alternative["all_of"], list) or not alternative["all_of"]:
                raise ContractError("all_of must be a non-empty AND list")
            for ref in alternative["all_of"]:
                validate_evidence_ref(ref)
    if case["expected_action"] == "answer" and fact_ids != group_fact_ids:
        raise ContractError("answer cases require one evidence group per necessary fact")


def _validate_v2_annotations(case):
    """Typed scoring annotations; never sent through make_rag_input."""
    if case["expected_action"] == "answer":
        constraints = case.get("numeric_constraints_v2", [])
        if not isinstance(constraints, list):
            raise ContractError("numeric_constraints_v2 must be a list")
        ids = set()
        facts = {f["fact_id"] for f in case["necessary_facts"]}
        for row in constraints:
            _require(row, {"constraint_id", "value", "unit", "comparison", "conditions", "fact_ids", "link_semantics"}, "numeric constraint")
            if row["constraint_id"] in ids or not isinstance(row["fact_ids"], list) or not row["fact_ids"] or not set(row["fact_ids"]) <= facts:
                raise ContractError("numeric constraint ID/fact links invalid")
            ids.add(row["constraint_id"])
            for key in ("constraint_id", "value", "unit", "comparison"):
                _nonempty(row[key], key)
            if row["link_semantics"] not in {"all_facts", "any_fact"} or not isinstance(row["conditions"], list) or not all(isinstance(c, str) and c.strip() for c in row["conditions"]):
                raise ContractError("numeric condition/link semantics invalid")
    elif case["expected_action"] == "refuse":
        b = case.get("refusal_annotation_v2")
        if b is not None:
            _require(b, {"supported_facts", "missing_facts", "allowed_explanation"}, "refusal annotation")
            if not isinstance(b["supported_facts"], list) or not isinstance(b["missing_facts"], list) or not b["missing_facts"] or not isinstance(b["allowed_explanation"], list):
                raise ContractError("refusal fact lists invalid")
            for f in b["supported_facts"] + b["missing_facts"]:
                _require(f, {"fact_id", "description"}, "behavior fact")
                _nonempty(f["fact_id"], "behavior fact ID")
                _nonempty(f["description"], "behavior fact description")
            if not all(isinstance(s, str) and s.strip() for s in b["allowed_explanation"]):
                raise ContractError("allowed explanation invalid")
    elif case["expected_action"] == "clarify":
        b = case.get("clarification_annotation_v2")
        if b is not None:
            _require(b, {"required_fields", "branches"}, "clarification annotation")
            if not isinstance(b["required_fields"], list) or not b["required_fields"] or not isinstance(b["branches"], list):
                raise ContractError("clarification fields/branches invalid")
            for field in b["required_fields"]:
                _nonempty(field, "required clarification field")
            for branch in b["branches"]:
                _require(branch, {"branch_id", "when", "evidence_groups"}, "future branch")
                _nonempty(branch["branch_id"], "branch ID")
                if not isinstance(branch["when"], dict) or not isinstance(branch["evidence_groups"], list):
                    raise ContractError("future branch invalid")
                for group in branch["evidence_groups"]:
                    for alternative in group["alternatives"]:
                        for ref in alternative["all_of"]:
                            validate_evidence_ref(ref)


def make_rag_input(case: dict[str, Any]) -> dict[str, Any]:
    """Build the only object an adapter may send to RAG; gold fields cannot leak."""
    validate_test_case(case)
    return {
        "schema_version": RAG_INPUT_VERSION,
        "case_id": case["case_id"],
        "question": case["question"],
        "query_scope": copy.deepcopy(case["query_scope"]),
    }


def validate_rag_input(item: dict[str, Any]) -> None:
    if set(item) != RAG_INPUT_KEYS:
        extra = sorted(set(item) - RAG_INPUT_KEYS)
        missing = sorted(RAG_INPUT_KEYS - set(item))
        raise ContractError(f"RAG input keys invalid; extra={extra}, missing={missing}")
    if item["schema_version"] != RAG_INPUT_VERSION:
        raise ContractError("unsupported RAG input schema_version")
    _nonempty(item["case_id"], "rag_input.case_id")
    _nonempty(item["question"], "rag_input.question")
    if not isinstance(item["query_scope"], dict):
        raise ContractError("rag_input.query_scope must be an object")


def validate_observation(item: dict[str, Any]) -> None:
    _require(
        item,
        {
            "schema_version", "case_id", "actual_action", "answer_text", "error",
            "initial_candidates", "reranked_results", "final_decision_evidence",
            "generator_invoked", "generator_context", "citations", "measurements", "retrieval_rounds", "actual_scope",
        },
        "observation",
    )
    if item["schema_version"] != OBSERVATION_VERSION:
        raise ContractError("unsupported observation schema_version")
    _nonempty(item["case_id"], "observation.case_id")
    if item["answer_text"] is not None and not isinstance(item["answer_text"], str):
        raise ContractError("answer_text must be string or null")
    if item["actual_action"] not in ACTUAL_ACTIONS:
        raise ContractError("invalid actual_action")
    _nullable_bool(item["generator_invoked"], "generator_invoked")
    if item["actual_action"] == "error":
        if not isinstance(item["error"], dict) or not item["error"].get("code"):
            raise ContractError("error action requires error.code")
    elif item["error"] is not None:
        raise ContractError("non-error action must have error=null")
    if item["actual_action"] == "answer" and (not item["answer_text"] or not item["answer_text"].strip()):
        raise ContractError("answer action requires non-empty answer_text")
    if not item["generator_invoked"] and item["generator_context"] is not None:
        raise ContractError("generator_context must be null when generator was not invoked")
    for name in ("initial_candidates", "reranked_results", "final_decision_evidence", "generator_context"):
        value = item[name]
        if value is not None and not isinstance(value, list):
            raise ContractError(f"{name} must be a list or null")
        if isinstance(value, list):
            for ref in value:
                validate_evidence_ref(ref)
    if not isinstance(item["citations"], list):
        raise ContractError("citations must be a list")
    if item["actual_scope"] is not None and not isinstance(item["actual_scope"], dict):
        raise ContractError("actual_scope must be object or null")
    if item["retrieval_rounds"] is not None:
        if not isinstance(item["retrieval_rounds"], list):
            raise ContractError("retrieval_rounds must be list or null")
        rounds = set()
        for row in item["retrieval_rounds"]:
            _require(row, {"round_id", "candidates", "reranked"}, "retrieval round")
            _nonempty(row["round_id"], "round_id")
            if row["round_id"] in rounds:
                raise ContractError("duplicate round_id")
            rounds.add(row["round_id"])
            for key in ("candidates", "reranked"):
                if row[key] is not None:
                    if not isinstance(row[key], list):
                        raise ContractError("round evidence must be list or null")
                    for ref in row[key]:
                        validate_evidence_ref(ref)
    known = {ref["evidence_id"] for name in ("initial_candidates", "reranked_results", "final_decision_evidence", "generator_context") for ref in (item[name] or [])}
    citation_ids = set()
    for citation in item["citations"]:
        _require(citation, {"citation_id", "evidence_id", "parse_valid", "scope_valid"}, "citation")
        _nonempty(citation["citation_id"], "citation_id")
        if citation["citation_id"] in citation_ids:
            raise ContractError("duplicate citation_id")
        citation_ids.add(citation["citation_id"])
        for key in ("parse_valid", "scope_valid"):
            _nullable_bool(citation[key], key)
        if citation["parse_valid"] is True and citation["evidence_id"] not in known:
            raise ContractError("valid citation references unknown evidence")
    measurements = item["measurements"]
    _require(measurements, {"latency_ms", "model_calls", "input_tokens", "output_tokens"}, "measurements")
    for key in measurements:
        value = measurements[key]
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ContractError(f"measurements.{key} must be non-negative or null")
        if key in {"model_calls", "input_tokens", "output_tokens"} and value is not None and type(value) is not int:
            raise ContractError(f"measurements.{key} must be an integer count or null")


def validate_review(item: dict[str, Any], case: dict[str, Any], observation: dict[str, Any]) -> None:
    _require(item, {"schema_version", "case_id", "reviewer", "fact_reviews", "claim_reviews", "behavior_review"}, "review")
    if item["schema_version"] != REVIEW_VERSION or item["case_id"] != case["case_id"]:
        raise ContractError("review version or case link is invalid")
    reviewer = item["reviewer"]
    _require(reviewer, {"identity", "reviewer_type", "reviewed_at", "rubric_version"}, "reviewer")
    if reviewer["reviewer_type"] not in {"human", "ai"}:
        raise ContractError("reviewer_type must disclose human or ai")
    for key in ("identity", "rubric_version"):
        _nonempty(reviewer[key], f"reviewer.{key}")
    if observation["case_id"] != case["case_id"]:
        raise ContractError("observation case link mismatch")
    if case["schema_version"] == TEST_CASE_VERSION_V2:
        expected_numeric = {c["constraint_id"] for c in case.get("numeric_constraints_v2", [])}
        rows = item.get("numeric_constraint_reviews_v2", [])
        if {r.get("constraint_id") for r in rows} != expected_numeric or len(rows) != len(expected_numeric):
            raise ContractError("numeric constraint review coverage invalid")
        for row in rows:
            _require(row, {"constraint_id", "correct", "reason"}, "numeric constraint review")
            _nullable_bool(row["correct"], "constraint.correct")
        for annotation_key, review_key, flags in (
            ("refusal_annotation_v2", "refusal_review_v2", ("missing_facts_not_asserted", "explanation_within_allowed")),
            ("clarification_annotation_v2", "clarification_review_v2", ("required_fields_requested", "no_premature_branch_answer")),
        ):
            if case.get(annotation_key):
                behavior = item.get(review_key)
                _require(behavior, {*flags, "reason"}, review_key)
                for flag in flags:
                    _nullable_bool(behavior[flag], review_key + "." + flag)
    known = {ref["evidence_id"] for name in ("initial_candidates", "reranked_results", "final_decision_evidence", "generator_context") for ref in (observation[name] or [])}
    claim_ids = set()
    for row in item["fact_reviews"] + item["claim_reviews"]:
        if not isinstance(row.get("evidence_ids"), list) or any(eid not in known for eid in row["evidence_ids"]):
            raise ContractError("review references unknown evidence")
        if not isinstance(row.get("reason"), str):
            raise ContractError("review reason must be a string")
    expected_facts = {fact["fact_id"] for fact in case["necessary_facts"]}
    seen: set[str] = set()
    for review in item["fact_reviews"]:
        _require(review, {"fact_id", "context_supported", "final_evidence_supported", "numeric_conditions_correct", "answer_covered", "correct", "evidence_ids", "reason"}, "fact review")
        if review["fact_id"] not in expected_facts or review["fact_id"] in seen:
            raise ContractError("fact review has unknown or duplicate fact_id")
        seen.add(review["fact_id"])
        for key in ("context_supported", "final_evidence_supported", "numeric_conditions_correct", "answer_covered", "correct"):
            _nullable_bool(review[key], f"fact_review.{key}")
    if seen != expected_facts:
        raise ContractError("review requires one row for every necessary fact; use null if unreviewed")
    for review in item["claim_reviews"]:
        if review.get("claim_id") in claim_ids:
            raise ContractError("duplicate claim_id")
        claim_ids.add(review.get("claim_id"))
        _nonempty(review.get("claim_id"), "claim_id")
        _nonempty(review.get("text"), "claim.text")
        _require(review, {"claim_id", "text", "support", "evidence_ids", "reason"}, "claim review")
        if review["support"] is not None and review["support"] not in SUPPORT_LABELS:
            raise ContractError("claim support must be supported/unsupported/contradicted/null")
    _require(item["behavior_review"], {"appropriate", "reason"}, "behavior review")
    _nullable_bool(item["behavior_review"]["appropriate"], "behavior_review.appropriate")
    _nullable_bool(item.get("human_approved"), "human_approved")
    if item.get("human_approved") is True and reviewer["reviewer_type"] != "human":
        raise ContractError("AI reviewer cannot supply human approval")
    if "answer_review" in item:
        _require(item["answer_review"], {"claims_exhaustive", "no_contradictions",
                 "no_material_outside_conclusions", "citations_support_claims"}, "answer_review")
        for key, value in item["answer_review"].items():
            _nullable_bool(value, f"answer_review.{key}")
    completed = any(row[key] is not None for row in item["fact_reviews"] for key in ("context_supported", "final_evidence_supported", "numeric_conditions_correct", "answer_covered", "correct")) or any(row["support"] is not None for row in item["claim_reviews"]) or item["behavior_review"]["appropriate"] is not None
    completed = completed or any(v is not None for v in item.get("answer_review", {}).values()) or item.get("human_approved") is not None
    if completed and not reviewer["reviewed_at"]:
        raise ContractError("completed review requires reviewed_at")
    if observation["actual_action"] != "answer" and item["claim_reviews"]:
        raise ContractError("non-answer observations cannot have answer claim reviews")


def evidence_scheme_satisfied(group: dict[str, Any], observed_ids: set[str]) -> bool:
    """Alternatives are OR; every reference inside one all_of scheme is AND."""
    return any(
        all(ref["evidence_id"] in observed_ids for ref in alternative["all_of"])
        for alternative in group["alternatives"]
    )


def rate(numerator: int, denominator: int, applicable_case_ids: list[str]) -> dict[str, Any]:
    if numerator < 0 or denominator < 0 or numerator > denominator:
        raise ContractError("invalid metric numerator/denominator")
    if denominator != len(applicable_case_ids):
        raise ContractError("metric denominator must equal applicable_case_ids length")
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": None if denominator == 0 else numerator / denominator,
        "applicable_case_ids": applicable_case_ids,
    }


def validate_bundle(bundle: dict[str, Any]) -> None:
    _require(bundle, {"test_cases", "rag_inputs", "observations", "reviews", "run", "report"}, "bundle")
    for name in ("test_cases", "rag_inputs", "observations", "reviews"):
        if not isinstance(bundle[name], list):
            raise ContractError(f"{name} must be a list")
        ids = [row.get("case_id") for row in bundle[name]]
        if len(ids) != len(set(ids)):
            raise ContractError(f"duplicate case_id in {name}; require exactly once")
    cases = {item["case_id"]: item for item in bundle["test_cases"]}
    if len(cases) != len(bundle["test_cases"]):
        raise ContractError("duplicate case_id")
    for case in bundle["test_cases"]:
        validate_test_case(case)
    if {row["case_id"] for row in bundle["rag_inputs"]} != set(cases):
        raise ContractError("rag_inputs must link exactly once to every case")
    for rag_input in bundle["rag_inputs"]:
        validate_rag_input(rag_input)
        case = cases.get(rag_input["case_id"])
        if case is None or rag_input != make_rag_input(case):
            raise ContractError("RAG input does not exactly match its test case public projection")
    observations = {item["case_id"]: item for item in bundle["observations"]}
    if set(observations) != set(cases):
        raise ContractError("observations must link exactly once to every case")
    for item in observations.values():
        validate_observation(item)
    reviews = {item["case_id"]: item for item in bundle["reviews"]}
    if set(reviews) != set(cases):
        raise ContractError("reviews must link exactly once to every case")
    for case_id, item in reviews.items():
        validate_review(item, cases[case_id], observations[case_id])
    run = bundle["run"]
    _require(run, {"schema_version", "run_id", "artifacts", "system_snapshot", "evaluation_snapshot"}, "run")
    if run["schema_version"] != RUN_VERSION:
        raise ContractError("unsupported run schema_version")
    for section in ("system_snapshot", "evaluation_snapshot"):
        if not isinstance(run[section], dict):
            raise ContractError(f"run.{section} must be an object")
    _nonempty(run["run_id"], "run_id")
    _require(run["system_snapshot"], {"git_commit", "git_dirty", "prompt_hashes", "config_hash", "model_id", "document_hashes", "index_snapshot"}, "system snapshot")
    _require(run["evaluation_snapshot"], {"code_commit", "testset_version", "rubric_version", "threshold_version"}, "evaluation snapshot")
    _require(run["artifacts"], {"dataset_sha256", "results_sha256"}, "artifacts")
    report = bundle["report"]
    _require(report, {"schema_version", "run_id", "metrics", "conclusion"}, "report")
    if report["schema_version"] != REPORT_VERSION or report["run_id"] != run["run_id"]:
        raise ContractError("report version or run link is invalid")
    if report["conclusion"] not in {"pass", "fail", "inconclusive", "not_applicable"}:
        raise ContractError("invalid report conclusion")

    if not isinstance(report["metrics"], dict):
        raise ContractError("metrics must be an object")
    for metric in report["metrics"].values():
        _require(metric, {"numerator", "denominator", "rate", "applicable_case_ids"}, "metric")
        ids = metric["applicable_case_ids"]
        allowed_ids = ({f"{cid}/{i+1}" for cid, c in cases.items() for i in range(len(c["evidence_groups"]))}
                       if metric.get("unit") == "case/fact-group" else set(cases))
        if not isinstance(ids, list) or len(ids) != len(set(ids)) or not set(ids) <= allowed_ids:
            raise ContractError("invalid metric case IDs")
        if "kind" in metric:
            from eval.scoring_v1 import aggregate
            values = metric.get("case_values", {})
            if metric["kind"] not in {"rate", "macro"} or set(values) != set(ids):
                raise ContractError("invalid metric kind or values")
            for value in values.values():
                if value is not None and (type(value) not in (bool, int, float) or not math.isfinite(value) or not 0 <= value <= 1):
                    raise ContractError("invalid metric case value")
            calculated = aggregate(values, mode=metric["kind"])
            if "unit" in metric:
                calculated["unit"] = metric["unit"]
            if metric != calculated:
                raise ContractError("inconsistent observed/full metric")
            continue
        for key in ("numerator", "denominator"):
            if type(metric[key]) is not int:
                raise ContractError("count metric requires integer counts")
        if metric != rate(metric["numerator"], metric["denominator"], ids):
            raise ContractError("inconsistent metric rate")
    if report["conclusion"] in {"pass", "fail"}:
        raise ContractError("v1 interface validator cannot authorize acceptance; use inconclusive")
    if report.get("scorer_version") == "rag-eval.scorer.v1":
        from eval.scoring_v1 import score
        computed = score(bundle["test_cases"], observations, reviews)
        for key, value in computed.items():
            if report.get(key) != value:
                raise ContractError(f"report does not match observations/reviews: {key}")
        if "provider_usage_summary" in report:
            from eval.usage_v1 import usage_report
            if report["provider_usage_summary"] != usage_report(bundle["observations"]):
                raise ContractError("provider usage summary mismatch")


def load_bundle(path: str | Path) -> dict[str, Any]:
    bundle = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_bundle(bundle)
    return bundle


def location_scheme_satisfied(group: dict, observed: list[dict] | None) -> bool | None:
    """Position coverage only, never semantic support; runtime IDs need not equal gold."""
    if observed is None:
        return None
    def matches(gold, actual):
        keys = ("document_id", "document_version", "article", "table", "locator", "quote")
        start = actual.get("page")
        end = actual.get("page_end") or start
        if type(start) is not int or type(end) is not int or not start <= gold["page"] <= end:
            return False
        return all(actual.get(key) == gold[key] for key in keys if gold.get(key) is not None)
    return any(all(any(matches(gold, actual) for actual in observed)
                   for gold in scheme["all_of"]) for scheme in group["alternatives"])
