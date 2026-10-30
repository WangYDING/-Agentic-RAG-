from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from src.config import AppConfig, ConfigurationError
from src.presentation import configure_utf8_output


def model_marker_path(config: AppConfig) -> Path:
    identity = json.dumps(
        {
            "embedding": config.embedding_model,
            "embedding_revision": config.embedding_revision,
            "reranker": config.reranker_model,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return Path(config.model_cache_dir) / "ready" / f"{digest}.json"


def models_are_prepared(config: AppConfig) -> bool:
    path = model_marker_path(config)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return data == {
        "embedding_model": config.embedding_model,
        "embedding_revision": config.embedding_revision,
        "reranker_model": config.reranker_model,
    }


def prepare_models(config: AppConfig) -> Path:
    os.environ.setdefault("HF_HOME", str(Path(config.model_cache_dir).resolve()))
    from src.embedder import Embedder
    from src.reranker import Reranker

    Embedder(config.embedding_model, model_revision=config.embedding_revision)
    Reranker(config.reranker_model)
    marker = model_marker_path(config)
    marker.parent.mkdir(parents=True, exist_ok=True)
    temporary = marker.with_name(f".{marker.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(
            {
                "embedding_model": config.embedding_model,
                "embedding_revision": config.embedding_revision,
                "reranker_model": config.reranker_model,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    os.replace(temporary, marker)
    return marker


def main(argv: list[str] | None = None) -> int:
    configure_utf8_output()
    parser = argparse.ArgumentParser(description="Prepare or check local RAG models.")
    parser.add_argument("command", choices=["prepare", "check"])
    args = parser.parse_args(argv)
    load_dotenv()
    try:
        config = AppConfig.from_sources()
        if args.command == "prepare":
            marker = prepare_models(config)
            print(f"status: prepared\nmarker: {marker}")
            return 0
        if models_are_prepared(config):
            print("status: ready")
            return 0
        print("status: not_ready\nreason: local model marker missing or mismatched")
        return 1
    except ConfigurationError as exc:
        print(f"配置错误：{exc}")
        return 2
    except Exception as exc:
        print(f"模型准备失败：{type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
