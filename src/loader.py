import re
import fitz
from pathlib import Path
from statistics import median

from src.document_schema import DocumentMetadata, Page, PageMetadata, Table, TableMetadata


HEADER_FOOTER_MIN_REPEAT_RATIO = 0.35
WATERMARK_MIN_REPEAT_RATIO = 0.35


def load_pdf_pages(file_path: str) -> tuple[DocumentMetadata, list[Page]]:
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    raw_pages: list[str] = []
    doc = fitz.open(file_path)
    try:
        for page in doc:
            raw_pages.append(page.get_text("text"))
        page_count = doc.page_count

        document = DocumentMetadata(
            document_id=file_path.stem,
            source=file_path.name,
            page_count=page_count,
        )
        repeated_noise = detect_repeated_page_noise(raw_pages)

        pages = []
        for index, raw_text in enumerate(raw_pages, start=1):
            cleaned_text = clean_page_text(raw_text, repeated_noise)
            tables = extract_page_tables(
                page=doc[index - 1],
                page_number=index,
                document=document,
                repeated_noise=repeated_noise,
            )
            pages.append(
                Page(
                    text=cleaned_text,
                    raw_text=raw_text,
                    tables=tables,
                    metadata=PageMetadata(
                        document_id=document.document_id,
                        source=document.source,
                        page_number=index,
                        char_count_raw=len(raw_text),
                        char_count_cleaned=len(cleaned_text),
                    ),
                )
            )
    finally:
        doc.close()

    return document, pages


def extract_page_tables(
    page,
    page_number: int,
    document: DocumentMetadata,
    repeated_noise: set[str] | None = None,
) -> list[Table]:
    repeated_noise = repeated_noise or set()
    tables: list[Table] = []
    if not hasattr(page, "find_tables"):
        return []
    captions = _extract_table_captions(page.get_text("text"), repeated_noise)
    for table_index, table in enumerate(page.find_tables().tables):
        cells = [
            [_clean_table_cell(cell, repeated_noise) for cell in row]
            for row in table.extract()
        ]
        cells = _drop_empty_table_edges(cells)
        if not cells:
            continue
        caption = captions[table_index] if table_index < len(captions) else (None, None)
        table_id, title = caption
        headers = _infer_table_headers(cells)
        rows = cells[len(headers):] if headers else cells
        metadata = TableMetadata(
            document_id=document.document_id,
            source=document.source,
            page_number=page_number,
            table_id=table_id,
            title=title,
            bbox=tuple(float(value) for value in table.bbox) if table.bbox else None,
        )
        tables.append(
            Table(
                metadata=metadata,
                headers=headers,
                rows=rows,
                cells=cells,
                retrieval_text=build_table_retrieval_text(metadata, headers, rows),
            )
        )
    return tables


def load_pdf_text(file_path: str) -> str:
    _, pages = load_pdf_pages(file_path)
    return "\n".join(page.text for page in pages if page.text.strip())


def detect_repeated_page_noise(page_texts: list[str]) -> set[str]:
    line_pages: dict[str, set[int]] = {}
    edge_line_pages: dict[str, set[int]] = {}
    total_pages = max(len(page_texts), 1)

    for page_index, text in enumerate(page_texts):
        lines = [_normalize_line(line) for line in text.splitlines()]
        lines = [line for line in lines if line]
        for line in set(lines):
            if _is_noise_candidate(line):
                line_pages.setdefault(line, set()).add(page_index)

        edge_lines = lines[:3] + lines[-30:]
        for line in set(edge_lines):
            if _is_header_footer_candidate(line):
                edge_line_pages.setdefault(line, set()).add(page_index)

    watermark_threshold = max(3, int(total_pages * WATERMARK_MIN_REPEAT_RATIO))
    edge_threshold = max(3, int(total_pages * HEADER_FOOTER_MIN_REPEAT_RATIO))

    repeated = {
        line for line, pages in line_pages.items() if len(pages) >= watermark_threshold
    }
    repeated.update(
        line for line, pages in edge_line_pages.items() if len(pages) >= edge_threshold
    )

    return repeated


def clean_page_text(text: str, repeated_noise: set[str] | None = None) -> str:
    repeated_noise = repeated_noise or set()
    text = re.sub(r"[—\-]\s*\d+\s*[—\-]", "", text)

    raw_lines = text.split("\n")
    watermark_like_lines = [
        _normalize_line(line)
        for line in raw_lines
        if _looks_like_watermark_fragment(_normalize_line(line))
    ]
    watermark_threshold = 4
    if watermark_like_lines:
        watermark_threshold = max(3, int(median([len(line) for line in watermark_like_lines])))

    cleaned_lines = []
    non_empty_positions = [
        index for index, raw_line in enumerate(raw_lines) if _normalize_line(raw_line)
    ]
    edge_positions = set(non_empty_positions[:3] + non_empty_positions[-3:])

    for index, raw_line in enumerate(raw_lines):
        line = _normalize_line(raw_line)
        if not line:
            cleaned_lines.append("")
            continue
        if index in edge_positions and re.fullmatch(r"\d+", line):
            continue
        if line in repeated_noise:
            continue
        if _looks_like_watermark_fragment(line) and len(line) >= watermark_threshold:
            continue
        line = re.sub(r'(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])', '', line)
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_table_retrieval_text(
    metadata: TableMetadata,
    headers: list[list[str]],
    rows: list[list[str]],
) -> str:
    parts = [f"表格 页码: {metadata.page_number}"]
    if metadata.table_id:
        parts.append(f"表号: {metadata.table_id}")
    if metadata.title:
        parts.append(f"表题: {metadata.title}")
    if headers:
        parts.append("表头: " + " | ".join(cell for row in headers for cell in row if cell))
    for row_index, row in enumerate(rows, start=1):
        values = [cell for cell in row if cell]
        if values:
            parts.append(f"第{row_index}行: " + " | ".join(values))
    return "\n".join(parts)


def clean_text(text: str) -> str:
    """
    面向规范类PDF的清洗：
    ✔ 去页码
    ✔ 去页眉页脚
    ✔ 保留换行结构（关键）
    ✔ 不破坏条文编号
    """

    # 1. 去页码（保守一点）
    text = re.sub(r"[—\-]\s*\d+\s*[—\-]", "", text)

    # 2. 按行处理（但不压平结构）
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            cleaned_lines.append("")  # 保留空行（结构很重要）
            continue

        # 去多余空格
        line = re.sub(r"[ \t]+", " ", line)

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # 3. 修复中文空格（安全操作）
    text = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', text)

    return text.strip()


def _normalize_line(line: str) -> str:
    return re.sub(r"[ \t]+", " ", line.strip())


def _is_header_footer_candidate(line: str) -> bool:
    if len(line) <= 2:
        return True
    if re.fullmatch(r"\d+", line):
        return True
    if re.fullmatch(r"[A-Z]{1,8}\d{0,4}/T\s*\d+-\d+", line):
        return True
    return _is_noise_candidate(line)


def _is_noise_candidate(line: str) -> bool:
    if len(line) > 30:
        return False
    if "规划和自然资源委" in line:
        return True
    if line in {"北京市", "源委", "资源委", "划和自然资源委", "北京市规划和自然"}:
        return True
    return False


def _looks_like_watermark_fragment(line: str) -> bool:
    if not line or len(line) > 20:
        return False
    return (
        "规划和自然资源委" in line
        or line in {
            "源委",
            "资源委",
            "划和自然资源委",
            "市规划和自然资源委",
            "北京市规划和自然",
        }
    )


def _extract_table_captions(text: str, repeated_noise: set[str]) -> list[tuple[str | None, str | None]]:
    lines = [_normalize_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line and line not in repeated_noise]
    captions: list[tuple[str | None, str | None]] = []
    pattern = re.compile(r"^(表\s*\d+(?:\.\d+)*(?:-\d+)?)\s*(.*)$")
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        table_id = re.sub(r"\s+", "", match.group(1))
        title = match.group(2).strip() or None
        if title is None and index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            if next_line and not pattern.match(next_line):
                title = next_line
        captions.append((table_id, title))
    return captions


def _clean_table_cell(cell, repeated_noise: set[str]) -> str:
    if cell is None:
        return ""
    lines = []
    for raw_line in str(cell).splitlines():
        line = _normalize_line(raw_line)
        if not line:
            continue
        if line in repeated_noise or _looks_like_watermark_fragment(line):
            continue
        line = _remove_watermark_tokens(line)
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def _remove_watermark_tokens(line: str) -> str:
    watermark_chars = "北京市规划和自然资源委"
    line = re.sub(rf"(?<![\u4e00-\u9fff])([{watermark_chars}])(\s+|$)", " ", line)
    line = re.sub(rf"(^|\s+)([{watermark_chars}])(?![\u4e00-\u9fff])", " ", line)
    return _normalize_line(line)


def _drop_empty_table_edges(cells: list[list[str]]) -> list[list[str]]:
    rows = [row for row in cells if any(cell for cell in row)]
    if not rows:
        return []
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    non_empty_columns = [
        index for index in range(width)
        if any(row[index] for row in padded)
    ]
    if not non_empty_columns:
        return []
    return [[row[index] for index in non_empty_columns] for row in padded]


def _infer_table_headers(cells: list[list[str]]) -> list[list[str]]:
    if not cells:
        return []
    header_rows = 1
    for row in cells[:3]:
        numeric_cells = sum(1 for cell in row if re.fullmatch(r"[—\-]?\d+(?:\.\d+)?%?", cell))
        if numeric_cells >= max(2, len(row) // 2):
            break
        header_rows += 1
    header_rows = min(header_rows, len(cells), 3)
    return cells[:header_rows]
