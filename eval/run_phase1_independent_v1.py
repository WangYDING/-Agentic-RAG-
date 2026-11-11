from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

from src.application import build_multi_spec_agent_workflow
from src.config import AppConfig
from src.query_scope import QueryScope


class _RequestRecords(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.by_request: dict[str, dict] = {}

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(record, "event", None) == "request_completed":
            fields = dict(getattr(record, "fields", {}))
            if request_id := fields.get("request_id"):
                self.by_request[request_id] = fields


class _RecordingScopedRetriever:
    def __init__(self, inner, sink: list[dict]) -> None:
        self.inner = inner
        self.sink = sink
        self.scope = inner.scope

    def retrieve(self, query: str, top_k: int = 10):
        results = self.inner.retrieve(query, top_k=top_k)
        self.sink.append(
            {
                "query": query,
                "top_k": top_k,
                "trace": self.inner.calls[-1],
                "candidates": results,
            }
        )
        return results

    def expand_neighbors(self, results):
        return self.inner.expand_neighbors(results)


class _RecordingRetrieverFacade:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.snapshot_id = inner.snapshot_id
        self.current_calls: list[dict] = []

    def for_scope(self, scope):
        return _RecordingScopedRetriever(self.inner.for_scope(scope), self.current_calls)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the frozen Phase 1 independent acceptance once")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--knowledge-base-root", default=".rag_knowledge_base")
    parser.add_argument("--catalog", default="data/spec_catalog.v1.json")
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite independent result: {args.output}")

    load_dotenv()
    config = AppConfig.from_sources()
    workflow = build_multi_spec_agent_workflow(
        config,
        knowledge_base_root=args.knowledge_base_root,
        catalog_path=args.catalog,
        expected_snapshot_id=args.snapshot_id,
    )
    recorder = _RecordingRetrieverFacade(workflow.retriever)
    workflow.retriever = recorder
    rows = [
        json.loads(line)
        for line in args.dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    handler = _RequestRecords()
    request_logger = logging.getLogger("rag.request")
    old_level = request_logger.level
    request_logger.setLevel(logging.INFO)
    request_logger.addHandler(handler)
    results = []
    try:
        for row in rows:
            recorder.current_calls = []
            scope = QueryScope.from_request_payload(row["requested_scope"])
            response = workflow.run(row["question"], scope=scope)
            results.append(
                {
                    "id": row["id"],
                    "question": row["question"],
                    "requested_scope": row["requested_scope"],
                    "request_id": response.request_id,
                    "result_type": response.result_type,
                    "answer": response.answer,
                    "snapshot_id": response.state.index_version_id,
                    "bound_scope": list(response.state.query_scope),
                    "retrieval_calls": recorder.current_calls,
                    "final_evidence": [item.to_dict() for item in response.state.evidences],
                    "retry_count": response.state.retry_count,
                    "trace": response.state.trace,
                    "request_metrics": handler.by_request.get(response.request_id),
                }
            )
            print(row["id"], response.result_type, response.request_id, flush=True)
    finally:
        request_logger.removeHandler(handler)
        request_logger.setLevel(old_level)

    payload = {
        "run_type": "phase1_cross_spec_independent_acceptance_v1",
        "dataset": str(args.dataset),
        "snapshot_id": args.snapshot_id,
        "models": {
            "embedding": config.embedding_model,
            "embedding_revision": config.embedding_revision,
            "reranker": config.reranker_model,
            "generation": config.generation_model,
        },
        "parameters": {
            "retrieval_top_k": config.retrieval_top_k,
            "evidence_top_n": config.evidence_top_n,
            "request_timeout_seconds": config.request_timeout_seconds,
            "max_network_retries": config.max_network_retries,
            "total_timeout_seconds": config.total_timeout_seconds,
            "max_model_calls": config.max_model_calls,
        },
        "questions": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"count": len(results), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
