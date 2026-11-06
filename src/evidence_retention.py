from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Iterable

from src.query_decomposition import decompose_retrieval_plan
from src.retrieval_fusion import chunk_identity


class RequirementSource(StrEnum):
    QUESTION = "question"
    GRADER = "grader"


@dataclass(frozen=True)
class EvidenceRequirement:
    business_id: str | None
    article_id: str | None
    subrequirement: str
    source: RequirementSource
    authoritative: bool
    status: str
    reason: str | None = None


@dataclass(frozen=True)
class ParsedRequirements:
    question_requirements: tuple[EvidenceRequirement, ...]
    grader_requirements: tuple[EvidenceRequirement, ...]


@dataclass(frozen=True)
class RetainedArticleGroup:
    business_id: str
    article_id: str
    chunk_ids: tuple[object, ...]
    basis: str
    covered_text: str


@dataclass(frozen=True)
class SelectionFallback:
    subrequirement: str
    reason: str
    candidate_articles: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetentionDecision:
    selected: tuple[dict, ...]
    retained_groups: tuple[RetainedArticleGroup, ...]
    fallbacks: tuple[SelectionFallback, ...]


def build_retry_query(parsed: ParsedRequirements, fallback: str) -> str:
    """Turn Grader free text into retrieval hints, not selection verdicts."""
    hints = []
    seen = set()
    for requirement in parsed.grader_requirements:
        hint = re.split(
            r"[，,；;](?:现有证据|给定证据|当前证据|证据中|E\d+|但(?:未|没有)|无法)",
            requirement.subrequirement,
            maxsplit=1,
        )[0]
        hint = re.sub(r"^(?:缺少|还缺少|需要补充)", "", hint).strip(" ：:，,；;")
        if hint and hint not in seen:
            seen.add(hint)
            hints.append(hint)
    return "；".join(hints) or fallback


_ARTICLE_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+){2,})(?!\d)")
_NOISE = re.compile(
    r"(?:请|说明|分别|比较|对比|并指出|指出|前者|后者|与|规定|要求|什么|哪些|如何|是否|还|必须|提供|缺少|"
    r"给出|明确|直接|相关|具体|规范|标准|条文|第\s*\d+(?:\.\d+){2,}\s*条)"
)


def parse_evidence_requirements(
    question: str,
    grader_missing: Iterable[str],
    allowed_business_ids: tuple[str, ...],
) -> ParsedRequirements:
    decomposition = decompose_retrieval_plan(question)
    question_parts = list(decomposition.targets) or _split_requirements(question)
    collective_scope = bool(
        decomposition.targets
        and re.search(r"(?:两份|三份|各份|各规范|分别|各自)", question)
    )
    question_requirements = tuple(
        requirement
        for part in question_parts
        if part.strip()
        for requirement in _question_target_requirements(
            part,
            allowed_business_ids,
            expand_unscoped=collective_scope,
        )
    )
    grader_requirements = []
    question_terms = set().union(
        *(_meaningful_terms(item.subrequirement) for item in question_requirements)
    ) if question_requirements else set()
    for missing in grader_missing:
        for part in _split_requirements(missing):
            for parsed in _parse_text_requirements(
                part, RequirementSource.GRADER, allowed_business_ids
            ):
                missing_terms = _meaningful_terms(parsed.subrequirement)
                authoritative = bool(question_terms and missing_terms & question_terms)
                grader_requirements.append(
                    EvidenceRequirement(
                        business_id=parsed.business_id,
                        article_id=parsed.article_id,
                        subrequirement=parsed.subrequirement,
                        source=RequirementSource.GRADER,
                        authoritative=authoritative,
                        status="mapped_to_question" if authoritative else "grader_only",
                        reason=None if authoritative else "not_derived_from_question",
                    )
                )
    return ParsedRequirements(question_requirements, tuple(grader_requirements))


def select_retained_article_groups(
    parsed: ParsedRequirements,
    candidates: list[dict],
    *,
    reranked: list[dict],
    evidence_limit: int,
    allowed_business_ids: tuple[str, ...],
) -> RetentionDecision:
    allowed = set(allowed_business_ids)
    in_scope = [
        item for item in candidates if not allowed or _business_id(item) in allowed
    ]
    reranked_in_scope = [
        item for item in reranked if not allowed or _business_id(item) in allowed
    ]
    groups = _group_articles(in_scope)
    retained: list[RetainedArticleGroup] = []
    retained_candidates: list[dict] = []
    retained_identities = set()
    fallbacks: list[SelectionFallback] = []

    for requirement in _authoritative_requirements(parsed):
        if not requirement.business_id:
            fallbacks.append(SelectionFallback(requirement.subrequirement, "missing_version"))
            continue
        eligible = [
            (key, group)
            for key, group in groups.items()
            if key[0] == requirement.business_id
            and (not requirement.article_id or key[1] == requirement.article_id)
            and _directly_covers(group, requirement)
        ]
        if len(eligible) != 1:
            fallbacks.append(
                SelectionFallback(
                    requirement.subrequirement,
                    "not_unique" if eligible else "no_direct_coverage",
                    tuple(key[1] for key, _ in eligible),
                )
            )
            continue
        (business_id, article_id, _segment_start), group = eligible[0]
        if not all(item.get("article_group_complete", True) for item in group):
            fallbacks.append(
                SelectionFallback(
                    requirement.subrequirement,
                    "incomplete_article_group",
                    (article_id,),
                )
            )
            continue
        unseen = [item for item in group if chunk_identity(item) not in retained_identities]
        if len(retained_candidates) + len(unseen) > evidence_limit:
            fallbacks.append(
                SelectionFallback(
                    requirement.subrequirement, "article_group_exceeds_limit", (article_id,)
                )
            )
            continue
        for item in unseen:
            retained_identities.add(chunk_identity(item))
            retained_candidates.append(item)
        retained.append(
            RetainedArticleGroup(
                business_id=business_id,
                article_id=article_id,
                chunk_ids=tuple(item.get("chunk_id") for item in group),
                basis=("explicit_article" if requirement.article_id else "unique_direct_coverage"),
                covered_text=requirement.subrequirement,
            )
        )

    selected = list(retained_candidates)
    seen = set(retained_identities)
    for item in reranked_in_scope:
        if len(selected) >= evidence_limit:
            break
        identity = chunk_identity(item)
        if identity not in seen:
            seen.add(identity)
            selected.append(item)
    return RetentionDecision(tuple(selected), tuple(retained), tuple(fallbacks))


def _authoritative_requirements(parsed: ParsedRequirements):
    yielded = set()
    for requirement in (*parsed.question_requirements, *parsed.grader_requirements):
        if not requirement.authoritative:
            continue
        key = (requirement.business_id, requirement.article_id, requirement.subrequirement)
        if key not in yielded:
            yielded.add(key)
            yield requirement


def _parse_text_requirements(text, source, allowed_business_ids):
    article = next(iter(_ARTICLE_RE.findall(text)), None)
    business_ids = _find_business_ids(text, allowed_business_ids)
    if (
        not business_ids
        and article
        and re.search(r"(?:两份|三份|各份|各规范|各自|分别)", text)
    ):
        business_ids = list(allowed_business_ids)
    business_ids = business_ids or [None]
    return [
        EvidenceRequirement(
            business_id=business_id,
            article_id=article,
            subrequirement=text.strip(),
            source=source,
            authoritative=source == RequirementSource.QUESTION,
            status="parsed" if business_id else "missing_version",
            reason=None if business_id else "specification_version_not_explicit",
        )
        for business_id in business_ids
    ]


def _question_target_requirements(
    text: str,
    allowed_business_ids: tuple[str, ...],
    *,
    expand_unscoped: bool,
):
    parsed = _parse_text_requirements(
        text, RequirementSource.QUESTION, allowed_business_ids
    )
    if not expand_unscoped or any(item.business_id for item in parsed):
        return parsed
    return [
        EvidenceRequirement(
            business_id=business_id,
            article_id=parsed[0].article_id,
            subrequirement=text.strip(),
            source=RequirementSource.QUESTION,
            authoritative=True,
            status="scope_expanded",
        )
        for business_id in allowed_business_ids
    ]


def _find_business_ids(text: str, allowed_business_ids: tuple[str, ...]):
    normalized = re.sub(r"[^A-Z0-9]", "", text.upper())
    matches = []
    for business_id in allowed_business_ids:
        spec_id, edition = business_id.rsplit("@", 1)
        spec_token = re.sub(r"[^A-Z0-9]", "", spec_id.upper())
        aliases = {spec_token.removeprefix("CN")}
        aliases.add(re.sub(r"[^A-Z0-9]", "", spec_id.rsplit(".", 1)[-1].upper()))
        if edition in normalized and any(
            alias and alias in normalized for alias in aliases
        ):
            matches.append(business_id)
    return matches


def _split_requirements(text: str):
    return [part.strip(" ：:，,。?") for part in re.split(r"[；;]", text) if part.strip()]


def _meaningful_terms(text: str):
    text = _canonical_retrieval_text(text)
    cleaned = _NOISE.sub("", text)
    cleaned = re.sub(r"[A-Z]{0,4}\s*\d+(?:[\s/.-]*\d+)*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]", "", cleaned)
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", cleaned))
    terms = {chinese[index:index + 2] for index in range(max(0, len(chinese) - 1))}
    terms.update(token.lower() for token in re.findall(r"[A-Za-z]{3,}", cleaned))
    return {term for term in terms if term}


def _directly_covers(group: list[dict], requirement: EvidenceRequirement):
    if requirement.article_id:
        return True
    group_text = " ".join(str(item.get("text", "")) for item in group)
    canonical_requirement = _canonical_retrieval_text(requirement.subrequirement)
    canonical_group = _canonical_retrieval_text(group_text)
    if "设计年限" in canonical_requirement:
        return "设计年限" in canonical_group
    if "人员新风量" in requirement.subrequirement:
        scene = canonical_requirement.split("人员新风量", 1)[0]
        scene = re.sub(
            r"(?:GB|DB)\s*\d*(?:/T)?\s*\d*(?:-\d{4})?",
            "",
            scene,
            flags=re.I,
        )
        scene = re.sub(r"[^\w\u4e00-\u9fff]", "", scene).lstrip("的")
        return bool(
            scene
            and scene in re.sub(r"\s+", "", canonical_group)
            and "人员新风量" in canonical_group
        )
    if "运能" in canonical_requirement:
        return "运能" in canonical_group
    required = _meaningful_terms(requirement.subrequirement)
    if not required:
        return False
    present = _meaningful_terms(group_text)
    overlap = required & present
    return len(overlap) >= 2 and len(overlap) / len(required) >= 0.45


def _canonical_retrieval_text(text: str) -> str:
    return (
        text.replace("设备与管理用房", "设备管理用房")
        .replace("新鲜空气量", "人员新风量")
        .replace("工作人员", "人员")
        .replace("乘客", "人员")
    )


def _business_id(candidate: dict):
    return f"{candidate.get('spec_id')}@{candidate.get('edition_id')}"


def _group_articles(candidates: list[dict]):
    article_candidates: dict[tuple[str, str], list[dict]] = {}
    for item in candidates:
        article = item.get("article_id")
        if not article:
            continue
        article_candidates.setdefault(
            (_business_id(item), str(article)), []
        ).append(item)
    groups: dict[tuple[str, str, object], list[dict]] = {}
    for (business_id, article_id), items in article_candidates.items():
        items.sort(key=lambda item: (item.get("chunk_id") is None, item.get("chunk_id")))
        segment: list[dict] = []
        previous_chunk_id = None
        for item in items:
            chunk_id = item.get("chunk_id")
            if (
                segment
                and isinstance(previous_chunk_id, int)
                and isinstance(chunk_id, int)
                and chunk_id != previous_chunk_id + 1
            ):
                groups[(business_id, article_id, segment[0].get("chunk_id"))] = segment
                segment = []
            segment.append(item)
            previous_chunk_id = chunk_id
        if segment:
            groups[(business_id, article_id, segment[0].get("chunk_id"))] = segment
    return groups
