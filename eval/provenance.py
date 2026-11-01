"""Explicit allowlisted run provenance. Does not serialize environment or secrets."""
import hashlib
import json
import platform
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from importlib.metadata import version, PackageNotFoundError

from eval.dataset_manifest import file_sha256


PUBLIC_CONFIG_FIELDS = (
    "embedding_model", "embedding_revision", "reranker_model", "generation_model",
    "retrieval_top_k", "evidence_top_n", "request_timeout_seconds",
    "max_network_retries", "total_timeout_seconds", "max_model_calls",
    "input_cost_per_million", "output_cost_per_million",
    "index_auto_build", "index_lock_timeout_seconds",
)
PROMPT_FILES = ("src/generator.py", "src/evidence_sufficiency.py", "src/query_rewriter.py")


def _git(root, *args):
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def capture_provenance(config, *, root, dataset_path, pdf_path, index_manifest=None):
    root = Path(root)
    public = {key: getattr(config, key, None) for key in PUBLIC_CONFIG_FIELDS}
    endpoint = getattr(config, "api_base_url", None)
    if endpoint:
        parsed = urlsplit(endpoint)
        endpoint_identity = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}{parsed.path}"
        public["api_endpoint_sha256"] = hashlib.sha256(endpoint_identity.encode()).hexdigest()
    packages = {}
    for name in ("numpy", "scipy", "scikit-learn", "faiss-cpu", "openai", "pymupdf", "sentence-transformers"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    canonical = json.dumps(public, sort_keys=True, ensure_ascii=False).encode()
    status = _git(root, "status", "--porcelain")
    return {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git(root, "rev-parse", "HEAD"),
        "git_dirty": bool(status) if status is not None else None,
        "uv_lock_sha256": file_sha256(root / "uv.lock") if (root / "uv.lock").exists() else None,
        "dataset_sha256": file_sha256(dataset_path),
        "pdf_sha256": file_sha256(pdf_path),
        "configuration": public,
        "configuration_sha256": hashlib.sha256(canonical).hexdigest(),
        "index_manifest": asdict(index_manifest) if index_manifest is not None else None,
        "prompt_source_sha256": {name: file_sha256(root / name) for name in PROMPT_FILES if (root / name).exists()},
        "runtime_source_sha256": {
            str(path.relative_to(root)).replace("\\", "/"): file_sha256(path)
            for directory in ("src", "eval") for path in sorted((root / directory).glob("*.py"))
        },
        "prompt_hash_scope": "whole source files; changes outside prompts also invalidate hashes",
        "model_revisions": {
            "embedding": getattr(config, "embedding_revision", None),
            "reranker": None,
            "generation": None,
        },
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "packages": packages},
        "release_dependencies": {
            "real_deployment_latency_baseline": "pending",
            "real_model_usage_cost_baseline": "pending",
        },
    }
