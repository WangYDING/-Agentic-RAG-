from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ocr_artifacts import (
    OcrBuildRequest,
    apply_reviewed_corrections,
    build_ocr_artifact,
    repair_ocr_artifact_gaps,
    validate_ocr_artifact,
    write_json,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and validate page-level OCR artifacts")
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="Build a new immutable OCR artifact")
    build.add_argument("--spec-id", required=True)
    build.add_argument("--edition-id", required=True)
    build.add_argument("--source-pdf", type=Path, required=True)
    build.add_argument("--source-sha256", required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    build.add_argument("--render-dpi", type=int, default=300)

    validate = commands.add_parser("validate", help="Validate an existing OCR artifact")
    validate.add_argument("--artifact-dir", type=Path, required=True)
    validate.add_argument("--source-pdf", type=Path, required=True)
    validate.add_argument("--write-validation", action="store_true")

    repair = commands.add_parser(
        "repair-gaps", help="Create a new artifact using binarized gap fallback"
    )
    repair.add_argument("--input-dir", type=Path, required=True)
    repair.add_argument("--output-dir", type=Path, required=True)
    repair.add_argument("--source-pdf", type=Path, required=True)

    correct = commands.add_parser(
        "apply-corrections", help="Create a new artifact with reviewed corrections"
    )
    correct.add_argument("--input-dir", type=Path, required=True)
    correct.add_argument("--output-dir", type=Path, required=True)
    correct.add_argument("--source-pdf", type=Path, required=True)
    correct.add_argument("--corrections", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "build":
        result = build_ocr_artifact(
            OcrBuildRequest(
                spec_id=args.spec_id,
                edition_id=args.edition_id,
                source_pdf=args.source_pdf.resolve(),
                source_pdf_sha256=args.source_sha256,
                output_dir=args.output_dir.resolve(),
                render_dpi=args.render_dpi,
            )
        )
    elif args.command == "validate":
        result = validate_ocr_artifact(
            args.artifact_dir.resolve(), source_pdf=args.source_pdf.resolve()
        )
        if args.write_validation:
            write_json(args.artifact_dir.resolve() / "validation.json", result)
    elif args.command == "repair-gaps":
        result = repair_ocr_artifact_gaps(
            args.input_dir.resolve(),
            args.output_dir.resolve(),
            source_pdf=args.source_pdf.resolve(),
        )
    else:
        result = apply_reviewed_corrections(
            args.input_dir.resolve(),
            args.output_dir.resolve(),
            source_pdf=args.source_pdf.resolve(),
            corrections_path=args.corrections.resolve(),
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
