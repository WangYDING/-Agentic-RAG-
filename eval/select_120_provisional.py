"""Select a reviewable 120-case draft; deliberately cannot freeze or run RAG."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

from eval.contract_v1 import validate_test_case

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "eval/datasets"
INPUTS = [
    "independent_120_candidates_batch1.jsonl",
    "independent_120_numeric_direct_batch5.jsonl",
    "independent_120_tables_batch2.jsonl",
    "independent_120_multi_batch4.jsonl",
    "independent_120_cross_batch3.jsonl",
    "independent_120_behavior_candidates.jsonl",
]
OUT = DATA / "independent_120_provisional_review.jsonl"
MANIFEST = DATA / "independent_120_provisional_review.manifest.json"
QA = DATA / "independent_120_provisional_review.qa.json"
EXCLUDE = {
    "I120-C012": "prior P1-Q008 covers GB 55033 passenger-door interlock",
    "I120-M001": "prior REG-001 covers operating organization and capacity",
    "I120-M014": "duplicates C016 access-control functionality",
    "I120-M015": "two unrelated topics; poor multi-evidence question",
    "I120-M013": "reuses GB 50157 article 16.1.2 in X009; replace with distinct M019",
    "I120-Q001": "same table and fact family as selected T010",
    "I120-Q002": "same article and fact family as selected C009",
    "I120-Q003": "same table and fact family as selected T006",
    "I120-Q004": "same table and fact family as selected T009",
    "I120-Q005": "ambiguous object even after normal clarification",
    "I120-Q006": "prior P1-V2-001 used DB11 design-life fact",
    "I120-Q008": "same edition-only mechanism as Q007",
    "I120-Q009": "same edition-only mechanism as Q007",
    "I120-Q010": "public all-documents scope may change; redundant scope mechanism",
    "I120-C020": "reserve direct question; direct category already at quota",
    "I120-C021": "reserve direct question; direct category already at quota",
    "I120-C022": "reserve direct question; direct category already at quota",
    "I120-C023": "reserve direct question; direct category already at quota",
    "I120-N023": "reserve numeric question; numeric category already at quota",
    "I120-N024": "reserve numeric question; numeric category already at quota",
    "I120-N025": "reserve numeric question; numeric category already at quota",
    "I120-N026": "reserve numeric question; numeric category already at quota",
    "I120-X021": "reserve cross-spec question; cross-spec category already at quota",
    "I120-X022": "reserve alternative overlapping C019; cross-spec category at quota",
    "I120-X023": "reserve alternative overlapping X012; cross-spec category at quota",
    "I120-X024": "reserve cross-spec question; cross-spec category already at quota",
    "I120-M020": "reserve alternative overlapping N023; multi-evidence category at quota",
    "I120-M021": "reserve alternative overlapping X024; multi-evidence category at quota",
    "I120-M022": "reserve alternative overlapping M019; multi-evidence category at quota",
    "I120-M023": "reserve alternative overlapping C014; multi-evidence category at quota",
}
QUOTAS = {
    "单规范直接查询": 20,
    "数值、单位与条件": 20,
    "表格查询": 15,
    "单规范多证据组合": 15,
    "跨规范查询与比较": 20,
    "应拒答问题": 20,
    "应澄清问题": 10,
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    catalog = json.loads(
        (ROOT / "data/spec_catalog.v1.json").read_text(encoding="utf-8")
    )
    docs = {(d["spec_id"], d["edition_id"]): d for d in catalog["documents"]}
    pdfs = {}
    for key, doc in docs.items():
        path = ROOT / doc["local_pdf_path"]
        if sha(path) != doc["pdf_sha256"]:
            raise ValueError(f"source PDF hash mismatch: {path}")
        pdfs[key] = pymupdf.open(path)
    candidates = [
        json.loads(line)
        for name in INPUTS
        for line in (DATA / name).read_text(encoding="utf-8").splitlines()
    ]
    selected = [case for case in candidates if case["case_id"] not in EXCLUDE]
    ids = [case["case_id"] for case in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate case IDs")
    if set(EXCLUDE) - set(ids):
        raise ValueError(
            f"exclusions absent from candidate pool: {sorted(set(EXCLUDE) - set(ids))}"
        )
    counts = Counter(case["main_category"] for case in selected)
    if len(selected) != 120 or counts != QUOTAS:
        raise ValueError(
            f"selection is not 120 / exact quotas: {len(selected)} {counts}"
        )
    if any(
        case.get("annotation_review", {}).get("status") != "pending"
        for case in selected
    ):
        raise ValueError("a draft claims review approval")
    location_checks = []
    used = defaultdict(list)
    text_checks = []
    for case in selected:
        validate_test_case(case)
        for group in case["evidence_groups"]:
            for alternative in group["alternatives"]:
                for ref in alternative["all_of"]:
                    key = ref["document_id"], ref["document_version"]
                    if key not in docs or not 1 <= ref["page"] <= len(pdfs[key]):
                        raise ValueError(f"bad document/page: {case['case_id']} {ref}")
                    if ref["document_id"] not in case["query_scope"].get(
                        "spec_ids", []
                    ):
                        raise ValueError(
                            f"gold document outside public scope: {case['case_id']}"
                        )
                    if ref["document_version"] not in case["query_scope"].get(
                        "edition_ids", []
                    ):
                        raise ValueError(
                            f"gold edition outside public scope: {case['case_id']}"
                        )
                    source_doc = docs[key]
                    if source_doc.get("ocr_artifact_path"):
                        page_text = json.loads(
                            (
                                ROOT
                                / source_doc["ocr_artifact_path"]
                                / "pages"
                                / f"{ref['page']:04}.json"
                            ).read_text(encoding="utf-8")
                        )["text"]
                    else:
                        page_text = pdfs[key][ref["page"] - 1].get_text(sort=True)
                    article_found = (
                        ref.get("article") in page_text if ref.get("article") else True
                    )
                    if not article_found:
                        raise ValueError(
                            f"article absent from source page: {case['case_id']} {ref}"
                        )

                    def compact(value):
                        return "".join(value.split())

                    quote_prefix_found = (
                        compact(ref.get("quote", ""))[:25] in compact(page_text)
                        if ref.get("quote") and not ref.get("table")
                        else None
                    )
                    text_checks.append(
                        {
                            "case_id": case["case_id"],
                            "article_found": article_found,
                            "quote_prefix_found": quote_prefix_found,
                            "table_visual_transcription": bool(ref.get("table")),
                        }
                    )
                    loc = (
                        ref["document_id"],
                        ref["document_version"],
                        ref.get("article"),
                        ref.get("table"),
                    )
                    used[loc].append(case["case_id"])
                    location_checks.append(
                        {
                            "case_id": case["case_id"],
                            "location": loc,
                            "pdf_page_valid": True,
                        }
                    )
    OUT.write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in selected),
        encoding="utf-8",
    )
    MANIFEST.write_text(
        json.dumps(
            {
                "dataset_id": "independent_120_provisional_review",
                "role": "independent_candidate",
                "status": "draft_pending_source_and_human_review",
                "frozen_at": None,
                "data_file": OUT.name,
                "sha256_raw_bytes": sha(OUT),
                "count": len(selected),
                "type_distribution": dict(counts),
                "candidate_count": len(candidates),
                "excluded_count": len(EXCLUDE),
                "input_sha256": {name: sha(DATA / name) for name in INPUTS},
                "source_pdf_sha256": {
                    doc["standard_code"]: doc["pdf_sha256"] for doc in docs.values()
                },
                "human_approved": False,
                "formal_run_allowed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    QA.write_text(
        json.dumps(
            {
                "selected_count": len(selected),
                "candidate_count": len(candidates),
                "excluded": EXCLUDE,
                "location_check_count": len(location_checks),
                "duplicate_locations_within_selected": [
                    {"location": key, "case_ids": sorted(set(values))}
                    for key, values in used.items()
                    if len(set(values)) > 1
                ],
                "source_text_checks": {
                    "article_present": sum(row["article_found"] for row in text_checks),
                    "checked_refs": len(text_checks),
                    "non_table_quote_prefix_matches": sum(
                        row["quote_prefix_found"] is True for row in text_checks
                    ),
                    "non_table_quote_prefix_misses": [
                        row["case_id"]
                        for row in text_checks
                        if row["quote_prefix_found"] is False
                    ],
                    "table_refs_requiring_visual_review": sum(
                        row["table_visual_transcription"] for row in text_checks
                    ),
                },
                "remaining_review": [
                    "Verify every full source page and exact quote; table row, column, continuation and notes.",
                    "Review historical question-answer facts, not just article numbers or lexical similarity.",
                    "Adjudicate refusal behavior and project-data assumptions; verify the frozen public scope policy.",
                    "Record actual human reviewer decisions and equivalent evidence alternatives before freeze.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"{len(candidates)} candidates -> {len(selected)} pending cases; {len(location_checks)} evidence refs"
    )


if __name__ == "__main__":
    main()
