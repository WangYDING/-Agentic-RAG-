import hashlib
import json
import threading
from pathlib import Path

import pytest

from src.document_schema import DocumentMetadata, Page, PageMetadata
from src.index_manager import IndexBuildInProgressError
from src.knowledge_base import (
    KnowledgeBaseError,
    KnowledgeBaseManager,
    KnowledgeDocumentIndexer,
)


pytestmark = pytest.mark.integration


class FakeEmbedder:
    model_name = "fake-embedder"
    model_revision = "fixture-v1"

    def embed_texts(self, texts):
        return [[float(index + 1) for index in range(8)] for _ in texts]


def _build_document(root: Path, spec_id: str, edition_id: str, text: str):
    document = DocumentMetadata(
        f"{spec_id}@{edition_id}",
        f"{spec_id}-{edition_id}.pdf",
        1,
        spec_id,
        edition_id,
    )
    page = Page(
        text,
        text,
        PageMetadata(
            document.document_id,
            document.source,
            1,
            len(text),
            len(text),
            spec_id,
            edition_id,
        ),
    )
    source_hash = hashlib.sha256(f"{spec_id}:{edition_id}".encode()).hexdigest()
    artifact_hash = hashlib.sha256(text.encode()).hexdigest()
    return KnowledgeDocumentIndexer(root / "document_indexes").build(
        document,
        [page],
        source_pdf_sha256=source_hash,
        ingestion_artifact_sha256=artifact_hash,
        parser_version="fixture-v1",
        embedder=FakeEmbedder(),
    )


def _three_documents(root: Path):
    return [
        _build_document(root, "cn.first", "2025", "1.0.1 第一份规范"),
        _build_document(root, "cn.second", "2022", "1.0.1 第二份规范"),
        _build_document(root, "cn.third", "2013", "1.0.1 第三份规范"),
    ]


def test_three_document_snapshot_reloads_after_restart(tmp_path):
    documents = _three_documents(tmp_path)
    published = KnowledgeBaseManager(tmp_path).publish(item.path for item in documents)

    loaded = KnowledgeBaseManager(tmp_path).load_active()

    assert loaded.snapshot_id == published.snapshot_id
    assert [item.manifest.business_id for item in loaded.documents] == [
        "cn.first@2025",
        "cn.second@2022",
        "cn.third@2013",
    ]


def test_corrupt_document_refuses_publish_and_keeps_old_snapshot(tmp_path):
    documents = _three_documents(tmp_path)
    manager = KnowledgeBaseManager(tmp_path)
    previous = manager.publish(item.path for item in documents)
    replacement = _build_document(
        tmp_path, "cn.second", "2023", "damaged replacement"
    )
    metadata = replacement.path / "metadata.json"
    metadata.write_text("[]", encoding="utf-8")

    with pytest.raises(KnowledgeBaseError, match="hash mismatch"):
        manager.publish([documents[0].path, replacement.path, documents[2].path])

    assert manager.load_active().snapshot_id == previous.snapshot_id


def test_interrupted_publish_does_not_create_active_half_snapshot(tmp_path):
    documents = _three_documents(tmp_path)

    def fail(point):
        if point == "before_snapshot_validation":
            raise RuntimeError("interrupted")

    with pytest.raises(RuntimeError, match="interrupted"):
        KnowledgeBaseManager(tmp_path, fault_injector=fail).publish(
            item.path for item in documents
        )

    assert not (tmp_path / "active.json").exists()
    assert list((tmp_path / "snapshots").glob(".tmp-*")) == []


def test_replacing_one_document_creates_clean_snapshot_and_can_rollback(tmp_path):
    documents = _three_documents(tmp_path)
    manager = KnowledgeBaseManager(tmp_path)
    old = manager.publish(item.path for item in documents)
    replacement = _build_document(
        tmp_path, "cn.second", "2022", "1.0.1 第二份规范的新摄取文本"
    )
    new = manager.publish([documents[0].path, replacement.path, documents[2].path])

    assert new.snapshot_id != old.snapshot_id
    assert {item.manifest.version_id for item in new.documents}.isdisjoint(
        {documents[1].manifest.version_id}
    )
    assert manager.rollback(old.snapshot_id).snapshot_id == old.snapshot_id
    assert manager.load_active().snapshot_id == old.snapshot_id


def test_publish_failure_before_pointer_replace_keeps_previous(tmp_path):
    documents = _three_documents(tmp_path)
    previous = KnowledgeBaseManager(tmp_path).publish(item.path for item in documents)
    replacement = _build_document(tmp_path, "cn.second", "2023", "new edition")

    def fail(point):
        if point == "before_active_replace":
            raise RuntimeError("pointer failure")

    with pytest.raises(RuntimeError, match="pointer failure"):
        KnowledgeBaseManager(tmp_path, fault_injector=fail).publish(
            [documents[0].path, replacement.path, documents[2].path]
        )

    assert KnowledgeBaseManager(tmp_path).load_active().snapshot_id == previous.snapshot_id


def test_concurrent_publish_cannot_mix_versions(tmp_path):
    documents = _three_documents(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    failures = []

    def pause(point):
        if point == "before_active_replace":
            entered.set()
            release.wait(timeout=3)

    def first_publish():
        try:
            KnowledgeBaseManager(tmp_path, fault_injector=pause).publish(
                item.path for item in documents
            )
        except Exception as exc:  # pragma: no cover - asserted below
            failures.append(exc)

    thread = threading.Thread(target=first_publish)
    thread.start()
    assert entered.wait(timeout=2)
    with pytest.raises(IndexBuildInProgressError):
        KnowledgeBaseManager(tmp_path, lock_timeout_seconds=0.1).publish(
            item.path for item in documents
        )
    release.set()
    thread.join(timeout=3)

    assert failures == []
    active = json.loads((tmp_path / "active.json").read_text(encoding="utf-8"))
    assert KnowledgeBaseManager(tmp_path).load(active["snapshot_id"]).snapshot_id
