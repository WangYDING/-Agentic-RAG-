from collections import defaultdict
from typing import Iterable


KS = (1, 3, 5, 10)


def first_hit_rank(hits: list[bool], max_rank: int = 10) -> int | None:
    for index, hit in enumerate(hits[:max_rank], start=1):
        if hit:
            return index
    return None


def compute_retrieval_metrics(cases: Iterable[dict]) -> dict:
    cases = [case for case in cases if case.get("metric_eligible", True)]
    if not cases:
        return _empty_metrics()

    metrics = {}
    for k in KS:
        metrics[f"recall@{k}"] = sum(_case_recall_at_k(case, k) for case in cases) / len(cases)
        metrics[f"hitrate@{k}"] = sum(any(case["hits"][:k]) for case in cases) / len(cases)

    reciprocal_ranks = []
    for case in cases:
        rank = first_hit_rank(case["hits"], max_rank=10)
        reciprocal_ranks.append(0.0 if rank is None else 1.0 / rank)
    metrics["mrr@10"] = sum(reciprocal_ranks) / len(reciprocal_ranks)
    metrics["count"] = len(cases)
    return metrics


def compute_grouped_metrics(cases: list[dict]) -> dict[str, dict]:
    groups = defaultdict(list)
    for case in cases:
        groups[case["question_type"]].append(case)
    return {name: compute_retrieval_metrics(items) for name, items in sorted(groups.items())}


def _case_recall_at_k(case: dict, k: int) -> float:
    gold_count = case.get("gold_count", 0)
    if gold_count <= 0:
        return 0.0
    matched = set()
    for indices in case.get("gold_hit_ids_by_rank", [])[:k]:
        matched.update(indices)
    return len(matched) / gold_count


def _empty_metrics() -> dict:
    metrics = {f"recall@{k}": 0.0 for k in KS}
    metrics.update({f"hitrate@{k}": 0.0 for k in KS})
    metrics["mrr@10"] = 0.0
    metrics["count"] = 0
    return metrics
