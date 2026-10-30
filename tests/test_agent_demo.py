import agent_demo
from src.agent_workflow import AgentResponse, AgentState
from src.evidence import CitationValidation, Evidence
from src.results import ApplicationResult


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
    message = "拒答" if missing else "答案 [E1]"
    return AgentResponse(
        message,
        state,
        ApplicationResult(
            result_type="refuse" if missing else "answer",
            message=message,
            missing_requirements=tuple(missing),
        ),
    )


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


def test_error_output_is_safe_and_hides_evidence():
    state = AgentState(
        original_query="问题",
        retrieval_query="问题",
        evidences=[evidence()],
        final_action="error",
        trace=[{"step": "error", "error_code": "RATE_LIMITED"}],
    )
    result = ApplicationResult(
        result_type="error",
        message="模型服务当前限流。",
        request_id="safe-request-id",
        error_code="RATE_LIMITED",
        retryable=True,
    )

    output = agent_demo.render_response(AgentResponse(result.message, state, result))

    assert "### Service Error" in output
    assert "模型服务当前限流。" in output
    assert "request_id: safe-request-id" in output
    assert "error_code: RATE_LIMITED" in output
    assert "retryable: true" in output
    assert "### Evidence" not in output
    assert "规范证据" not in output
