from dataclasses import asdict, dataclass, field
from typing import Any


def _validate_spec_identity(spec_id: str | None, edition_id: str | None) -> None:
    if (spec_id is None) != (edition_id is None):
        raise ValueError("spec_id and edition_id must be provided together")
    for field_name, value in (("spec_id", spec_id), ("edition_id", edition_id)):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True)
class DocumentMetadata:
    document_id: str
    source: str
    page_count: int
    spec_id: str | None = None
    edition_id: str | None = None

    def __post_init__(self) -> None:
        _validate_spec_identity(self.spec_id, self.edition_id)


@dataclass(frozen=True)
class PageMetadata:
    document_id: str
    source: str
    page_number: int
    char_count_raw: int
    char_count_cleaned: int
    spec_id: str | None = None
    edition_id: str | None = None

    def __post_init__(self) -> None:
        _validate_spec_identity(self.spec_id, self.edition_id)


@dataclass(frozen=True)
class TableMetadata:
    document_id: str
    source: str
    page_number: int
    table_id: str | None
    title: str | None
    bbox: tuple[float, float, float, float] | None = None
    spec_id: str | None = None
    edition_id: str | None = None

    def __post_init__(self) -> None:
        _validate_spec_identity(self.spec_id, self.edition_id)


@dataclass(frozen=True)
class Table:
    metadata: TableMetadata
    headers: list[list[str]]
    rows: list[list[str]]
    cells: list[list[str]]
    retrieval_text: str


@dataclass(frozen=True)
class Page:
    text: str
    raw_text: str
    metadata: PageMetadata
    tables: list[Table] = field(default_factory=list)


@dataclass(frozen=True)
class ChunkMetadata:
    document_id: str
    source: str
    chunk_id: int
    page_start: int
    page_end: int
    char_start: int
    char_end: int
    chapter_id: str | None = None
    chapter_title: str | None = None
    article_id: str | None = None
    display_ref: str | None = None
    content_type: str = "text"
    table_id: str | None = None
    table_title: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    spec_id: str | None = None
    edition_id: str | None = None

    def __post_init__(self) -> None:
        _validate_spec_identity(self.spec_id, self.edition_id)

    @property
    def evidence_identity(self) -> tuple[str, str, str] | None:
        if self.spec_id is None or self.edition_id is None:
            return None
        return self.spec_id, self.edition_id, str(self.chunk_id)


@dataclass(frozen=True)
class Chunk:
    text: str
    metadata: ChunkMetadata

    def to_record(self) -> dict[str, Any]:
        record = asdict(self.metadata)
        record["text"] = self.text
        if record["display_ref"] is None:
            record["display_ref"] = f"chunk_{self.metadata.chunk_id}"
        return record
