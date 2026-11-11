from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class QueryScopeKind(str, Enum):
    UNSPECIFIED = "unspecified"
    ALL = "all"
    SPECIFICATIONS = "specifications"
    VERSIONS = "versions"


class QueryScopeError(ValueError):
    """Raised when a requested scope cannot be served by the bound snapshot."""


class QueryScopeClarificationRequired(QueryScopeError):
    """Raised when the user has not selected enough scope to start retrieval."""


@dataclass(frozen=True, order=True)
class SpecEdition:
    spec_id: str
    edition_id: str

    def __post_init__(self) -> None:
        if not self.spec_id.strip() or not self.edition_id.strip():
            raise QueryScopeError("spec_id and edition_id must be non-empty")

    @property
    def business_id(self) -> str:
        return f"{self.spec_id}@{self.edition_id}"


@dataclass(frozen=True)
class QueryScope:
    kind: QueryScopeKind
    spec_ids: tuple[str, ...] = ()
    versions: tuple[SpecEdition, ...] = ()

    @classmethod
    def unspecified(cls) -> QueryScope:
        return cls(QueryScopeKind.UNSPECIFIED)

    @classmethod
    def all_documents(cls) -> QueryScope:
        return cls(QueryScopeKind.ALL)

    @classmethod
    def specifications(cls, spec_ids: Iterable[str]) -> QueryScope:
        normalized = _unique_nonempty(spec_ids, "spec_id")
        return cls(QueryScopeKind.SPECIFICATIONS, spec_ids=normalized)

    @classmethod
    def exact_versions(cls, versions: Iterable[SpecEdition]) -> QueryScope:
        unique = tuple(sorted(set(versions)))
        if not unique:
            raise QueryScopeError("at least one specification version is required")
        return cls(QueryScopeKind.VERSIONS, versions=unique)

    @classmethod
    def from_request_payload(cls, payload: Mapping[str, object]) -> QueryScope:
        raw_specs = payload.get("spec_ids", [])
        raw_editions = payload.get("edition_ids", [])
        if not isinstance(raw_specs, list) or not all(isinstance(x, str) for x in raw_specs):
            raise QueryScopeError("spec_ids must be a list of strings")
        if not isinstance(raw_editions, list) or not all(
            isinstance(x, str) for x in raw_editions
        ):
            raise QueryScopeError("edition_ids must be a list of strings")
        if not raw_specs and not raw_editions:
            return cls.unspecified()
        if raw_specs and not raw_editions:
            return cls.specifications(raw_specs)
        if len(raw_specs) != len(raw_editions):
            raise QueryScopeError("spec_ids and edition_ids must have matching lengths")
        return cls.exact_versions(
            SpecEdition(spec_id, edition_id)
            for spec_id, edition_id in zip(raw_specs, raw_editions, strict=True)
        )


@dataclass(frozen=True)
class ResolvedQueryScope:
    requested: QueryScope
    snapshot_id: str
    versions: tuple[SpecEdition, ...]

    @property
    def business_ids(self) -> tuple[str, ...]:
        return tuple(item.business_id for item in self.versions)

    def allows(self, spec_id: str | None, edition_id: str | None) -> bool:
        if spec_id is None or edition_id is None:
            return False
        return SpecEdition(spec_id, edition_id) in self.versions


def resolve_query_scope(
    scope: QueryScope,
    *,
    snapshot_id: str,
    snapshot_versions: Iterable[SpecEdition],
    catalog_versions: Iterable[SpecEdition],
) -> ResolvedQueryScope:
    available = set(snapshot_versions)
    catalog = set(catalog_versions)
    if scope.kind is QueryScopeKind.UNSPECIFIED:
        raise QueryScopeClarificationRequired(
            "请先选择查询范围：全部三份规范，或指定规范及版本。"
        )
    if scope.kind is QueryScopeKind.ALL:
        selected = available
    elif scope.kind is QueryScopeKind.SPECIFICATIONS:
        selected = {item for item in available if item.spec_id in scope.spec_ids}
        missing_specs = sorted(set(scope.spec_ids) - {item.spec_id for item in available})
        if missing_specs:
            raise QueryScopeError(
                "所选规范不在当前知识库快照中：" + ", ".join(missing_specs)
            )
        ambiguous = sorted(
            spec_id
            for spec_id in scope.spec_ids
            if len([item for item in catalog if item.spec_id == spec_id]) >= 1
        )
        if ambiguous:
            raise QueryScopeClarificationRequired(
                "请为所选规范明确版本或适用日期：" + ", ".join(ambiguous)
            )
    elif scope.kind is QueryScopeKind.VERSIONS:
        requested = set(scope.versions)
        missing_catalog = sorted(requested - catalog)
        if missing_catalog:
            raise QueryScopeError(
                "所选版本不在文档目录中："
                + ", ".join(item.business_id for item in missing_catalog)
            )
        missing_snapshot = sorted(requested - available)
        if missing_snapshot:
            raise QueryScopeError(
                "所选版本尚未发布到当前知识库快照："
                + ", ".join(item.business_id for item in missing_snapshot)
            )
        selected = requested
    else:  # pragma: no cover - enum protects construction
        raise QueryScopeError("unsupported query scope")
    if not selected:
        raise QueryScopeError("查询范围没有可用文档")
    return ResolvedQueryScope(scope, snapshot_id, tuple(sorted(selected)))


def versions_from_snapshot(snapshot) -> tuple[SpecEdition, ...]:
    return tuple(
        SpecEdition(item.manifest.spec_id, item.manifest.edition_id)
        for item in snapshot.documents
    )


def versions_from_catalog(catalog) -> tuple[SpecEdition, ...]:
    return tuple(
        SpecEdition(item.spec_id, item.edition_id) for item in catalog.documents
    )


def _unique_nonempty(values: Iterable[str], field_name: str) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(value.strip() for value in values))
    if not normalized or any(not value for value in normalized):
        raise QueryScopeError(f"at least one non-empty {field_name} is required")
    return normalized
