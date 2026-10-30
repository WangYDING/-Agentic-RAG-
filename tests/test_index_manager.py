import tempfile
import unittest
import json
import threading
import time
from pathlib import Path

import fitz
import pytest

from src.index_manager import (
    INDEX_SCHEMA_VERSION,
    IndexManager,
    calculate_document_id,
    calculate_file_checksum,
)


pytestmark = pytest.mark.integration


class FakeEmbedder:
    model_name = "fake-embedder"

    def __init__(self):
        self.embed_texts_calls = 0

    def embed_texts(self, texts):
        self.embed_texts_calls += 1
        return [[float(index + 1) for index in range(8)] for _ in texts]


def make_pdf(path: Path, text: str):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


class IndexManagerTest(unittest.TestCase):
    def test_first_build_writes_manifest_index_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "spec.pdf"
            make_pdf(pdf_path, "1.0.1\nhello world")
            embedder = FakeEmbedder()

            result = IndexManager(root / "index").build_or_load(pdf_path, embedder=embedder)
            index_dir = next((root / "index").iterdir())
            version_dir = index_dir / "versions" / result.manifest.version_id

            self.assertEqual(result.action, "rebuild")
            self.assertEqual(embedder.embed_texts_calls, 1)
            self.assertTrue((index_dir / "active.json").exists())
            self.assertTrue((version_dir / "manifest.json").exists())
            self.assertTrue((version_dir / "index.faiss").exists())
            self.assertTrue((version_dir / "metadata.json").exists())
            self.assertEqual(result.manifest.checksum_sha256, calculate_file_checksum(pdf_path))
            self.assertEqual(result.manifest.document_id, calculate_document_id(pdf_path))
            self.assertTrue(result.manifest.version_id)
            self.assertEqual(
                result.manifest.index_sha256,
                calculate_file_checksum(version_dir / "index.faiss"),
            )
            self.assertEqual(
                result.manifest.metadata_sha256,
                calculate_file_checksum(version_dir / "metadata.json"),
            )
            self.assertEqual(result.manifest.schema_version, INDEX_SCHEMA_VERSION)
            self.assertEqual(result.vector_store.index.ntotal, result.manifest.chunk_count)
            self.assertEqual(len(result.vector_store.chunk_records), result.manifest.chunk_count)

    def test_unchanged_document_loads_existing_index_without_embedding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "spec.pdf"
            make_pdf(pdf_path, "1.0.1\nhello world")
            manager = IndexManager(root / "index")
            manager.build_or_load(pdf_path, embedder=FakeEmbedder())

            embedder = FakeEmbedder()
            result = manager.build_or_load(pdf_path, embedder=embedder)

            self.assertEqual(result.action, "load")
            self.assertEqual(embedder.embed_texts_calls, 0)
            self.assertGreater(result.vector_store.index.ntotal, 0)

    def test_changed_document_triggers_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "spec.pdf"
            make_pdf(pdf_path, "1.0.1\nhello world")
            manager = IndexManager(root / "index")
            first = manager.build_or_load(pdf_path, embedder=FakeEmbedder())

            pdf_path.unlink()
            make_pdf(pdf_path, "1.0.1\nchanged document")
            embedder = FakeEmbedder()
            second = manager.build_or_load(pdf_path, embedder=embedder)

            self.assertEqual(second.action, "rebuild")
            self.assertEqual(embedder.embed_texts_calls, 1)
            self.assertNotEqual(first.manifest.checksum_sha256, second.manifest.checksum_sha256)

    def test_force_rebuild_ignores_valid_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "spec.pdf"
            make_pdf(pdf_path, "1.0.1\nhello world")
            manager = IndexManager(root / "index")
            manager.build_or_load(pdf_path, embedder=FakeEmbedder())

            embedder = FakeEmbedder()
            result = manager.build_or_load(pdf_path, embedder=embedder, force_rebuild=True)

            self.assertEqual(result.action, "load_after_wait")
            self.assertEqual(embedder.embed_texts_calls, 0)

    def test_non_ascii_document_name_still_loads_persisted_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "城市轨道交通工程设计标准.pdf"
            make_pdf(pdf_path, "1.0.1\nhello world")
            manager = IndexManager(root / "index")
            manager.build_or_load(pdf_path, embedder=FakeEmbedder())

            embedder = FakeEmbedder()
            result = manager.build_or_load(pdf_path, embedder=embedder)
            index_files = list((root / "index").glob("*/versions/*/index.faiss"))

            self.assertEqual(result.action, "load")
            self.assertEqual(embedder.embed_texts_calls, 0)
            self.assertEqual(len(index_files), 1)

    def test_manifest_schema_version_mismatch_triggers_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "spec.pdf"
            make_pdf(pdf_path, "1.0.1\nhello world")
            manager = IndexManager(root / "index")
            manager.build_or_load(pdf_path, embedder=FakeEmbedder())
            manifest_path = next((root / "index").glob("*/versions/*/manifest.json"))
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["schema_version"] = -1
            manifest_path.write_text(json.dumps(data), encoding="utf-8")

            embedder = FakeEmbedder()
            result = manager.build_or_load(pdf_path, embedder=embedder)

            self.assertEqual(result.action, "rebuild")
            self.assertEqual(embedder.embed_texts_calls, 1)

    def test_same_filename_in_different_directories_has_distinct_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_path = root / "first" / "spec.pdf"
            second_path = root / "second" / "spec.pdf"
            first_path.parent.mkdir()
            second_path.parent.mkdir()
            make_pdf(first_path, "1.0.1\nfirst")
            make_pdf(second_path, "1.0.1\nsecond")
            manager = IndexManager(root / "index")

            first = manager.build_or_load(first_path, embedder=FakeEmbedder())
            second = manager.build_or_load(second_path, embedder=FakeEmbedder())

            self.assertNotEqual(first.manifest.document_id, second.manifest.document_id)
            self.assertEqual(len(list((root / "index").iterdir())), 2)

    def test_chunk_parameters_change_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "spec.pdf"
            make_pdf(pdf_path, "1.0.1\nhello world")
            manager = IndexManager(root / "index")

            first = manager.build_or_load(pdf_path, embedder=FakeEmbedder(), chunk_size=300)
            second = manager.build_or_load(pdf_path, embedder=FakeEmbedder(), chunk_size=120)

            self.assertNotEqual(first.manifest.version_id, second.manifest.version_id)

    def test_modified_metadata_hash_is_detected_and_rebuilt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "spec.pdf"
            make_pdf(pdf_path, "1.0.1\nhello world")
            manager = IndexManager(root / "index")
            manager.build_or_load(pdf_path, embedder=FakeEmbedder())
            metadata_path = next((root / "index").glob("*/versions/*/metadata.json"))
            metadata_path.write_text("[]", encoding="utf-8")

            embedder = FakeEmbedder()
            result = manager.build_or_load(pdf_path, embedder=embedder)

            self.assertEqual(result.action, "rebuild")
            self.assertEqual(embedder.embed_texts_calls, 1)

    def test_interrupted_build_does_not_replace_previous_active_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "spec.pdf"
            make_pdf(pdf_path, "1.0.1\nold content")
            manager = IndexManager(root / "index")
            first = manager.build_or_load(pdf_path, embedder=FakeEmbedder())
            document_dir = next((root / "index").iterdir())
            active_before = (document_dir / "active.json").read_text(encoding="utf-8")

            pdf_path.unlink()
            make_pdf(pdf_path, "1.0.1\nnew content")

            def fail(point):
                if point == "after_index_write":
                    raise RuntimeError("simulated interruption")

            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                IndexManager(root / "index", fault_injector=fail).build_or_load(
                    pdf_path, embedder=FakeEmbedder()
                )

            self.assertEqual(
                (document_dir / "active.json").read_text(encoding="utf-8"),
                active_before,
            )
            self.assertTrue(
                (document_dir / "versions" / first.manifest.version_id / "manifest.json").exists()
            )

    def test_failure_before_active_replace_keeps_previous_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "spec.pdf"
            make_pdf(pdf_path, "1.0.1\nold content")
            manager = IndexManager(root / "index")
            manager.build_or_load(pdf_path, embedder=FakeEmbedder())
            document_dir = next((root / "index").iterdir())
            active_before = (document_dir / "active.json").read_text(encoding="utf-8")
            pdf_path.unlink()
            make_pdf(pdf_path, "1.0.1\nnew content")

            def fail(point):
                if point == "before_active_replace":
                    raise RuntimeError("publish failed")

            with self.assertRaisesRegex(RuntimeError, "publish failed"):
                IndexManager(root / "index", fault_injector=fail).build_or_load(
                    pdf_path, embedder=FakeEmbedder()
                )

            self.assertEqual(
                (document_dir / "active.json").read_text(encoding="utf-8"),
                active_before,
            )

    def test_second_builder_times_out_while_document_lock_is_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "spec.pdf"
            make_pdf(pdf_path, "1.0.1\nhello world")
            entered = threading.Event()
            release = threading.Event()
            failures = []

            def pause(point):
                if point == "after_index_write":
                    entered.set()
                    release.wait(timeout=3)

            def first_build():
                try:
                    IndexManager(root / "index", fault_injector=pause).build_or_load(
                        pdf_path, embedder=FakeEmbedder()
                    )
                except Exception as exc:
                    failures.append(exc)

            thread = threading.Thread(target=first_build)
            thread.start()
            self.assertTrue(entered.wait(timeout=2))
            started = time.monotonic()
            with self.assertRaisesRegex(TimeoutError, "正在由另一个进程构建"):
                IndexManager(root / "index", lock_timeout_seconds=0.15).build_or_load(
                    pdf_path, embedder=FakeEmbedder()
                )
            self.assertGreaterEqual(time.monotonic() - started, 0.1)
            release.set()
            thread.join(timeout=3)
            self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
