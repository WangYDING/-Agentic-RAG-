from src.reranker import Reranker


class FakeCrossEncoder:
    def __init__(self):
        self.pairs = []

    def predict(self, pairs):
        self.pairs = list(pairs)
        return [0.5, 0.9, 0.5]


def test_scoring_returns_every_candidate_and_selection_is_stable():
    reranker = Reranker.__new__(Reranker)
    reranker.model = FakeCrossEncoder()
    candidates = [
        {"chunk_id": 1, "text": "one"},
        {"chunk_id": 2, "text": "two"},
        {"chunk_id": 3, "text": "three"},
    ]

    scored = reranker.score_candidates("question", candidates)
    selected = reranker.select_top(scored, top_n=3)

    assert reranker.model.pairs == [
        ("question", "one"),
        ("question", "two"),
        ("question", "three"),
    ]
    assert [item["chunk_id"] for item in scored] == [1, 2, 3]
    assert [item["chunk_id"] for item in selected] == [2, 1, 3]
    assert all("rerank_score" not in item for item in candidates)


def test_legacy_rerank_composes_scoring_and_selection():
    reranker = Reranker.__new__(Reranker)
    reranker.model = FakeCrossEncoder()
    candidates = [
        {"chunk_id": 1, "text": "one"},
        {"chunk_id": 2, "text": "two"},
        {"chunk_id": 3, "text": "three"},
    ]

    assert [item["chunk_id"] for item in reranker.rerank("question", candidates, 2)] == [2, 1]
