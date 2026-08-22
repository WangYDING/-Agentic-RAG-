import re
from typing import Iterable

from src.document_schema import Chunk, ChunkMetadata, DocumentMetadata, Page


def extract_article_id(text: str):
    """
    更严格地提取条文编号：
    1. 优先匹配行首的条文编号
    2. 避免把 0.2、0.05 这种数值误识别成条文
    """
    lines = text.split("\n")

    # 匹配行首条文编号，如：
    # 7.2 xxx
    # 13.1.1 xxx
    # 30.8.5 xxx
    pattern = re.compile(r'^\s*((?:\d+\.){2,}\d+)\s+')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = pattern.match(line)
        if match:
            article_id = match.group(1)

            # 过滤明显像数值的小数，例如 0.2、0.05
            parts = article_id.split(".")
            if len(parts) >= 2:
                # 至少要求第一段不是 0
                if parts[0] != "0":
                    return article_id

    return None


def parse_structural_lines(text: str):
    lines = [line.strip() for line in text.splitlines()]
    inferred_chapter = _infer_page_chapter(lines)
    current_chapter_id = inferred_chapter[0] if inferred_chapter else None
    current_chapter_title = inferred_chapter[1] if inferred_chapter else None
    current_article_id = None
    parsed = []

    for index, line in enumerate(lines):
        if not line:
            continue

        chapter = _match_chapter(line, lines, index)
        if chapter:
            current_chapter_id, current_chapter_title = chapter

        article_id = _match_article(line, lines, index)
        if article_id:
            current_article_id = article_id

        parsed.append({
            "text": line,
            "chapter_id": current_chapter_id,
            "chapter_title": current_chapter_title,
            "article_id": current_article_id,
        })

    return parsed


def split_pages_with_ref(
    document: DocumentMetadata,
    pages: Iterable[Page],
    chunk_size=300,
    overlap=50,
):
    chunks: list[Chunk] = []
    chunk_id = 0
    current_chapter_id = None
    current_chapter_title = None
    current_article_id = None
    chapter_titles: dict[str, str] = {}

    for page in pages:
        page_text = page.text.strip()
        if page_text:
            chapter_titles.update(_extract_chapter_titles(page_text))

        if page_text:
            blocks, current_article_id = _split_article_blocks(
                page_text,
                inherited_article_id=current_article_id,
            )
            for block in blocks:
                article_id = block["article_id"]
                if article_id:
                    next_chapter_id = article_id.split(".")[0]
                    if next_chapter_id != current_chapter_id:
                        current_chapter_title = chapter_titles.get(next_chapter_id)
                    else:
                        current_chapter_title = chapter_titles.get(
                            next_chapter_id,
                            current_chapter_title,
                        )
                    current_chapter_id = next_chapter_id

                for local_start, local_end, chunk_text in _split_within_block(
                    block["text"],
                    chunk_size=chunk_size,
                    overlap=overlap,
                ):
                    if chunk_text:
                        display_ref = (
                            f"第{article_id}条"
                            if article_id
                            else f"p{page.metadata.page_number}-chunk_{chunk_id}"
                        )

                        chunks.append(
                            Chunk(
                                text=chunk_text,
                                metadata=ChunkMetadata(
                                    document_id=document.document_id,
                                    source=document.source,
                                    chunk_id=chunk_id,
                                    page_start=page.metadata.page_number,
                                    page_end=page.metadata.page_number,
                                    char_start=block["char_start"] + local_start,
                                    char_end=block["char_start"] + local_end,
                                    chapter_id=current_chapter_id,
                                    chapter_title=current_chapter_title,
                                    article_id=article_id,
                                    display_ref=display_ref,
                                ),
                            )
                        )
                        chunk_id += 1

        for table in page.tables:
            display_ref = table.metadata.table_id or f"p{page.metadata.page_number}-table"
            chunks.append(
                Chunk(
                    text=table.retrieval_text,
                    metadata=ChunkMetadata(
                        document_id=document.document_id,
                        source=document.source,
                        chunk_id=chunk_id,
                        page_start=page.metadata.page_number,
                        page_end=page.metadata.page_number,
                        char_start=0,
                        char_end=len(table.retrieval_text),
                        chapter_id=current_chapter_id,
                        chapter_title=current_chapter_title,
                        article_id=None,
                        display_ref=display_ref,
                        content_type="table",
                        table_id=table.metadata.table_id,
                        table_title=table.metadata.title,
                        extra={
                            "table": {
                                "headers": table.headers,
                                "rows": table.rows,
                                "cells": table.cells,
                                "bbox": table.metadata.bbox,
                            }
                        },
                    ),
                )
            )
            chunk_id += 1

    return [chunk.to_record() for chunk in chunks]


def _split_article_blocks(text: str, inherited_article_id: str | None):
    """Split a page before chunking so no block contains multiple articles."""
    markers = []
    offset = 0
    lines = text.splitlines(keepends=True)
    plain_lines = [line.rstrip("\r\n") for line in lines]
    for index, line in enumerate(plain_lines):
        article_id = _match_article(line.strip(), plain_lines, index)
        if article_id:
            markers.append((offset, article_id))
        offset += len(lines[index])

    if not markers:
        return ([{
            "text": text,
            "char_start": 0,
            "article_id": inherited_article_id,
            "chapter_id": inherited_article_id.split(".")[0] if inherited_article_id else None,
        }], inherited_article_id)

    blocks = []
    first_marker_start = markers[0][0]
    first_start = _find_structural_prefix_start(text[:first_marker_start])
    if first_start is None:
        first_start = first_marker_start
    if first_start > 0 and text[:first_start].strip():
        blocks.append({
            "text": text[:first_start],
            "char_start": 0,
            "article_id": inherited_article_id,
            "chapter_id": inherited_article_id.split(".")[0] if inherited_article_id else None,
        })

    for marker_index, (start, article_id) in enumerate(markers):
        if marker_index == 0:
            start = first_start
        end = markers[marker_index + 1][0] if marker_index + 1 < len(markers) else len(text)
        blocks.append({
            "text": text[start:end],
            "char_start": start,
            "article_id": article_id,
            "chapter_id": article_id.split(".")[0],
        })

    return blocks, markers[-1][1]


def _split_within_block(text: str, *, chunk_size: int, overlap: int):
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")

    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        raw_chunk = text[start:end]
        chunk_text = raw_chunk.strip()
        if chunk_text:
            leading = len(raw_chunk) - len(raw_chunk.lstrip())
            trailing = len(raw_chunk) - len(raw_chunk.rstrip())
            yield start + leading, end - trailing, chunk_text
        if end == len(text):
            break
        start += chunk_size - overlap


def _extract_chapter_titles(text: str) -> dict[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    prefix = []
    first_article_id = None
    for index, line in enumerate(lines[:12]):
        first_article_id = _match_article(line, lines, index)
        if first_article_id:
            break
        prefix.append(line)

    if first_article_id and prefix:
        chapter_id = first_article_id.split(".")[0]
        if prefix[0] == chapter_id:
            title = "".join(item for item in prefix[1:] if _looks_like_title(item)).strip()
            if title:
                return {chapter_id: title}

    for index, line in enumerate(prefix):
        section = re.fullmatch(r"(\d{1,2})\.\d{1,2}", line)
        if not section:
            continue
        title_parts = [
            item for item in prefix[max(0, index - 3):index]
            if _looks_like_title(item) and not re.fullmatch(r"\d+", item)
        ]
        title = "".join(title_parts).strip()
        if title:
            return {section.group(1): title}
    return {}


def _find_structural_prefix_start(prefix: str) -> int | None:
    lines = prefix.splitlines(keepends=True)
    plain_lines = [line.rstrip("\r\n") for line in lines]
    offset = 0
    for index, line in enumerate(plain_lines):
        if _match_chapter(line.strip(), plain_lines, index):
            return offset
        offset += len(lines[index])
    return None


def split_text_with_ref(text: str, source="unknown", chunk_size=300, overlap=50):
    """
    滑窗切分 + 尝试提取条文编号用于展示引用
    """
    chunks = []
    start = 0
    chunk_id = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk_text = text[start:end].strip()

        if chunk_text:
            article_id = extract_article_id(chunk_text)

            if article_id:
                display_ref = f"第{article_id}条"
            else:
                display_ref = f"chunk_{chunk_id}"

            chunks.append({
                "text": chunk_text,
                "source": source,
                "chunk_id": chunk_id,
                "document_id": source,
                "page_start": None,
                "page_end": None,
                "char_start": start,
                "char_end": end,
                "article_id": article_id,
                "display_ref": display_ref,
                "content_type": "text",
            })
            chunk_id += 1

        start += chunk_size - overlap

    return chunks


def _match_chapter(line: str, lines: list[str], index: int):
    match = re.fullmatch(r"(\d{1,2}(?:\.\d{1,2})?)", line)
    if match and index + 1 < len(lines) and not _looks_like_catalog_line(lines[index + 1]):
        title = lines[index + 1].strip()
        if _looks_like_title(title):
            return match.group(1), title

    inline = re.match(r"^(\d{1,2}(?:\.\d{1,2})?)\s+(.{2,30})$", line)
    if inline and _looks_like_title(inline.group(2)):
        return inline.group(1), inline.group(2)

    return None


def _match_article(line: str, lines: list[str], index: int):
    inline = re.match(r"^((?:\d+\.){2,}\d+)\s+", line)
    if inline and inline.group(1).split(".")[0] != "0":
        return inline.group(1)

    standalone = re.fullmatch(r"((?:\d+\.){2,}\d+)", line)
    if standalone and standalone.group(1).split(".")[0] != "0":
        if index + 1 < len(lines) and not re.fullmatch(r"\d+", lines[index + 1].strip()):
            return standalone.group(1)

    return None


def _looks_like_title(text: str):
    if not text or len(text) > 30:
        return False
    if re.search(r"[。；，,.;:：]", text):
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _looks_like_catalog_line(text: str):
    return "·" in text or re.search(r"\.{3,}", text)


def _infer_page_chapter(lines: list[str]):
    title_parts = []
    for line in lines[:12]:
        line = line.strip()
        if not line:
            continue
        article = re.fullmatch(r"((?:\d+\.){2,}\d+)", line)
        section = re.fullmatch(r"(\d{1,2})\.\d{1,2}", line)
        if article:
            chapter_id = article.group(1).split(".")[0]
            chapter_title = "".join(title_parts).strip() or None
            return chapter_id, chapter_title
        if section:
            chapter_id = section.group(1)
            chapter_title = "".join(title_parts).strip() or None
            return chapter_id, chapter_title
        if _looks_like_catalog_line(line) or re.fullmatch(r"\d+", line):
            continue
        if _looks_like_title(line):
            title_parts.append(line)

    return None


def _metadata_for_chunk(
    chunk_text: str,
    structural_lines: list[dict],
    *,
    fallback_chapter_id,
    fallback_chapter_title,
    fallback_article_id,
):
    article_id = extract_article_id(chunk_text)
    chapter_id = fallback_chapter_id
    chapter_title = fallback_chapter_title

    for item in structural_lines:
        if item["text"] and item["text"] in chunk_text:
            chapter_id = item["chapter_id"] or chapter_id
            chapter_title = item["chapter_title"] or chapter_title
            article_id = article_id or item["article_id"]
            if article_id:
                break

    return {
        "chapter_id": chapter_id,
        "chapter_title": chapter_title,
        "article_id": article_id or fallback_article_id,
    }
