"""Offline old-dev rehearsal. All approval/signature roles here are synthetic fixtures."""
import argparse
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from eval.adapter_v1 import WorkflowAdapter
from eval.decision_v1 import sign_assessment
from eval.fingerprints_v1 import canonical_hash, lock_inventory, sha256, source_snapshot, write_json
from eval.freeze_v1 import inspect_knowledge_base, precheck, write_freeze
from eval.offline_workflow_v1 import DOC, EDITION, SOURCE, convert_seen_examples, fixture_workflow
from eval.pipeline_v1 import EVALUATION_SOURCE_FILES, run_pipeline
from eval.review_workflow_v1 import import_reviews, initial_state


def now():
    return datetime.now(timezone.utc).isoformat()


def fixture_actor(kind="ai"):
    return {"identity": "SYNTHETIC-" + kind.upper() + "-ROLE-NOT-A-REAL-REVIEWER", "type": kind, "at": now()}


def fixture_policy():
    return {"schema_version": "rag-eval.policy.v1", "policy_id": "synthetic-rehearsal-only",
            "declared_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
            "on_missing_observation": "inconclusive", "on_unreviewed": "inconclusive", "on_service_error": "fail",
            "required_observations": [{"path": "measurements.latency_ms", "applies_to": "all"},
                                      {"path": "generator_context", "applies_to": "generator"}],
            "thresholds": [{"metric": "task_success", "op": ">=", "value": 1}],
            "require_human_approval": True,
            "hard_failures": ["invalid_citation", "numeric_conditions_wrong", "material_outside_conclusions", "scope_violation"],
            "rerun_policy": {"allowed": False, "merge": "none", "retain_all_attempts": True},
            "allow_unavailable_model_revision": True}


def prepare_fixture(directory):
    root = Path(__file__).resolve().parent.parent
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    cases = convert_seen_examples(root / "eval/datasets/dev_v0.jsonl", ["SEM-001", "SEM-002"])
    dataset = directory / "old-dev-cases.json"
    write_json(dataset, cases)
    # Fake document/index bytes test hash binding only; these are never loaded by FAISS.
    (directory / "data").mkdir()
    pdf = directory / "data/fake-document.pdf"
    pdf.write_bytes(b"synthetic document bytes for hash rehearsal; not an actual PDF")
    catalog = directory / "data/catalog.json"
    write_json(catalog, {"documents": [{"spec_id": DOC, "edition_id": EDITION,
                                        "local_pdf_path": "data/fake-document.pdf", "pdf_sha256": sha256(pdf)}]})
    kb = directory / "knowledge"
    document = kb / "documents/fixture"
    document.mkdir(parents=True)
    (document / "index.faiss").write_bytes(b"synthetic index bytes; not a FAISS index")
    write_json(document / "metadata.json", {"notice": "synthetic index metadata"})
    write_json(document / "manifest.json", {
        "schema_version": 1, "spec_id": DOC, "edition_id": EDITION, "source": SOURCE,
        "source_pdf_sha256": sha256(pdf), "ingestion_artifact_sha256": "0"*64,
        "parser_version": "fixture", "embedding_model": "offline-embedding", "embedding_revision": None,
        "chunk_size": 300, "overlap": 50, "version_id": "fixture-version", "embedding_dim": 1, "chunk_count": 2,
        "index_file": "index.faiss", "metadata_file": "metadata.json",
        "index_sha256": sha256(document / "index.faiss"), "metadata_sha256": sha256(document / "metadata.json")})
    refs = [{"business_id": DOC + "@" + EDITION, "version_id": "fixture-version",
             "manifest_path": "documents/fixture/manifest.json", "manifest_sha256": sha256(document / "manifest.json")}]
    sid = canonical_hash({"documents": refs})
    (kb / "snapshots" / sid).mkdir(parents=True)
    write_json(kb / "snapshots" / sid / "manifest.json", {"schema_version": 1, "documents": refs})
    write_json(kb / "active.json", {"schema_version": 1, "snapshot_id": sid})
    knowledge = inspect_knowledge_base(kb, catalog)
    policy = fixture_policy()
    public = {"embedding_model": "offline-embedding", "reranker_model": "offline-reranker", "generation_model": "offline-generation",
              "retrieval_top_k": 10, "evidence_top_n": 3, "max_model_calls": 6, "total_timeout_seconds": 90.0}
    models = {key: {"id": public[key + "_model" if key != "generation" else "generation_model"],
                    "revision": None, "revision_status": "unavailable"} for key in ("embedding", "reranker", "generation")}
    descriptor = {"dataset_id": "old-dev-rehearsal", "role": "historical", "status": "frozen",
                  "count": len(cases), "sha256": sha256(dataset), "used_for_tuning": True,
                  "notice": "SYNTHETIC approval records only, NOT actual annotation approval",
                  "case_approvals": [{"case_id": c["case_id"], "status": "approved", "reviewer": fixture_actor(),
                                      "facts_sha256": canonical_hash(c["necessary_facts"]),
                                      "schemes_sha256": canonical_hash(c["evidence_groups"])} for c in cases]}
    environment = {**lock_inventory(root / "uv.lock"), "locked_sync_verified": False,
                   "note": "Existing interpreter audited; fresh locked sync failed, rehearsal only"}
    values = {"rag_source": source_snapshot(root, ("src",)),
              "evaluation_source": source_snapshot(root, (), files=EVALUATION_SOURCE_FILES),
              "configuration": {"public_config": public, "models": models},
              "knowledge_base": knowledge, "dataset_descriptor": descriptor,
              "thresholds": policy, "environment": environment}
    bindings = {"dataset": dataset, "rules": root / "docs/EVALUATION_METRICS_CONTRACT_V1.md"}
    for name, payload in values.items():
        path = directory / (name + ".json")
        write_json(path, payload)
        bindings[name] = path
    freeze_path = directory / "freeze.json"
    freeze = write_freeze(freeze_path, bindings, purpose="rehearsal", approved_by=fixture_actor(), frozen_at=now())
    workflow = fixture_workflow()
    workflow.index_version_id = sid
    workflow.model_ids = {name: value["id"] for name, value in models.items()}
    return {"directory": directory, "root": root, "dataset": dataset, "cases": cases, "freeze": freeze,
            "freeze_path": freeze_path, "bindings": bindings, "config": public, "workflow": workflow,
            "models": workflow.model_ids, "knowledge": knowledge, "policy": policy}


def execute_fixture(fixture, output):
    adapter = WorkflowAdapter(fixture["workflow"], identities={SOURCE: (DOC, EDITION)})
    return run_pipeline(fixture["dataset"], adapter, output, config=fixture["config"], model_ids=fixture["models"],
                        freeze_path=fixture["freeze_path"], execution_mode="frozen_rehearsal")


def packet_for(bundle, bundle_hash, *, kind="ai", prior=None):
    prior = prior or initial_state(bundle, bundle_hash)
    return {"schema_version": "rag-eval.review-change.v1", "actor": fixture_actor(kind),
            "base_bundle_sha256": bundle_hash, "parent_state_sha256": canonical_hash(prior),
            "changes": [], "disputes": [], "adjudications": []}


def completed_fixture_review(case, obs, reviewer_actor):
    """Synthetic labels exercise code paths; never assert actual human/expert review."""
    from eval.scoring_v1 import pending_review
    review = pending_review(case)
    review["reviewer"] = {"identity": reviewer_actor["identity"], "reviewer_type": reviewer_actor["type"],
                          "reviewed_at": reviewer_actor["at"], "rubric_version": "metrics-v1"}
    ids = [e["evidence_id"] for e in obs["final_decision_evidence"] or []]
    for row in review["fact_reviews"]:
        row.update(context_supported=True, final_evidence_supported=True, answer_covered=True, correct=True,
                   numeric_conditions_correct=True, evidence_ids=ids, reason="SYNTHETIC review label, not actual semantic verification")
    review["claim_reviews"] = [{"claim_id": "fixture-claim", "text": obs["answer_text"], "support": "supported", "evidence_ids": ids,
                                "reason": "SYNTHETIC label for testing only"}]
    review["answer_review"] = dict.fromkeys(review["answer_review"], True)
    review["behavior_review"] = {"appropriate": True, "reason": "synthetic label"}
    review["human_approved"] = True if reviewer_actor["type"] == "human" else None
    return review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    fixture = prepare_fixture(args.output)
    run_directory = args.output / "run"
    bundle = execute_fixture(fixture, run_directory)
    bh = sha256(run_directory / "bundle.json")
    packet = packet_for(bundle, bh)
    for case, obs, prior in zip(bundle["test_cases"], bundle["observations"], bundle["reviews"]):
        r = completed_fixture_review(case, obs, packet["actor"])
        r["reviewer"]["rubric_version"] = bundle["run"]["evaluation_snapshot"]["rubric_version"]
        packet["changes"].append({"case_id": case["case_id"], "previous_review_sha256": canonical_hash(prior),
                                  "review": r, "reason": "AI-labelled synthetic rehearsal; pending actual human review"})
    packet_path = args.output / "review-import.json"
    write_json(packet_path, packet)
    revision = args.output / "review-1"
    import_reviews(run_directory, packet_path, revision)
    # A clearly synthetic human-role signature exercises serialization, not real human sign-off.
    decision = sign_assessment(run_directory, args.output / "assessment", signer=fixture_actor("human"), revision=revision)
    blocked = copy.deepcopy(fixture["freeze"])
    blocked["purpose"] = "independent"
    write_json(args.output / "formal-blocked-precheck.json", precheck(blocked))
    write_json(args.output / "summary.json", {"notice": "OFFLINE REHEARSAL ONLY; synthetic signature role, no actual human approval",
                                               "cases": len(bundle["test_cases"]), "conclusion": decision["conclusion"],
                                               "formal_acceptance_started": False})
    print(decision["conclusion"] + ": offline rehearsal; no actual human approval")


if __name__ == "__main__":
    main()
