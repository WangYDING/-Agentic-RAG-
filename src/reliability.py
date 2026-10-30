from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class CallPolicy:
    request_timeout_seconds: float = 30.0
    max_network_retries: int = 1


@dataclass
class CallBudget:
    max_calls: int = 6
    total_timeout_seconds: float = 90.0
    started_at: float = field(default_factory=time.monotonic)
    calls_used: int = 0
    network_retries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float | None = None
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None

    def consume(self) -> None:
        if self.calls_used >= self.max_calls:
            raise ReliabilityError(
                "CALL_BUDGET_EXHAUSTED",
                "请求调用次数已达到上限。",
                retryable=True,
            )
        if self.remaining_seconds() <= 0:
            raise ReliabilityError(
                "TOTAL_TIMEOUT_EXCEEDED",
                "请求处理已超过总时限。",
                retryable=True,
            )
        self.calls_used += 1

    def remaining_seconds(self) -> float:
        elapsed = time.monotonic() - self.started_at
        return max(0.0, self.total_timeout_seconds - elapsed)

    def record_usage(self, response) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        self.input_tokens += int(
            getattr(usage, "prompt_tokens", getattr(usage, "input_tokens", 0)) or 0
        )
        self.output_tokens += int(
            getattr(usage, "completion_tokens", getattr(usage, "output_tokens", 0)) or 0
        )
        if (
            self.input_cost_per_million is not None
            and self.output_cost_per_million is not None
        ):
            self.estimated_cost = round(
                self.input_tokens * self.input_cost_per_million / 1_000_000
                + self.output_tokens * self.output_cost_per_million / 1_000_000,
                8,
            )


class ReliabilityError(RuntimeError):
    def __init__(self, code: str, public_message: str, *, retryable: bool):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.retryable = retryable


class InvalidModelResponseError(ReliabilityError):
    def __init__(self, detail: str = ""):
        super().__init__(
            "INVALID_MODEL_RESPONSE",
            "模型服务返回了无法解析的响应。",
            retryable=False,
        )
        self.detail = detail


def execute_model_call(
    call: Callable[[float], T],
    *,
    operation: str,
    budget: CallBudget,
    policy: CallPolicy,
) -> T:
    """Execute one SDK call with one centrally controlled retry layer."""

    for attempt in range(policy.max_network_retries + 1):
        budget.consume()
        timeout = min(policy.request_timeout_seconds, budget.remaining_seconds())
        try:
            return call(timeout)
        except ReliabilityError:
            raise
        except Exception as exc:
            error = classify_service_error(exc, operation=operation)
            if not error.retryable or attempt >= policy.max_network_retries:
                raise error from exc
            budget.network_retries += 1
    raise AssertionError("unreachable")


def classify_service_error(exc: Exception, *, operation: str) -> ReliabilityError:
    name = type(exc).__name__.lower()
    status = getattr(exc, "status_code", None)
    prefix = f"{operation}服务"
    if isinstance(exc, TimeoutError) or "timeout" in name:
        return ReliabilityError(
            "MODEL_TIMEOUT", f"{prefix}调用超时。", retryable=True
        )
    if status == 429 or "ratelimit" in name or "rate_limit" in name:
        return ReliabilityError(
            "RATE_LIMITED", f"{prefix}当前限流。", retryable=True
        )
    if status in {401, 403} or "authentication" in name or "permission" in name:
        return ReliabilityError(
            "AUTHENTICATION_FAILED",
            f"{prefix}认证失败，请检查服务配置。",
            retryable=False,
        )
    if isinstance(status, int) and status >= 500:
        return ReliabilityError(
            "UPSTREAM_SERVER_ERROR", f"{prefix}暂时不可用。", retryable=True
        )
    if "connection" in name:
        return ReliabilityError(
            "CONNECTION_FAILED", f"{prefix}连接失败。", retryable=True
        )
    return ReliabilityError(
        "MODEL_SERVICE_ERROR", f"{prefix}调用失败。", retryable=False
    )
