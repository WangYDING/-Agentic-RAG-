import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.vector_store import VectorStore


INDEX_SCHEMA_VERSION = 2
EMPTY_DOCUMENT_MESSAGE = "当前文档未提取到可用文本，可能是扫描版 PDF。"


class EmptyDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class IndexManifest:
    schema_version: int
    source: str
    document_id: str
    checksum_sha256: str
    chunk_size: int
    overlap: int
    embedding_model: str
    embedding_dim: int
    chunk_count: int
    index_file: str
    metadata_file: str


@dataclass(frozen=True)
class ManagedIndex:
    vector_store: VectorStore
    manifest: IndexManifest
    action: str
    cleaned_text_preview: str = ""


class IndexManager:
    def __init__(self, index_root: str | Path = ".rag_index"):
        self.index_root = Path(index_root)

    def build_or_load(
        self,
        pdf_path: str | Path,
        *,
        embedder,
        chunk_size: int = 300,
        overlap: int = 50,
        force_rebuild: bool = False,
    ) -> ManagedIndex:
        pdf_path = Path(pdf_path)
        checksum = calculate_file_checksum(pdf_path)
        embedding_model = getattr(embedder, "model_name", embedder.__class__.__name__)
        index_dir = self._document_index_dir(pdf_path)
        manifest_path = index_dir / "manifest.json"

        if not force_rebuild:
            manifest = self._load_manifest_if_valid(
                manifest_path=manifest_path,
                pdf_path=pdf_path,
                checksum=checksum,
                chunk_size=chunk_size,
                overlap=overlap,
                embedding_model=embedding_model,
            )
            if manifest is not None:
                store = VectorStore.load_from_files(
                    index_dir / manifest.index_file,
                    index_dir / manifest.metadata_file,
                    expected_dim=manifest.embedding_dim,
                    expected_count=manifest.chunk_count,
                )
                return ManagedIndex(vector_store=store, manifest=manifest, action="load")

        return self.rebuild(
            pdf_path,
            embedder=embedder,
            chunk_size=chunk_size,
            overlap=overlap,
            checksum=checksum,
            embedding_model=embedding_model,
        )

    def rebuild(
        self,
        pdf_path: str | Path,
        *,
        embedder,
        chunk_size: int = 300,
        overlap: int = 50,
        checksum: str | None = None,
        embedding_model: str | None = None,
    ) -> ManagedIndex:
        from src.loader import load_pdf_pages
        from src.splitter import split_pages_with_ref

        pdf_path = Path(pdf_path)
        checksum = checksum or calculate_file_checksum(pdf_path)
        embedding_model = embedding_model or getattr(embedder, "model_name", embedder.__class__.__name__)
        document, pages = load_pdf_pages(str(pdf_path))
        cleaned_text = "\n".join(page.text for page in pages if page.text.strip())
        chunk_records = split_pages_with_ref(
            document,
            pages,
            chunk_size=chunk_size,
            overlap=overlap,
        )
        if not chunk_records:
            raise EmptyDocumentError(EMPTY_DOCUMENT_MESSAGE)

        embeddings = embedder.embed_texts([item["text"] for item in chunk_records])
        store = VectorStore(dim=len(embeddings[0]))
        store.add(embeddings, chunk_records)

        index_dir = self._document_index_dir(pdf_path)
        index_dir.mkdir(parents=True, exist_ok=True)
        index_file = "index.faiss"
        metadata_file = "metadata.json"
        store.save(index_dir / index_file, index_dir / metadata_file)

        manifest = IndexManifest(
            schema_version=INDEX_SCHEMA_VERSION,
            source=pdf_path.name,
            document_id=document.document_id,
            checksum_sha256=checksum,
            chunk_size=chunk_size,
            overlap=overlap,
            embedding_model=embedding_model,
            embedding_dim=len(embeddings[0]),
            chunk_count=len(chunk_records),
            index_file=index_file,
            metadata_file=metadata_file,
        )
        _write_json(index_dir / "manifest.json", asdict(manifest))
        return ManagedIndex(
            vector_store=store,
            manifest=manifest,
            action="rebuild",
            cleaned_text_preview=cleaned_text[:2000],
        )

    def _load_manifest_if_valid(
        self,
        *,
        manifest_path: Path,
        pdf_path: Path,
        checksum: str,
        chunk_size: int,
        overlap: int,
        embedding_model: str,
    ) -> IndexManifest | None:
        if not manifest_path.exists():
            return None
        data = _read_json(manifest_path)
        required = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "source": pdf_path.name,
            "checksum_sha256": checksum,
            "chunk_size": chunk_size,
            "overlap": overlap,
            "embedding_model": embedding_model,
        }
        if any(data.get(key) != value for key, value in required.items()):
            return None

        manifest = IndexManifest(**data)
        index_dir = manifest_path.parent
        if not (index_dir / manifest.index_file).exists():
            return None
        if not (index_dir / manifest.metadata_file).exists():
            return None
        return manifest

    def _document_index_dir(self, pdf_path: Path) -> Path:
        return self.index_root / _safe_name(pdf_path.stem)


def calculate_file_checksum(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
