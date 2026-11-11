"""Predeclared pass/fail/inconclusive decisions, separate from immutable raw runs."""
import json
from pathlib import Path

from eval.fingerprints_v1 import artifact_manifest, canonical_hash, sha256, verify_artifacts, write_json
from eval.freeze_v1 import precheck, read_bound, read_json, validate_policy
from eval.pipeline_v1 import verify_run
from eval.review_workflow_v1 import actor, initial_state, load_revision, timestamp
from eval.scoring_v1 import score, citation_legal
from eval.usage_v1 import usage_report


def evaluate_decision(bundle, state, policy, freeze):
    validate_policy(policy)
    reasons = []
    def issue(code, effect, detail):
        reasons.append({"code": code, "effect": effect, "detail": detail})
    run = bundle["run"]
    admission = run.get("admission", {})
    if admission.get("freeze_sha256") != canonical_hash(freeze):
        issue("UNBOUND_FREEZE", "inconclusive", "run was not admitted against this freeze")
    if timestamp(policy["declared_at"]) > timestamp(run["started_at"]) or timestamp(freeze["frozen_at"]) > timestamp(run["started_at"]):
        issue("LATE_FREEZE_OR_POLICY", "inconclusive", "policy or freeze declared after run started")
    if canonical_hash(policy) != canonical_hash(read_json(read_bound(freeze["bindings"]["thresholds"]))):
        issue("POLICY_NOT_BOUND", "inconclusive", "policy differs from frozen thresholds")
    observations = {o["case_id"]: o for o in bundle["observations"]}
    reviews = {r["case_id"]: r for r in state["reviews"]}
    scored = score(bundle["test_cases"], observations, reviews)
    allowed_knowledge = set(read_json(read_bound(freeze["bindings"]["knowledge_base"]))["business_ids"])
    for d in state["disputes"]:
        if d["resolution"] is None:
            issue("OPEN_DISPUTE", "inconclusive", d["dispute_id"])
    for case in bundle["test_cases"]:
        cid = case["case_id"]
        obs, review = observations[cid], reviews[cid]
        if obs["actual_action"] == "error":
            issue("SERVICE_ERROR", policy["on_service_error"], cid)
        for rule in policy["required_observations"]:
            relevant = (rule["applies_to"] == "all" or rule["applies_to"] == "answer" and case["expected_action"] == "answer"
                        or rule["applies_to"] == "generator" and obs["generator_invoked"] is not False)
            value = obs
            for part in rule["path"].split("."):
                value = value.get(part) if isinstance(value, dict) else None
            if relevant and value is None:
                issue("MISSING_OBSERVATION", policy["on_missing_observation"], cid + ":" + rule["path"])
        if cid not in scored["review_progress"]["human_reviewed_case_ids"]:
            issue("UNREVIEWED_OR_AI_ONLY", policy["on_unreviewed"], cid)
        if obs["actual_action"] == "answer" and citation_legal(obs) is False:
            issue("INVALID_CITATION", "fail", cid)
        facts = {f["fact_id"]: f for f in review["fact_reviews"]}
        if any(facts[f["fact_id"]]["numeric_conditions_correct"] is False for f in case["necessary_facts"] if f.get("numeric")):
            issue("NUMERIC_CONDITIONS_WRONG", "fail", cid)
        if review.get("answer_review", {}).get("no_material_outside_conclusions") is False:
            issue("MATERIAL_OUTSIDE_CONCLUSIONS", "fail", cid)
        requested = case["query_scope"]
        expected_ids = (set(zip(requested["spec_ids"], requested["edition_ids"])) if requested.get("edition_ids") else None)
        for ref in obs["final_decision_evidence"] or []:
            if (ref["document_id"] + "@" + ref["document_version"] not in allowed_knowledge
                    or expected_ids is not None and (ref["document_id"], ref["document_version"]) not in expected_ids
                    or expected_ids is None and requested.get("spec_ids") and ref["document_id"] not in requested["spec_ids"]):
                issue("SCOPE_VIOLATION", "fail", cid)
        if obs["actual_scope"] is not None:
            scope_ids = obs["actual_scope"].get("business_ids")
            if not isinstance(scope_ids, list) or not set(scope_ids) <= allowed_knowledge:
                issue("SCOPE_VIOLATION", "fail", cid + ":actual_scope")
            elif expected_ids is not None and not set(scope_ids) <= {d + "@" + v for d, v in expected_ids}:
                issue("SCOPE_VIOLATION", "fail", cid + ":actual_scope")
    for threshold in policy["thresholds"]:
        name = threshold["metric"]
        if name.startswith("performance."):
            try:
                _, group, field, statistic = name.split(".")
                value = scored["performance"][group][field][statistic]
            except (ValueError, KeyError):
                value = None
        else:
            value = scored["metrics"].get(name, {}).get("rate")
        if value is None:
            issue("METRIC_UNAVAILABLE", policy["on_missing_observation"], name)
        elif not (value >= threshold["value"] if threshold["op"] == ">=" else value <= threshold["value"]):
            issue("THRESHOLD_NOT_MET", "fail", {"metric": name, "observed": value, **threshold})
    effects = {r["effect"] for r in reasons}
    conclusion = "fail" if "fail" in effects else "inconclusive" if effects else "pass"
    return {"schema_version": "rag-eval.decision.v1", "run_id": run["run_id"], "conclusion": conclusion,
            "purpose": freeze["purpose"], "reasons": reasons, "scored_report": scored,
            "provider_usage_summary": usage_report(list(observations.values())),
            "notice": "REHEARSAL ONLY; no independent acceptance" if freeze["purpose"] == "rehearsal" else "Frozen independent assessment",
            "identity_assurance": "review/signature identities are asserted metadata, not authenticated digital signatures"}


def sign_assessment(run_directory, output, *, signer, revision=None):
    """Create a new signed assessment; original output and review files remain intact."""
    actor(signer, human=True)
    run_directory = Path(run_directory).resolve()
    bundle = verify_run(run_directory, verify_live_sources=False)
    if timestamp(signer["at"]) < timestamp(bundle["run"]["completed_at"]):
        raise ValueError("signer timestamp precedes run completion")
    admission = bundle["run"].get("admission")
    if not admission:
        raise ValueError("cannot sign unbound legacy/development run with retrospective thresholds")
    if sha256(admission["freeze_path"]) != admission["freeze_file_sha256"]:
        raise ValueError("freeze artifact changed")
    freeze = read_json(admission["freeze_path"])
    checked = precheck(freeze, allow_claimed_attempt=True)
    if not checked["eligible"]:
        raise ValueError("signing blocked by freeze changes: " + json.dumps(checked["reasons"]))
    state = load_revision(revision)[1] if revision else initial_state(bundle, sha256(run_directory / "bundle.json"))
    if state["base_bundle_sha256"] != sha256(run_directory / "bundle.json"):
        raise ValueError("review lineage belongs to another run")
    for r in state["reviews"]:
        reviewed_at = r["reviewer"].get("reviewed_at")
        if reviewed_at and timestamp(reviewed_at) > timestamp(signer["at"]):
            raise ValueError("signature precedes review")
    policy = read_json(read_bound(freeze["bindings"]["thresholds"]))
    decision = evaluate_decision(bundle, state, policy, freeze)
    decision.update({"signer": signer, "run_bundle_sha256": sha256(run_directory / "bundle.json"),
                     "review_state_sha256": canonical_hash(state), "freeze_sha256": canonical_hash(freeze),
                     "policy_sha256": sha256(freeze["bindings"]["thresholds"]["path"])})
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    refs = {"run_directory": str(run_directory), "revision_directory": str(Path(revision).resolve()) if revision else None}
    write_json(output / "decision.json", decision)
    write_json(output / "lineage.json", refs)
    with (output / "decision.md").open("x", encoding="utf-8") as stream:
        stream.write(f"# {decision['conclusion']}\n\n{decision['notice']}\n\n" + json.dumps(decision["reasons"], ensure_ascii=False, indent=2) + "\n")
    write_json(output / "integrity.json", artifact_manifest(output, [output / n for n in ("decision.json", "lineage.json", "decision.md")]))
    verify_assessment(output)
    return decision


def verify_assessment(directory):
    directory = Path(directory)
    verify_artifacts(directory, read_json(directory / "integrity.json"))
    decision, refs = read_json(directory / "decision.json"), read_json(directory / "lineage.json")
    bundle = verify_run(refs["run_directory"], verify_live_sources=False)
    if sha256(Path(refs["run_directory"]) / "bundle.json") != decision["run_bundle_sha256"]:
        raise ValueError("assessment original run changed")
    state = load_revision(refs["revision_directory"])[1] if refs["revision_directory"] else initial_state(bundle, decision["run_bundle_sha256"])
    if canonical_hash(state) != decision["review_state_sha256"]:
        raise ValueError("assessment review state changed")
    admission = bundle["run"]["admission"]
    if "attempt" in admission:
        read_bound(admission["attempt"])
    freeze = read_json(read_bound({"path": admission["freeze_path"], "sha256": admission["freeze_file_sha256"]}))
    policy = read_json(read_bound(freeze["bindings"]["thresholds"]))
    computed = evaluate_decision(bundle, state, policy, freeze)
    if any(decision.get(k) != v for k, v in computed.items()):
        raise ValueError("decision does not reproduce from immutable lineage")
    actor(decision["signer"], human=True)
    if timestamp(decision["signer"]["at"]) < timestamp(bundle["run"]["completed_at"]):
        raise ValueError("signature predates completion")
    if decision["freeze_sha256"] != canonical_hash(freeze) or decision["policy_sha256"] != sha256(freeze["bindings"]["thresholds"]["path"]):
        raise ValueError("assessment policy/freeze binding mismatch")
    return decision
