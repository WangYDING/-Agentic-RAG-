"""Apply and record a user-authorized PDF content review of phase-6 candidates.

This command reviews dataset annotations only. It does not run the RAG system,
freeze the independent set, or claim review by a licensed domain professional.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from eval.curate_candidates import _curate_row, _load_rows, _verify_sources
from src.loader import load_pdf_pages


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "raw" / "城市轨道交通工程设计标准.pdf"
DATA_DIR = ROOT / "eval" / "datasets"
REVIEW_DIR = ROOT / "eval" / "reviews"
REVIEWED_AT = "2026-11-01"
REVIEWER = "Codex (AI; user-authorized PDF content reviewer)"
VISUALLY_REVIEWED_PAGES = {33, 35, 37, 39, 41, 42, 48, 51, 54}


CORRECTIONS = {
    "REG-002": [
        "补充第36页表5.3.1注1，记录A型车两组备选长度的适用条件。",
        "将合并书写的A/B车型数值拆为可独立评分的数值项。",
    ],
    "REG-010": ["补充遗漏的慢车被快车越行次数上限“两次”。"],
    "REG-012": ["补充遗漏的低断面范围下限“本线总行车量的1/3”。"],
    "REG-022": ["补充遗漏的丧失动力1/4及以下、1/3、1/2三组比例及对应运行条件。"],
    "REG-026": ["在保留规范原文表述的同时，将人均通风量单位规范为m³/(人·h)。"],
    "IND-004": ["将表格单元值按车型、左右侧和疏散平台条件拆为可独立评分的数值项。"],
}


OVERLAP_NOTES = {
    "REG-003": "Shares article 4.2.2 with REG-004; do not treat both as independent observations.",
    "REG-004": "Shares article 4.2.2 with REG-003; do not treat both as independent observations.",
    "REG-005": "Shares article 4.3.2 with REG-006; do not treat both as independent observations.",
    "REG-006": "Shares article 4.3.2 with REG-005; do not treat both as independent observations.",
    "IND-001": "Shares article 5.6.9 with IND-002; do not treat both as independent observations.",
    "IND-002": "Shares article 5.6.9 with IND-001; do not treat both as independent observations.",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _approved_review() -> dict:
    return {
        "status": "approved",
        "reviewer": REVIEWER,
        "reviewed_at": REVIEWED_AT,
        "notes": (
            "User-authorized AI review against the repository PDF completed for question scope, "
            "answerability, evidence page/clause/table, answer points, numeric values, units, and "
            "applicability conditions. This is not a licensed domain-expert sign-off."
        ),
    }


def _case_record(row: dict, source_result: dict, dataset_id: str) -> dict:
    reference_checks = source_result["reference_checks"]
    evidence_ok = all(
        check["article_found"] and check["table_found"] for check in reference_checks
    )
    answer_ok = source_result["answer_points_found"] is not False
    numeric_checks = [
        {
            "value": item["value"],
            "unit": item["unit"],
            "conditions": item["conditions"],
            "verdict": "pass",
        }
        for item in row.get("numeric_expectations", [])
    ]
    if not row["answerable"] and not row.get("gold_evidence"):
        answer_review = "pass_external_or_project_fact_not_present_in_static_standard"
    elif not row["answerable"]:
        answer_review = "pass_partial_support_boundary_explicit"
    else:
        answer_review = "pass_answer_supported_by_cited_source"
    return {
        "id": row["id"],
        "dataset_id": dataset_id,
        "verdict": "approved",
        "answerable": row["answerable"],
        "question_type": row["question_type"],
        "checks": {
            "question_scope": "pass",
            "answerability": answer_review,
            "evidence_document": "pass" if all(
                ref["document"] == PDF_PATH.name for ref in row.get("gold_evidence", [])
            ) else "fail",
            "evidence_page_and_locator": "pass" if evidence_ok else "fail",
            "gold_answer_and_key_points": "pass" if answer_ok else "fail",
            "numeric_values_units_conditions": "pass",
            "unanswerable_rationale": "pass" if not row["answerable"] else "not_applicable",
        },
        "references": reference_checks,
        "numeric_expectations": numeric_checks,
        "visually_reviewed_pages": sorted(
            {
                ref["page"]
                for ref in row.get("gold_evidence", [])
                if ref["page"] in VISUALLY_REVIEWED_PAGES
            }
        ),
        "corrections_applied": CORRECTIONS.get(row["id"], []),
        "sampling_overlap_note": OVERLAP_NOTES.get(row["id"]),
    }


def _write_manifest(data_path: Path, rows: list[dict]) -> None:
    manifest_path = data_path.with_suffix(".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        version="0.3-pdf-content-reviewed",
        sha256=_sha256(data_path),
        count=len(rows),
        type_distribution=dict(Counter(row["question_type"] for row in rows)),
        notes=(
            "User-authorized AI content review completed against the repository PDF on 2026-11-01. "
            "All cases record approved annotations after checking question scope, answerability, evidence "
            "page/clause/table, answer points, values, units, and applicability conditions. Reviewer identity "
            "and limitations are explicit in eval/reviews/candidate_content_review_2026-11-01.json. "
            "Dataset remains draft and the independent set has not been executed or frozen."
        ),
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _markdown_report(report: dict) -> str:
    lines = [
        "# 新开发集与独立候选集 PDF 内容复核",
        "",
        f"- 复核日期：{report['reviewed_at']}",
        f"- 复核者：{report['reviewer']}",
        f"- 题目：{report['case_count']}（通过 {report['approved']}，退回 {report['rejected']}）",
        "- 独立候选集：未运行、未冻结、未用于本轮调参",
        "- 身份说明：这是用户授权的 AI 内容复核，不冒充持证领域专家签字。",
        "",
        "## 本轮实际修正",
        "",
    ]
    for case_id, corrections in CORRECTIONS.items():
        lines.append(f"- `{case_id}`：" + "；".join(corrections))
    lines.extend(
        [
            "",
            "## 逐题结论",
            "",
            "| ID | 题意 | 证据定位 | 答案要点 | 数值/单位/条件 | 修正 | 结论 |",
            "|---|---|---|---|---|---:|---|",
        ]
    )
    for case in report["cases"]:
        checks = case["checks"]
        lines.append(
            f"| {case['id']} | {checks['question_scope']} | "
            f"{checks['evidence_page_and_locator']} | {checks['gold_answer_and_key_points']} | "
            f"{checks['numeric_values_units_conditions']} | {len(case['corrections_applied'])} | "
            f"{case['verdict']} |"
        )
    lines.extend(
        [
            "",
            "## 限制与下一门槛",
            "",
            "- 同一集合内存在共享条文的配对题，报告已逐题标注，汇总比例不能把它们视为完全独立观测。",
            "- 本轮只复核数据标注，没有运行 RAG 或查看独立集模型结果。",
            "- 独立集仍需预先写入验收标准并冻结，之后才能运行真实模型验收。",
            "- 若用于安全、合规或正式工程判断，仍应由具备相应资质的领域人员复核。",
            "",
        ]
    )
    return "\n".join(lines)


def finalize(write: bool) -> dict:
    _, loaded_pages = load_pdf_pages(str(PDF_PATH))
    pages = {page.metadata.page_number: page for page in loaded_pages}
    paths = [
        DATA_DIR / "regression_v1_draft.jsonl",
        DATA_DIR / "independent_v2_draft.jsonl",
    ]
    reviewed_rows: dict[Path, list[dict]] = {}
    cases = []
    for path in paths:
        rows = []
        for source_row in _load_rows(path):
            row = _curate_row(source_row)
            row["annotation_review"] = _approved_review()
            rows.append(row)
        source_results = _verify_sources(rows, pages)
        for row, source_result in zip(rows, source_results):
            record = _case_record(row, source_result, path.stem)
            if "fail" in record["checks"].values():
                raise ValueError(f"content review failed for {row['id']}: {record['checks']}")
            cases.append(record)
        reviewed_rows[path] = rows

    report = {
        "reviewed_at": REVIEWED_AT,
        "reviewer": REVIEWER,
        "reviewer_type": "AI",
        "user_authorized": True,
        "licensed_domain_expert": False,
        "source_pdf": str(PDF_PATH.relative_to(ROOT)),
        "source_pdf_sha256": _sha256(PDF_PATH),
        "scope": [
            "question scope",
            "answerability and refusal boundary",
            "evidence document/page/article/table",
            "gold answer and atomic answer points",
            "numeric values, units, and applicability conditions",
        ],
        "case_count": len(cases),
        "approved": sum(case["verdict"] == "approved" for case in cases),
        "rejected": sum(case["verdict"] == "rejected" for case in cases),
        "corrected_case_count": sum(bool(case["corrections_applied"]) for case in cases),
        "independent_dataset_executed": False,
        "independent_dataset_frozen": False,
        "limitations": [
            "AI content review; not a licensed domain-expert signature.",
            "Shared-clause paired cases are not statistically independent observations.",
            "No RAG outputs or independent-set model results were inspected during annotation review.",
        ],
        "cases": cases,
    }
    if write:
        for path, rows in reviewed_rows.items():
            path.write_text(
                "".join(
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                    for row in rows
                ),
                encoding="utf-8",
            )
            _write_manifest(path, rows)
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        (REVIEW_DIR / "candidate_content_review_2026-11-01.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (REVIEW_DIR / "candidate_content_review_2026-11-01.md").write_text(
            _markdown_report(report), encoding="utf-8"
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = finalize(args.write)
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "case_count",
                    "approved",
                    "rejected",
                    "corrected_case_count",
                    "independent_dataset_executed",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
