from __future__ import annotations

import re

import jieba
from rank_bm25 import BM25Okapi


class BM25Retriever:
    """BM25 retrieval over persisted chunk metadata."""

    def __init__(self, chunk_records: list[dict]):
        self.chunk_records = chunk_records
        self._tokens = [self._tokenize(record["text"]) for record in chunk_records]
        self._index = BM25Okapi(self._tokens)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        tokens = []
        for part in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9]+", text):
            if re.fullmatch(r"[\u4e00-\u9fff]+", part):
                tokens.extend(
                    token for token in jieba.lcut(part, cut_all=False) if token.strip()
                )
            else:
                tokens.append(part.lower())
        return tokens

    def retrieve(self, query: str, top_k: int = 10) -> list[dict]:
        scores = self._index.get_scores(self._tokenize(query))
        ranked = sorted(
            enumerate(scores), key=lambda item: (-float(item[1]), item[0])
        )[:top_k]
        results = []
        for index, score in ranked:
            record = self.chunk_records[index]
            results.append(
                {
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
                    "article_id": record.get(
                        "article_id", f"chunk_{record['chunk_id']}"
                    ),
                    "chapter_id": record.get("chapter_id"),
                    "chapter_title": record.get("chapter_title"),
                    "display_ref": record.get(
                        "display_ref", f"chunk_{record['chunk_id']}"
                    ),
                    "score": float(score),
                }
            )
        return results
