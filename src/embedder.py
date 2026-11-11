from sentence_transformers import SentenceTransformer


class Embedder:
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        model_revision: str | None = None,
    ):
        self.model_name = model_name
        self.model_revision = model_revision
        self.model = SentenceTransformer(model_name, revision=model_revision)

    def embed_text(self, text: str):
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_texts(self, texts: list[str]):
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()
