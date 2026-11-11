"""Build 150 unseen-location leads for human question authoring, without RAG calls."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

import pymupdf

from eval.build_120_seen_inventory import DATASETS, ROOT


CLAUSE = re.compile(r"(?m)^\s*(\d{1,2}\.\d{1,2}(?:\.\d{1,3})?)\s*(?![-–])")
CATALOG = json.loads((ROOT / "data/spec_catalog.v1.json").read_text(encoding="utf-8"))
SEEN = json.loads((DATASETS / "independent_120_seen_inventory.json").read_text(encoding="utf-8"))["records"]
OUT = DATASETS / "independent_120_source_leads.json"


def pages(doc: dict):
    ocr = doc.get("ocr_artifact_path")
    if ocr:
        for path in sorted((ROOT / ocr / "pages").glob("*.json")):
            page = json.loads(path.read_text(encoding="utf-8"))
            yield page["page_number"], page["text"]
    else:
        pdf = pymupdf.open(ROOT / doc["local_pdf_path"])
        for i, page in enumerate(pdf):
            yield i + 1, page.get_text(sort=True)


def main() -> None:
    seen_locations = set()
    for record in SEEN:
        for location in record["locations"]:
            article = location.get("article")
            if article:
                seen_locations.add((location.get("business_id"), str(article)))
                # Old single-PDF datasets lack business ID; conservatively avoid its article across all documents.
                if not location.get("business_id"):
                    seen_locations.add((None, str(article)))
    grouped = defaultdict(list)
    for doc in CATALOG["documents"]:
        business = f'{doc["spec_id"]}@{doc["edition_id"]}'
        for page_no, content in pages(doc):
            hits = list(CLAUSE.finditer(content))
            for i, hit in enumerate(hits):
                article = hit.group(1)
                if (business, article) in seen_locations or (None, article) in seen_locations:
                    continue
                if int(article.split(".")[0]) < 3 or article.count(".") != 2:
                    continue
                excerpt = re.sub(r"\s+", " ", content[hit.end():hits[i + 1].start() if i + 1 < len(hits) else hit.end() + 400]).strip()
                if len(excerpt) < 35 or len(excerpt) > 700 or "···" in excerpt:
                    continue
                grouped[business].append({
                    "document_id": doc["spec_id"], "document_version": doc["edition_id"],
                    "pdf_sha256": doc["pdf_sha256"], "pdf_page": page_no,
                    "article": article, "chapter": article.split(".")[0],
                    "source_excerpt_unverified": excerpt[:400],
                    "status": "authoring_lead_not_a_test_case",
                })
    result = []
    for business, rows in grouped.items():
        by_chapter = defaultdict(list)
        for row in rows:
            by_chapter[row["chapter"]].append(row)
        chapters = sorted(by_chapter, key=lambda x: int(x))
        cursor = 0
        chosen = []
        while len(chosen) < 50 and any(by_chapter.values()):
            chapter = chapters[cursor % len(chapters)]
            if by_chapter[chapter]:
                chosen.append(by_chapter[chapter].pop(0))
            cursor += 1
        result.extend(chosen)
    OUT.write_text(json.dumps({
        "warning": "These are source leads, not 150 candidate questions or reviewed gold labels. OCR and PDF page content require visual checking; semantic overlap remains unchecked.",
        "count": len(result), "by_document": dict(Counter(f'{r["document_id"]}@{r["document_version"]}' for r in result)),
        "leads": result,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(result)} source leads -> {OUT}")


if __name__ == "__main__":
    main()
