from __future__ import annotations

import argparse
from pathlib import Path

from src.config import DEFAULT_EMBEDDING_MODEL
from src.embedder import Embedder
from src.index_manager import PARSER_VERSION, calculate_file_checksum
from src.knowledge_base import KnowledgeBaseManager, KnowledgeDocumentIndexer
from src.loader import load_pdf_pages, load_verified_ocr_pages
from src.spec_catalog import SpecCatalog, SpecCatalogError


DEFAULT_CATALOG = "data/spec_catalog.v1.json"
DEFAULT_ROOT = ".rag_knowledge_base"
OCR_PARSER_VERSION = "rapidocr-page-artifact-v1-clause-spacing"
OCR_TABLE_PARSER_VERSION = "rapidocr-page-artifact-v2-reviewed-tables"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="构建、校验和回滚多规范知识库快照")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="构建目录文档索引并原子发布快照")
    build.add_argument("--catalog", default=DEFAULT_CATALOG)
    build.add_argument("--root", default=DEFAULT_ROOT)
    build.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    build.add_argument("--embedding-revision")
    build.add_argument("--chunk-size", type=int, default=300)
    build.add_argument("--overlap", type=int, default=50)
    check = subparsers.add_parser("check", help="校验并加载活动快照")
    check.add_argument("--root", default=DEFAULT_ROOT)
    rollback = subparsers.add_parser("rollback", help="将活动指针切换到已验证旧快照")
    rollback.add_argument("snapshot_id")
    rollback.add_argument("--root", default=DEFAULT_ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manager = KnowledgeBaseManager(args.root)
    if args.command == "check":
        _print_snapshot(manager.load_active())
        return 0
    if args.command == "rollback":
        _print_snapshot(manager.rollback(args.snapshot_id))
        return 0

    catalog_path = Path(args.catalog).resolve()
    repository_root = catalog_path.parent.parent
    catalog = SpecCatalog.load(catalog_path, repository_root=repository_root)
    embedder = Embedder(args.embedding_model, args.embedding_revision)
    indexer = KnowledgeDocumentIndexer(Path(args.root) / "document_indexes")
    built = []
    for spec in catalog.documents:
        pdf_path = spec.verify_local_pdf()
        if spec.ingestion_readiness == "ready":
            document, pages = load_pdf_pages(
                str(pdf_path), spec_id=spec.spec_id, edition_id=spec.edition_id
            )
            ingestion_hash = spec.pdf_sha256
            parser_version = PARSER_VERSION
        elif spec.ingestion_readiness == "ocr_verified":
            artifact = spec.resolved_ocr_artifact_path
            if artifact is None or spec.ocr_manifest_sha256 is None:
                raise SpecCatalogError(f"{spec.business_id} OCR artifact is incomplete")
            manifest_path = artifact / "manifest.json"
            validation_path = artifact / "validation.json"
            if calculate_file_checksum(manifest_path) != spec.ocr_manifest_sha256:
                raise SpecCatalogError(f"{spec.business_id} OCR manifest SHA-256 mismatch")
            if (
                spec.ocr_validation_sha256 is None
                or calculate_file_checksum(validation_path) != spec.ocr_validation_sha256
            ):
                raise SpecCatalogError(f"{spec.business_id} OCR validation SHA-256 mismatch")
            document, pages = load_verified_ocr_pages(artifact, source_pdf=pdf_path)
            ingestion_hash = spec.ocr_manifest_sha256
            parser_version = (
                OCR_TABLE_PARSER_VERSION
                if any(page.tables for page in pages)
                else OCR_PARSER_VERSION
            )
        else:
            raise SpecCatalogError(f"{spec.business_id} is not ready for ingestion")
        built.append(
            indexer.build(
                document,
                pages,
                source_pdf_sha256=spec.pdf_sha256,
                ingestion_artifact_sha256=ingestion_hash,
                parser_version=parser_version,
                embedder=embedder,
                chunk_size=args.chunk_size,
                overlap=args.overlap,
            )
        )
    _print_snapshot(manager.publish(item.path for item in built))
    return 0


def _print_snapshot(snapshot) -> None:
    print(f"snapshot_id: {snapshot.snapshot_id}")
    for document in snapshot.documents:
        manifest = document.manifest
        print(
            f"{manifest.business_id}: {manifest.version_id} "
            f"({manifest.chunk_count} chunks)"
        )


if __name__ == "__main__":
    raise SystemExit(main())
