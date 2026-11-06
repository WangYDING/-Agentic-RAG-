from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

from src.application import build_multi_spec_agent_workflow
from src.config import AppConfig
from src.query_scope import QueryScope


class _RequestRecordHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.by_request: dict[str, dict] = {}

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(record, "event", None) != "request_completed":
            return
        fields = dict(getattr(record, "fields", {}))
        request_id = fields.get("request_id")
        if request_id:
            self.by_request[request_id] = fields


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run scoped real-model smoke questions")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--knowledge-base-root", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--question-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    load_dotenv()
    config = AppConfig.from_sources()
    workflow = build_multi_spec_agent_workflow(
        config,
        knowledge_base_root=args.knowledge_base_root,
        catalog_path=args.catalog,
        expected_snapshot_id=args.snapshot_id,
    )
    rows = {
        row["id"]: row
        for row in (
            json.loads(line)
            for line in args.dataset.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    handler = _RequestRecordHandler()
    request_logger = logging.getLogger("rag.request")
    previous_level = request_logger.level
    request_logger.setLevel(logging.INFO)
    request_logger.addHandler(handler)
    results = []
    try:
        for question_id in args.question_id:
            row = rows[question_id]
            scope = QueryScope.from_request_payload(row["requested_scope"])
            response = workflow.run(row["question"], scope=scope)
            results.append(
                {
                    "id": question_id,
                    "question": row["question"],
                    "requested_scope": row["requested_scope"],
                    "request_id": response.request_id,
                    "result_type": response.result_type,
                    "answer": response.answer,
                    "snapshot_id": response.state.index_version_id,
                    "bound_scope": list(response.state.query_scope),
                    "retry_count": response.state.retry_count,
                    "evidence": [item.to_dict() for item in response.state.evidences],
                    "request_metrics": handler.by_request.get(response.request_id),
                }
            )
    finally:
        request_logger.removeHandler(handler)
        request_logger.setLevel(previous_level)

    payload = {
        "run_type": "phase1_scoped_real_agent_evaluation",
        "snapshot_id": args.snapshot_id,
        "generation_model": config.generation_model,
        "questions": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "count": len(results),
                "outcomes": [item["result_type"] for item in results],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
