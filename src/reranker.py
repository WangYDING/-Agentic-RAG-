from sentence_transformers import CrossEncoder


class Reranker:
    supports_score_cache = True

    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model = CrossEncoder(model_name)

    def score_candidates(self, query: str, results: list[dict]) -> list[dict]:
        """Return every candidate with its cross-encoder score, preserving order."""
        if not results:
            return []

        pairs = [(query, item["text"]) for item in results]
        scores = self.model.predict(pairs)

        scored_results = []
        for item, rerank_score in zip(results, scores):
            new_item = item.copy()
            new_item["rerank_score"] = float(rerank_score)
            scored_results.append(new_item)
        return scored_results

    @staticmethod
    def select_top(scored_results: list[dict], top_n: int = 3) -> list[dict]:
        """Stably rank already-scored candidates and select the requested prefix."""
        ranked = sorted(
            scored_results,
            key=lambda item: item["rerank_score"],
            reverse=True,
        )
        return ranked[:top_n]

    def rerank(self, query: str, results: list[dict], top_n: int = 3):
        """Score, rank, and select candidates using the legacy public interface."""
        scored_results = self.score_candidates(query, results)
        return self.select_top(scored_results, top_n=top_n)
