"""Immutable review revisions. Human identities are asserted, never authenticated here."""
import copy
import json
from datetime import datetime
from pathlib import Path

from eval.contract_v1 import validate_review
from eval.fingerprints_v1 import artifact_manifest, canonical_hash, sha256, verify_artifacts, write_json
from eval.pipeline_v1 import verify_run
from eval.scoring_v1 import case_quality


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be a timezone-aware ISO string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp requires timezone")
    return parsed


def actor(value, *, human=False):
    if not isinstance(value, dict) or set(value) != {"identity", "type", "at"}:
        raise ValueError("actor requires identity/type/at")
    if not isinstance(value["identity"], str) or not value["identity"].strip() or value["identity"] == "unassigned":
        raise ValueError("actor identity is missing")
    if value["type"] not in {"human", "ai"} or (human and value["type"] != "human"):
        raise ValueError("human actor required")
    timestamp(value["at"])


def strict_review(review, case, observation):
    allowed = {"schema_version", "case_id", "reviewer", "fact_reviews", "claim_reviews",
               "behavior_review", "answer_review", "human_approved", "adjudication",
               "numeric_constraint_reviews_v2", "refusal_review_v2", "clarification_review_v2"}
    if not isinstance(review, dict) or set(review) - allowed:
        raise ValueError("unknown review fields")
    for key in ("fact_reviews", "claim_reviews"):
        if not isinstance(review.get(key), list) or not all(isinstance(row, dict) for row in review[key]):
            raise ValueError("review rows must be objects")
    nested_fields = {
        "reviewer": {"identity", "reviewer_type", "reviewed_at", "rubric_version"},
        "behavior_review": {"appropriate", "reason"},
        "answer_review": {"claims_exhaustive", "no_contradictions", "no_material_outside_conclusions", "citations_support_claims"}}
    for key, fields in nested_fields.items():
        if key in review and (not isinstance(review[key], dict) or set(review[key]) != fields):
            raise ValueError("invalid nested review fields: " + key)
    for row in review["fact_reviews"]:
        if set(row) != {"fact_id", "context_supported", "final_evidence_supported", "numeric_conditions_correct", "answer_covered", "correct", "evidence_ids", "reason"}:
            raise ValueError("invalid fact review fields")
    for row in review["claim_reviews"]:
        if set(row) != {"claim_id", "text", "support", "evidence_ids", "reason"}:
            raise ValueError("invalid claim review fields")
    if review.get("adjudication") is not None:
        raise ValueError("adjudications must be imported as versioned dispute resolutions")
    validate_review(review, case, observation)
    reviewer = review["reviewer"]
    if reviewer["reviewed_at"]:
        timestamp(reviewer["reviewed_at"])
    if not isinstance(review["behavior_review"].get("reason"), str):
        raise ValueError("behavior review reason required")
    for row in review["claim_reviews"]:
        if row["support"] == "supported" and not row["evidence_ids"]:
            raise ValueError("supported claim requires evidence")
    for row in review["fact_reviews"]:
        if (row["context_supported"] is True or row["final_evidence_supported"] is True) and not row["evidence_ids"]:
            raise ValueError("supported fact requires evidence")
        for key, stage in (("context_supported", "generator_context"), ("final_evidence_supported", "final_decision_evidence")):
            available = {e["evidence_id"] for e in observation[stage] or []}
            if row[key] is True and not available.intersection(row["evidence_ids"]):
                raise ValueError("support review does not reference the observed stage")
    if review.get("human_approved") is True:
        actor({"identity": reviewer["identity"], "type": reviewer["reviewer_type"], "at": reviewer["reviewed_at"]}, human=True)
        if case_quality(case, observation, review)["task_success"] is None:
            raise ValueError("cannot approve unreviewed task quality")
        if observation["actual_action"] == "answer":
            flags = review.get("answer_review", {})
            if not flags or any(type(v) is not bool for v in flags.values()):
                raise ValueError("human answer approval requires complete answer review")
            for f, r in zip(sorted(case["necessary_facts"], key=lambda x: x["fact_id"]),
                            sorted(review["fact_reviews"], key=lambda x: x["fact_id"])):
                required = ["answer_covered", "correct"]
                if observation["final_decision_evidence"] is not None:
                    required.append("final_evidence_supported")
                if observation["generator_context"] is not None:
                    required.append("context_supported")
                if f.get("numeric"):
                    required.append("numeric_conditions_correct")
                if any(type(r[k]) is not bool for k in required):
                    raise ValueError("human approval requires complete fact review")
            if any(c["support"] is None for c in review["claim_reviews"]):
                raise ValueError("human approval requires complete claim review")


def apply_packet(bundle, prior, packet):
    if set(packet) != {"schema_version", "actor", "base_bundle_sha256", "parent_state_sha256", "changes", "disputes", "adjudications"}:
        raise ValueError("review packet fields invalid")
    if packet["schema_version"] != "rag-eval.review-change.v1":
        raise ValueError("unsupported review packet")
    actor(packet["actor"])
    prior_dates = [r["reviewer"]["reviewed_at"] for r in prior["reviews"] if r["reviewer"].get("reviewed_at")]
    prior_dates += [d["opened_by"]["at"] for d in prior["disputes"]]
    prior_dates += [d["resolution"]["actor"]["at"] for d in prior["disputes"] if d.get("resolution")]
    if any(timestamp(packet["actor"]["at"]) < timestamp(date) for date in prior_dates):
        raise ValueError("review change predates its parent")
    expected_parent = canonical_hash(prior)
    if packet["parent_state_sha256"] != expected_parent or packet["base_bundle_sha256"] != prior["base_bundle_sha256"]:
        raise ValueError("stale or foreign review packet")
    rows = {r["case_id"]: copy.deepcopy(r) for r in prior["reviews"]}
    cases = {c["case_id"]: c for c in bundle["test_cases"]}
    observations = {o["case_id"]: o for o in bundle["observations"]}
    disputes = {d["dispute_id"]: copy.deepcopy(d) for d in prior["disputes"]}
    changed, events = set(), []
    for change in packet["changes"]:
        if set(change) != {"case_id", "previous_review_sha256", "review", "reason"}:
            raise ValueError("change fields invalid")
        cid = change["case_id"]
        if cid not in rows or cid in changed:
            raise ValueError("unknown/duplicate review change")
        if not isinstance(change["reason"], str) or not change["reason"].strip():
            raise ValueError("change reason missing")
        if canonical_hash(rows[cid]) != change["previous_review_sha256"]:
            raise ValueError("stale review hash")
        r = change["review"]
        if r.get("case_id") != cid:
            raise ValueError("review case mismatch")
        reviewer = r["reviewer"]
        if (reviewer["identity"], reviewer["reviewer_type"], reviewer["reviewed_at"]) != (
                packet["actor"]["identity"], packet["actor"]["type"], packet["actor"]["at"]):
            raise ValueError("reviewer/actor mismatch")
        strict_review(r, cases[cid], observations[cid])
        if reviewer["rubric_version"] != bundle["run"]["evaluation_snapshot"]["rubric_version"]:
            raise ValueError("review rubric hash differs from run rules")
        events.append({"case_id": cid, "before_sha256": canonical_hash(rows[cid]),
                       "after_sha256": canonical_hash(r), "reason": change["reason"], "actor": packet["actor"]})
        rows[cid] = copy.deepcopy(r)
        changed.add(cid)
    for dispute in packet["disputes"]:
        if set(dispute) != {"dispute_id", "case_id", "field", "reason", "review_sha256"}:
            raise ValueError("dispute fields invalid")
        did, cid = dispute["dispute_id"], dispute["case_id"]
        if not isinstance(did, str) or not did.strip() or did in disputes or cid not in rows:
            raise ValueError("unknown case or duplicate dispute")
        if any(not isinstance(dispute[k], str) or not dispute[k].strip() for k in ("field", "reason")):
            raise ValueError("dispute field/reason required")
        if dispute["review_sha256"] != canonical_hash(rows[cid]):
            raise ValueError("dispute review hash mismatch")
        try:
            if not dispute["field"].startswith("/"):
                raise ValueError("use a review JSON pointer")
            target = rows[cid]
            for part in dispute["field"][1:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                target = target[int(part)] if isinstance(target, list) else target[part]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError("dispute field does not exist") from exc
        disputes[did] = {**dispute, "opened_by": packet["actor"], "resolution": None}
    resolved = set()
    for resolution in packet["adjudications"]:
        if set(resolution) != {"dispute_id", "decision", "reason", "review_sha256"}:
            raise ValueError("adjudication fields invalid")
        actor(packet["actor"], human=True)
        did = resolution["dispute_id"]
        if did not in disputes or did in resolved or disputes[did]["resolution"] is not None:
            raise ValueError("unknown or already adjudicated dispute")
        cid = disputes[did]["case_id"]
        if resolution["decision"] not in {"uphold", "replace"} or not isinstance(resolution["reason"], str) or not resolution["reason"].strip():
            raise ValueError("adjudication decision/reason invalid")
        if resolution["review_sha256"] != canonical_hash(rows[cid]):
            raise ValueError("adjudication review hash mismatch")
        if resolution["decision"] == "replace" and cid not in changed:
            raise ValueError("replace adjudication requires explicit review change")
        disputes[did]["resolution"] = {**resolution, "actor": packet["actor"]}
        resolved.add(did)
    return {"schema_version": "rag-eval.review-state.v1", "base_bundle_sha256": prior["base_bundle_sha256"],
            "parent_state_sha256": expected_parent, "packet_sha256": canonical_hash(packet),
            "reviews": [rows[c] for c in sorted(rows)], "disputes": [disputes[d] for d in sorted(disputes)],
            "changes": events, "identity_assurance": "asserted identity; not a cryptographic or professional credential verification"}


def initial_state(bundle, bundle_hash):
    return {"schema_version": "rag-eval.review-state.v1", "base_bundle_sha256": bundle_hash,
            "reviews": copy.deepcopy(bundle["reviews"]), "disputes": []}


def load_revision(directory, *, _seen=None):
    directory = Path(directory).resolve()
    seen = set() if _seen is None else _seen
    if directory in seen:
        raise ValueError("cyclic review lineage")
    seen.add(directory)
    def read(name):
        return json.loads((directory / name).read_text(encoding="utf-8"))
    verify_artifacts(directory, read("integrity.json"))
    lineage, packet, state = read("lineage.json"), read("packet.json"), read("state.json")
    if "packet_original_sha256" in lineage:
        if sha256(directory / "packet-original.json") != lineage["packet_original_sha256"] or read("packet-original.json") != packet:
            raise ValueError("original submitted review packet changed")
    bundle = verify_run(lineage["run_directory"], verify_live_sources=False)
    if sha256(Path(lineage["run_directory"]) / "bundle.json") != lineage["base_bundle_sha256"]:
        raise ValueError("original run changed")
    prior = (load_revision(lineage["parent_directory"], _seen=seen)[1] if lineage["parent_directory"]
             else initial_state(bundle, lineage["base_bundle_sha256"]))
    if state != apply_packet(bundle, prior, packet):
        raise ValueError("review revision cannot be replayed")
    return bundle, state


def import_reviews(run_directory, packet_path, output, *, parent=None):
    run_directory = Path(run_directory).resolve()
    bundle = verify_run(run_directory, verify_live_sources=False)
    base_hash = sha256(run_directory / "bundle.json")
    prior = load_revision(parent)[1] if parent else initial_state(bundle, base_hash)
    if prior["base_bundle_sha256"] != base_hash:
        raise ValueError("parent belongs to a different run")
    original_packet = Path(packet_path).read_bytes()
    packet = json.loads(original_packet.decode("utf-8"))
    state = apply_packet(bundle, prior, packet)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    lineage = {"run_directory": str(run_directory), "base_bundle_sha256": base_hash,
               "parent_directory": str(Path(parent).resolve()) if parent else None}
    with (output / "packet-original.json").open("xb") as stream:
        stream.write(original_packet)
    lineage["packet_original_sha256"] = sha256(output / "packet-original.json")
    for name, value in (("packet.json", packet), ("state.json", state), ("lineage.json", lineage)):
        write_json(output / name, value)
    write_json(output / "integrity.json", artifact_manifest(output, [output / n for n in ("packet.json", "state.json", "lineage.json", "packet-original.json")]))
    load_revision(output)
    return state


def export_review_template(run_directory, output, *, parent=None):
    """A deliberately invalid-to-import draft until the actual reviewer fills it."""
    run_directory = Path(run_directory).resolve()
    bundle = verify_run(run_directory, verify_live_sources=False)
    base = sha256(run_directory / "bundle.json")
    state = load_revision(parent)[1] if parent else initial_state(bundle, base)
    if state["base_bundle_sha256"] != base:
        raise ValueError("review parent belongs to another run")
    changes = []
    for original in state["reviews"]:
        r = copy.deepcopy(original)
        r["reviewer"] = {"identity": "", "reviewer_type": "human", "reviewed_at": None,
                         "rubric_version": bundle["run"]["evaluation_snapshot"]["rubric_version"]}
        r["human_approved"] = None
        changes.append({"case_id": r["case_id"], "previous_review_sha256": canonical_hash(original), "review": r, "reason": ""})
    packet = {"schema_version": "rag-eval.review-change.v1", "actor": {"identity": "", "type": "human", "at": None},
              "base_bundle_sha256": base, "parent_state_sha256": canonical_hash(state),
              "changes": changes, "disputes": [], "adjudications": []}
    write_json(output, packet)
    return packet
