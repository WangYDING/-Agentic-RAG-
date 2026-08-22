import faiss
import numpy as np
import json
from pathlib import Path


class VectorStore:
    def __init__(self, dim):
        self.index = faiss.IndexFlatIP(dim)
        self.chunk_records = []

    def add(self, embeddings, chunk_records):
        vectors = np.array(embeddings, dtype="float32")
        self.index.add(vectors)
        self.chunk_records.extend(chunk_records)

    def search(self, query_embedding, top_k=3):
        query = np.array([query_embedding], dtype="float32")
        scores, indices = self.index.search(query, top_k)

        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx != -1:
                record = self.chunk_records[idx]
                results.append({
                    "text": record["text"],
                    "source": record["source"],
                    "chunk_id": record["chunk_id"],
                    "document_id": record.get("document_id"),
                    "page_start": record.get("page_start"),
                    "page_end": record.get("page_end"),
                    "char_start": record.get("char_start"),
                    "char_end": record.get("char_end"),
                    "content_type": record.get("content_type", "text"),
                    "table_id": record.get("table_id"),
                    "table_title": record.get("table_title"),
                    "extra": record.get("extra", {}),
                    "article_id": record.get("article_id", f"chunk_{record['chunk_id']}"),
                    "chapter_id": record.get("chapter_id"),
                    "chapter_title": record.get("chapter_title"),
                    "display_ref": record.get("display_ref", f"chunk_{record['chunk_id']}"),
                    "score": float(score)
                })
        return results

    def save(self, index_path: str | Path, meta_path: str | Path):
        faiss.write_index(self.index, str(index_path))
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self.chunk_records, f, ensure_ascii=False)
        if not Path(index_path).exists():
            raise OSError(f"FAISS index was not written: {index_path}")
        if not Path(meta_path).exists():
            raise OSError(f"Metadata was not written: {meta_path}")

    def load(self, index_path: str, meta_path: str):
        self.index = faiss.read_index(str(index_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            self.chunk_records = json.load(f)

    @classmethod
    def load_from_files(
        cls,
        index_path: str | Path,
        meta_path: str | Path,
        *,
        expected_dim: int,
        expected_count: int,
    ):
        store = cls(dim=expected_dim)
        store.load(index_path, meta_path)
        if store.index.d != expected_dim:
            raise ValueError("FAISS index dimension does not match manifest")
        if store.index.ntotal != expected_count:
            raise ValueError("FAISS index vector count does not match manifest")
        if len(store.chunk_records) != expected_count:
            raise ValueError("Metadata count does not match manifest")
        return store
