from __future__ import annotations

import json
import logging
import sys
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Iterator


def application_version() -> str:
    try:
        return version("engineering-spec-rag")
    except PackageNotFoundError:
        return "development"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": getattr(record, "event", "application_log"),
            "message": record.getMessage(),
        }
        fields = getattr(record, "fields", {})
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_json_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers[:] = [handler]
    root.setLevel(level)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    logger.info(event, extra={"event": event, "fields": fields})


class MetricsRegistry:
    def __init__(self, sample_limit: int = 1000):
        self._lock = threading.Lock()
        self._counters: defaultdict[str, int] = defaultdict(int)
        self._durations: defaultdict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=sample_limit)
        )

    def increment(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def observe_ms(self, name: str, value: float) -> None:
        with self._lock:
            self._durations[name].append(float(value))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = dict(self._counters)
            durations = {
                name: {
                    "samples": len(values),
                    "p50_ms": _percentile(values, 0.50),
                    "p95_ms": _percentile(values, 0.95),
                }
                for name, values in self._durations.items()
            }
        total = counters.get("requests_total", 0)
        outcomes = {
            outcome: counters.get(f"requests_{outcome}", 0)
            for outcome in ("answer", "refuse", "error")
        }
        rates = {
            key: (round(value / total, 4) if total else 0.0)
            for key, value in outcomes.items()
        }
        return {"counters": counters, "outcomes": outcomes, "rates": rates, "durations": durations}

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._durations.clear()


def _percentile(values: deque[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = round((len(ordered) - 1) * fraction)
    return round(ordered[position], 3)


metrics = MetricsRegistry()


@dataclass
class RequestObserver:
    request_id: str
    index_version_id: str | None
    model_ids: dict[str, str]
    started_at: float = field(default_factory=time.monotonic)
    stage_timings_ms: defaultdict[str, float] = field(
        default_factory=lambda: defaultdict(float)
    )

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started = time.monotonic()
        try:
            yield
        finally:
            duration = (time.monotonic() - started) * 1000
            self.stage_timings_ms[name] += duration
            metrics.observe_ms(f"stage_{name}", duration)

    def finish(self, response, budget) -> None:
        total_ms = (time.monotonic() - self.started_at) * 1000
        outcome = response.result_type
        metrics.increment("requests_total")
        metrics.increment(f"requests_{outcome}")
        metrics.increment("model_calls_total", budget.calls_used)
        metrics.increment("model_retries_total", budget.network_retries)
        metrics.increment("retrieval_retries_total", response.state.retry_count)
        metrics.increment("input_tokens_total", budget.input_tokens)
        metrics.increment("output_tokens_total", budget.output_tokens)
        metrics.observe_ms("request_total", total_ms)
        log_event(
            logging.getLogger("rag.request"),
            "request_completed",
            request_id=self.request_id,
            app_version=application_version(),
            index_version=self.index_version_id,
            models=self.model_ids,
            stage_timings_ms={
                key: round(value, 3) for key, value in self.stage_timings_ms.items()
            },
            total_ms=round(total_ms, 3),
            outcome=outcome,
            error_code=response.error_code,
            retryable=response.retryable,
            retrieval_retries=response.state.retry_count,
            model_calls=budget.calls_used,
            model_retries=budget.network_retries,
            token_usage={
                "input": budget.input_tokens,
                "output": budget.output_tokens,
                "total": budget.input_tokens + budget.output_tokens,
            },
            estimated_cost=budget.estimated_cost,
        )
