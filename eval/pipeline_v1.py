"""End-to-end evaluation tooling. CLI is offline-only; independent datasets blocked."""
import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from eval.contract_v1 import (REPORT_VERSION, RUN_VERSION, make_rag_input,
                              validate_bundle, validate_test_case, validate_observation, validate_review)
from eval.fingerprints_v1 import (artifact_manifest, canonical_hash, lock_inventory,
                                  sha256, source_snapshot, verify_artifacts, verify_source, write_json)
from eval.scoring_v1 import pending_review, score


# Explicit tooling boundary: do not open unrelated independent-set authoring files.
EVALUATION_SOURCE_FILES = (
    "eval/__init__.py", "eval/schema.py", "eval/metrics.py", "eval/review.py",
    "eval/provenance.py", "eval/dataset_manifest.py", "eval/adapter_v1.py",
    "eval/contract_v1.py", "eval/fingerprints_v1.py", "eval/pipeline_v1.py",
    "eval/scoring_v1.py", "eval/offline_workflow_v1.py", "eval/validate_contract.py",
    "eval/usage_v1.py",
    "eval/review_workflow_v1.py", "eval/freeze_v1.py", "eval/decision_v1.py",
    "eval/rehearsal_v1.py",
    "eval/interface_probe_v1.py", "eval/governance_cli_v1.py",
    "tests/test_eval_contract_v1.py", "tests/test_eval_pipeline_v1.py",
    "tests/test_eval_governed_v1.py",
    "tests/test_eval_governance.py", "tests/test_eval_schema.py", "tests/test_eval_metrics.py", "tests/test_eval_runner.py",
)


def load_cases(path, *, allow_independent=False):
    path = Path(path)
    if path.suffix == ".jsonl":
        cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        cases = data["test_cases"] if isinstance(data, dict) else data
    if not cases:
        raise ValueError("empty dataset")
    for case in cases:
        validate_test_case(case)
        if case["dataset_role"] == "independent" and not allow_independent:
            raise ValueError("this development runner does not run independent datasets")
    ids = [c["case_id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate dataset IDs")
    return cases


class ReplayAdapter:
    """Fixture replay, not a RAG execution or a claim of system accuracy."""
    def __init__(self, observations):
        self.observations = {o["case_id"]: copy.deepcopy(o) for o in observations}

    def __call__(self, public):
        from eval.contract_v1 import validate_rag_input
        validate_rag_input(public)
        result = copy.deepcopy(self.observations[public["case_id"]])
        result.setdefault("extensions", {})["execution_mode"] = "synthetic_fixture_replay"
        return result


def run_pipeline(dataset, adapter, output, *, reviews=None, system_root=None,
                 rules=None, model_ids=None, documents=None, index_manifest=None,
                 config=None, extra_inputs=None, execution_mode="offline_fixture",
                 freeze_path=None, independent_authorized=False):
    root = Path(__file__).resolve().parent.parent
    system_root = Path(system_root or root).resolve()
    dataset = Path(dataset).resolve()
    rules = Path(rules or root / "docs/EVALUATION_METRICS_CONTRACT_V1.md").resolve()
    admission = None
    if freeze_path is not None:
        from eval.freeze_v1 import precheck, read_json
        freeze = read_json(freeze_path)
        freeze_file_hash = sha256(freeze_path)
        admission = precheck(freeze)
        if not admission["eligible"]:
            raise ValueError("frozen admission blocked: " + json.dumps(admission["reasons"]))
        if freeze["purpose"] == "independent" and independent_authorized is not True:
            raise ValueError("independent execution is not authorized by this call")
        if Path(freeze["bindings"]["dataset"]["path"]).resolve() != dataset or freeze["bindings"]["rules"]["sha256"] != sha256(rules):
            raise ValueError("runtime dataset/rules differ from freeze")
        if Path(read_json(freeze["bindings"]["rag_source"]["path"])["root"]).resolve() != system_root:
            raise ValueError("runtime RAG source root differs from freeze")
        cfg = read_json(freeze["bindings"]["configuration"]["path"])
        if config != cfg["public_config"] or model_ids != {k: v["id"] for k, v in cfg["models"].items()}:
            raise ValueError("runtime config/models differ from freeze")
        if not hasattr(adapter, "check_binding"):
            raise ValueError("frozen execution requires an explicitly bound workflow adapter")
        adapter.check_binding(cfg, read_json(freeze["bindings"]["knowledge_base"]["path"]),
                              read_json(freeze["bindings"]["rag_source"]["path"]),
                              require_provider_policy=freeze["purpose"] == "independent")
        if execution_mode != ("frozen_independent" if freeze["purpose"] == "independent" else "frozen_rehearsal"):
            raise ValueError("execution mode differs from freeze purpose")
    cases = load_cases(dataset, allow_independent=bool(admission and independent_authorized))
    started_at = datetime.now(timezone.utc).isoformat()
    if config is not None:
        from eval.provenance import PUBLIC_CONFIG_FIELDS
        if not isinstance(config, dict) or set(config) - set(PUBLIC_CONFIG_FIELDS):
            raise ValueError("config must contain only public allowlisted configuration fields")
    if execution_mode not in {"offline_fixture", "offline_injected_workflow"} and admission is None:
        raise ValueError("only explicitly offline modes supported in this stage")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)  # never overwrite previous attempts
    system = source_snapshot(system_root, ("src",))
    evaluation = source_snapshot(root, (), files=EVALUATION_SOURCE_FILES)
    if admission is not None:
        declared_evaluation = read_json(freeze["bindings"]["evaluation_source"]["path"])
        if declared_evaluation["source_hashes"] != evaluation["source_hashes"]:
            raise ValueError("runtime evaluation tool source differs from freeze")
    doc_hashes = {str(Path(p).resolve()): sha256(p) for p in (documents or [])}
    index_snapshot = {"path": str(Path(index_manifest).resolve()), "sha256": sha256(index_manifest)} if index_manifest else None
    input_paths = {"dataset": dataset, "rules": rules, **(extra_inputs or {})}
    if admission is not None:
        input_paths["freeze"] = Path(freeze_path)
        input_paths.update({"frozen-" + k: Path(v["path"]) for k, v in freeze["bindings"].items() if k not in {"dataset", "rules"}})
    input_hashes = {key: {"path": str(path), "sha256": sha256(path)} for key, path in input_paths.items()}
    copied = []
    for i, (key, path) in enumerate(input_paths.items()):
        destination = output / f"input-{i}-{Path(path).name}"
        destination.write_bytes(Path(path).read_bytes())
        copied.append(destination)
        input_hashes[key]["archived_as"] = destination.name
    public_inputs = [make_rag_input(c) for c in cases]
    attempt = None
    if admission is not None:
        from eval.freeze_v1 import claim_attempt
        attempt = claim_attempt(freeze, output)
    observations = []
    for public in public_inputs:
        observation = adapter(copy.deepcopy(public))
        validate_observation(observation)
        if observation["case_id"] != public["case_id"]:
            raise ValueError("adapter returned wrong case_id")
        observations.append(observation)
    observation_map = {o["case_id"]: o for o in observations}
    if reviews is None:
        review_rows = [pending_review(c) for c in cases]
    else:
        review_rows = copy.deepcopy(reviews)
    if len(review_rows) != len(cases) or len({r["case_id"] for r in review_rows}) != len(cases):
        raise ValueError("review coverage/duplicate IDs")
    review_map = {r["case_id"]: r for r in review_rows}
    if set(review_map) != set(observation_map):
        raise ValueError("review case IDs mismatch")
    for c in cases:
        validate_review(review_map[c["case_id"]], c, observation_map[c["case_id"]])
    run_id = output.name
    report = {"schema_version": REPORT_VERSION, "scorer_version": "rag-eval.scorer.v1",
              "run_id": run_id, "execution_mode": execution_mode,
              "conclusion": "not_applicable", "acceptance": "not_started",
              "notice": "Offline fixture/tool validation only; not real RAG evaluation or independent acceptance.",
              **score(cases, observation_map, review_map)}
    from eval.usage_v1 import usage_report
    report["provider_usage_summary"] = usage_report(observations)
    if execution_mode == "frozen_independent":
        report.update(conclusion="inconclusive", acceptance="pending_review",
                      notice="Frozen independent raw run, pending review and separately signed decision.")
    # Audit before writing run files. Never claim service/provider reproducibility.
    for item in input_hashes.values():
        if sha256(item["path"]) != item["sha256"]:
            raise ValueError("input changed during run")
    verify_source(system)
    verify_source(evaluation)
    for path, expected in doc_hashes.items():
        if sha256(path) != expected:
            raise ValueError("document changed during run")
    if index_snapshot and sha256(index_snapshot["path"]) != index_snapshot["sha256"]:
        raise ValueError("index manifest changed during run")
    config_hash = canonical_hash(config) if config is not None else None
    run = {"schema_version": RUN_VERSION, "run_id": run_id,
           "started_at": started_at, "completed_at": datetime.now(timezone.utc).isoformat(),
           "initialization_ms": None,
           "execution_mode": execution_mode, "inputs": input_hashes,
           "artifacts": {"dataset_sha256": sha256(dataset),
                         "results_sha256": canonical_hash(observations),
                         "results_hash_mode": "canonical-json-sha256"},
           "system_snapshot": {"git_commit": system["git_commit"], "git_dirty": system["git_dirty"],
                               "source": system,
                               "prompt_hashes": {name: value for name, value in system["source_hashes"].items()
                                                 if name in {"src/generator.py", "src/evidence_sufficiency.py", "src/query_rewriter.py"}},
                               "config_hash": config_hash, "public_config": config, "model_id": model_ids,
                               "model_revisions": None, "document_hashes": doc_hashes,
                               "index_snapshot": index_snapshot},
           "evaluation_snapshot": {"code_commit": evaluation["git_commit"], "source": evaluation,
                                   "testset_version": sha256(dataset), "rubric_version": sha256(rules),
                                   "threshold_version": None},
           "environment": lock_inventory(root / "uv.lock"),
           "freeze_readiness": {"ready": False, "missing": ["independent_dataset", "frozen_thresholds", "human_quality_approval",
                                                            "provider_model_revisions", "formal_system_snapshot"]}}
    if admission is not None:
        from eval.freeze_v1 import precheck
        after = precheck(freeze, allow_claimed_attempt=True)
        if not after["eligible"] or sha256(freeze_path) != freeze_file_hash:
            raise ValueError("frozen inputs changed during execution")
        run["admission"] = {"freeze_path": str(Path(freeze_path).resolve()), "freeze_file_sha256": freeze_file_hash,
                            "freeze_sha256": canonical_hash(freeze), "before": admission, "after": after,
                            "attempt": attempt}
        run["frozen_snapshot_bindings"] = freeze["bindings"]
        run["evaluation_snapshot"]["threshold_version"] = freeze["bindings"]["thresholds"]["sha256"]
        run["system_snapshot"]["model_revisions"] = cfg["models"]
        run["freeze_readiness"] = {"ready": True, "purpose": freeze["purpose"], "missing": [],
                                   "notice": "Rehearsal admission is not formal eligibility" if freeze["purpose"] == "rehearsal" else "Admitted before execution"}
    bundle = {"test_cases": cases, "rag_inputs": public_inputs, "observations": observations,
              "reviews": review_rows, "run": run, "report": report}
    validate_bundle(bundle)
    paths = list(copied)
    for name, payload in (("cases.json", cases), ("rag-inputs.json", public_inputs),
                          ("observations.json", observations), ("reviews.json", review_rows),
                          ("run.json", run), ("report.json", report), ("bundle.json", bundle)):
        path = output / name
        write_json(path, payload)
        paths.append(path)
    md = output / "report.md"
    with md.open("x", encoding="utf-8") as stream:
        stream.write(render_markdown(report))
    paths.append(md)
    manifest = artifact_manifest(output, paths)
    write_json(output / "artifacts.json", manifest)
    verify_run(output)
    return bundle


def verify_run(output, *, verify_live_sources=True):
    output = Path(output)
    def read(name):
        return json.loads((output / name).read_text(encoding="utf-8"))
    manifest = read("artifacts.json")
    verify_artifacts(output, manifest)
    bundle = read("bundle.json")
    validate_bundle(bundle)
    for name, key in (("cases.json", "test_cases"), ("rag-inputs.json", "rag_inputs"),
                      ("observations.json", "observations"), ("reviews.json", "reviews"),
                      ("run.json", "run"), ("report.json", "report")):
        if name not in manifest["files"] or read(name) != bundle[key]:
            raise ValueError(f"bundle/artifact linkage mismatch: {name}")
    run = bundle["run"]
    config = run["system_snapshot"]["public_config"]
    if run["system_snapshot"]["config_hash"] != (canonical_hash(config) if config is not None else None):
        raise ValueError("configuration fingerprint mismatch")
    if canonical_hash(bundle["observations"]) != run["artifacts"]["results_sha256"]:
        raise ValueError("observation hash mismatch")
    for item in run["inputs"].values():
        if sha256(output / item["archived_as"]) != item["sha256"]:
            raise ValueError("archived input hash mismatch")
        if verify_live_sources and sha256(item["path"]) != item["sha256"]:
            raise ValueError("live input hash mismatch")
    if run["artifacts"]["dataset_sha256"] != run["inputs"]["dataset"]["sha256"]:
        raise ValueError("dataset hash linkage mismatch")
    archived_dataset = output / run["inputs"]["dataset"]["archived_as"]
    if load_cases(archived_dataset, allow_independent=bundle["run"].get("execution_mode") == "frozen_independent") != bundle["test_cases"]:
        raise ValueError("archived dataset/cases linkage mismatch")
    if run["evaluation_snapshot"]["rubric_version"] != run["inputs"]["rules"]["sha256"]:
        raise ValueError("rules hash linkage mismatch")
    if run.get("execution_mode") in {"frozen_rehearsal", "frozen_independent"}:
        admission = run.get("admission")
        if not admission or "freeze" not in run["inputs"]:
            raise ValueError("frozen run is missing admission lineage")
        freeze = read(run["inputs"]["freeze"]["archived_as"])
        if canonical_hash(freeze) != admission["freeze_sha256"]:
            raise ValueError("admission freeze fingerprint mismatch")
        if any(a.get("eligible") is not True or a.get("freeze_sha256") != canonical_hash(freeze)
               for a in (admission["before"], admission["after"])):
            raise ValueError("frozen run admission was not eligible")
        if freeze["bindings"]["dataset"]["sha256"] != run["artifacts"]["dataset_sha256"]:
            raise ValueError("admission dataset differs from executed data")
        if freeze["bindings"]["thresholds"]["sha256"] != run["evaluation_snapshot"]["threshold_version"]:
            raise ValueError("admission threshold fingerprint mismatch")
        if verify_live_sources:
            from eval.freeze_v1 import read_bound
            read_bound(admission["attempt"])
    if verify_live_sources:
        verify_source(run["system_snapshot"]["source"])
        verify_source(run["evaluation_snapshot"]["source"])
        for path, expected in run["system_snapshot"]["document_hashes"].items():
            if sha256(path) != expected:
                raise ValueError("document snapshot changed")
        index = run["system_snapshot"]["index_snapshot"]
        if index and sha256(index["path"]) != index["sha256"]:
            raise ValueError("index manifest changed")
    return bundle


def render_markdown(report):
    lines = ["# Offline evaluation tool validation", "", report["notice"], "",
             f"Run: `{report['run_id']}`. Conclusion: `{report['conclusion']}`.", "",
             "Semantic metrics use explicit review labels; null is unobserved/unreviewed.", "",
             "| Metric | Confirmed numerator | Applicable denominator | Full rate | Observed rate | Missing |",
             "|---|---:|---:|---:|---:|---:|"]
    for name, m in report["metrics"].items():
        lines.append(f"| {name} | {m['numerator']} | {m['denominator']} | {m['rate']} | {m['observed_rate']} | {len(m['missing_case_ids'])} |")
    lines.extend(["", "## Review progress", "", "```json", json.dumps(report["review_progress"], ensure_ascii=False, indent=2),
                  "```", "", "## Behavior confusion matrix", "", "```json", json.dumps(report["confusion_matrix"], indent=2),
                  "```", "", "## Performance and observed coverage", "", "```json",
                  json.dumps(report["performance"], ensure_ascii=False, indent=2), "```", "",
                  report["scoring_note"], ""])
    lines.extend(["## Scoring modes", "", "```json", json.dumps(report["metric_scoring_modes"], indent=2), "```", "",
                  "## Grouped metrics", "", "Grouped metrics by expected action and question type are in report.json.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    replay = sub.add_parser("replay")
    replay.add_argument("bundle", type=Path)
    replay.add_argument("--output", required=True, type=Path)
    replay.add_argument("--use-fixture-reviews", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--archive-only", action="store_true")
    args = parser.parse_args()
    if args.command == "verify":
        bundle = verify_run(args.directory, verify_live_sources=not args.archive_only)
    else:
        source = json.loads(args.bundle.read_text(encoding="utf-8"))
        bundle = run_pipeline(args.bundle, ReplayAdapter(source["observations"]), args.output,
                              reviews=source["reviews"] if args.use_fixture_reviews else None)
    print(json.dumps({"cases": len(bundle["test_cases"]), "conclusion": bundle["report"]["conclusion"]}))


if __name__ == "__main__":
    main()
