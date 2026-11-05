import hashlib
import json
from pathlib import Path

import pytest

from src.spec_catalog import EvidenceIdentity, SpecCatalog, SpecCatalogError


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _document(
    *,
    spec_id: str = "cn.example.spec",
    edition_id: str = "2025",
    local_pdf_path: str | None = None,
    pdf_sha256: str | None = None,
    verification_status: str = "official_source_and_local_pdf_verified",
) -> dict:
    return {
        "spec_id": spec_id,
        "edition_id": edition_id,
        "standard_code": "EX 1-2025",
        "title": "示例规范",
        "authority": "示例机构",
        "jurisdiction": "示例地区",
        "source_page_url": "https://example.com/spec",
        "source_pdf_url": "https://example.com/spec.pdf",
        "release_date": "2025-01-01",
        "effective_from": "2025-02-01",
        "effective_to": None,
        "effective_status": "effective",
        "supersedes": [],
        "applicability_note": "仅用于测试。",
        "local_pdf_path": local_pdf_path,
        "pdf_sha256": pdf_sha256,
        "verification_status": verification_status,
        "verified_at": "2026-11-05",
        "verification_notes": "测试记录。",
    }


def _write_catalog(path: Path, documents: list[dict]) -> Path:
    payload = {
        "schema_version": 1,
        "catalog_id": "test-catalog",
        "catalog_version": "1",
        "scope": {"domain": "测试", "jurisdiction_note": "测试", "document_count": len(documents)},
        "documents": documents,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_business_identity_does_not_depend_on_pdf_location(tmp_path):
    first = tmp_path / "one" / "spec.pdf"
    second = tmp_path / "two" / "renamed.pdf"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"same pdf bytes")
    second.write_bytes(first.read_bytes())
    digest = _sha256(first)

    first_catalog = SpecCatalog.load(
        _write_catalog(
            tmp_path / "first.json",
            [_document(local_pdf_path=str(first), pdf_sha256=digest)],
        )
    )
    second_catalog = SpecCatalog.load(
        _write_catalog(
            tmp_path / "second.json",
            [_document(local_pdf_path=str(second), pdf_sha256=digest)],
        )
    )

    assert first_catalog.documents[0].business_id == "cn.example.spec@2025"
    assert first_catalog.documents[0].business_id == second_catalog.documents[0].business_id
    assert first_catalog.available_documents()[0].resolved_pdf_path == first.resolve()
    assert second_catalog.available_documents()[0].resolved_pdf_path == second.resolve()


def test_same_chunk_number_is_isolated_by_spec_and_edition():
    first = EvidenceIdentity("cn.example.alpha", "2025", "42")
    second = EvidenceIdentity("cn.example.beta", "2025", "42")
    old_edition = EvidenceIdentity("cn.example.alpha", "2013", "42")

    assert len({first, second, old_edition}) == 3
    assert first.key != second.key
    assert first.key != old_edition.key


def test_pending_pdf_is_kept_in_catalog_but_not_available(tmp_path):
    catalog = SpecCatalog.load(
        _write_catalog(
            tmp_path / "catalog.json",
            [
                _document(
                    local_pdf_path=None,
                    pdf_sha256=None,
                    verification_status="official_announcement_verified_pdf_pending",
                )
            ],
        )
    )

    assert len(catalog.documents) == 1
    assert catalog.available_documents() == ()


def test_verified_document_requires_matching_pdf_hash(tmp_path):
    pdf = tmp_path / "spec.pdf"
    pdf.write_bytes(b"actual bytes")
    catalog = SpecCatalog.load(
        _write_catalog(
            tmp_path / "catalog.json",
            [_document(local_pdf_path=str(pdf), pdf_sha256="0" * 64)],
        )
    )

    with pytest.raises(SpecCatalogError, match="SHA-256 mismatch"):
        catalog.available_documents()


def test_duplicate_spec_edition_is_rejected(tmp_path):
    document = _document(
        local_pdf_path="missing.pdf",
        pdf_sha256="0" * 64,
        verification_status="official_announcement_verified_pdf_pending",
    )

    with pytest.raises(SpecCatalogError, match="duplicate spec edition"):
        SpecCatalog.load(_write_catalog(tmp_path / "catalog.json", [document, document]))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("release_date", "2025/01/01"),
        ("pdf_sha256", "not-a-hash"),
        ("source_page_url", "file:///tmp/spec"),
    ],
)
def test_catalog_rejects_invalid_review_fields(tmp_path, field, value):
    document = _document(
        local_pdf_path=None,
        pdf_sha256=None,
        verification_status="official_announcement_verified_pdf_pending",
    )
    document[field] = value

    with pytest.raises(SpecCatalogError):
        SpecCatalog.load(_write_catalog(tmp_path / "catalog.json", [document]))
