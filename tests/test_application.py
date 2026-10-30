from types import SimpleNamespace

from src.agent_workflow import AgentWorkflow
from src.application import build_agent_workflow
from src.config import AppConfig


def test_application_factory_assembles_workflow_from_configured_components():
    calls = {}
    sentinel = SimpleNamespace(
        vector_store=SimpleNamespace(chunk_records=[{"text": "chunk"}])
    )

    class FakeIndexManager:
        def __init__(self, index_dir):
            calls["index_dir"] = index_dir

        def build_or_load(self, pdf_path, embedder):
            calls["pdf_path"] = pdf_path
            calls["index_embedder"] = embedder
            return sentinel

    def remember(name):
        def factory(*args, **kwargs):
            value = SimpleNamespace(name=name)
            calls[name] = {"args": args, "kwargs": kwargs, "value": value}
            return value

        return factory

    factories = SimpleNamespace(
        Embedder=remember("embedder"),
        IndexManager=FakeIndexManager,
        Retriever=remember("dense"),
        BM25Retriever=remember("bm25"),
        HybridRetriever=remember("hybrid"),
        Reranker=remember("reranker"),
        EvidenceSufficiencyGrader=remember("grader"),
        Generator=remember("generator"),
        QueryRewriter=remember("rewriter"),
    )
    config = AppConfig.from_sources(
        environ={},
        pdf_path="spec.pdf",
        index_dir="index-dir",
        embedding_model="embedding-model",
        reranker_model="reranker-model",
        generation_model="generation-model",
        api_base_url="https://api.test",
        api_key="secret",
        retrieval_top_k=14,
        evidence_top_n=4,
    )

    workflow = build_agent_workflow(config, factories=factories)

    assert isinstance(workflow, AgentWorkflow)
    assert workflow.max_retries == 1
    assert workflow.retrieval_top_k == 14
    assert workflow.evidence_top_n == 4
    assert calls["embedder"]["args"] == ("embedding-model",)
    assert calls["index_dir"] == "index-dir"
    assert calls["pdf_path"] == "spec.pdf"
    assert calls["reranker"]["args"] == ("reranker-model",)
    assert calls["grader"]["kwargs"]["model"] == "generation-model"
    assert calls["generator"]["kwargs"]["api_key"] == "secret"
    assert calls["rewriter"]["kwargs"]["base_url"] == "https://api.test"
