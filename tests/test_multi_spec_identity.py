import hashlib
import json
from pathlib import Path

import pytest

from src.document_schema import (
    DocumentMetadata,
    Page,
    PageMetadata,
    Table,
    TableMetadata,
)
from src.bm25_retriever import BM25Retriever
from src.loader import load_verified_ocr_pages
from src.ocr_artifacts import OcrArtifactError, canonical_json_bytes
from src.retrieval_fusion import chunk_identity, reciprocal_rank_fusion
from src.splitter import split_pages_with_ref
from src.vector_store import VectorStore


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ocr_fixture(tmp_path: Path) -> Path:
    artifact = tmp_path / "ocr"
    pages = artifact / "pages"
    pages.mkdir(parents=True)
    record = {
        "schema_version": 1,
        "spec_id": "cn.example",
        "edition_id": "2025",
        "source_pdf_sha256": "a" * 64,
        "page_number": 1,
        "render_dpi": 300,
        "text": "1.0.1 示例条文。",
        "lines": [],
    }
    page = pages / "0001.json"
    page.write_bytes(canonical_json_bytes(record))
    manifest = {
        "schema_version": 1,
        "artifact_type": "page_ocr_text",
        "spec_id": "cn.example",
        "edition_id": "2025",
        "business_id": "cn.example@2025",
        "source_pdf": {
            "file_name": "example.pdf",
            "sha256": "a" * 64,
            "page_count": 1,
        },
        "ocr_tool": {"name": "fixture"},
        "pages": [
            {
                "page_number": 1,
                "path": "pages/0001.json",
                "sha256": _sha256(page),
                "character_count": len(record["text"]),
                "line_count": 0,
                "render_dpi": 300,
            }
        ],
    }
    (artifact / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    return artifact


def test_spec_identity_must_be_complete_pair():
    with pytest.raises(ValueError, match="provided together"):
        DocumentMetadata("doc", "doc.pdf", 1, spec_id="cn.example")


def test_verified_ocr_identity_propagates_to_pages_and_chunks(tmp_path):
    document, pages = load_verified_ocr_pages(_ocr_fixture(tmp_path))
    chunks = split_pages_with_ref(document, pages)

    assert document.document_id == "cn.example@2025"
    assert (pages[0].metadata.spec_id, pages[0].metadata.edition_id) == (
        "cn.example",
        "2025",
    )
    assert (chunks[0]["spec_id"], chunks[0]["edition_id"]) == (
        "cn.example",
        "2025",
    )
    assert chunk_identity(chunks[0]) == ("cn.example", "2025", 0)


def test_verified_ocr_table_preserves_row_column_value_mapping(tmp_path):
    artifact = _ocr_fixture(tmp_path)
    page_path = artifact / "pages" / "0001.json"
    record = json.loads(page_path.read_text(encoding="utf-8"))
    cells = [
        ["车辆类型", "100km/h及以下", "120km/h", "140km/h", "160km/h"],
        ["密闭性车体", "—", "—", "<0.35", "<0.29"],
        ["非密闭性车体", "≤0.5", "≤0.4", "≤0.27", "—"],
    ]
    record["tables"] = [
        {
            "table_id": "表3.0.4",
            "title": "车辆断面与隧道净断面面积之比",
            "bbox": [0, 0, 100, 100],
            "headers": cells[:1],
            "rows": cells[1:],
            "cells": cells,
        }
    ]
    page_path.write_bytes(canonical_json_bytes(record))
    manifest_path = artifact / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["pages"][0]["sha256"] = _sha256(page_path)
    manifest_path.write_bytes(canonical_json_bytes(manifest))

    document, pages = load_verified_ocr_pages(artifact)
    chunks = split_pages_with_ref(document, pages)
    table = next(chunk for chunk in chunks if chunk["content_type"] == "table")

    assert "表头: 车辆类型 | 100km/h及以下 | 120km/h | 140km/h | 160km/h" in table["text"]
    assert "第1行: 密闭性车体 | — | — | <0.35 | <0.29" in table["text"]
    assert table["extra"]["table"]["rows"][0][3:] == ["<0.35", "<0.29"]


def test_verified_ocr_table_rejects_shifted_or_non_rectangular_cells(tmp_path):
    artifact = _ocr_fixture(tmp_path)
    page_path = artifact / "pages" / "0001.json"
    record = json.loads(page_path.read_text(encoding="utf-8"))
    record["tables"] = [
        {
            "table_id": "表3.0.4",
            "title": "车辆断面与隧道净断面面积之比",
            "headers": [["车辆类型", "140km/h", "160km/h"]],
            "rows": [["密闭性车体", "<0.35"]],
            "cells": [
                ["车辆类型", "140km/h", "160km/h"],
                ["密闭性车体", "<0.35"],
            ],
        }
    ]
    page_path.write_bytes(canonical_json_bytes(record))
    manifest_path = artifact / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["pages"][0]["sha256"] = _sha256(page_path)
    manifest_path.write_bytes(canonical_json_bytes(manifest))

    with pytest.raises(OcrArtifactError, match="rectangular strings"):
        load_verified_ocr_pages(artifact)


def test_table_chunk_keeps_spec_identity():
    document = DocumentMetadata("doc", "doc.pdf", 1, "cn.example", "2025")
    table_metadata = TableMetadata(
        "doc", "doc.pdf", 1, "表1", "示例", spec_id="cn.example", edition_id="2025"
    )
    page = Page(
        text="",
        raw_text="",
        metadata=PageMetadata("doc", "doc.pdf", 1, 0, 0, "cn.example", "2025"),
        tables=[Table(table_metadata, [["项目"]], [["值"]], [["项目"], ["值"]], "表格")],
    )

    chunk = split_pages_with_ref(document, [page])[0]

    assert chunk["content_type"] == "table"
    assert (chunk["spec_id"], chunk["edition_id"]) == ("cn.example", "2025")


def test_same_source_and_chunk_id_do_not_collide_across_spec_versions():
    first = {
        "source": "standard.pdf",
        "spec_id": "cn.example",
        "edition_id": "2020",
        "chunk_id": 0,
        "text": "old",
    }
    second = {**first, "edition_id": "2025", "text": "new"}

    fused = reciprocal_rank_fusion([first], [second])

    assert len(fused) == 2
    assert {item["edition_id"] for item in fused} == {"2020", "2025"}


def test_old_single_pdf_identity_remains_supported():
    record = {"source": "legacy.pdf", "chunk_id": 7, "text": "legacy"}
    assert chunk_identity(record) == ("legacy.pdf", 7)


def test_dense_and_bm25_results_keep_spec_identity():
    record = {
        "source": "standard.pdf",
        "spec_id": "cn.example",
        "edition_id": "2025",
        "chunk_id": 0,
        "text": "城市轨道交通",
    }
    bm25_result = BM25Retriever([record]).retrieve("轨道交通", top_k=1)[0]
    store = VectorStore(dim=2)
    store.add([[1.0, 0.0]], [record])
    dense_result = store.search([1.0, 0.0], top_k=1)[0]

    assert chunk_identity(bm25_result) == ("cn.example", "2025", 0)
    assert chunk_identity(dense_result) == ("cn.example", "2025", 0)


def test_ocr_loader_rejects_changed_page(tmp_path):
    artifact = _ocr_fixture(tmp_path)
    page = artifact / "pages" / "0001.json"
    payload = json.loads(page.read_text(encoding="utf-8"))
    payload["text"] = "tampered"
    page.write_bytes(canonical_json_bytes(payload))

    with pytest.raises(OcrArtifactError, match="page artifact mismatch"):
        load_verified_ocr_pages(artifact)
