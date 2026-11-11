from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4


ResultType = Literal["answer", "refuse", "error"]


@dataclass(frozen=True)
class ApplicationResult:
    """Public result contract shared by application adapters."""

    result_type: ResultType
    message: str
    request_id: str = field(default_factory=lambda: uuid4().hex)
    error_code: str | None = None
    retryable: bool = False
    missing_requirements: tuple[str, ...] = ()
    trace: tuple[dict[str, Any], ...] = ()
    index_version_id: str | None = None

    @property
    def is_answer(self) -> bool:
        return self.result_type == "answer"

