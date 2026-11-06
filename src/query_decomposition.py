from __future__ import annotations

from dataclasses import dataclass
import re


_TAIL_PATTERNS = (
    r"[，,；;]?(?:三份|各份|这些|上述)?规范分别.*$",
    r"[，,；;]?(?:并)?分别列出.*$",
    r"[，,；;]?仅陈述.*$",
    r"分别(?:怎样|如何|有哪些)?.*$",
)

_SPECIFICATION = r"(?:GB\s*\d+-\d{4}|DB\d+(?:/T)?\s*\d+-\d{4})"


@dataclass(frozen=True)
class RetrievalDecomposition:
    targets: tuple[str, ...]
    reason: str | None = None


def decompose_retrieval_targets(query: str, *, max_targets: int = 3) -> list[str]:
    """Extract parallel information needs without adding facts or document scope."""
    return list(decompose_retrieval_plan(query, max_targets=max_targets).targets)


def decompose_retrieval_plan(
    query: str, *, max_targets: int = 3
) -> RetrievalDecomposition:
    """Extract supported parallel targets and explain conservative fallback."""
    text = re.sub(r"\s+", "", query).strip("？?。 ")
    comparison = _comparison_targets(text, max_targets)
    if comparison:
        return RetrievalDecomposition(tuple(comparison))

    scene_plan = _parallel_scene_targets(text, max_targets)
    if scene_plan is not None:
        return scene_plan

    target = _target_span(text)
    for pattern in _TAIL_PATTERNS:
        target = re.sub(pattern, "", target)
    parts = [
        part.strip("，,；;：:的要求规定内容")
        for part in re.split(r"(?:以及|以及对|并且|同时|或|与)", target)
    ]
    focused = []
    for part in parts:
        if len(part) < 4 or part == text or part in focused:
            continue
        focused.append(part)
        if len(focused) >= max_targets:
            break
    return RetrievalDecomposition(tuple(focused if len(focused) >= 2 else []))


def focused_query_variants(targets: list[str]) -> list[str]:
    variants = []
    for target in targets:
        if "人员新风量" in target:
            scene = target.replace("人员新风量", "").strip()
            variants.append(
                f"{scene} 人员 新风量 新鲜空气量 乘客 工作人员 每小时".strip()
            )
            continue
        if "适用范围" in target:
            variants.append("本标准适用于 本规范适用于 必须执行本规范")
            continue
        protections = list(
            dict.fromkeys(
                re.findall(r"防(?:内涝|洪水|水淹|洪|淹|震|雪|滑|风|雨|雷)", target)
            )
        )
        if len(protections) >= 2:
            core = "防止自然灾害 防内涝 防洪 防淹"
            if core not in variants:
                variants.append(core)
        variants.append(target)
    return variants


def _target_span(text: str) -> str:
    about = re.search(r"关于(.+)", text)
    if about:
        return about.group(1)
    comparison = re.search(r"(?:三份规范|各规范)对(.+)", text)
    if comparison:
        return comparison.group(1)
    generic = re.search(r"对(.+?)(?:分别|有哪些|怎样|如何)", text)
    return generic.group(1) if generic else text


def _comparison_targets(text: str, max_targets: int) -> list[str]:
    match = re.search(
        rf"比较({_SPECIFICATION})与({_SPECIFICATION})的(.+?)(?:，|,)(?:并)?指出前者(.+)$",
        text,
        re.I,
    )
    if not match:
        return []
    first, second, shared, extra = match.groups()
    shared = re.sub(r"(?:的)?规定$", "", shared).strip("，,：:")
    extra = re.sub(r"^(?:额外)?(?:提出)?的?", "", extra)
    extra = re.sub(r"(?:的)?要求$", "", extra).strip("，,：:")
    if not shared or not extra:
        return []
    targets = [f"{first}{shared}", f"{second}{shared}", f"{first}{extra}"]
    return targets[:max_targets]


def _parallel_scene_targets(
    text: str, max_targets: int
) -> RetrievalDecomposition | None:
    match = re.search(
        r"(?:三份规范|各规范)对(.+?)分别(?:有|怎样|如何)", text
    )
    if not match:
        return None
    span = match.group(1)
    parts = [part for part in re.split(r"、|以及|及", span) if part]
    if len(parts) < 2:
        return None
    last = parts[-1]
    metric = re.search(
        r"((?:工作人员|乘客|人员)[\u4e00-\u9fff]{1,8}(?:量|率|值|时间|距离|宽度|高度|间隙|年限))$",
        last,
    )
    if not metric:
        return RetrievalDecomposition((), "parallel_target_not_uniquely_parsed")
    predicate = metric.group(1)
    last_scene = last[: -len(predicate)]
    scenes = [*parts[:-1], last_scene]
    if not last_scene or any(len(scene) < 2 for scene in scenes):
        return RetrievalDecomposition((), "parallel_target_not_uniquely_parsed")
    return RetrievalDecomposition(
        tuple(f"{scene}{predicate}" for scene in scenes[:max_targets])
    )
