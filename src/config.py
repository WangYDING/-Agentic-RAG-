from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field


DEFAULT_PDF_PATH = "data/raw/城市轨道交通工程设计标准.pdf"
DEFAULT_INDEX_DIR = ".rag_index"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-base"
DEFAULT_GENERATION_MODEL = "deepseek-chat"
DEFAULT_RETRIEVAL_TOP_K = 10
DEFAULT_EVIDENCE_TOP_N = 3


class ConfigurationError(ValueError):
    """Raised when application configuration is missing or invalid."""


def _resolve(explicit, environ: Mapping[str, str], name: str, default):
    if explicit is not None:
        return explicit
    if name in environ:
        return environ[name]
    return default


def _positive_int(value: int | str, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} 必须是正整数。") from exc
    if parsed <= 0:
        raise ConfigurationError(f"{name} 必须是正整数。")
    return parsed


@dataclass(frozen=True)
class AppConfig:
    pdf_path: str = DEFAULT_PDF_PATH
    index_dir: str = DEFAULT_INDEX_DIR
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    reranker_model: str = DEFAULT_RERANKER_MODEL
    generation_model: str = DEFAULT_GENERATION_MODEL
    api_base_url: str | None = None
    api_key: str | None = field(default=None, repr=False)
    retrieval_top_k: int = DEFAULT_RETRIEVAL_TOP_K
    evidence_top_n: int = DEFAULT_EVIDENCE_TOP_N

    @classmethod
    def from_sources(
        cls,
        *,
        environ: Mapping[str, str] | None = None,
        pdf_path: str | None = None,
        index_dir: str | None = None,
        embedding_model: str | None = None,
        reranker_model: str | None = None,
        generation_model: str | None = None,
        api_base_url: str | None = None,
        api_key: str | None = None,
        retrieval_top_k: int | str | None = None,
        evidence_top_n: int | str | None = None,
    ) -> AppConfig:
        values = os.environ if environ is None else environ
        resolved_top_k = _resolve(
            retrieval_top_k,
            values,
            "RAG_RETRIEVAL_TOP_K",
            DEFAULT_RETRIEVAL_TOP_K,
        )
        resolved_top_n = _resolve(
            evidence_top_n,
            values,
            "RAG_EVIDENCE_TOP_N",
            DEFAULT_EVIDENCE_TOP_N,
        )
        return cls(
            pdf_path=str(
                _resolve(pdf_path, values, "RAG_PDF_PATH", DEFAULT_PDF_PATH)
            ),
            index_dir=str(
                _resolve(index_dir, values, "RAG_INDEX_DIR", DEFAULT_INDEX_DIR)
            ),
            embedding_model=str(
                _resolve(
                    embedding_model,
                    values,
                    "RAG_EMBEDDING_MODEL",
                    DEFAULT_EMBEDDING_MODEL,
                )
            ),
            reranker_model=str(
                _resolve(
                    reranker_model,
                    values,
                    "RAG_RERANKER_MODEL",
                    DEFAULT_RERANKER_MODEL,
                )
            ),
            generation_model=str(
                _resolve(
                    generation_model,
                    values,
                    "DEEPSEEK_MODEL",
                    DEFAULT_GENERATION_MODEL,
                )
            ),
            api_base_url=_resolve(
                api_base_url, values, "DEEPSEEK_BASE_URL", None
            ),
            api_key=_resolve(api_key, values, "DEEPSEEK_API_KEY", None),
            retrieval_top_k=_positive_int(
                resolved_top_k, "RAG_RETRIEVAL_TOP_K"
            ),
            evidence_top_n=_positive_int(resolved_top_n, "RAG_EVIDENCE_TOP_N"),
        )

    def validate_for_agent(self) -> AppConfig:
        missing = []
        if not (self.api_key or "").strip():
            missing.append("DEEPSEEK_API_KEY")
        if not (self.api_base_url or "").strip():
            missing.append("DEEPSEEK_BASE_URL")
        if missing:
            raise ConfigurationError(
                "缺少配置："
                + ", ".join(missing)
                + "。请通过显式参数、环境变量或 .env 提供。"
            )
        return self
