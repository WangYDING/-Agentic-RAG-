from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

import fitz
from PIL import Image


OCR_SCHEMA_VERSION = 1
DEFAULT_RENDER_DPI = 300
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CLAUSE_PATTERN = re.compile(
    r"(?<!\d)(\d{1,2}\s*\.\s*\d{1,2}\s*\.\s*\d{1,3})(?!\d)"
)
_MODEL_NAMES = (
    "PP-OCRv6_det_medium.onnx",
    "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
    "PP-OCRv6_rec_medium.onnx",
)


class OcrArtifactError(ValueError):
    """Raised when an OCR artifact cannot be built or trusted."""


@dataclass(frozen=True)
class OcrBuildRequest:
    spec_id: str
    edition_id: str
    source_pdf: Path
    source_pdf_sha256: str
    output_dir: Path
    render_dpi: int = DEFAULT_RENDER_DPI

    @property
    def business_id(self) -> str:
        return f"{self.spec_id}@{self.edition_id}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def write_json(path: Path, payload: Any) -> str:
    data = canonical_json_bytes(payload)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def build_ocr_artifact(request: OcrBuildRequest) -> dict[str, Any]:
    _validate_request(request)
    if request.output_dir.exists():
        raise OcrArtifactError(f"output already exists: {request.output_dir}")

    try:
        from rapidocr import ModelType, RapidOCR
        import onnxruntime
    except ImportError as exc:
        raise OcrArtifactError(
            "OCR dependencies are missing; install the locked 'ocr' extra"
        ) from exc

    engine = RapidOCR(
        params={
            "Det.model_type": ModelType.MEDIUM,
            "Rec.model_type": ModelType.MEDIUM,
        }
    )
    tool = {
        "name": "RapidOCR",
        "version": version("rapidocr"),
        "engine": "onnxruntime",
        "engine_version": onnxruntime.__version__,
        "render_library": "PyMuPDF",
        "render_library_version": fitz.version[0],
        "render_dpi": request.render_dpi,
        "models": _model_identities(),
        "parameters": {
            "detector": "PP-OCRv6 medium",
            "classifier": "default",
            "recognizer": "PP-OCRv6 medium",
            "reading_order": "RapidOCR output order",
        },
    }

    temporary = request.output_dir.with_name(
        f".{request.output_dir.name}.building-{uuid.uuid4().hex}"
    )
    pages_dir = temporary / "pages"
    pages_dir.mkdir(parents=True)
    page_entries: list[dict[str, Any]] = []
    try:
        with fitz.open(request.source_pdf) as document:
            page_count = document.page_count
            scale = request.render_dpi / 72
            matrix = fitz.Matrix(scale, scale)
            for index, pdf_page in enumerate(document, start=1):
                image = pdf_page.get_pixmap(matrix=matrix, alpha=False).tobytes("png")
                result = engine(image)
                record = _page_record(request, index, request.render_dpi, result)
                relative_path = Path("pages") / f"{index:04d}.json"
                digest = write_json(temporary / relative_path, record)
                page_entries.append(
                    {
                        "page_number": index,
                        "path": relative_path.as_posix(),
                        "sha256": digest,
                        "character_count": len(record["text"]),
                        "line_count": len(record["lines"]),
                        "render_dpi": request.render_dpi,
                    }
                )

            initial_clauses = _clauses_from_page_files(temporary, page_entries)
            initial_gaps = _clause_sequence_gaps(initial_clauses)
            fallback_dpi = max(400, request.render_dpi + 100)
            fallback_pages = _fallback_pages(initial_clauses, initial_gaps)
            recovered_clauses: dict[str, int] = {}
            fallback_matrix = fitz.Matrix(fallback_dpi / 72, fallback_dpi / 72)
            for page_number in fallback_pages:
                image = document[page_number - 1].get_pixmap(
                    matrix=fallback_matrix, alpha=False
                ).tobytes("png")
                result = engine(image)
                record = _page_record(request, page_number, fallback_dpi, result)
                recovered = [gap for gap in initial_gaps if gap in record["text"]]
                if not recovered:
                    continue
                relative_path = Path("pages") / f"{page_number:04d}.json"
                digest = write_json(temporary / relative_path, record)
                entry = page_entries[page_number - 1]
                entry.update(
                    {
                        "sha256": digest,
                        "character_count": len(record["text"]),
                        "line_count": len(record["lines"]),
                        "render_dpi": fallback_dpi,
                    }
                )
                for clause in recovered:
                    recovered_clauses[clause] = page_number

            clauses_after_fallback = _clauses_from_page_files(temporary, page_entries)
            gaps_after_fallback = _clause_sequence_gaps(clauses_after_fallback)
            binarized_pages, binarized_recovered = _run_binarized_fallback(
                document,
                engine,
                request,
                temporary,
                page_entries,
                clauses_after_fallback,
                gaps_after_fallback,
                render_dpi=fallback_dpi,
            )

        manifest = {
            "schema_version": OCR_SCHEMA_VERSION,
            "artifact_type": "page_ocr_text",
            "spec_id": request.spec_id,
            "edition_id": request.edition_id,
            "business_id": request.business_id,
            "source_pdf": {
                "file_name": request.source_pdf.name,
                "sha256": request.source_pdf_sha256,
                "page_count": page_count,
            },
            "ocr_tool": tool,
            "fallback_pass": {
                "trigger": "detected clause sequence gap",
                "render_dpi": fallback_dpi,
                "candidate_pages": fallback_pages,
                "recovered_clauses": recovered_clauses,
            },
            "binarized_fallback_pass": {
                "trigger": "clause gap remaining after higher-DPI pass",
                "render_dpi": fallback_dpi,
                "grayscale_threshold": 150,
                "candidate_pages": binarized_pages,
                "recovered_clauses": binarized_recovered,
            },
            "pages": page_entries,
        }
        write_json(temporary / "manifest.json", manifest)
        validation = validate_ocr_artifact(temporary, source_pdf=request.source_pdf)
        write_json(temporary / "validation.json", validation)
        request.output_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, request.output_dir)
        return validation
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def validate_ocr_artifact(
    artifact_dir: Path,
    *,
    source_pdf: Path | None = None,
    max_blank_page_ratio: float = 0.10,
    max_replacement_character_ratio: float = 0.001,
) -> dict[str, Any]:
    manifest_path = artifact_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OcrArtifactError(f"cannot read OCR manifest: {exc}") from exc
    if manifest.get("schema_version") != OCR_SCHEMA_VERSION:
        raise OcrArtifactError("unsupported OCR schema_version")
    source = manifest.get("source_pdf")
    pages = manifest.get("pages")
    if not isinstance(source, dict) or not isinstance(pages, list) or not pages:
        raise OcrArtifactError("OCR manifest source_pdf/pages are invalid")
    expected_count = source.get("page_count")
    if expected_count != len(pages):
        raise OcrArtifactError("OCR page count does not match manifest")
    if source_pdf is not None:
        actual_source_hash = sha256_file(source_pdf)
        if actual_source_hash != source.get("sha256"):
            raise OcrArtifactError("source PDF SHA-256 mismatch")
        with fitz.open(source_pdf) as document:
            if document.page_count != expected_count:
                raise OcrArtifactError("source PDF page count mismatch")

    blank_pages: list[int] = []
    clauses: dict[str, list[int]] = {}
    replacement_count = 0
    total_characters = 0
    superscript_pages: list[int] = []
    for expected_page, entry in enumerate(pages, start=1):
        if entry.get("page_number") != expected_page:
            raise OcrArtifactError("OCR page numbers are not contiguous")
        path = artifact_dir / str(entry.get("path"))
        if not path.is_file() or sha256_file(path) != entry.get("sha256"):
            raise OcrArtifactError(f"OCR page artifact mismatch: {expected_page}")
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("page_number") != expected_page:
            raise OcrArtifactError(f"OCR page record mismatch: {expected_page}")
        text = record.get("text")
        if not isinstance(text, str):
            raise OcrArtifactError(f"OCR text is invalid: {expected_page}")
        if not text.strip():
            blank_pages.append(expected_page)
        total_characters += len(text)
        replacement_count += text.count("�")
        if re.search(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]", text):
            superscript_pages.append(expected_page)
        for clause in _extract_clauses(text):
            clauses.setdefault(clause, []).append(expected_page)

    blank_ratio = len(blank_pages) / expected_count
    replacement_ratio = replacement_count / max(total_characters, 1)
    clause_sequence_gaps = _clause_sequence_gaps(clauses)
    return {
        "schema_version": OCR_SCHEMA_VERSION,
        "business_id": manifest.get("business_id"),
        "source_pdf_sha256": source.get("sha256"),
        "page_count": expected_count,
        "page_sequence_valid": True,
        "page_hashes_valid": True,
        "blank_pages": blank_pages,
        "blank_page_ratio": blank_ratio,
        "replacement_character_count": replacement_count,
        "replacement_character_ratio": replacement_ratio,
        "detected_clause_count": len(clauses),
        "detected_clauses": clauses,
        "clause_sequence_gaps": clause_sequence_gaps,
        "superscript_pages": superscript_pages,
        "automatic_checks_passed": (
            blank_ratio <= max_blank_page_ratio
            and replacement_ratio <= max_replacement_character_ratio
            and not clause_sequence_gaps
        ),
        "manual_review_status": "pending",
    }


def repair_ocr_artifact_gaps(
    input_dir: Path, output_dir: Path, *, source_pdf: Path
) -> dict[str, Any]:
    """Create a new artifact by applying the auditable binarized gap fallback."""
    validation = validate_ocr_artifact(input_dir, source_pdf=source_pdf)
    if output_dir.exists():
        raise OcrArtifactError(f"output already exists: {output_dir}")
    manifest = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    source = manifest["source_pdf"]
    source.pop("path", None)
    source["file_name"] = source_pdf.name
    request = OcrBuildRequest(
        spec_id=manifest["spec_id"],
        edition_id=manifest["edition_id"],
        source_pdf=source_pdf,
        source_pdf_sha256=source["sha256"],
        output_dir=output_dir,
        render_dpi=int(manifest["ocr_tool"]["render_dpi"]),
    )
    _validate_request(request)
    try:
        from rapidocr import ModelType, RapidOCR
    except ImportError as exc:
        raise OcrArtifactError(
            "OCR dependencies are missing; install the locked 'ocr' extra"
        ) from exc
    engine = RapidOCR(
        params={
            "Det.model_type": ModelType.MEDIUM,
            "Rec.model_type": ModelType.MEDIUM,
        }
    )
    temporary = output_dir.with_name(f".{output_dir.name}.building-{uuid.uuid4().hex}")
    try:
        shutil.copytree(input_dir, temporary)
        page_entries = manifest["pages"]
        clauses = validation["detected_clauses"]
        gaps = validation["clause_sequence_gaps"]
        render_dpi = max(400, request.render_dpi + 100)
        with fitz.open(source_pdf) as document:
            pages, recovered = _run_binarized_fallback(
                document,
                engine,
                request,
                temporary,
                page_entries,
                clauses,
                gaps,
                render_dpi=render_dpi,
            )
        manifest["pages"] = page_entries
        manifest["binarized_fallback_pass"] = {
            "trigger": "clause gap remaining after higher-DPI pass",
            "render_dpi": render_dpi,
            "grayscale_threshold": 150,
            "candidate_pages": pages,
            "recovered_clauses": recovered,
            "derived_from_manifest_sha256": sha256_file(input_dir / "manifest.json"),
        }
        write_json(temporary / "manifest.json", manifest)
        result = validate_ocr_artifact(temporary, source_pdf=source_pdf)
        write_json(temporary / "validation.json", result)
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, output_dir)
        return result
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def apply_reviewed_corrections(
    input_dir: Path,
    output_dir: Path,
    *,
    source_pdf: Path,
    corrections_path: Path,
) -> dict[str, Any]:
    """Create a new immutable artifact with visually reviewed text corrections."""
    validate_ocr_artifact(input_dir, source_pdf=source_pdf)
    if output_dir.exists():
        raise OcrArtifactError(f"output already exists: {output_dir}")
    corrections = json.loads(corrections_path.read_text(encoding="utf-8"))
    if corrections.get("input_manifest_sha256") != sha256_file(
        input_dir / "manifest.json"
    ):
        raise OcrArtifactError("correction input manifest SHA-256 mismatch")
    items = corrections.get("corrections")
    if not isinstance(items, list) or not items:
        raise OcrArtifactError("corrections must be a non-empty list")
    manifest = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    temporary = output_dir.with_name(f".{output_dir.name}.building-{uuid.uuid4().hex}")
    try:
        shutil.copytree(input_dir, temporary)
        changed_pages: set[int] = set()
        for item in items:
            page_number = int(item["page_number"])
            old_text = str(item["old_text"])
            new_text = str(item["new_text"])
            page_path = temporary / "pages" / f"{page_number:04d}.json"
            page = json.loads(page_path.read_text(encoding="utf-8"))
            matching_lines = [line for line in page["lines"] if old_text in line["text"]]
            if len(matching_lines) != 1:
                raise OcrArtifactError(
                    f"correction must match exactly one line on page {page_number}"
                )
            matching_lines[0]["text"] = matching_lines[0]["text"].replace(
                old_text, new_text, 1
            )
            page["text"] = "\n".join(line["text"] for line in page["lines"])
            page.setdefault("reviewed_corrections", []).append(
                {
                    "old_text": old_text,
                    "new_text": new_text,
                    "reason": item["reason"],
                    "verified_against": item["verified_against"],
                }
            )
            digest = write_json(page_path, page)
            entry = manifest["pages"][page_number - 1]
            entry.update(
                {
                    "sha256": digest,
                    "character_count": len(page["text"]),
                    "line_count": len(page["lines"]),
                }
            )
            changed_pages.add(page_number)
        manifest["reviewed_corrections"] = {
            "record_name": corrections_path.name,
            "record_sha256": sha256_file(corrections_path),
            "reviewer": corrections["reviewer"],
            "reviewed_at": corrections["reviewed_at"],
            "changed_pages": sorted(changed_pages),
        }
        write_json(temporary / "manifest.json", manifest)
        result = validate_ocr_artifact(temporary, source_pdf=source_pdf)
        write_json(temporary / "validation.json", result)
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, output_dir)
        return result
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _validate_request(request: OcrBuildRequest) -> None:
    if not request.source_pdf.is_file():
        raise OcrArtifactError(f"source PDF does not exist: {request.source_pdf}")
    if not _SHA256_PATTERN.fullmatch(request.source_pdf_sha256):
        raise OcrArtifactError("source_pdf_sha256 is invalid")
    actual = sha256_file(request.source_pdf)
    if actual != request.source_pdf_sha256:
        raise OcrArtifactError(
            f"source PDF SHA-256 mismatch: expected {request.source_pdf_sha256}, got {actual}"
        )
    if request.render_dpi < 150 or request.render_dpi > 600:
        raise OcrArtifactError("render_dpi must be between 150 and 600")


def _page_record(
    request: OcrBuildRequest, page_number: int, render_dpi: int, result: Any
) -> dict[str, Any]:
    raw_texts = result.txts if result.txts is not None else []
    raw_scores = result.scores if result.scores is not None else []
    raw_boxes = result.boxes if result.boxes is not None else []
    texts = _as_list(raw_texts)
    scores = _as_list(raw_scores)
    boxes = _as_list(raw_boxes)
    lines = []
    for text, score, box in zip(texts, scores, boxes, strict=True):
        lines.append(
            {
                "text": str(text),
                "confidence": round(float(score), 6),
                "polygon": [[round(float(x), 2), round(float(y), 2)] for x, y in box],
            }
        )
    return {
        "schema_version": OCR_SCHEMA_VERSION,
        "spec_id": request.spec_id,
        "edition_id": request.edition_id,
        "source_pdf_sha256": request.source_pdf_sha256,
        "page_number": page_number,
        "render_dpi": render_dpi,
        "text": "\n".join(line["text"] for line in lines),
        "lines": lines,
    }


def _as_list(value: Any) -> list[Any]:
    return value.tolist() if hasattr(value, "tolist") else list(value)


def _clause_sequence_gaps(clauses: dict[str, list[int]]) -> list[str]:
    groups: dict[tuple[int, int], set[int]] = {}
    for clause in clauses:
        major, section, item = (int(part) for part in clause.split("."))
        groups.setdefault((major, section), set()).add(item)
    gaps = []
    for (major, section), items in sorted(groups.items()):
        if len(items) < 2:
            continue
        for item in range(1, max(items) + 1):
            if item not in items:
                gaps.append(f"{major}.{section}.{item}")
    return gaps


def _clauses_from_page_files(
    artifact_dir: Path, entries: list[dict[str, Any]]
) -> dict[str, list[int]]:
    clauses: dict[str, list[int]] = {}
    for entry in entries:
        page_number = int(entry["page_number"])
        record = json.loads((artifact_dir / entry["path"]).read_text(encoding="utf-8"))
        for clause in _extract_clauses(record["text"]):
            clauses.setdefault(clause, []).append(page_number)
    return clauses


def _fallback_pages(
    clauses: dict[str, list[int]], gaps: list[str]
) -> list[int]:
    pages: set[int] = set()
    for gap in gaps:
        major, section, item = (int(part) for part in gap.split("."))
        previous = clauses.get(f"{major}.{section}.{item - 1}", [])
        following = clauses.get(f"{major}.{section}.{item + 1}", [])
        if previous and following:
            pages.update(range(min(previous), max(following) + 1))
        else:
            pages.update(previous)
            pages.update(following)
    return sorted(pages)


def _extract_clauses(text: str) -> list[str]:
    return [re.sub(r"\s+", "", match) for match in _CLAUSE_PATTERN.findall(text)]


def _run_binarized_fallback(
    document: fitz.Document,
    engine: Any,
    request: OcrBuildRequest,
    artifact_dir: Path,
    page_entries: list[dict[str, Any]],
    clauses: dict[str, list[int]],
    gaps: list[str],
    *,
    render_dpi: int,
) -> tuple[list[int], dict[str, int]]:
    candidate_pages = _fallback_pages(clauses, gaps)
    recovered_clauses: dict[str, int] = {}
    matrix = fitz.Matrix(render_dpi / 72, render_dpi / 72)
    for page_number in candidate_pages:
        raw_image = document[page_number - 1].get_pixmap(
            matrix=matrix, alpha=False
        ).tobytes("png")
        grayscale = Image.open(io.BytesIO(raw_image)).convert("L")
        binary = grayscale.point(lambda value: 0 if value < 150 else 255)
        buffer = io.BytesIO()
        binary.save(buffer, format="PNG")
        result = engine(buffer.getvalue())
        record = _page_record(request, page_number, render_dpi, result)
        recovered = [gap for gap in gaps if gap in record["text"]]
        if not recovered:
            continue
        record["preprocessing"] = {"grayscale_threshold": 150}
        relative_path = Path("pages") / f"{page_number:04d}.json"
        digest = write_json(artifact_dir / relative_path, record)
        entry = page_entries[page_number - 1]
        entry.update(
            {
                "sha256": digest,
                "character_count": len(record["text"]),
                "line_count": len(record["lines"]),
                "render_dpi": render_dpi,
                "preprocessing": {"grayscale_threshold": 150},
            }
        )
        for clause in recovered:
            recovered_clauses[clause] = page_number
    return candidate_pages, recovered_clauses


def _model_identities() -> list[dict[str, str]]:
    import rapidocr

    models_dir = Path(rapidocr.__file__).resolve().parent / "models"
    identities = []
    for name in _MODEL_NAMES:
        path = models_dir / name
        if not path.is_file():
            raise OcrArtifactError(f"RapidOCR model is missing: {name}")
        identities.append({"name": name, "sha256": sha256_file(path)})
    return identities
