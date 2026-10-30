from __future__ import annotations

import argparse
from types import SimpleNamespace

from dotenv import load_dotenv

from src.config import AppConfig, ConfigurationError
from src.index_manager import (
    IndexBuildInProgressError,
    IndexCorruptionError,
    IndexManager,
    IndexUnavailableError,
)
from src.presentation import configure_utf8_output


def main(argv: list[str] | None = None) -> int:
    configure_utf8_output()
    parser = argparse.ArgumentParser(description="Build and verify published RAG indexes.")
    parser.add_argument("command", choices=["build", "rebuild", "check"])
    parser.add_argument("--pdf", help="覆盖 RAG_PDF_PATH")
    parser.add_argument("--index-dir", help="覆盖 RAG_INDEX_DIR")
    parser.add_argument("--chunk-size", type=int, default=300)
    parser.add_argument("--overlap", type=int, default=50)
    args = parser.parse_args(argv)
    load_dotenv()
    try:
        config = AppConfig.from_sources(pdf_path=args.pdf, index_dir=args.index_dir)
        if args.command == "check":
            embedder = SimpleNamespace(
                model_name=config.embedding_model,
                model_revision=config.embedding_revision,
            )
        else:
            from src.embedder import Embedder

            embedder = Embedder(
                config.embedding_model,
                model_revision=config.embedding_revision,
            )
        manager = IndexManager(
            config.index_dir,
            lock_timeout_seconds=config.index_lock_timeout_seconds,
        )
        kwargs = {
            "embedder": embedder,
            "chunk_size": args.chunk_size,
            "overlap": args.overlap,
        }
        if args.command == "check":
            manifest = manager.check(config.pdf_path, **kwargs)
            action = "valid"
        else:
            result = manager.build_or_load(
                config.pdf_path,
                force_rebuild=args.command == "rebuild",
                **kwargs,
            )
            manifest = result.manifest
            action = result.action
        print(f"status: {action}")
        print(f"document_id: {manifest.document_id}")
        print(f"version_id: {manifest.version_id}")
        print(f"chunks: {manifest.chunk_count}")
        return 0
    except ConfigurationError as exc:
        print(f"配置错误：{exc}")
        return 2
    except IndexBuildInProgressError as exc:
        print(f"索引构建忙：{exc}")
        return 3
    except (IndexCorruptionError, IndexUnavailableError) as exc:
        print(f"索引不可用：{exc}")
        return 4
    except (FileNotFoundError, ValueError) as exc:
        print(f"索引操作失败：{exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
