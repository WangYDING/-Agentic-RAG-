from src.embedder import Embedder
from src.vector_store import VectorStore


class Retriever:
    def __init__(self, vector_store: VectorStore, embedder: Embedder):
        self.vector_store = vector_store
        self.embedder = embedder

    def retrieve(self, query: str, top_k: int = 3):
        query_embedding = self.embedder.embed_text(query)
        results = self.vector_store.search(query_embedding, top_k=top_k)
        return results