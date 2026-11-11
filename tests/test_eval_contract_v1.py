import copy
import json
from pathlib import Path

import pytest

from eval.contract_v1 import (
    ContractError,
    evidence_scheme_satisfied,
    load_bundle,
    make_rag_input,
    rate,
    validate_bundle,
    validate_observation,
    validate_rag_input,
)


EXAMPLE = Path("eval/examples/synthetic_contract_v1.json")


def bundle():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_synthetic_bundle_is_valid_and_all_ids_link():
    loaded = load_bundle(EXAMPLE)
    assert len(loaded["test_cases"]) == 7
    assert {x["actual_action"] for x in loaded["observations"]} == {
        "answer", "refuse", "clarify", "error"
    }


def test_gold_fields_never_enter_rag_input():
    case = bundle()["test_cases"][0]
    rag_input = make_rag_input(case)
    assert set(rag_input) == {"schema_version", "case_id", "question", "query_scope"}
    serialized = json.dumps(rag_input, ensure_ascii=False)
    for forbidden in ("reference_answer", "necessary_facts", "evidence_groups", "expected_action"):
        assert forbidden not in serialized
    poisoned = dict(rag_input, reference_answer="leak")
    with pytest.raises(ContractError, match="extra"):
        validate_rag_input(poisoned)


def test_illegal_behavior_and_missing_observations_are_distinct():
    item = copy.deepcopy(bundle()["observations"][0])
    item["actual_action"] = "error"
    item["error"] = None
    with pytest.raises(ContractError, match="error.code"):
        validate_observation(item)
    item = copy.deepcopy(bundle()["observations"][1])
    item["generator_context"] = []
    with pytest.raises(ContractError, match="must be null"):
        validate_observation(item)
    missing = copy.deepcopy(bundle())
    missing["observations"].pop()
    with pytest.raises(ContractError, match="exactly once"):
        validate_bundle(missing)


def test_zero_denominator_is_null_and_not_zero_or_pass():
    assert rate(0, 0, []) == {
        "numerator": 0, "denominator": 0, "rate": None, "applicable_case_ids": []
    }


def test_unreviewed_values_remain_null():
    data = bundle()
    review = next(x for x in data["reviews"] if x["case_id"] == "SYN-MISSING-OBS")
    assert review["fact_reviews"][0]["correct"] is None
    assert review["behavior_review"]["appropriate"] is None
    validate_bundle(data)


def test_evidence_alternatives_are_or_and_scheme_members_are_and():
    case = next(x for x in bundle()["test_cases"] if x["case_id"] == "SYN-EQUIVALENT")
    group = case["evidence_groups"][0]
    assert evidence_scheme_satisfied(group, {"EV-A"})
    assert evidence_scheme_satisfied(group, {"EV-B1", "EV-B2"})
    assert not evidence_scheme_satisfied(group, {"EV-B1"})


def test_unknown_fact_link_and_duplicate_case_are_rejected():
    data = bundle()
    data["test_cases"][0]["evidence_groups"][0]["fact_id"] = "UNKNOWN"
    with pytest.raises(ContractError, match="unknown fact"):
        validate_bundle(data)
    data = bundle()
    data["test_cases"].append(copy.deepcopy(data["test_cases"][0]))
    with pytest.raises(ContractError, match="duplicate case_id"):
        validate_bundle(data)


@pytest.mark.parametrize("section", ["rag_inputs", "observations", "reviews"])
def test_duplicate_links_rejected(section):
    data = bundle()
    data[section].append(copy.deepcopy(data[section][0]))
    with pytest.raises(ContractError, match="duplicate"):
        validate_bundle(data)


@pytest.mark.parametrize("mutation", ["unknown_evidence", "no_reviewer_date", "bad_metric", "missing_snapshot", "boolean_page", "nan_latency"])
def test_invalid_payloads_rejected(mutation):
    data = bundle()
    if mutation == "unknown_evidence":
        data["reviews"][0]["fact_reviews"][0]["evidence_ids"] = ["UNKNOWN"]
    elif mutation == "no_reviewer_date":
        data["reviews"][0]["reviewer"]["reviewed_at"] = None
    elif mutation == "bad_metric":
        data["report"]["metrics"]["service_error_rate"]["rate"] = 1
    elif mutation == "missing_snapshot":
        del data["run"]["system_snapshot"]["config_hash"]
    elif mutation == "boolean_page":
        data["observations"][0]["initial_candidates"][0]["page"] = True
    else:
        data["observations"][0]["measurements"]["latency_ms"] = float("nan")
    with pytest.raises(ContractError):
        validate_bundle(data)


def test_location_coverage_uses_stable_identity_not_runtime_ids():
    from eval.contract_v1 import location_scheme_satisfied
    group = bundle()["test_cases"][4]["evidence_groups"][0]
    refs = copy.deepcopy(group["alternatives"][1]["all_of"])
    for ref in refs:
        ref["evidence_id"] = "runtime-" + ref["evidence_id"]
    assert location_scheme_satisfied(group, refs) is True
    assert location_scheme_satisfied(group, refs[:1]) is False
    assert location_scheme_satisfied(group, None) is None
    refs[0]["document_version"] = "wrong"
    assert location_scheme_satisfied(group, refs) is False


def test_public_projection_does_not_alias_private_scope():
    case = bundle()["test_cases"][0]
    public = make_rag_input(case)
    public["query_scope"]["spec_ids"].append("other")
    assert "other" not in case["query_scope"]["spec_ids"]


def test_generator_invoked_but_context_unobserved_is_null():
    data = bundle()
    data["observations"][-1]["generator_context"] = None
    validate_bundle(data)
