from __future__ import annotations

from types import SimpleNamespace

from src.agent_workflow import AgentWorkflow
from src.config import AppConfig
from src.reliability import CallPolicy


def _load_component_factories():
    """Load model-backed components only when constructing the real application."""
    from src.bm25_retriever import BM25Retriever
    from src.embedder import Embedder
    from src.evidence_sufficiency import EvidenceSufficiencyGrader
    from src.generator import Generator
    from src.hybrid_retriever import HybridRetriever
    from src.index_manager import IndexManager
    from src.query_rewriter import QueryRewriter
    from src.reranker import Reranker
    from src.retriever import Retriever

    return SimpleNamespace(
        BM25Retriever=BM25Retriever,
        Embedder=Embedder,
        EvidenceSufficiencyGrader=EvidenceSufficiencyGrader,
        Generator=Generator,
        HybridRetriever=HybridRetriever,
        IndexManager=IndexManager,
        QueryRewriter=QueryRewriter,
        Reranker=Reranker,
        Retriever=Retriever,
    )


def build_agent_workflow(
    config: AppConfig,
    *,
    factories=None,
) -> AgentWorkflow:
    """Build the complete Hybrid + sufficiency bounded Agent application."""
    config.validate_for_agent()
    factories = factories or _load_component_factories()
    call_policy = CallPolicy(
        request_timeout_seconds=config.request_timeout_seconds,
        max_network_retries=config.max_network_retries,
    )

    embedder = factories.Embedder(
        config.embedding_model,
        model_revision=config.embedding_revision,
    )
    index_manager = factories.IndexManager(
        config.index_dir,
        lock_timeout_seconds=config.index_lock_timeout_seconds,
    )
    if config.index_auto_build:
        managed = index_manager.build_or_load(config.pdf_path, embedder=embedder)
    else:
        managed = index_manager.load_published(config.pdf_path, embedder=embedder)
    retriever = factories.HybridRetriever(
        factories.Retriever(managed.vector_store, embedder),
        factories.BM25Retriever(managed.vector_store.chunk_records),
    )
    return AgentWorkflow(
        retriever=retriever,
        reranker=factories.Reranker(config.reranker_model),
        grader=factories.EvidenceSufficiencyGrader(
            api_key=config.api_key,
            base_url=config.api_base_url,
            model=config.generation_model,
            call_policy=call_policy,
        ),
        generator=factories.Generator(
            api_key=config.api_key,
            base_url=config.api_base_url,
            model=config.generation_model,
            call_policy=call_policy,
        ),
        rewriter=factories.QueryRewriter(
            api_key=config.api_key,
            base_url=config.api_base_url,
            model=config.generation_model,
            call_policy=call_policy,
        ),
        retrieval_top_k=config.retrieval_top_k,
        evidence_top_n=config.evidence_top_n,
        max_model_calls=config.max_model_calls,
        total_timeout_seconds=config.total_timeout_seconds,
        index_version_id=managed.manifest.version_id,
        model_ids={
            "embedding": config.embedding_model,
            "reranker": config.reranker_model,
            "generation": config.generation_model,
        },
    )


def get_index_cache_token(config: AppConfig) -> str:
    from src.index_manager import IndexManager

    return IndexManager(config.index_dir).active_version_token(config.pdf_path)
