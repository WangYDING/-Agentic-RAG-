from types import SimpleNamespace

import pytest

from src.reliability import (
    CallBudget,
    CallPolicy,
    ReliabilityError,
    execute_model_call,
)


class RateLimitError(Exception):
    status_code = 429


class AuthenticationError(Exception):
    status_code = 401


def test_transient_timeout_retries_once_then_succeeds():
    calls = []

    def call(timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise TimeoutError("private upstream detail")
        return "ok"

    result = execute_model_call(
        call,
        operation="测试",
        budget=CallBudget(max_calls=3),
        policy=CallPolicy(request_timeout_seconds=5, max_network_retries=1),
    )

    assert result == "ok"
    assert len(calls) == 2


def test_rate_limit_stops_after_bounded_retry():
    calls = []

    with pytest.raises(ReliabilityError) as error:
        execute_model_call(
            lambda timeout: calls.append(timeout) or (_ for _ in ()).throw(RateLimitError()),
            operation="测试",
            budget=CallBudget(max_calls=3),
            policy=CallPolicy(max_network_retries=1),
        )

    assert error.value.code == "RATE_LIMITED"
    assert error.value.retryable is True
    assert len(calls) == 2


def test_authentication_failure_is_not_retried():
    calls = []

    with pytest.raises(ReliabilityError) as error:
        execute_model_call(
            lambda timeout: calls.append(timeout) or (_ for _ in ()).throw(AuthenticationError()),
            operation="测试",
            budget=CallBudget(max_calls=3),
            policy=CallPolicy(max_network_retries=1),
        )

    assert error.value.code == "AUTHENTICATION_FAILED"
    assert error.value.retryable is False
    assert len(calls) == 1


def test_total_call_budget_prevents_another_call():
    budget = CallBudget(max_calls=1)
    assert execute_model_call(
        lambda timeout: SimpleNamespace(value="first"),
        operation="测试",
        budget=budget,
        policy=CallPolicy(max_network_retries=0),
    ).value == "first"

    with pytest.raises(ReliabilityError) as error:
        execute_model_call(
            lambda timeout: "never",
            operation="测试",
            budget=budget,
            policy=CallPolicy(max_network_retries=0),
        )

    assert error.value.code == "CALL_BUDGET_EXHAUSTED"
