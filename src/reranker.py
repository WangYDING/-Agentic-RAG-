from sentence_transformers import CrossEncoder


class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, results: list[dict], top_n: int = 3):
        """
        对初步召回结果进行重排序
        :param query: 用户问题
        :param results: 初步检索结果，每个元素是 {"text": ..., "source": ..., "chunk_id": ..., "score": ...}
        :param top_n: 重排序后保留前几条
        :return: 重排序后的结果
        """
        if not results:
            return []

        pairs = [(query, item["text"]) for item in results]
        scores = self.model.predict(pairs)

        reranked_results = []
        for item, rerank_score in zip(results, scores):
            new_item = item.copy()
            new_item["rerank_score"] = float(rerank_score)
            reranked_results.append(new_item)

        reranked_results.sort(key=lambda x: x["rerank_score"], reverse=True)

        return reranked_results[:top_n]