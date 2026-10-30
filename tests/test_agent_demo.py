from types import SimpleNamespace

import pytest

import agent_demo
from src.agent_workflow import AgentResponse, AgentState, AgentWorkflow
from src.evidence import CitationValidation, Evidence


def evidence():
    return Evidence(
        evidence_id="E1",
        text="规范证据",
        source="城市轨道交通工程设计标准.pdf",
        page_start=169,
        page_end=169,
        chunk_id=1,
        article_id="19.1.8",
    )


def response(*, action="answer", missing=None):
    missing = missing or []
    state = AgentState(
        original_query="问题",
        retrieval_query="问题",
        retry_count=1 if missing else 0,
        evidences=[evidence()],
        sufficiency_decision="insufficient" if missing else "sufficient",
        missing_requirements=missing,
        final_action=action,
        citation_validation=CitationValidation(True, ["E1"], ["E1"], []),
        trace=[
            {"step": "retrieve", "private_reasoning": "must not appear"},
            {"step": "grade", "decision": "insufficient" if missing else "sufficient", "reason": "hidden"},
            *([{"step": "retry", "missing_requirements": missing}, {"step": "refuse"}] if missing else [{"step": "answer"}, {"step": "citation_validation", "valid": True}]),
        ],
    )
    return AgentResponse("拒答" if missing else "答案 [E1]", state)


def test_demo_builds_existing_agent_workflow(monkeypatch):
    sentinel = SimpleNamespace(vector_store=SimpleNamespace(chunk_records=[]))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "model")
    factories = SimpleNamespace(
        Embedder=lambda: object(),
        IndexManager=lambda index_dir: SimpleNamespace(
            build_or_load=lambda pdf, embedder: sentinel
        ),
        Retriever=lambda store, embedder: object(),
        BM25Retriever=lambda records: object(),
        HybridRetriever=lambda dense, bm25: object(),
        Reranker=lambda: object(),
        EvidenceSufficiencyGrader=lambda: object(),
        Generator=lambda: object(),
        QueryRewriter=lambda: object(),
    )
    monkeypatch.setattr(
        agent_demo, "_load_workflow_component_factories", lambda: factories
    )

    workflow = agent_demo.build_agent_workflow()

    assert isinstance(workflow, AgentWorkflow)
    assert workflow.max_retries == 1


def test_sufficient_output_contains_answer_evidence_and_trace():
    output = agent_demo.render_response(response())

    assert "### Final Answer" in output
    assert "答案 [E1]" in output
    assert "[E1] 城市轨道交通工程设计标准.pdf - p.169 - 第19.1.8条" in output
    assert "[E1] [E1]" not in output
    assert "grade: sufficient" in output
    assert "generate" in output
    assert "citation_validate: true" in output
    assert "final_action: answer" in output


def test_refusal_output_contains_missing_requirements():
    output = agent_demo.render_response(
        response(action="refuse", missing=["项目实际运营数据"])
    )

    assert "拒答" in output
    assert "retry" in output
    assert "refuse" in output
    assert "retry_count: 1" in output
    assert "- 项目实际运营数据" in output


def test_trace_does_not_expose_reasoning_fields():
    output = agent_demo.render_response(response())

    assert "must not appear" not in output
    assert "hidden" not in output
    assert "private_reasoning" not in output


@pytest.mark.parametrize("missing", agent_demo.REQUIRED_ENV_VARS)
def test_missing_environment_has_clear_error(missing):
    environ = {name: "value" for name in agent_demo.REQUIRED_ENV_VARS}
    environ[missing] = ""

    with pytest.raises(agent_demo.DemoConfigurationError, match=missing):
        agent_demo.validate_environment(environ)
