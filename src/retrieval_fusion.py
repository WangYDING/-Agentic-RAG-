from __future__ import annotations

RRF_K = 60


def chunk_identity(result: dict) -> tuple[object, ...]:
    """Stable identity for a persisted chunk across retrieval implementations."""
    spec_id = result.get("spec_id")
    edition_id = result.get("edition_id")
    if spec_id is not None and edition_id is not None:
        return spec_id, edition_id, result.get("chunk_id")
    return result.get("source"), result.get("chunk_id")


def reciprocal_rank_fusion(
    *ranked_lists: list[dict], top_k: int | None = 10
) -> list[dict]:
    fused: dict[tuple[object, ...], dict] = {}
    for ranked in ranked_lists:
        for rank, result in enumerate(ranked, start=1):
            identity = chunk_identity(result)
            if identity not in fused:
                fused[identity] = {**result, "rrf_score": 0.0}
            fused[identity]["rrf_score"] += 1.0 / (RRF_K + rank)
    fused_results = sorted(
        fused.values(),
        key=lambda result: (-result["rrf_score"], chunk_identity(result)),
    )
    return fused_results if top_k is None else fused_results[:top_k]
