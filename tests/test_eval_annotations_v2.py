import copy

import pytest

from eval.contract_v1 import ContractError, make_rag_input, validate_review, validate_test_case
from eval.scoring_v1 import case_quality, pending_review


def synthetic(action):
    case = {"schema_version": "rag-eval.test-case.v2", "case_id": "SYN-" + action,
            "dataset_role": "synthetic", "question": "合成问题", "query_scope": {"spec_ids": ["SYN"], "edition_ids": ["v1"]},
            "expected_action": action, "reference_answer": "合成答案" if action == "answer" else None,
            "necessary_facts": [{"fact_id": "F1", "description": "合成限值"}] if action == "answer" else [],
            "evidence_groups": [{"fact_id": "F1", "alternatives": [{"scheme_id": "S1", "all_of": [{"evidence_id": "E1", "document_id": "SYN", "document_version": "v1", "page": 1, "article": "1"}]}]}] if action == "answer" else []}
    if action == "answer":
        case["numeric_constraints_v2"] = [{"constraint_id": "N1", "value": "2", "unit": "m", "comparison": ">=", "conditions": ["地下", "有设备"], "fact_ids": ["F1"], "link_semantics": "all_facts"}]
    elif action == "refuse":
        case["refusal_annotation_v2"] = {"supported_facts": [{"fact_id": "S1", "description": "一般限值"}], "missing_facts": [{"fact_id": "M1", "description": "现场实测"}], "allowed_explanation": ["可说明一般限值"]}
    else:
        case["clarification_annotation_v2"] = {"required_fields": ["车辆类型"], "branches": [{"branch_id": "A", "when": {"车辆类型": "A"}, "evidence_groups": [{"fact_id": "FUTURE", "alternatives": [{"scheme_id": "S", "all_of": [{"evidence_id": "B1", "document_id": "SYN", "document_version": "v1", "page": 2, "table": "T1"}]}]}]}]}
    return case


@pytest.mark.parametrize("action", ["answer", "refuse", "clarify"])
def test_v2_validation_and_public_boundary(action):
    case = synthetic(action)
    validate_test_case(case)
    assert set(make_rag_input(case)) == {"schema_version", "case_id", "question", "query_scope"}
    review = pending_review(case)
    observation = {"case_id": case["case_id"], "actual_action": action, "answer_text": "合成答案",
                   "citations": [], "final_decision_evidence": [], "generator_context": None,
                   "initial_candidates": [], "reranked_results": []}
    validate_review(review, case, observation)
    if action != "answer":
        review["behavior_review"]["appropriate"] = True
        assert case_quality(case, observation, review)["task_success"] is None
        key = "refusal_review_v2" if action == "refuse" else "clarification_review_v2"
        for flag in review[key]:
            if flag != "reason":
                review[key][flag] = True
        assert case_quality(case, observation, review)["task_success"] is True


def test_numeric_link_and_review_are_required():
    case = synthetic("answer")
    bad = copy.deepcopy(case)
    bad["numeric_constraints_v2"][0]["fact_ids"] = ["OTHER"]
    with pytest.raises(ContractError):
        validate_test_case(bad)
    obs = {"case_id": case["case_id"], "actual_action": "answer", "initial_candidates": [],
           "reranked_results": [], "final_decision_evidence": [], "generator_context": None}
    review = pending_review(case)
    review["numeric_constraint_reviews_v2"] = []
    with pytest.raises(ContractError):
        validate_review(review, case, obs)
