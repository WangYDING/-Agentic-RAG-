"""Byte-exact artifact hashes and explicit, non-secret reproducibility metadata."""
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def endpoint_hash(url):
    parsed = urlsplit(str(url))
    if not parsed.scheme or not parsed.hostname:
        raise ValueError("endpoint identity unavailable")
    public_identity = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}{parsed.path.rstrip('/')}"
    return hashlib.sha256(public_identity.encode()).hexdigest()


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            text=True, encoding="utf-8", timeout=10)
    return result.stdout.strip() if result.returncode == 0 else None


def source_snapshot(root, directories, *, files=None):
    root = Path(root).resolve()
    paths = set()
    for name in directories:
        paths.update((root / name).rglob("*.py"))
    for name in files or []:
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"invalid explicit source file: {name}")
        paths.add(path)
    paths.update(root / name for name in ("uv.lock", "pyproject.toml") if (root / name).is_file())
    hashes = {path.relative_to(root).as_posix(): sha256(path) for path in sorted(paths)}
    status = git(root, "status", "--porcelain")
    return {"root": str(root), "directories": list(directories), "explicit_files": list(files or []), "git_commit": git(root, "rev-parse", "HEAD"),
            "branch": git(root, "branch", "--show-current"),
            "git_dirty": bool(status) if status is not None else None,
            "git_status": status, "source_hashes": hashes,
            "source_tree_sha256": canonical_hash(hashes)}


def verify_source(snapshot):
    root = Path(snapshot["root"])
    for name, expected in snapshot["source_hashes"].items():
        path = root / name
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"source hash mismatch: {name}")
    if source_snapshot(root, snapshot["directories"], files=snapshot.get("explicit_files"))["source_hashes"] != snapshot["source_hashes"]:
        raise ValueError("source file inventory changed")
    if canonical_hash(snapshot["source_hashes"]) != snapshot["source_tree_sha256"]:
        raise ValueError("source fingerprint mismatch")
    if git(root, "rev-parse", "HEAD") != snapshot["git_commit"]:
        raise ValueError("source commit changed")


def lock_inventory(lock_path):
    """Audit installed versions without mutating the shared environment.

    All-platform lock entries may be absent on Windows; report those explicitly.
    This is an audit, not a claim that uv sync succeeded.
    """
    lock = tomllib.loads(Path(lock_path).read_text(encoding="utf-8"))
    installed = {dist.metadata["Name"].lower().replace("_", "-"): dist.version
                 for dist in importlib.metadata.distributions() if dist.metadata["Name"]}
    versions = {}
    for package in lock["package"]:
        versions.setdefault(package["name"], set()).add(package["version"])
    rows = []
    for name, allowed in sorted(versions.items()):
        value = installed.get(name)
        rows.append({"name": name, "locked_versions": sorted(allowed), "installed": value,
                     "status": "not_installed_or_platform_excluded" if value is None else
                     "matches" if value in allowed else "version_mismatch"})
    return {"python": platform.python_version(), "python_executable": sys.executable,
            "lock_sha256": sha256(lock_path),
            "packages": rows, "installed_version_mismatches": [r for r in rows if r["status"] == "version_mismatch"],
            "note": "Platform markers/extras not resolved by this inventory; a complete locked sync remains a separate check."}


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def artifact_manifest(root, paths):
    root = Path(root).resolve()
    return {"schema_version": "rag-eval.artifacts.v1", "hash_mode": "sha256-raw-bytes",
            "files": {Path(p).resolve().relative_to(root).as_posix(): sha256(p) for p in paths}}


def verify_artifacts(root, manifest):
    root = Path(root).resolve()
    if manifest.get("schema_version") != "rag-eval.artifacts.v1" or manifest.get("hash_mode") != "sha256-raw-bytes":
        raise ValueError("unsupported artifact manifest")
    if not manifest.get("files"):
        raise ValueError("empty artifact manifest")
    for name, expected in manifest["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError("artifact path escapes run directory")
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"artifact hash mismatch: {name}")
