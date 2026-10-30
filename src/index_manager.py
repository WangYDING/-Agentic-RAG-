from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from src.vector_store import VectorStore


INDEX_SCHEMA_VERSION = 3
ACTIVE_SCHEMA_VERSION = 1
PARSER_VERSION = "pymupdf-structured-v1"
EMPTY_DOCUMENT_MESSAGE = "当前文档未提取到可用文本，可能是扫描版 PDF。"


class EmptyDocumentError(ValueError):
    pass


class IndexBuildInProgressError(TimeoutError):
    pass


class IndexCorruptionError(RuntimeError):
    pass


class IndexUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class IndexManifest:
    schema_version: int
    source: str
    document_id: str
    version_id: str
    checksum_sha256: str
    chunk_size: int
    overlap: int
    embedding_model: str
    embedding_revision: str | None
    parser_version: str
    embedding_dim: int
    chunk_count: int
    index_file: str
    metadata_file: str
    index_sha256: str
    metadata_sha256: str


@dataclass(frozen=True)
class ManagedIndex:
    vector_store: VectorStore
    manifest: IndexManifest
    action: str
    cleaned_text_preview: str = ""


class BuildLock:
    """Small cross-platform advisory lock held for one document build."""

    def __init__(self, path: Path, timeout_seconds: float, poll_seconds: float = 0.05):
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.poll_seconds = poll_seconds
        self._file = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.path, "a+b")
        if self.path.stat().st_size == 0:
            self._file.write(b"0")
            self._file.flush()
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self._acquire()
                return self
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    self._file.close()
                    self._file = None
                    raise IndexBuildInProgressError(
                        f"索引正在由另一个进程构建，等待超过 {self.timeout_seconds:g} 秒。"
                    )
                time.sleep(self.poll_seconds)

    def __exit__(self, exc_type, exc, traceback):
        if self._file is not None:
            self._release()
            self._file.close()
            self._file = None

    def _acquire(self) -> None:
        if os.name == "nt":
            import msvcrt

            self._file.seek(0)
            msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _release(self) -> None:
        if os.name == "nt":
            import msvcrt

            self._file.seek(0)
            msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)


class IndexManager:
    def __init__(
        self,
        index_root: str | Path = ".rag_index",
        *,
        lock_timeout_seconds: float = 30.0,
        fault_injector: Callable[[str], None] | None = None,
    ):
        self.index_root = Path(index_root)
        self.lock_timeout_seconds = lock_timeout_seconds
        self.fault_injector = fault_injector

    def build_or_load(
        self,
        pdf_path: str | Path,
        *,
        embedder,
        chunk_size: int = 300,
        overlap: int = 50,
        force_rebuild: bool = False,
    ) -> ManagedIndex:
        identity = self._identity(
            pdf_path, embedder=embedder, chunk_size=chunk_size, overlap=overlap
        )
        if not force_rebuild:
            loaded = self._try_load_active(identity)
            if loaded is not None:
                return loaded
        return self.rebuild(embedder=embedder, **identity)

    def load_published(
        self,
        pdf_path: str | Path,
        *,
        embedder,
        chunk_size: int = 300,
        overlap: int = 50,
        recover_pointer: bool = True,
    ) -> ManagedIndex:
        """Load only the exact requested snapshot; never auto-build or use stale content."""

        identity = self._identity(
            pdf_path, embedder=embedder, chunk_size=chunk_size, overlap=overlap
        )
        loaded = self._try_load_active(identity)
        if loaded is not None:
            return loaded
        document_dir = self._document_index_dir(
            identity["pdf_path"], identity["document_id"]
        )
        candidate = self._try_load_version(
            document_dir, identity["version_id"], identity
        )
        if candidate is not None and recover_pointer:
            with BuildLock(document_dir / "build.lock", self.lock_timeout_seconds):
                loaded = self._try_load_active(identity)
                if loaded is not None:
                    return loaded
                self._publish_active(document_dir, candidate.manifest)
            return ManagedIndex(candidate.vector_store, candidate.manifest, "recover_pointer")

        active_path = document_dir / "active.json"
        target_path = document_dir / "versions" / identity["version_id"]
        if target_path.exists():
            raise IndexCorruptionError(
                "请求对应的索引版本存在但未通过完整性校验，未回退到其他文档版本。"
            )
        if active_path.exists():
            raise IndexUnavailableError(
                "活动索引与当前文档或构建配置不匹配，需要显式构建目标版本。"
            )
        raise IndexUnavailableError("尚未发布当前文档对应的索引版本。")

    def check(
        self,
        pdf_path: str | Path,
        *,
        embedder,
        chunk_size: int = 300,
        overlap: int = 50,
    ) -> IndexManifest:
        return self.load_published(
            pdf_path,
            embedder=embedder,
            chunk_size=chunk_size,
            overlap=overlap,
            recover_pointer=False,
        ).manifest

    def active_version_token(self, pdf_path: str | Path) -> str:
        pdf_path = Path(pdf_path)
        document_id = calculate_document_id(pdf_path)
        active_path = self._document_index_dir(pdf_path, document_id) / "active.json"
        try:
            active = _read_json(active_path)
        except (OSError, json.JSONDecodeError):
            return "unpublished"
        if active.get("document_id") != document_id:
            return "invalid"
        version_id = active.get("version_id")
        return version_id if isinstance(version_id, str) and version_id else "invalid"

    def rebuild(
        self,
        pdf_path: str | Path,
        *,
        embedder,
        chunk_size: int = 300,
        overlap: int = 50,
        checksum: str | None = None,
        embedding_model: str | None = None,
        embedding_revision: str | None = None,
        document_id: str | None = None,
        version_id: str | None = None,
        **_ignored,
    ) -> ManagedIndex:
        pdf_path = Path(pdf_path)
        checksum = checksum or calculate_file_checksum(pdf_path)
        embedding_model = embedding_model or getattr(
            embedder, "model_name", embedder.__class__.__name__
        )
        embedding_revision = embedding_revision or getattr(embedder, "model_revision", None)
        document_id = document_id or calculate_document_id(pdf_path)
        version_id = version_id or calculate_version_id(
            checksum=checksum,
            chunk_size=chunk_size,
            overlap=overlap,
            embedding_model=embedding_model,
            embedding_revision=embedding_revision,
        )
        identity = {
            "pdf_path": pdf_path,
            "checksum": checksum,
            "embedding_model": embedding_model,
            "embedding_revision": embedding_revision,
            "document_id": document_id,
            "version_id": version_id,
            "chunk_size": chunk_size,
            "overlap": overlap,
        }
        document_dir = self._document_index_dir(pdf_path, document_id)
        with BuildLock(document_dir / "build.lock", self.lock_timeout_seconds):
            loaded = self._try_load_active(identity)
            if loaded is not None:
                return ManagedIndex(loaded.vector_store, loaded.manifest, "load_after_wait")
            existing = self._try_load_version(document_dir, version_id, identity)
            if existing is not None:
                self._publish_active(document_dir, existing.manifest)
                return ManagedIndex(existing.vector_store, existing.manifest, "publish_existing")
            return self._build_and_publish(document_dir, embedder=embedder, **identity)

    def _build_and_publish(
        self,
        document_dir: Path,
        *,
        pdf_path: Path,
        embedder,
        checksum: str,
        embedding_model: str,
        embedding_revision: str | None,
        document_id: str,
        version_id: str,
        chunk_size: int,
        overlap: int,
    ) -> ManagedIndex:
        from src.loader import load_pdf_pages
        from src.splitter import split_pages_with_ref

        versions_dir = document_dir / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        temporary_dir = versions_dir / f".tmp-{version_id[:12]}-{uuid4().hex}"
        final_dir = versions_dir / version_id
        temporary_dir.mkdir()
        try:
            document, pages = load_pdf_pages(str(pdf_path))
            cleaned_text = "\n".join(page.text for page in pages if page.text.strip())
            chunk_records = split_pages_with_ref(
                document, pages, chunk_size=chunk_size, overlap=overlap
            )
            if not chunk_records:
                raise EmptyDocumentError(EMPTY_DOCUMENT_MESSAGE)
            for record in chunk_records:
                record["document_id"] = document_id

            embeddings = embedder.embed_texts([item["text"] for item in chunk_records])
            store = VectorStore(dim=len(embeddings[0]))
            store.add(embeddings, chunk_records)
            index_path = temporary_dir / "index.faiss"
            metadata_path = temporary_dir / "metadata.json"
            store.save_index(index_path)
            self._fault("after_index_write")
            store.save_metadata(metadata_path)
            self._fault("after_metadata_write")

            manifest = IndexManifest(
                schema_version=INDEX_SCHEMA_VERSION,
                source=pdf_path.name,
                document_id=document_id,
                version_id=version_id,
                checksum_sha256=checksum,
                chunk_size=chunk_size,
                overlap=overlap,
                embedding_model=embedding_model,
                embedding_revision=embedding_revision,
                parser_version=PARSER_VERSION,
                embedding_dim=len(embeddings[0]),
                chunk_count=len(chunk_records),
                index_file="index.faiss",
                metadata_file="metadata.json",
                index_sha256=calculate_file_checksum(index_path),
                metadata_sha256=calculate_file_checksum(metadata_path),
            )
            _write_json(temporary_dir / "manifest.json", asdict(manifest), durable=True)
            self._fault("before_version_validation")
            self._load_version(temporary_dir, expected=manifest)

            if final_dir.exists():
                corrupt_dir = versions_dir / f".corrupt-{version_id[:12]}-{uuid4().hex}"
                os.replace(final_dir, corrupt_dir)
            os.replace(temporary_dir, final_dir)
            self._fault("after_version_publish")
            self._publish_active(document_dir, manifest)
            return ManagedIndex(
                store, manifest, "rebuild", cleaned_text_preview=cleaned_text[:2000]
            )
        finally:
            if temporary_dir.exists():
                shutil.rmtree(temporary_dir, ignore_errors=True)

    def _publish_active(self, document_dir: Path, manifest: IndexManifest) -> None:
        document_dir.mkdir(parents=True, exist_ok=True)
        pointer = {
            "schema_version": ACTIVE_SCHEMA_VERSION,
            "document_id": manifest.document_id,
            "version_id": manifest.version_id,
        }
        temporary = document_dir / f".active-{uuid4().hex}.tmp"
        _write_json(temporary, pointer, durable=True)
        self._fault("before_active_replace")
        os.replace(temporary, document_dir / "active.json")

    def _try_load_active(self, identity: dict[str, Any]) -> ManagedIndex | None:
        document_dir = self._document_index_dir(
            identity["pdf_path"], identity["document_id"]
        )
        active_path = document_dir / "active.json"
        if not active_path.exists():
            return None
        try:
            active = _read_json(active_path)
        except (OSError, json.JSONDecodeError):
            return None
        if active.get("schema_version") != ACTIVE_SCHEMA_VERSION:
            return None
        if active.get("document_id") != identity["document_id"]:
            return None
        if active.get("version_id") != identity["version_id"]:
            return None
        loaded = self._try_load_version(document_dir, identity["version_id"], identity)
        if loaded is None:
            return None
        return ManagedIndex(loaded.vector_store, loaded.manifest, "load")

    def _try_load_version(
        self, document_dir: Path, version_id: str, identity: dict[str, Any]
    ) -> ManagedIndex | None:
        version_dir = document_dir / "versions" / version_id
        try:
            manifest = self._manifest_for_identity(version_dir / "manifest.json", identity)
            if manifest is None:
                return None
            store = self._load_version(version_dir, expected=manifest)
            return ManagedIndex(store, manifest, "load")
        except (OSError, ValueError, IndexCorruptionError, json.JSONDecodeError):
            return None

    def _manifest_for_identity(
        self, manifest_path: Path, identity: dict[str, Any]
    ) -> IndexManifest | None:
        if not manifest_path.exists():
            return None
        try:
            manifest = IndexManifest(**_read_json(manifest_path))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        required = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "source": identity["pdf_path"].name,
            "document_id": identity["document_id"],
            "version_id": identity["version_id"],
            "checksum_sha256": identity["checksum"],
            "chunk_size": identity["chunk_size"],
            "overlap": identity["overlap"],
            "embedding_model": identity["embedding_model"],
            "embedding_revision": identity["embedding_revision"],
            "parser_version": PARSER_VERSION,
        }
        if any(getattr(manifest, key) != value for key, value in required.items()):
            return None
        return manifest

    def _load_version(self, version_dir: Path, *, expected: IndexManifest) -> VectorStore:
        index_path = version_dir / expected.index_file
        metadata_path = version_dir / expected.metadata_file
        if not index_path.is_file() or not metadata_path.is_file():
            raise IndexCorruptionError("索引产物文件缺失。")
        if calculate_file_checksum(index_path) != expected.index_sha256:
            raise IndexCorruptionError("FAISS 索引哈希不匹配。")
        if calculate_file_checksum(metadata_path) != expected.metadata_sha256:
            raise IndexCorruptionError("索引 metadata 哈希不匹配。")
        try:
            return VectorStore.load_from_files(
                index_path,
                metadata_path,
                expected_dim=expected.embedding_dim,
                expected_count=expected.chunk_count,
            )
        except (OSError, ValueError, RuntimeError) as exc:
            raise IndexCorruptionError("索引结构校验失败。") from exc

    def _identity(
        self,
        pdf_path: str | Path,
        *,
        embedder,
        chunk_size: int,
        overlap: int,
    ) -> dict[str, Any]:
        pdf_path = Path(pdf_path)
        checksum = calculate_file_checksum(pdf_path)
        embedding_model = getattr(embedder, "model_name", embedder.__class__.__name__)
        embedding_revision = getattr(embedder, "model_revision", None)
        document_id = calculate_document_id(pdf_path)
        return {
            "pdf_path": pdf_path,
            "checksum": checksum,
            "embedding_model": embedding_model,
            "embedding_revision": embedding_revision,
            "document_id": document_id,
            "version_id": calculate_version_id(
                checksum=checksum,
                chunk_size=chunk_size,
                overlap=overlap,
                embedding_model=embedding_model,
                embedding_revision=embedding_revision,
            ),
            "chunk_size": chunk_size,
            "overlap": overlap,
        }

    def _document_index_dir(self, pdf_path: Path, document_id: str) -> Path:
        return self.index_root / f"{_safe_name(pdf_path.stem)}_{document_id[:12]}"

    def _fault(self, point: str) -> None:
        if self.fault_injector is not None:
            self.fault_injector(point)


def calculate_file_checksum(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def calculate_document_id(path: str | Path) -> str:
    canonical = os.path.normcase(str(Path(path).resolve()))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def calculate_version_id(
    *,
    checksum: str,
    chunk_size: int,
    overlap: int,
    embedding_model: str,
    embedding_revision: str | None,
) -> str:
    payload = {
        "checksum_sha256": checksum,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "embedding_model": embedding_model,
        "embedding_revision": embedding_revision,
        "parser_version": PARSER_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _safe_name(value: str) -> str:
    ascii_name = "".join(
        char if char.isascii() and (char.isalnum() or char in "-_.") else "_"
        for char in value
    ).strip("._")
    ascii_name = re.sub(r"_+", "_", ascii_name).strip("_")
    suffix = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    if not ascii_name:
        ascii_name = "document"
    return f"{ascii_name}_{suffix}"


def _read_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, data: dict[str, Any], *, durable: bool = False) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        if durable:
            file.flush()
            os.fsync(file.fileno())
