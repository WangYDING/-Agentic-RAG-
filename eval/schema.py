from dataclasses import asdict, dataclass, field
from typing import Any


CONVERSATION_ROLES = frozenset({"user", "assistant"})


@dataclass(frozen=True)
class ConversationMessage:
    role: str
    content: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        role = data["role"]
        if role not in CONVERSATION_ROLES:
            allowed = ", ".join(sorted(CONVERSATION_ROLES))
            raise ValueError(f"Invalid conversation role {role!r}; expected one of: {allowed}")
        content = data["content"]
        if not isinstance(content, str):
            raise ValueError("Conversation message content must be a string")
        return cls(role=role, content=content)


@dataclass(frozen=True)
class GoldEvidence:
    document: str
    page: int | None = None
    article: str | None = None
    table: str | None = None


@dataclass(frozen=True)
class NumericExpectation:
    value: str
    unit: str
    conditions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnnotationReview:
    status: str = "pending"
    reviewer: str | None = None
    reviewed_at: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class EvalExample:
    id: str
    question: str
    question_type: str
    answerable: bool
    gold_answer: str
    gold_evidence: list[GoldEvidence] = field(default_factory=list)
    conversation_history: list[ConversationMessage] = field(default_factory=list)
    rewritten_query_reference: str | None = None
    hard_negative_type: str | None = None
    why_unanswerable: str | None = None

    required_requirements: list[str] = field(default_factory=list)
    key_answer_points: list[str] = field(default_factory=list)
    numeric_expectations: list[NumericExpectation] = field(default_factory=list)
    annotation_review: AnnotationReview = field(default_factory=AnnotationReview)

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        if type(data["answerable"]) is not bool:
            raise ValueError("answerable must be a boolean")
        for key in ("id", "question", "question_type"):
            if not isinstance(data[key], str) or not data[key].strip():
                raise ValueError(f"{key} must be a non-empty string")
        for key in ("required_requirements", "key_answer_points"):
            items = data.get(key, [])
            if not isinstance(items, list) or any(not isinstance(x, str) or not x.strip() for x in items):
                raise ValueError(f"{key} must be a list of non-empty strings")
        numeric = []
        for item in data.get("numeric_expectations", []):
            if not all(isinstance(item.get(k), str) and item[k].strip() for k in ("value", "unit")):
                raise ValueError("numeric expectations require string value and unit")
            conditions = item.get("conditions", [])
            if not isinstance(conditions, list) or any(not isinstance(x, str) or not x.strip() for x in conditions):
                raise ValueError("numeric conditions must be non-empty strings")
            numeric.append(NumericExpectation(item["value"], item["unit"], conditions))
        review = AnnotationReview(**data.get("annotation_review", {}))
        if review.status not in {"pending", "source_verified", "approved", "rejected"}:
            raise ValueError("invalid annotation review status")
        if review.status in {"source_verified", "approved"} and not (
            review.reviewer and review.reviewed_at
        ):
            raise ValueError(
                f"{review.status} annotation requires reviewer and reviewed_at"
            )
        rewritten_query_reference = data.get("rewritten_query_reference")
        if rewritten_query_reference is not None and not isinstance(
            rewritten_query_reference,
            str,
        ):
            raise ValueError("rewritten_query_reference must be a string or null")
        return cls(
            id=data["id"],
            question=data["question"],
            question_type=data["question_type"],
            answerable=data["answerable"],
            gold_answer=data.get("gold_answer", ""),
            gold_evidence=[
                GoldEvidence(
                    document=item["document"],
                    page=item.get("page"),
                    article=item.get("article"),
                    table=item.get("table"),
                )
                for item in data.get("gold_evidence", [])
            ],
            conversation_history=[
                ConversationMessage.from_dict(item)
                for item in data.get("conversation_history", [])
            ],
            rewritten_query_reference=rewritten_query_reference,
            required_requirements=data.get("required_requirements", []),
            key_answer_points=data.get("key_answer_points", []),
            numeric_expectations=numeric,
            annotation_review=review,
            hard_negative_type=data.get("hard_negative_type"),
            why_unanswerable=data.get("why_unanswerable"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_eval_dataset(path) -> list[EvalExample]:
    import json
    from pathlib import Path

    path = Path(path)
    examples = []
    with open(path, "r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                examples.append(EvalExample.from_dict(json.loads(line)))
            except KeyError as exc:
                raise ValueError(f"Missing required field {exc} at {path}:{line_number}") from exc
    ids = [example.id for example in examples]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate example IDs in {path}")
    return examples


def is_gold_hit(retrieved: dict[str, Any], gold_items: list[GoldEvidence]) -> bool:
    return bool(matched_gold_indices(retrieved, gold_items))


def matched_gold_indices(retrieved: dict[str, Any], gold_items: list[GoldEvidence]) -> list[int]:
    matches = []
    for index, gold in enumerate(gold_items):
        if _matches_gold(retrieved, gold):
            matches.append(index)
    return matches


def _matches_gold(retrieved: dict[str, Any], gold: GoldEvidence) -> bool:
    if gold.document and retrieved.get("source") != gold.document:
        return False
    if gold.page is not None:
        page_start = retrieved.get("page_start")
        page_end = retrieved.get("page_end") or page_start
        if page_start is None or not (page_start <= gold.page <= page_end):
            return False
    if gold.article and retrieved.get("article_id") != gold.article:
        return False
    if gold.table and retrieved.get("table_id") != gold.table:
        return False
    return True


def _legacy_is_gold_hit(retrieved: dict[str, Any], gold_items: list[GoldEvidence]) -> bool:
    for gold in gold_items:
        if gold.document and retrieved.get("source") != gold.document:
            continue
        if gold.page is not None:
            page_start = retrieved.get("page_start")
            page_end = retrieved.get("page_end") or page_start
            if page_start is None or not (page_start <= gold.page <= page_end):
                continue
        if gold.article and retrieved.get("article_id") != gold.article:
            continue
        if gold.table and retrieved.get("table_id") != gold.table:
            continue
        return True
    return False
