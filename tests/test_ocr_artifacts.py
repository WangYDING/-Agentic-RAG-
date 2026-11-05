import hashlib
import json
from pathlib import Path

import fitz
import pytest

from src.ocr_artifacts import OcrArtifactError, canonical_json_bytes, validate_ocr_artifact


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fixture(tmp_path: Path, *, text_by_page: list[str]) -> tuple[Path, Path]:
    pdf_path = tmp_path / "source.pdf"
    document = fitz.open()
    for text in text_by_page:
        page = document.new_page()
        page.insert_text((72, 72), text)
    document.save(pdf_path)
    document.close()

    artifact = tmp_path / "artifact"
    pages_dir = artifact / "pages"
    pages_dir.mkdir(parents=True)
    entries = []
    source_hash = _sha256(pdf_path)
    for number, text in enumerate(text_by_page, start=1):
        payload = {
            "schema_version": 1,
            "spec_id": "cn.example",
            "edition_id": "2025",
            "source_pdf_sha256": source_hash,
            "page_number": number,
            "render_dpi": 200,
            "text": text,
            "lines": [],
        }
        page_path = pages_dir / f"{number:04d}.json"
        page_path.write_bytes(canonical_json_bytes(payload))
        entries.append(
            {
                "page_number": number,
                "path": f"pages/{number:04d}.json",
                "sha256": _sha256(page_path),
                "character_count": len(text),
                "line_count": 0,
                "render_dpi": 200,
            }
        )
    manifest = {
        "schema_version": 1,
        "artifact_type": "page_ocr_text",
        "spec_id": "cn.example",
        "edition_id": "2025",
        "business_id": "cn.example@2025",
        "source_pdf": {
            "path": pdf_path.as_posix(),
            "sha256": source_hash,
            "page_count": len(text_by_page),
        },
        "ocr_tool": {"name": "fixture"},
        "pages": entries,
    }
    (artifact / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    return pdf_path, artifact


def test_validation_binds_each_page_to_source_pdf(tmp_path):
    pdf, artifact = _write_fixture(tmp_path, text_by_page=["1.0.1 范围", "10⁸ Ω"])

    result = validate_ocr_artifact(artifact, source_pdf=pdf)

    assert result["page_count"] == 2
    assert result["page_sequence_valid"] is True
    assert result["page_hashes_valid"] is True
    assert result["detected_clauses"] == {"1.0.1": [1]}
    assert result["clause_sequence_gaps"] == []
    assert result["superscript_pages"] == [2]
    assert result["manual_review_status"] == "pending"


def test_validation_rejects_changed_page_artifact(tmp_path):
    pdf, artifact = _write_fixture(tmp_path, text_by_page=["1.0.1 范围"])
    page = artifact / "pages" / "0001.json"
    payload = json.loads(page.read_text(encoding="utf-8"))
    payload["text"] = "tampered"
    page.write_bytes(canonical_json_bytes(payload))

    with pytest.raises(OcrArtifactError, match="page artifact mismatch"):
        validate_ocr_artifact(artifact, source_pdf=pdf)


def test_validation_rejects_different_source_pdf(tmp_path):
    pdf, artifact = _write_fixture(tmp_path, text_by_page=["1.0.1 范围"])
    other = tmp_path / "other.pdf"
    other.write_bytes(pdf.read_bytes() + b"changed")

    with pytest.raises(OcrArtifactError, match="source PDF SHA-256 mismatch"):
        validate_ocr_artifact(artifact, source_pdf=other)


def test_validation_reports_blank_and_replacement_character_pages(tmp_path):
    pdf, artifact = _write_fixture(tmp_path, text_by_page=["", "�"])

    result = validate_ocr_artifact(artifact, source_pdf=pdf)

    assert result["blank_pages"] == [1]
    assert result["replacement_character_count"] == 1
    assert result["automatic_checks_passed"] is False


def test_validation_reports_missing_clause_number(tmp_path):
    pdf, artifact = _write_fixture(
        tmp_path, text_by_page=["2.1.1 第一条\n2.1.3 第三条"]
    )

    result = validate_ocr_artifact(artifact, source_pdf=pdf)

    assert result["clause_sequence_gaps"] == ["2.1.2"]
    assert result["automatic_checks_passed"] is False
