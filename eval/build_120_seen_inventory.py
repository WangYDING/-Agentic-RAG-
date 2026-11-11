"""Offline inventory of previously exposed questions and gold locations.

No RAG modules, model clients, or indexes are imported. This is preparation only.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "eval" / "datasets"
OUT = DATASETS / "independent_120_seen_inventory.json"


def main() -> None:
    rows = []
    for path in sorted(DATASETS.glob("*.jsonl")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            item = json.loads(line)
            refs = item.get("source_references") or item.get("gold_evidence") or []
            locations = []
            for ref in refs:
                locations.append({key: ref.get(key) for key in (
                    "business_id", "document", "pdf_page", "page", "article", "table"
                ) if ref.get(key) is not None})
            for spec, articles in (item.get("expected_articles_by_spec") or {}).items():
                locations.extend({"business_id": spec, "article": article} for article in articles)
            rows.append({
                "source_file": path.name, "source_line": line_no,
                "id": item.get("case_id") or item.get("id"),
                "question": item.get("question"), "locations": locations,
                "known_answer": item.get("gold_answer") or item.get("reference_answer"),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "exposure": "seen_or_historical_conservative",
            })
    OUT.write_text(json.dumps({
        "purpose": "Conservative prior exposure index; overlap by fact and semantic meaning still requires review.",
        "source_files": sorted({row["source_file"] for row in rows}),
        "record_count": len(rows), "records": rows,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(rows)} historical rows -> {OUT}")


if __name__ == "__main__":
    main()
