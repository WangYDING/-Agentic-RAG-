import json
import logging
from types import SimpleNamespace

from src.observability import JsonFormatter, RequestObserver, metrics
from src.reliability import CallBudget


def test_request_observer_records_safe_summary_without_prompt_or_request_id_label(caplog):
    metrics.reset()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("rag.request")
    logger.handlers[:] = [handler]
    logger.propagate = True
    logger.setLevel(logging.INFO)
    observer = RequestObserver("req-1", "index-v1", {"generation": "model-v1"})
    with observer.stage("retrieval"):
        pass
    response = SimpleNamespace(
        result_type="answer",
        error_code=None,
        retryable=False,
        state=SimpleNamespace(retry_count=0),
    )
    budget = CallBudget()
    budget.calls_used = 2
    budget.input_tokens = 12
    budget.output_tokens = 5

    with caplog.at_level(logging.INFO, logger="rag.request"):
        observer.finish(response, budget)

    snapshot = metrics.snapshot()
    assert snapshot["counters"]["requests_total"] == 1
    assert snapshot["outcomes"]["answer"] == 1
    assert "request_id" not in snapshot["counters"]
    record = next(record for record in caplog.records if record.getMessage() == "request_completed")
    encoded = JsonFormatter().format(record)
    payload = json.loads(encoded)
    assert payload["request_id"] == "req-1"
    assert payload["token_usage"] == {"input": 12, "output": 5, "total": 17}
    assert "question" not in payload
    assert "evidence" not in payload


def test_metrics_keep_refusal_and_error_separate():
    metrics.reset()
    for outcome in ("refuse", "error"):
        observer = RequestObserver(f"req-{outcome}", None, {})
        response = SimpleNamespace(
            result_type=outcome,
            error_code="X" if outcome == "error" else None,
            retryable=False,
            state=SimpleNamespace(retry_count=1),
        )
        observer.finish(response, CallBudget())

    snapshot = metrics.snapshot()
    assert snapshot["outcomes"] == {"answer": 0, "refuse": 1, "error": 1}
    assert snapshot["rates"] == {"answer": 0.0, "refuse": 0.5, "error": 0.5}
