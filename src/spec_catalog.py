from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


VERIFIED_PDF_STATUS = "official_source_and_local_pdf_verified"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class SpecCatalogError(ValueError):
    """Raised when a specification catalog cannot be trusted."""


@dataclass(frozen=True)
class EvidenceIdentity:
    spec_id: str
    edition_id: str
    chunk_id: str

    def __post_init__(self) -> None:
        for field_name in ("spec_id", "edition_id", "chunk_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise SpecCatalogError(f"{field_name} must be a non-empty string")

    @property
    def key(self) -> str:
        return json.dumps(
            [self.spec_id, self.edition_id, self.chunk_id],
            ensure_ascii=False,
            separators=(",", ":"),
        )


@dataclass(frozen=True)
class SpecDocument:
    spec_id: str
    edition_id: str
    standard_code: str
    title: str
    authority: str
    jurisdiction: str
    source_page_url: str
    source_pdf_url: str | None
    release_date: str | None
    effective_from: str | None
    effective_to: str | None
    effective_status: str
    supersedes: tuple[str, ...]
    applicability_note: str
    local_pdf_path: str | None
    pdf_sha256: str | None
    verification_status: str
    verified_at: str | None
    verification_notes: str
    catalog_root: Path

    @property
    def business_id(self) -> str:
        return f"{self.spec_id}@{self.edition_id}"

    @property
    def is_pdf_verified(self) -> bool:
        return self.verification_status == VERIFIED_PDF_STATUS

    @property
    def resolved_pdf_path(self) -> Path | None:
        if self.local_pdf_path is None:
            return None
        path = Path(self.local_pdf_path)
        if not path.is_absolute():
            path = self.catalog_root / path
        return path.resolve()

    def evidence_identity(self, chunk_id: str | int) -> EvidenceIdentity:
        return EvidenceIdentity(self.spec_id, self.edition_id, str(chunk_id))

    def verify_local_pdf(self) -> Path:
        if not self.is_pdf_verified:
            raise SpecCatalogError(f"{self.business_id} PDF is not verified")
        path = self.resolved_pdf_path
        if path is None or self.pdf_sha256 is None:
            raise SpecCatalogError(
                f"{self.business_id} verified document requires local_pdf_path and pdf_sha256"
            )
        if not path.is_file():
            raise SpecCatalogError(f"{self.business_id} PDF does not exist: {path}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != self.pdf_sha256:
            raise SpecCatalogError(
                f"{self.business_id} PDF SHA-256 mismatch: expected "
                f"{self.pdf_sha256}, got {actual}"
            )
        return path


@dataclass(frozen=True)
class SpecCatalog:
    schema_version: int
    catalog_id: str
    catalog_version: str
    scope: dict[str, Any]
    documents: tuple[SpecDocument, ...]
    source_path: Path

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        repository_root: str | Path | None = None,
    ) -> SpecCatalog:
        source_path = Path(path).resolve()
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SpecCatalogError(f"cannot read catalog {source_path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise SpecCatalogError("catalog root must be an object")
        if payload.get("schema_version") != 1:
            raise SpecCatalogError("unsupported catalog schema_version")
        catalog_id = _required_text(payload, "catalog_id")
        catalog_version = _required_text(payload, "catalog_version")
        scope = payload.get("scope")
        if not isinstance(scope, dict):
            raise SpecCatalogError("scope must be an object")
        raw_documents = payload.get("documents")
        if not isinstance(raw_documents, list) or not raw_documents:
            raise SpecCatalogError("documents must be a non-empty list")
        if scope.get("document_count") != len(raw_documents):
            raise SpecCatalogError("scope.document_count does not match documents")

        root = Path(repository_root).resolve() if repository_root else Path.cwd().resolve()
        documents = tuple(_parse_document(item, root) for item in raw_documents)
        identities: set[tuple[str, str]] = set()
        for document in documents:
            identity = (document.spec_id, document.edition_id)
            if identity in identities:
                raise SpecCatalogError(f"duplicate spec edition: {document.business_id}")
            identities.add(identity)
        return cls(
            schema_version=1,
            catalog_id=catalog_id,
            catalog_version=catalog_version,
            scope=dict(scope),
            documents=documents,
            source_path=source_path,
        )

    def available_documents(self) -> tuple[SpecDocument, ...]:
        available = tuple(document for document in self.documents if document.is_pdf_verified)
        for document in available:
            document.verify_local_pdf()
        return available

    def get(self, spec_id: str, edition_id: str) -> SpecDocument:
        for document in self.documents:
            if document.spec_id == spec_id and document.edition_id == edition_id:
                return document
        raise SpecCatalogError(f"unknown spec edition: {spec_id}@{edition_id}")


def _parse_document(payload: Any, catalog_root: Path) -> SpecDocument:
    if not isinstance(payload, dict):
        raise SpecCatalogError("each document must be an object")
    spec_id = _required_text(payload, "spec_id")
    edition_id = _required_text(payload, "edition_id")
    if not _IDENTIFIER_PATTERN.fullmatch(spec_id):
        raise SpecCatalogError(f"invalid spec_id: {spec_id}")
    if not _IDENTIFIER_PATTERN.fullmatch(edition_id.lower()):
        raise SpecCatalogError(f"invalid edition_id: {edition_id}")

    source_page_url = _required_https_url(payload, "source_page_url")
    source_pdf_url = _optional_https_url(payload, "source_pdf_url")
    release_date = _optional_date(payload, "release_date")
    effective_from = _optional_date(payload, "effective_from")
    effective_to = _optional_date(payload, "effective_to")
    if effective_from and effective_to and effective_to < effective_from:
        raise SpecCatalogError("effective_to cannot be earlier than effective_from")
    verified_at = _optional_date(payload, "verified_at")

    pdf_sha256 = payload.get("pdf_sha256")
    if pdf_sha256 is not None:
        if not isinstance(pdf_sha256, str) or not _SHA256_PATTERN.fullmatch(pdf_sha256):
            raise SpecCatalogError("pdf_sha256 must be 64 lowercase hexadecimal characters")
    local_pdf_path = payload.get("local_pdf_path")
    if local_pdf_path is not None and (
        not isinstance(local_pdf_path, str) or not local_pdf_path.strip()
    ):
        raise SpecCatalogError("local_pdf_path must be null or a non-empty string")
    verification_status = _required_text(payload, "verification_status")
    if verification_status == VERIFIED_PDF_STATUS and (
        local_pdf_path is None or pdf_sha256 is None
    ):
        raise SpecCatalogError(
            "verified document requires local_pdf_path and pdf_sha256"
        )
    supersedes = payload.get("supersedes")
    if not isinstance(supersedes, list) or not all(
        isinstance(item, str) and item.strip() for item in supersedes
    ):
        raise SpecCatalogError("supersedes must be a list of non-empty strings")

    return SpecDocument(
        spec_id=spec_id,
        edition_id=edition_id,
        standard_code=_required_text(payload, "standard_code"),
        title=_required_text(payload, "title"),
        authority=_required_text(payload, "authority"),
        jurisdiction=_required_text(payload, "jurisdiction"),
        source_page_url=source_page_url,
        source_pdf_url=source_pdf_url,
        release_date=release_date,
        effective_from=effective_from,
        effective_to=effective_to,
        effective_status=_required_text(payload, "effective_status"),
        supersedes=tuple(supersedes),
        applicability_note=_required_text(payload, "applicability_note"),
        local_pdf_path=local_pdf_path,
        pdf_sha256=pdf_sha256,
        verification_status=verification_status,
        verified_at=verified_at,
        verification_notes=_required_text(payload, "verification_notes"),
        catalog_root=catalog_root,
    )


def _required_text(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise SpecCatalogError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_date(payload: dict[str, Any], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise SpecCatalogError(f"{field_name} must be an ISO date or null")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise SpecCatalogError(f"{field_name} must be an ISO date") from exc
    return value


def _required_https_url(payload: dict[str, Any], field_name: str) -> str:
    value = _required_text(payload, field_name)
    if urlparse(value).scheme != "https":
        raise SpecCatalogError(f"{field_name} must use https")
    return value


def _optional_https_url(payload: dict[str, Any], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or urlparse(value).scheme != "https":
        raise SpecCatalogError(f"{field_name} must use https or be null")
    return value
