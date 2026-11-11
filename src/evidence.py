import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    text: str
    source: str
    page_start: int | None
    page_end: int | None
    chunk_id: int
    content_type: str = "text"
    chapter_id: str | None = None
    chapter_title: str | None = None
    article_id: str | None = None
    table_id: str | None = None
    table_title: str | None = None
    display_ref: str | None = None
    score: float | None = None
    rerank_score: float | None = None
    metadata: dict[str, Any] | None = None
    spec_id: str | None = None
    edition_id: str | None = None
    standard_code: str | None = None
    spec_title: str | None = None
    pdf_page_start: int | None = None
    pdf_page_end: int | None = None
    printed_page_start: str | None = None
    printed_page_end: str | None = None

    @property
    def stable_identity(self) -> tuple[object, ...]:
        if self.spec_id is not None and self.edition_id is not None:
            return self.spec_id, self.edition_id, self.chunk_id
        return self.source, self.chunk_id

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def citation_label(self) -> str:
        if self.standard_code and self.spec_title:
            parts = [f"{self.standard_code}《{self.spec_title}》", f"版本 {self.edition_id}"]
        else:
            parts = [self.source]
        if self.standard_code and self.pdf_page_start is not None:
            page = f"PDF 第 {self.pdf_page_start} 页"
            if self.pdf_page_end and self.pdf_page_end != self.pdf_page_start:
                page = f"PDF 第 {self.pdf_page_start}-{self.pdf_page_end} 页"
            parts.append(page)
        elif self.page_start is not None:
            page = f"p.{self.page_start}"
            if self.page_end and self.page_end != self.page_start:
                page = f"p.{self.page_start}-{self.page_end}"
            parts.append(page)
        if self.article_id:
            parts.append(f"第{self.article_id}条")
        if self.table_id:
            table = self.table_id
            if self.table_title:
                table = f"{table} {self.table_title}"
            parts.append(table)
        if not (self.article_id or self.table_id or self.table_title) and self.display_ref:
            parts.append(self.display_ref)
        if self.printed_page_start is not None:
            printed = f"印刷页 {self.printed_page_start}"
            if self.printed_page_end and self.printed_page_end != self.printed_page_start:
                printed = f"印刷页 {self.printed_page_start}-{self.printed_page_end}"
            parts.append(printed)
        return " - ".join(parts)

    def to_context_block(self) -> str:
        meta = [
            f"来源: {self.source}",
            f"规范: {self.standard_code or self.spec_id or 'UNKNOWN'}",
            f"版本: {self.edition_id or 'UNKNOWN'}",
            f"PDF页码: {self.pdf_page_start}"
            if self.pdf_page_start is not None
            else "PDF页码: UNKNOWN",
            f"类型: {self.content_type}",
        ]
        if self.chapter_id or self.chapter_title:
            meta.append(f"章节: {self.chapter_id or ''} {self.chapter_title or ''}".strip())
        if self.article_id:
            meta.append(f"条文: {self.article_id}")
        if self.table_id or self.table_title:
            meta.append(f"表格: {self.table_id or ''} {self.table_title or ''}".strip())
        return f"[{self.evidence_id}]\n" + "\n".join(meta) + f"\n内容:\n{self.text}"


@dataclass(frozen=True)
class CitationValidation:
    valid: bool
    cited_ids: list[str]
    available_ids: list[str]
    errors: list[str]


def build_evidence_list(results: list[dict[str, Any]]) -> list[Evidence]:
    evidences = []
    for index, result in enumerate(results, start=1):
        evidences.append(
            Evidence(
                evidence_id=f"E{index}",
                text=result["text"],
                source=result["source"],
                page_start=result.get("page_start"),
                page_end=result.get("page_end"),
                chunk_id=result["chunk_id"],
                content_type=result.get("content_type", "text"),
                chapter_id=result.get("chapter_id"),
                chapter_title=result.get("chapter_title"),
                article_id=result.get("article_id"),
                table_id=result.get("table_id"),
                table_title=result.get("table_title"),
                display_ref=result.get("display_ref"),
                score=result.get("score"),
                rerank_score=result.get("rerank_score"),
                metadata=result.get("extra", {}),
                spec_id=result.get("spec_id"),
                edition_id=result.get("edition_id"),
                standard_code=result.get("standard_code"),
                spec_title=result.get("spec_title"),
                pdf_page_start=result.get("pdf_page_start", result.get("page_start")),
                pdf_page_end=result.get("pdf_page_end", result.get("page_end")),
                printed_page_start=result.get("printed_page_start"),
                printed_page_end=result.get("printed_page_end"),
            )
        )
    return evidences


def build_evidence_context(evidences: list[Evidence]) -> str:
    return "\n\n".join(evidence.to_context_block() for evidence in evidences)


def validate_citations(answer: str, evidences: list[Evidence]) -> CitationValidation:
    available = {evidence.evidence_id: evidence for evidence in evidences}
    cited_ids = sorted(set(re.findall(r"\[(E\d+)\]", answer)), key=_evidence_sort_key)
    errors = []

    if not cited_ids:
        errors.append("MISSING_CITATION")

    for cited_id in cited_ids:
        if cited_id not in available:
            errors.append(f"UNKNOWN_EVIDENCE_ID:{cited_id}")

    for cited_id in cited_ids:
        evidence = available.get(cited_id)
        if evidence is None:
            continue
        if not evidence.source:
            errors.append(f"UNRESOLVED_SOURCE:{evidence.evidence_id}")
        if evidence.page_start is None:
            errors.append(f"UNRESOLVED_PAGE:{evidence.evidence_id}")
        if evidence.content_type == "table" and not (evidence.table_id or evidence.table_title):
            errors.append(f"UNRESOLVED_TABLE:{evidence.evidence_id}")

    return CitationValidation(
        valid=not errors,
        cited_ids=cited_ids,
        available_ids=list(available.keys()),
        errors=errors,
    )


def format_evidence_citation(evidence: Evidence) -> str:
    return f"[{evidence.evidence_id}] {evidence.citation_label()}"


def _evidence_sort_key(evidence_id: str) -> int:
    return int(evidence_id[1:])
