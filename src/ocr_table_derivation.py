from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from src.ocr_artifacts import (
    OcrArtifactError,
    sha256_file,
    validate_ocr_artifact,
    write_json,
)


def derive_reviewed_tables(
    source_artifact: Path,
    review_path: Path,
    output_artifact: Path,
    *,
    source_pdf: Path,
) -> dict:
    if output_artifact.exists():
        raise OcrArtifactError(f"output already exists: {output_artifact}")
    manifest_path = source_artifact / "manifest.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    source_manifest_hash = sha256_file(manifest_path)
    if review.get("source_ocr_manifest_sha256") != source_manifest_hash:
        raise OcrArtifactError("table review source manifest SHA-256 mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if review.get("business_id") != manifest.get("business_id"):
        raise OcrArtifactError("table review business identity mismatch")

    temporary = output_artifact.with_name(f".{output_artifact.name}.building")
    if temporary.exists():
        shutil.rmtree(temporary)
    shutil.copytree(source_artifact, temporary)
    try:
        tables_by_page: dict[int, list[dict]] = {}
        for table in review.get("tables", []):
            page_number = table.get("page_number")
            if not isinstance(page_number, int):
                raise OcrArtifactError("reviewed table page_number is invalid")
            payload = {
                key: table[key]
                for key in ("table_id", "title", "bbox", "headers", "rows", "cells")
                if key in table
            }
            tables_by_page.setdefault(page_number, []).append(payload)

        for entry in manifest["pages"]:
            page_number = entry["page_number"]
            if page_number not in tables_by_page:
                continue
            page_path = temporary / entry["path"]
            record = json.loads(page_path.read_text(encoding="utf-8"))
            record["tables"] = tables_by_page[page_number]
            entry["sha256"] = write_json(page_path, record)

        manifest["artifact_type"] = "page_ocr_text_with_reviewed_tables"
        manifest["derived_from"] = {
            "source_ocr_manifest_sha256": source_manifest_hash,
            "table_review_file": review_path.name,
            "table_review_sha256": sha256_file(review_path),
        }
        write_json(temporary / "manifest.json", manifest)
        validation = validate_ocr_artifact(temporary, source_pdf=source_pdf)
        write_json(temporary / "validation.json", validation)
        output_artifact.parent.mkdir(parents=True, exist_ok=True)
        temporary.replace(output_artifact)
        return validation
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Derive immutable reviewed OCR tables")
    parser.add_argument("--source-artifact", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output-artifact", type=Path, required=True)
    parser.add_argument("--source-pdf", type=Path, required=True)
    args = parser.parse_args(argv)
    result = derive_reviewed_tables(
        args.source_artifact,
        args.review,
        args.output_artifact,
        source_pdf=args.source_pdf,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
