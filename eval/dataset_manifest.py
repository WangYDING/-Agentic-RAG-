"""Offline dataset inventory and freeze validation; never calls models."""
import argparse
import hashlib
import glob
import json
from collections import Counter
from pathlib import Path

from eval.schema import load_eval_dataset


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_manifest(path):
    path = Path(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for key in ("dataset_id", "version", "role", "status", "data_file", "sha256", "count", "type_distribution"):
        if key not in manifest:
            raise ValueError(f"manifest missing {key}")
    if manifest["role"] not in {"development", "independent", "historical"}:
        raise ValueError("invalid dataset role")
    if manifest["status"] not in {"draft", "frozen", "historical", "demoted"}:
        raise ValueError("invalid dataset status")
    data_path = (path.parent / manifest["data_file"]).resolve()
    if file_sha256(data_path) != manifest["sha256"]:
        raise ValueError("dataset SHA-256 mismatch")
    data_format = manifest.get("data_format", "agent")
    if data_format == "agent":
        examples = load_eval_dataset(data_path)
        distribution = dict(Counter(x.question_type for x in examples))
    elif data_format == "sufficiency":
        examples = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        ids = [item["id"] for item in examples]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate sufficiency IDs")
        for item in examples:
            if item["expected_decision"] not in {"sufficient", "insufficient"} or not isinstance(item["evidence"], list):
                raise ValueError("invalid sufficiency evidence bundle")
        distribution = dict(Counter(x["case_type"] for x in examples))
    else:
        raise ValueError("unknown dataset data_format")
    if len(examples) != manifest["count"]:
        raise ValueError("dataset count mismatch")
    if distribution != manifest["type_distribution"]:
        raise ValueError("dataset type distribution mismatch")
    if manifest["status"] == "frozen":
        if data_format != "agent":
            raise ValueError("freeze currently supports agent examples only")
        if manifest["role"] != "independent":
            raise ValueError("only independent datasets may be frozen")
        if not manifest.get("frozen_at") or not manifest.get("acceptance_criteria"):
            raise ValueError("freeze requires date and acceptance criteria")
        criteria = manifest["acceptance_criteria"]
        if not isinstance(criteria, dict) or not criteria.get("path") or not criteria.get("sha256"):
            raise ValueError("freeze requires a versioned acceptance gate path and SHA-256")
        gate_path = (path.parent / criteria["path"]).resolve()
        if not gate_path.is_file() or file_sha256(gate_path) != criteria["sha256"]:
            raise ValueError("acceptance gate SHA-256 mismatch")
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        if gate.get("gate_id") != criteria.get("gate_id"):
            raise ValueError("acceptance gate ID mismatch")
        if gate.get("dataset_id") != manifest["dataset_id"]:
            raise ValueError("acceptance gate dataset mismatch")
        if gate.get("declared_before_independent_run") is not True:
            raise ValueError("acceptance gate must be declared before the independent run")
        if manifest.get("used_for_tuning") is not False:
            raise ValueError("a frozen independent dataset must not be used for tuning")
        if not examples:
            raise ValueError("cannot freeze an empty dataset")
        for example in examples:
            if not example.required_requirements:
                raise ValueError(f"{example.id}: required requirements missing")
            if example.annotation_review.status != "approved":
                raise ValueError(f"{example.id}: annotation approval missing")
            if example.answerable and not (example.gold_evidence and example.key_answer_points):
                raise ValueError(f"{example.id}: answerable case requires evidence and key points")
            if not example.answerable and not example.why_unanswerable:
                raise ValueError(f"{example.id}: missing unanswerability rationale")
    return manifest, examples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+")
    args = parser.parse_args()
    paths = [match for pattern in args.manifests for match in glob.glob(pattern)]
    if not paths:
        parser.error("no manifest files matched")
    for path in paths:
        manifest, examples = validate_manifest(path)
        print(f"{manifest['dataset_id']} {manifest['version']}: {len(examples)} cases ({manifest['status']})")


if __name__ == "__main__":
    main()
