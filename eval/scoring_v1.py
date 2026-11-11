"""Contract-v1 metrics; no inference from reference wording or missing reviews."""
import math
from collections import Counter

from eval.contract_v1 import location_scheme_satisfied


def all_known(values):
    values = list(values)
    if any(value is False for value in values):
        return False
    if not values or any(value is None for value in values):
        return None
    return True


def aggregate(values, *, mode="rate"):
    """Strict full-population rate plus observed subset and confirmed lower bound."""
    values = dict(sorted(values.items()))
    known = {key: value for key, value in values.items() if value is not None}
    total = len(values)
    numerator = sum(known.values())
    return {"kind": mode, "numerator": numerator, "denominator": total,
            "rate": numerator / total if total and len(known) == total else None,
            "applicable_case_ids": list(values), "observed_case_ids": list(known),
            "missing_case_ids": [key for key, value in values.items() if value is None],
            "observed_rate": numerator / len(known) if known else None,
            "observed_denominator": len(known),
            "confirmed_lower_bound": numerator / total if total else None,
            "case_values": values}


def citation_legal(obs):
    if obs["actual_action"] != "answer":
        return None
    if not obs["citations"]:
        return False
    return all_known(c[key] for c in obs["citations"] for key in ("parse_valid", "scope_valid"))


def pending_review(case):
    review = {"schema_version": "rag-eval.review.v1", "case_id": case["case_id"],
            "reviewer": {"identity": "unassigned", "reviewer_type": "human",
                         "reviewed_at": None, "rubric_version": "metrics-v1"},
            "fact_reviews": [{"fact_id": f["fact_id"], "context_supported": None,
                              "final_evidence_supported": None, "numeric_conditions_correct": None,
                              "answer_covered": None, "correct": None, "evidence_ids": [],
                              "reason": "unreviewed"} for f in case["necessary_facts"]],
            "claim_reviews": [], "behavior_review": {"appropriate": None, "reason": "unreviewed"},
            "answer_review": {"claims_exhaustive": None, "no_contradictions": None,
                              "no_material_outside_conclusions": None, "citations_support_claims": None},
            "human_approved": None, "adjudication": None}
    if case["schema_version"] == "rag-eval.test-case.v2":
        review["numeric_constraint_reviews_v2"] = [{"constraint_id": c["constraint_id"], "correct": None, "reason": "unreviewed"} for c in case.get("numeric_constraints_v2", [])]
        if case["expected_action"] == "refuse" and case.get("refusal_annotation_v2"):
            review["refusal_review_v2"] = {"missing_facts_not_asserted": None, "explanation_within_allowed": None, "reason": "unreviewed"}
        if case["expected_action"] == "clarify" and case.get("clarification_annotation_v2"):
            review["clarification_review_v2"] = {"required_fields_requested": None, "no_premature_branch_answer": None, "reason": "unreviewed"}
    return review


def case_quality(case, obs, review):
    facts = {f["fact_id"]: f for f in review["fact_reviews"]}
    actual, expected = obs["actual_action"], case["expected_action"]
    full_evidence = (all_known(f["final_evidence_supported"] for f in facts.values())
                     if obs["final_decision_evidence"] is not None else None)
    context = (all_known(f["context_supported"] for f in facts.values())
               if obs["generator_context"] is not None else None)
    claims = review["claim_reviews"]
    flags = review.get("answer_review", {})
    full_answer = False if actual != "answer" else all_known([
        bool((obs["answer_text"] or "").strip()),
        bool(claims) if flags.get("claims_exhaustive") is True else None, citation_legal(obs),
        *[f[key] for f in facts.values() for key in ("answer_covered", "correct")],
        *[facts[f["fact_id"]]["numeric_conditions_correct"] for f in case["necessary_facts"] if f.get("numeric")],
        *[r["correct"] for r in review.get("numeric_constraint_reviews_v2", [])],
        *[flags.get(key) for key in ("claims_exhaustive", "no_contradictions",
                                    "no_material_outside_conclusions", "citations_support_claims")],
        *[None if c["support"] is None else c["support"] == "supported" for c in claims],
    ])
    support = None
    if actual == "answer" and expected == "answer":
        if flags.get("claims_exhaustive") is True and claims and all(c["support"] is not None for c in claims):
            support = sum(c["support"] == "supported" for c in claims) / len(claims)
        elif flags.get("claims_exhaustive") is True and not claims:
            support = 0.0  # invalid, never an empty-set perfect score
    success = False if actual != expected else (full_answer if expected == "answer" else review["behavior_review"]["appropriate"])
    if actual == expected == "refuse" and case.get("refusal_annotation_v2"):
        b = review.get("refusal_review_v2", {})
        success = all_known([success, b.get("missing_facts_not_asserted"), b.get("explanation_within_allowed")])
    if actual == expected == "clarify" and case.get("clarification_annotation_v2"):
        b = review.get("clarification_review_v2", {})
        success = all_known([success, b.get("required_fields_requested"), b.get("no_premature_branch_answer")])
    return {"final_fact_complete": full_evidence, "generator_fact_complete": context,
            "complete_correct_answer": full_answer, "evidence_support": support,
            "task_success": success, "citation_legal": citation_legal(obs)}


def retrieval_metrics(cases, observations):
    answerable = [c for c in cases if c["expected_action"] == "answer"]
    stages = {"initial_candidates", "initial_reranked"}
    stages |= {f"round:{r['round_id']}:{key}" for o in observations.values()
               for r in (o["retrieval_rounds"] or []) for key in ("candidates", "reranked")}
    metrics = {}
    def stage_rows(obs, stage):
        if stage == "initial_candidates":
            return obs["initial_candidates"]
        if stage == "initial_reranked":
            return obs["reranked_results"]
        _, rid, key = stage.split(":")
        row = next((r for r in (obs["retrieval_rounds"] or []) if r["round_id"] == rid), None)
        return row[key] if row else None
    for stage in sorted(stages):
        for k in (1, 3, 5, 10):
            recall, hits, micro = {}, {}, {}
            for case in answerable:
                cid = case["case_id"]
                rows = stage_rows(observations[cid], stage)
                matched = [location_scheme_satisfied(g, None if rows is None else rows[:k])
                           for g in case["evidence_groups"]]
                recall[cid] = None if rows is None else sum(matched) / len(matched)
                hits[cid] = None if rows is None else any(matched)
                for index, value in enumerate(matched):
                    micro[f"{cid}/{index+1}"] = value
            metrics[f"{stage}.recall@{k}"] = aggregate(recall, mode="macro")
            metrics[f"{stage}.hitrate@{k}"] = aggregate(hits)
            # Fact-level micro metric is a diagnostic separate from the A-case macro mean.
            m = aggregate(micro)
            m["unit"] = "case/fact-group"
            metrics[f"{stage}.recall_micro@{k}"] = m
        reciprocal = {}
        for case in answerable:
            cid = case["case_id"]
            rows = stage_rows(observations[cid], stage)
            if rows is None:
                reciprocal[cid] = None
                continue
            # First relevant position, including an individual AND-scheme member.
            gold_refs = [ref for g in case["evidence_groups"] for a in g["alternatives"] for ref in a["all_of"]]
            rank = next((i for i, row in enumerate(rows[:10], 1)
                         if any(location_scheme_satisfied({"alternatives": [{"all_of": [ref]}]}, [row]) for ref in gold_refs)), None)
            reciprocal[cid] = 1 / rank if rank else 0
        metrics[f"{stage}.mrr@10"] = aggregate(reciprocal, mode="macro")
    return metrics


def performance(cases, observations):
    def summarize(ids):
        out = {"case_ids": ids, "actual_actions": dict(Counter(observations[cid]["actual_action"] for cid in ids))}
        for key in ("latency_ms", "model_calls", "input_tokens", "output_tokens"):
            vals = sorted(observations[cid]["measurements"][key] for cid in ids
                          if observations[cid]["measurements"][key] is not None)
            out[key] = {"observed_count": len(vals), "total_count": len(ids),
                        "observed_fraction": len(vals) / len(ids) if ids else None,
                        "observed_sum": sum(vals) if vals else None,
                        "p50": vals[math.ceil(.5*len(vals))-1] if vals else None,
                        "p95": vals[math.ceil(.95*len(vals))-1] if vals else None}
        return out
    groups = {"all": [c["case_id"] for c in cases]}
    for case in cases:
        cid = case["case_id"]
        for name in (f"expected:{case['expected_action']}", f"type:{case.get('question_type', 'unspecified')}",
                     f"outcome:{observations[cid]['actual_action']}"):
            groups.setdefault(name, []).append(cid)
    return {name: summarize(ids) for name, ids in sorted(groups.items())}


def score(cases, observations, reviews, *, _grouped=True):
    quality = {c["case_id"]: case_quality(c, observations[c["case_id"]], reviews[c["case_id"]]) for c in cases}
    expected = {a: [c["case_id"] for c in cases if c["expected_action"] == a] for a in ("answer", "refuse", "clarify")}
    metrics = retrieval_metrics(cases, observations)
    for name, field, ids in (
        ("final_fact_complete", "final_fact_complete", expected["answer"]),
        ("complete_correct_answer", "complete_correct_answer", expected["answer"]),
        ("generator_fact_complete", "generator_fact_complete", [cid for cid in expected["answer"] if observations[cid]["generator_invoked"]]),
        ("evidence_support", "evidence_support", [cid for cid in expected["answer"] if observations[cid]["actual_action"] == "answer"]),
        ("citation_legal", "citation_legal", [cid for cid in observations if observations[cid]["actual_action"] == "answer"]),
        ("task_success", "task_success", list(observations)),
    ):
        metrics[name] = aggregate({cid: quality[cid][field] for cid in ids}, mode="macro" if name == "evidence_support" else "rate")
    for name, ids, action in (
        ("false_accept", expected["refuse"], "answer"),
        ("false_refuse", expected["answer"], "refuse"),
        ("clarify_action_correct", expected["clarify"], "clarify"),
        ("service_error", list(observations), "error"),
    ):
        metrics[name] = aggregate({cid: observations[cid]["actual_action"] == action for cid in ids})
    confusion = {a: {b: 0 for b in ("answer", "refuse", "clarify", "error")} for a in expected}
    for case in cases:
        confusion[case["expected_action"]][observations[case["case_id"]]["actual_action"]] += 1
    human = [cid for cid, r in reviews.items() if r["reviewer"]["reviewer_type"] == "human" and r["reviewer"]["reviewed_at"]
             and r.get("human_approved") is True and quality[cid]["task_success"] is not None]
    for stage, field in (("final", "final_decision_evidence"), ("generator", "generator_context")):
        ids = expected["answer"] if stage == "final" else [cid for cid in expected["answer"] if observations[cid]["generator_invoked"]]
        positional = {}
        for case in cases:
            cid = case["case_id"]
            if cid in ids:
                rows = observations[cid][field]
                positional[cid] = (all(location_scheme_satisfied(g, rows) for g in case["evidence_groups"])
                                   if rows is not None else None)
        metrics[f"{stage}_position_complete_diagnostic"] = aggregate(positional)
    human_lower = sum(quality[cid]["task_success"] is True for cid in human) / len(cases) if cases else None
    automatic = {"false_accept", "false_refuse", "clarify_action_correct", "service_error", "citation_legal"}
    scoring_modes = {name: "automatic_location_or_behavior" if name in automatic or "." in name or name.endswith("_diagnostic")
                     else "review_required_provisional" for name in metrics}
    result = {"metrics": metrics, "case_quality": quality, "confusion_matrix": confusion,
            "metric_scoring_modes": scoring_modes,
            "performance": performance(cases, observations),
            "review_progress": {"human_reviewed_case_ids": human,
                                "ai_reviewed_case_ids": [cid for cid, r in reviews.items() if r["reviewer"]["reviewer_type"] == "ai" and r["reviewer"]["reviewed_at"]],
                                "pending_quality_case_ids": [cid for cid, q in quality.items() if q["task_success"] is None],
                                "human_confirmed_task_success_lower_bound": human_lower,
                                "human_approval_complete": len(human) == len(cases) and bool(cases)},
            "scoring_note": "Semantic scores may include disclosed AI reviews; no acceptance without human approval and frozen thresholds."}
    result["generator_invocation_observation"] = {
        "unknown_case_ids": sorted(cid for cid in expected["answer"] if observations[cid]["generator_invoked"] is None),
        "known_invoked_case_ids": sorted(cid for cid in expected["answer"] if observations[cid]["generator_invoked"] is True),
        "note": "Context metric denominator is conditional on observed generator calls; unknown invocation is separately disclosed."}
    if _grouped:
        groups = {}
        for case in cases:
            for key in ("expected:" + case["expected_action"], "type:" + case.get("question_type", "unspecified")):
                groups.setdefault(key, []).append(case)
        result["grouped_metrics"] = {
            key: score(items, {c["case_id"]: observations[c["case_id"]] for c in items},
                       {c["case_id"]: reviews[c["case_id"]] for c in items}, _grouped=False)["metrics"]
            for key, items in sorted(groups.items())}
    return result
