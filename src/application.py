from __future__ import annotations

from types import SimpleNamespace

from src.agent_workflow import AgentWorkflow
from src.config import AppConfig


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

    embedder = factories.Embedder(config.embedding_model)
    managed = factories.IndexManager(config.index_dir).build_or_load(
        config.pdf_path,
        embedder=embedder,
    )
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
        ),
        generator=factories.Generator(
            api_key=config.api_key,
            base_url=config.api_base_url,
            model=config.generation_model,
        ),
        rewriter=factories.QueryRewriter(
            api_key=config.api_key,
            base_url=config.api_base_url,
            model=config.generation_model,
        ),
        retrieval_top_k=config.retrieval_top_k,
        evidence_top_n=config.evidence_top_n,
    )
