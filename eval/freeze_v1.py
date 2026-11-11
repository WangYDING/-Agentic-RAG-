"""Explicit artifact bindings and admission checks. No discovery of test datasets."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from eval.contract_v1 import validate_test_case
from eval.fingerprints_v1 import canonical_hash, sha256, verify_source, write_json
from eval.review_workflow_v1 import actor, timestamp


REQUIRED_BINDINGS = {"rag_source", "configuration", "knowledge_base", "evaluation_source",
                     "dataset", "dataset_descriptor", "rules", "thresholds", "environment"}


def bind(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha256(path)}


def read_bound(binding):
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
        raise ValueError("binding requires path/sha256")
    if sha256(binding["path"]) != binding["sha256"]:
        raise ValueError("binding hash changed: " + binding["path"])
    return Path(binding["path"])


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_policy(policy):
    required = {"schema_version", "policy_id", "declared_at", "on_missing_observation", "on_unreviewed",
                "on_service_error", "required_observations", "thresholds", "require_human_approval",
                "hard_failures", "rerun_policy", "allow_unavailable_model_revision"}
    if not isinstance(policy, dict) or set(policy) != required or policy["schema_version"] != "rag-eval.policy.v1":
        raise ValueError("policy fields/version invalid")
    if not isinstance(policy["policy_id"], str) or not policy["policy_id"].strip():
        raise ValueError("policy ID missing")
    timestamp(policy["declared_at"])
    for key in ("on_missing_observation", "on_unreviewed", "on_service_error"):
        if policy[key] not in {"fail", "inconclusive"}:
            raise ValueError("missing/unreviewed/service errors may not default to pass")
    if policy["require_human_approval"] is not True or type(policy["allow_unavailable_model_revision"]) is not bool:
        raise ValueError("explicit human approval/revision policy required")
    if policy["rerun_policy"] != {"allowed": False, "merge": "none", "retain_all_attempts": True}:
        raise ValueError("v1 supports single-attempt runs only; retain all failures")
    known_hard = {"invalid_citation", "numeric_conditions_wrong", "material_outside_conclusions", "scope_violation"}
    if not isinstance(policy["hard_failures"], list) or set(policy["hard_failures"]) != known_hard:
        raise ValueError("hard failure policy must enumerate all four rules")
    if not isinstance(policy["required_observations"], list) or not policy["required_observations"]:
        raise ValueError("required observations missing")
    paths = {"actual_scope", "initial_candidates", "reranked_results", "final_decision_evidence",
             "generator_context", "generator_invoked", "retrieval_rounds", "measurements.latency_ms",
             "measurements.model_calls", "measurements.input_tokens", "measurements.output_tokens"}
    for row in policy["required_observations"]:
        if set(row) != {"path", "applies_to"} or row["path"] not in paths or row["applies_to"] not in {"all", "answer", "generator"}:
            raise ValueError("invalid observation rule")
    if not isinstance(policy["thresholds"], list) or not policy["thresholds"]:
        raise ValueError("thresholds missing")
    ids = set()
    for rule in policy["thresholds"]:
        if set(rule) != {"metric", "op", "value"} or rule["op"] not in {">=", "<="} or rule["metric"] in ids:
            raise ValueError("invalid/duplicate threshold")
        if not isinstance(rule["metric"], str) or not rule["metric"].strip():
            raise ValueError("invalid metric name")
        value = rule["value"]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("threshold must be finite")
        ids.add(rule["metric"])


def _safe(root, relative):
    path = (Path(root) / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("knowledge base path escapes root")
    return path


def inspect_knowledge_base(root, catalog_path):
    """Read manifests and hash PDFs/index bytes. Never load a model or build an index."""
    root, catalog_path = Path(root).resolve(), Path(catalog_path).resolve()
    catalog = read_json(catalog_path)
    pointer_path = root / "active.json"
    pointer = read_json(pointer_path)
    sid = pointer.get("snapshot_id")
    if pointer.get("schema_version") != 1 or not isinstance(sid, str) or len(sid) != 64 or any(c not in "0123456789abcdef" for c in sid):
        raise ValueError("invalid active knowledge snapshot")
    manifest_path = root / "snapshots" / sid / "manifest.json"
    manifest = read_json(manifest_path)
    refs = manifest.get("documents")
    if manifest.get("schema_version") != 1 or not isinstance(refs, list) or not refs or canonical_hash({"documents": refs}) != sid:
        raise ValueError("knowledge snapshot identity mismatch")
    docs = {(d["spec_id"], d["edition_id"]): d for d in catalog["documents"]}
    files = [bind(catalog_path), bind(pointer_path), bind(manifest_path)]
    identities, models = [], set()
    for ref in refs:
        doc_path = _safe(root, ref["manifest_path"])
        if sha256(doc_path) != ref["manifest_sha256"]:
            raise ValueError("document manifest hash changed")
        doc = read_json(doc_path)
        identity = (doc["spec_id"], doc["edition_id"])
        if identity not in docs or ref["business_id"] != "@".join(identity) or doc["version_id"] != ref["version_id"]:
            raise ValueError("document identity mismatch")
        if identity in identities:
            raise ValueError("duplicate knowledge identity")
        identities.append(identity)
        models.add(doc["embedding_model"])
        files.append(bind(doc_path))
        for key in ("index", "metadata"):
            path = _safe(doc_path.parent, doc[key + "_file"])
            if sha256(path) != doc[key + "_sha256"]:
                raise ValueError("index/metadata hash changed")
            files.append(bind(path))
        pdf = _safe(catalog_path.parent.parent, docs[identity]["local_pdf_path"])
        if sha256(pdf) != docs[identity]["pdf_sha256"] or sha256(pdf) != doc["source_pdf_sha256"]:
            raise ValueError("source document hash changed")
        files.append(bind(pdf))
    return {"schema_version": "rag-eval.knowledge-binding.v1", "root": str(root), "catalog_path": str(catalog_path), "snapshot_id": sid,
            "business_ids": sorted("@".join(i) for i in identities),
            "embedding_models": sorted(models), "files": files,
            "check_scope": "manifest identity and byte hashes, not FAISS semantics or model inference"}


def verify_knowledge(binding):
    if binding.get("schema_version") != "rag-eval.knowledge-binding.v1" or not binding.get("files"):
        raise ValueError("knowledge binding missing")
    for file in binding["files"]:
        read_bound(file)
    # The captured set contains the catalog and active pointer as well as all child files.
    if not binding.get("snapshot_id") or not binding.get("business_ids"):
        raise ValueError("knowledge snapshot identity missing")
    if inspect_knowledge_base(binding["root"], binding["catalog_path"]) != binding:
        raise ValueError("knowledge binding does not reconstruct from manifests")


def precheck(freeze, *, now=None, allow_claimed_attempt=False):
    """Return reasons; all checks precede adapter invocation. Caller names the dataset."""
    reasons, checked = [], {}
    def issue(code, detail):
        reasons.append({"code": code, "detail": str(detail)})
    if not isinstance(freeze, dict) or freeze.get("schema_version") != "rag-eval.freeze.v1":
        return {"eligible": False, "reasons": [{"code": "FREEZE_SCHEMA", "detail": "invalid freeze version"}]}
    purpose = freeze.get("purpose")
    if purpose not in {"independent", "rehearsal"}:
        issue("PURPOSE", "invalid freeze purpose")
    if not isinstance(freeze.get("attempt_registry"), str) or not Path(freeze["attempt_registry"]).is_absolute():
        issue("ATTEMPT_REGISTRY", "absolute append-only attempt registry path required")
    elif not allow_claimed_attempt:
        dataset_hash = freeze.get("bindings", {}).get("dataset", {}).get("sha256")
        if isinstance(dataset_hash, str) and (Path(freeze["attempt_registry"]) / (dataset_hash + ".json")).exists():
            issue("ATTEMPT_ALREADY_EXISTS", "single-attempt policy forbids another execution")
    try:
        frozen_at = timestamp(freeze["frozen_at"])
        if frozen_at > (now or datetime.now(timezone.utc)):
            issue("FREEZE_TIME", "freeze date is in the future")
        actor(freeze["approved_by"], human=purpose == "independent")
        if timestamp(freeze["approved_by"]["at"]) > frozen_at:
            issue("FREEZE_APPROVAL", "approval postdates freeze")
    except (KeyError, ValueError, TypeError) as exc:
        issue("FREEZE_APPROVAL", exc)
    bindings = freeze.get("bindings", {})
    if not isinstance(bindings, dict):
        bindings = {}
    for key in sorted(REQUIRED_BINDINGS):
        if key not in bindings:
            issue("MISSING_BINDING", key)
            continue
        try:
            path = read_bound(bindings[key])
            checked[key] = path if key in {"dataset", "rules"} else read_json(path)
        except (ValueError, OSError, TypeError, KeyError) as exc:
            issue("BINDING_INVALID", f"{key}: {exc}")
    for key in ("rag_source", "evaluation_source"):
        if key in checked:
            try:
                verify_source(checked[key])
                from eval.pipeline_v1 import EVALUATION_SOURCE_FILES
                required_sources = ({"src/agent_workflow.py", "src/application.py", "src/query_scope.py", "src/generator.py",
                                     "src/evidence_sufficiency.py", "src/query_rewriter.py", "uv.lock", "pyproject.toml"}
                                    if key == "rag_source" else set(EVALUATION_SOURCE_FILES) | {"uv.lock", "pyproject.toml"})
                if not required_sources <= set(checked[key]["source_hashes"]):
                    issue("INCOMPLETE_SOURCE", key)
                if purpose == "independent" and (checked[key].get("git_dirty") is not False or not checked[key].get("git_commit")):
                    issue("DIRTY_SOURCE", key)
                if purpose == "independent":
                    from eval.fingerprints_v1 import git
                    if git(checked[key]["root"], "status", "--porcelain") != "":
                        issue("DIRTY_SOURCE", key + " current working tree")
            except (ValueError, OSError, KeyError) as exc:
                issue("SOURCE_CHANGED", f"{key}: {exc}")
    if "thresholds" in checked:
        try:
            validate_policy(checked["thresholds"])
            if timestamp(checked["thresholds"]["declared_at"]) > timestamp(freeze["frozen_at"]):
                issue("LATE_POLICY", "thresholds declared after freeze")
        except (ValueError, KeyError, TypeError) as exc:
            issue("POLICY_INVALID", exc)
    if "knowledge_base" in checked:
        try:
            verify_knowledge(checked["knowledge_base"])
        except (ValueError, OSError, KeyError) as exc:
            issue("KNOWLEDGE_CHANGED", exc)
    if "configuration" in checked:
        try:
            from eval.provenance import PUBLIC_CONFIG_FIELDS
            cfg = checked["configuration"]
            if set(cfg) - {"public_config", "models", "api_endpoint_sha256", "pricing"}:
                raise ValueError("non-public or unknown configuration section")
            if not cfg.get("public_config") or set(cfg["public_config"]) - set(PUBLIC_CONFIG_FIELDS):
                raise ValueError("configuration missing or contains non-public keys")
            if purpose == "independent":
                controls = {"embedding_revision", "retrieval_top_k", "evidence_top_n", "max_model_calls", "total_timeout_seconds",
                            "request_timeout_seconds", "max_network_retries"}
                if not controls <= set(cfg["public_config"]):
                    raise ValueError("runtime controls missing from formal configuration")
                endpoint = cfg.get("api_endpoint_sha256")
                if not isinstance(endpoint, str) or len(endpoint) != 64 or any(c not in "0123456789abcdef" for c in endpoint):
                    raise ValueError("provider endpoint identity hash missing")
            models = cfg["models"]
            for name in ("embedding", "reranker", "generation"):
                model = models[name]
                if not isinstance(model.get("id"), str) or not model["id"].strip():
                    raise ValueError("model ID missing")
                field = {"embedding": "embedding_model", "reranker": "reranker_model", "generation": "generation_model"}[name]
                if cfg["public_config"].get(field) != model["id"]:
                    raise ValueError("public configuration/model identity mismatch")
                if not model.get("revision"):
                    if model.get("revision_status") != "unavailable" or checked.get("thresholds", {}).get("allow_unavailable_model_revision") is not True:
                        raise ValueError("unknown model revision not explicitly permitted")
            kb = checked.get("knowledge_base", {})
            if kb.get("embedding_models") != [models["embedding"]["id"]]:
                raise ValueError("embedding model differs from knowledge snapshot")
        except (ValueError, KeyError, TypeError) as exc:
            issue("CONFIG_INVALID", exc)
    if "environment" in checked:
        env = checked["environment"]
        if env.get("locked_sync_verified") is not True and purpose == "independent":
            issue("ENVIRONMENT_UNVERIFIED", "complete locked environment sync has not been verified")
        if env.get("lock_sha256") != checked.get("rag_source", {}).get("source_hashes", {}).get("uv.lock"):
            issue("ENVIRONMENT_LOCK", "environment lock differs from RAG source lock")
        if purpose == "independent":
            from eval.fingerprints_v1 import lock_inventory
            record = env.get("sync_record", {})
            if record.get("exit_code") != 0 or record.get("lock_sha256") != env.get("lock_sha256") or "--locked" not in record.get("command", ""):
                issue("ENVIRONMENT_UNVERIFIED", "locked sync success attestation missing")
            if env.get("installed_version_mismatches") != []:
                issue("ENVIRONMENT_VERSION", "installed dependency mismatch or absent inventory")
            try:
                current = lock_inventory(Path(checked["rag_source"]["root"]) / "uv.lock")
                if any(env.get(key) != current[key] for key in ("python", "python_executable", "packages")):
                    issue("ENVIRONMENT_CHANGED", "runtime interpreter or installed versions differ from freeze")
            except (OSError, KeyError, ValueError) as exc:
                issue("ENVIRONMENT_CHANGED", str(exc))
    if "dataset" in checked and "dataset_descriptor" in checked:
        try:
            data = checked["dataset"]
            raw = data.read_text(encoding="utf-8")
            rows = ([json.loads(line) for line in raw.splitlines() if line.strip()] if data.suffix == ".jsonl" else json.loads(raw))
            cases = rows["test_cases"] if isinstance(rows, dict) else rows
            descriptor = checked["dataset_descriptor"]
            expected_role = "independent" if purpose == "independent" else descriptor["role"]
            if purpose == "rehearsal" and expected_role not in {"synthetic", "development", "historical"}:
                raise ValueError("rehearsal cannot consume independent data")
            if descriptor["role"] != expected_role or descriptor["status"] != "frozen" or descriptor["sha256"] != sha256(data):
                raise ValueError("dataset role/status/hash mismatch")
            ids = [c["case_id"] for c in cases]
            if not cases or len(ids) != len(set(ids)) or descriptor["count"] != len(cases):
                raise ValueError("dataset IDs/count invalid")
            approvals = descriptor["case_approvals"]
            if len(approvals) != len(cases) or {a["case_id"] for a in approvals} != set(ids):
                raise ValueError("annotation review coverage incomplete")
            approval_map = {a["case_id"]: a for a in approvals}
            allowed_docs = set(checked.get("knowledge_base", {}).get("business_ids", []))
            for c in cases:
                validate_test_case(c)
                if c["dataset_role"] != expected_role:
                    raise ValueError("case role differs from frozen descriptor")
                a = approval_map[c["case_id"]]
                actor(a["reviewer"], human=purpose == "independent")
                if timestamp(a["reviewer"]["at"]) > timestamp(freeze["frozen_at"]):
                    raise ValueError("annotation review postdates freeze")
                if a["status"] != "approved" or a["facts_sha256"] != canonical_hash(c["necessary_facts"]) or a["schemes_sha256"] != canonical_hash(c["evidence_groups"]):
                    raise ValueError("unapproved or changed facts/equivalent evidence schemes")
                for g in c["evidence_groups"]:
                    for alt in g["alternatives"]:
                        for ref in alt["all_of"]:
                            if ref["document_id"] + "@" + ref["document_version"] not in allowed_docs:
                                raise ValueError("gold evidence is outside frozen knowledge snapshot")
            if descriptor.get("used_for_tuning") is not False and purpose == "independent":
                raise ValueError("independent data already seen/used for tuning")
        except (ValueError, KeyError, TypeError, OSError) as exc:
            issue("DATASET_INVALID", exc)
    return {"eligible": not reasons, "purpose": purpose, "reasons": reasons,
            "freeze_sha256": canonical_hash(freeze), "checked_bindings": sorted(checked)}


def write_freeze(output, bindings, *, purpose, approved_by, frozen_at):
    freeze = {"schema_version": "rag-eval.freeze.v1", "purpose": purpose,
              "approved_by": approved_by, "frozen_at": frozen_at,
              "attempt_registry": str(Path(output).resolve().parent / "attempts"),
              "bindings": {name: bind(path) for name, path in bindings.items()}}
    result = precheck(freeze)
    if not result["eligible"]:
        raise ValueError(json.dumps(result["reasons"], ensure_ascii=False))
    write_json(output, freeze)
    return freeze


def claim_attempt(freeze, output):
    """Single attempt per dataset in the declared registry, including failed attempts."""
    registry = Path(freeze["attempt_registry"])
    registry.mkdir(parents=True, exist_ok=True)
    dataset_hash = freeze["bindings"]["dataset"]["sha256"]
    path = registry / (dataset_hash + ".json")
    write_json(path, {"schema_version": "rag-eval.attempt.v1", "dataset_sha256": dataset_hash,
                      "freeze_sha256": canonical_hash(freeze), "output": str(Path(output).resolve()),
                      "claimed_at": datetime.now(timezone.utc).isoformat(), "retain_failed_attempts": True})
    return bind(path)
