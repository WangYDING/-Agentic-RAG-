from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

from src.document_schema import DocumentMetadata, Page
from src.index_manager import BuildLock, calculate_file_checksum
from src.splitter import split_pages_with_ref
from src.vector_store import VectorStore


DOCUMENT_INDEX_SCHEMA_VERSION = 1
KNOWLEDGE_BASE_SCHEMA_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class KnowledgeBaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class KnowledgeDocumentManifest:
    schema_version: int
    spec_id: str
    edition_id: str
    source: str
    source_pdf_sha256: str
    ingestion_artifact_sha256: str
    parser_version: str
    embedding_model: str
    embedding_revision: str | None
    chunk_size: int
    overlap: int
    version_id: str
    embedding_dim: int
    chunk_count: int
    index_file: str
    metadata_file: str
    index_sha256: str
    metadata_sha256: str

    @property
    def business_id(self) -> str:
        return f"{self.spec_id}@{self.edition_id}"


@dataclass(frozen=True)
class KnowledgeDocumentIndex:
    path: Path
    manifest: KnowledgeDocumentManifest
    vector_store: VectorStore


@dataclass(frozen=True)
class KnowledgeBaseSnapshot:
    snapshot_id: str
    documents: tuple[KnowledgeDocumentIndex, ...]
    manifest_path: Path


class KnowledgeDocumentIndexer:
    def __init__(self, root: str | Path, *, lock_timeout_seconds: float = 30.0):
        self.root = Path(root)
        self.lock_timeout_seconds = lock_timeout_seconds

    def build(
        self,
        document: DocumentMetadata,
        pages: Iterable[Page],
        *,
        source_pdf_sha256: str,
        ingestion_artifact_sha256: str,
        parser_version: str,
        embedder,
        chunk_size: int = 300,
        overlap: int = 50,
    ) -> KnowledgeDocumentIndex:
        if document.spec_id is None or document.edition_id is None:
            raise KnowledgeBaseError("multi-spec document identity is required")
        _require_sha256(source_pdf_sha256, "source_pdf_sha256")
        _require_sha256(ingestion_artifact_sha256, "ingestion_artifact_sha256")
        model = getattr(embedder, "model_name", embedder.__class__.__name__)
        revision = getattr(embedder, "model_revision", None)
        identity = {
            "spec_id": document.spec_id,
            "edition_id": document.edition_id,
            "source_pdf_sha256": source_pdf_sha256,
            "ingestion_artifact_sha256": ingestion_artifact_sha256,
            "parser_version": parser_version,
            "embedding_model": model,
            "embedding_revision": revision,
            "chunk_size": chunk_size,
            "overlap": overlap,
        }
        version_id = _json_hash(identity)
        document_root = self.root / _safe_name(document.spec_id) / _safe_name(document.edition_id)
        version_dir = document_root / "versions" / version_id
        with BuildLock(document_root / "build.lock", self.lock_timeout_seconds):
            if version_dir.exists():
                return load_document_index(version_dir)
            chunks = split_pages_with_ref(
                document, pages, chunk_size=chunk_size, overlap=overlap
            )
            if not chunks:
                raise KnowledgeBaseError(f"document has no chunks: {document.spec_id}@{document.edition_id}")
            embeddings = embedder.embed_texts([item["text"] for item in chunks])
            if len(embeddings) != len(chunks) or not embeddings:
                raise KnowledgeBaseError("embedding result count does not match chunks")
            store = VectorStore(dim=len(embeddings[0]))
            store.add(embeddings, chunks)
            temporary = version_dir.parent / f".tmp-{version_id[:12]}-{uuid4().hex}"
            temporary.mkdir(parents=True)
            try:
                index_path = temporary / "index.faiss"
                metadata_path = temporary / "metadata.json"
                store.save(index_path, metadata_path)
                manifest = KnowledgeDocumentManifest(
                    schema_version=DOCUMENT_INDEX_SCHEMA_VERSION,
                    spec_id=document.spec_id,
                    edition_id=document.edition_id,
                    source=document.source,
                    source_pdf_sha256=source_pdf_sha256,
                    ingestion_artifact_sha256=ingestion_artifact_sha256,
                    parser_version=parser_version,
                    embedding_model=model,
                    embedding_revision=revision,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    version_id=version_id,
                    embedding_dim=len(embeddings[0]),
                    chunk_count=len(chunks),
                    index_file="index.faiss",
                    metadata_file="metadata.json",
                    index_sha256=calculate_file_checksum(index_path),
                    metadata_sha256=calculate_file_checksum(metadata_path),
                )
                _write_json(temporary / "manifest.json", asdict(manifest))
                load_document_index(temporary)
                version_dir.parent.mkdir(parents=True, exist_ok=True)
                os.replace(temporary, version_dir)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary, ignore_errors=True)
        return load_document_index(version_dir)


class KnowledgeBaseManager:
    def __init__(
        self,
        root: str | Path,
        *,
        lock_timeout_seconds: float = 30.0,
        fault_injector: Callable[[str], None] | None = None,
    ):
        self.root = Path(root)
        self.lock_timeout_seconds = lock_timeout_seconds
        self.fault_injector = fault_injector

    def publish(self, document_paths: Iterable[str | Path]) -> KnowledgeBaseSnapshot:
        documents = tuple(load_document_index(Path(path)) for path in document_paths)
        if not documents:
            raise KnowledgeBaseError("knowledge base must contain at least one document")
        identities = [item.manifest.business_id for item in documents]
        if len(set(identities)) != len(identities):
            raise KnowledgeBaseError("knowledge base contains duplicate document identities")
        ordered = tuple(sorted(documents, key=lambda item: item.manifest.business_id))
        refs = [self._document_reference(item) for item in ordered]
        snapshot_id = _json_hash({"documents": refs})
        snapshots = self.root / "snapshots"
        final = snapshots / snapshot_id
        with BuildLock(self.root / "publish.lock", self.lock_timeout_seconds):
            if not final.exists():
                temporary = snapshots / f".tmp-{snapshot_id[:12]}-{uuid4().hex}"
                temporary.mkdir(parents=True)
                try:
                    _write_json(
                        temporary / "manifest.json",
                        {
                            "schema_version": KNOWLEDGE_BASE_SCHEMA_VERSION,
                            "snapshot_id": snapshot_id,
                            "documents": refs,
                        },
                    )
                    self._fault("before_snapshot_validation")
                    self._load_snapshot_dir(temporary)
                    os.replace(temporary, final)
                finally:
                    if temporary.exists():
                        shutil.rmtree(temporary, ignore_errors=True)
            self._fault("before_active_replace")
            self._publish_pointer(snapshot_id)
        return self.load(snapshot_id)

    def load_active(self) -> KnowledgeBaseSnapshot:
        try:
            pointer = _read_json(self.root / "active.json")
        except (OSError, json.JSONDecodeError) as exc:
            raise KnowledgeBaseError("knowledge base active pointer is unavailable") from exc
        if pointer.get("schema_version") != KNOWLEDGE_BASE_SCHEMA_VERSION:
            raise KnowledgeBaseError("knowledge base active pointer schema is invalid")
        return self.load(pointer.get("snapshot_id"))

    def load(self, snapshot_id: str) -> KnowledgeBaseSnapshot:
        if not isinstance(snapshot_id, str) or not _SHA256.fullmatch(snapshot_id):
            raise KnowledgeBaseError("knowledge base snapshot id is invalid")
        return self._load_snapshot_dir(self.root / "snapshots" / snapshot_id)

    def rollback(self, snapshot_id: str) -> KnowledgeBaseSnapshot:
        snapshot = self.load(snapshot_id)
        with BuildLock(self.root / "publish.lock", self.lock_timeout_seconds):
            self._publish_pointer(snapshot.snapshot_id)
        return snapshot

    def _load_snapshot_dir(self, directory: Path) -> KnowledgeBaseSnapshot:
        try:
            payload = _read_json(directory / "manifest.json")
        except (OSError, json.JSONDecodeError) as exc:
            raise KnowledgeBaseError("knowledge base snapshot manifest is unavailable") from exc
        if payload.get("schema_version") != KNOWLEDGE_BASE_SCHEMA_VERSION:
            raise KnowledgeBaseError("knowledge base snapshot schema is invalid")
        refs = payload.get("documents")
        if not isinstance(refs, list) or not refs:
            raise KnowledgeBaseError("knowledge base document list is invalid")
        expected_id = _json_hash({"documents": refs})
        if payload.get("snapshot_id") != expected_id:
            raise KnowledgeBaseError("knowledge base snapshot identity mismatch")
        documents = []
        for ref in refs:
            relative = ref.get("manifest_path") if isinstance(ref, dict) else None
            if not isinstance(relative, str):
                raise KnowledgeBaseError("knowledge base document reference is invalid")
            manifest_path = (self.root / relative).resolve()
            if self.root.resolve() not in manifest_path.parents:
                raise KnowledgeBaseError("knowledge base document reference escapes root")
            loaded = load_document_index(manifest_path.parent)
            if (
                loaded.manifest.business_id != ref.get("business_id")
                or loaded.manifest.version_id != ref.get("version_id")
                or calculate_file_checksum(manifest_path) != ref.get("manifest_sha256")
            ):
                raise KnowledgeBaseError("knowledge base document reference mismatch")
            documents.append(loaded)
        return KnowledgeBaseSnapshot(expected_id, tuple(documents), directory / "manifest.json")

    def _document_reference(self, document: KnowledgeDocumentIndex) -> dict:
        manifest_path = (document.path / "manifest.json").resolve()
        try:
            relative = manifest_path.relative_to(self.root.resolve()).as_posix()
        except ValueError as exc:
            raise KnowledgeBaseError("document index must be inside knowledge base root") from exc
        return {
            "business_id": document.manifest.business_id,
            "version_id": document.manifest.version_id,
            "manifest_path": relative,
            "manifest_sha256": calculate_file_checksum(manifest_path),
        }

    def _publish_pointer(self, snapshot_id: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.root / f".active-{uuid4().hex}.tmp"
        _write_json(
            temporary,
            {"schema_version": KNOWLEDGE_BASE_SCHEMA_VERSION, "snapshot_id": snapshot_id},
        )
        os.replace(temporary, self.root / "active.json")

    def _fault(self, point: str) -> None:
        if self.fault_injector is not None:
            self.fault_injector(point)


def load_document_index(path: str | Path) -> KnowledgeDocumentIndex:
    path = Path(path)
    try:
        manifest = KnowledgeDocumentManifest(**_read_json(path / "manifest.json"))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise KnowledgeBaseError(f"invalid document index manifest: {path}") from exc
    if manifest.schema_version != DOCUMENT_INDEX_SCHEMA_VERSION:
        raise KnowledgeBaseError("document index schema is invalid")
    _require_sha256(manifest.source_pdf_sha256, "source_pdf_sha256")
    _require_sha256(manifest.ingestion_artifact_sha256, "ingestion_artifact_sha256")
    index_path = path / manifest.index_file
    metadata_path = path / manifest.metadata_file
    if (
        calculate_file_checksum(index_path) != manifest.index_sha256
        or calculate_file_checksum(metadata_path) != manifest.metadata_sha256
    ):
        raise KnowledgeBaseError("document index artifact hash mismatch")
    store = VectorStore.load_from_files(
        index_path,
        metadata_path,
        expected_dim=manifest.embedding_dim,
        expected_count=manifest.chunk_count,
    )
    for record in store.chunk_records:
        if (
            record.get("spec_id") != manifest.spec_id
            or record.get("edition_id") != manifest.edition_id
        ):
            raise KnowledgeBaseError("chunk identity does not match document manifest")
    return KnowledgeDocumentIndex(path, manifest, store)


def _json_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_sha256(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise KnowledgeBaseError(f"{field_name} must be a SHA-256 value")


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value)
