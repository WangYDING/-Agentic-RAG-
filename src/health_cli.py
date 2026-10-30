from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from types import SimpleNamespace

from dotenv import load_dotenv

from src.config import AppConfig, ConfigurationError
from src.index_manager import IndexManager
from src.model_cli import models_are_prepared
from src.presentation import configure_utf8_output


def check_liveness(url: str, timeout: float = 3.0) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if 200 <= response.status < 300:
                return {"status": "alive", "url": url}
            return {"status": "dead", "reason": f"http_{response.status}"}
    except (OSError, urllib.error.URLError) as exc:
        return {"status": "dead", "reason": type(exc).__name__}


def check_readiness(config: AppConfig) -> dict:
    checks = {"configuration": False, "models": False, "index": False}
    try:
        config.validate_for_agent()
        checks["configuration"] = True
        checks["models"] = models_are_prepared(config)
        embedder = SimpleNamespace(
            model_name=config.embedding_model,
            model_revision=config.embedding_revision,
        )
        manifest = IndexManager(
            config.index_dir,
            lock_timeout_seconds=config.index_lock_timeout_seconds,
        ).check(config.pdf_path, embedder=embedder)
        checks["index"] = True
        return {
            "status": "ready" if all(checks.values()) else "not_ready",
            "checks": checks,
            "index_version": manifest.version_id,
        }
    except ConfigurationError as exc:
        return {"status": "not_ready", "checks": checks, "reason": str(exc)}
    except Exception as exc:
        return {
            "status": "not_ready",
            "checks": checks,
            "reason": type(exc).__name__,
        }


def main(argv: list[str] | None = None) -> int:
    configure_utf8_output()
    parser = argparse.ArgumentParser(description="Check RAG liveness or business readiness.")
    parser.add_argument("command", choices=["live", "ready"])
    parser.add_argument(
        "--url", default="http://127.0.0.1:8501/_stcore/health"
    )
    args = parser.parse_args(argv)
    load_dotenv()
    if args.command == "live":
        result = check_liveness(args.url)
        success = result["status"] == "alive"
    else:
        try:
            result = check_readiness(AppConfig.from_sources())
        except ConfigurationError as exc:
            result = {"status": "not_ready", "reason": str(exc)}
        success = result["status"] == "ready"
    print(json.dumps(result, ensure_ascii=False))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
