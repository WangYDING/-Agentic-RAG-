from __future__ import annotations

import re


_TAIL_PATTERNS = (
    r"[，,；;]?(?:三份|各份|这些|上述)?规范分别.*$",
    r"[，,；;]?(?:并)?分别列出.*$",
    r"[，,；;]?仅陈述.*$",
    r"分别(?:怎样|如何|有哪些)?.*$",
)


def decompose_retrieval_targets(query: str, *, max_targets: int = 3) -> list[str]:
    """Extract parallel information needs without adding facts or document scope."""
    text = re.sub(r"\s+", "", query).strip("？?。 ")
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
    return focused if len(focused) >= 2 else []


def focused_query_variants(targets: list[str]) -> list[str]:
    variants = []
    for target in targets:
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
