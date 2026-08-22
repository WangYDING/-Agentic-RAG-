import json
from pathlib import Path

from eval.schema import load_eval_dataset


ANSWERABLE_CASES = {
    "SEM-001": ("ordinary_sufficient", "sufficient"),
    "SEM-003": ("ordinary_sufficient", "sufficient"),
    "NUM-001": ("ordinary_sufficient", "sufficient"),
    "TAB-002": ("ordinary_sufficient", "sufficient"),
    "TERM-001": ("ordinary_sufficient", "sufficient"),
    "HARD-002": ("ordinary_sufficient", "sufficient"),
    "MULTI-001": ("multi_evidence", "sufficient"),
    "MHARD-001": ("multi_evidence", "sufficient"),
    "MULTI-002": ("multi_evidence", "insufficient"),
    "MULTI-003": ("multi_evidence", "insufficient"),
}

REFUSAL_CASES = (
    "UA-CAND-A01", "UA-CAND-A02",
    "UA-CAND-B01", "UA-CAND-B03",
    "UA-CAND-C01", "UA-CAND-C03",
    "UA-CAND-D01", "UA-CAND-D02", "UA-CAND-D03",
)


def _evidence_bundle(retrieved: list[dict]) -> list[dict]:
    fields = (
        "text", "source", "page_start", "page_end", "article_id", "table_id",
        "content_type", "chunk_id", "display_ref", "rerank_score",
    )
    return [
        {"evidence_id": f"E{index}", **{field: item.get(field) for field in fields}}
        for index, item in enumerate(retrieved[:3], start=1)
    ]


def build_dataset(answerable_report_path, refusal_report_path, refusal_dataset_path) -> list[dict]:
    answerable_report = json.loads(Path(answerable_report_path).read_text(encoding="utf-8"))
    refusal_report = json.loads(Path(refusal_report_path).read_text(encoding="utf-8"))
    refusal_examples = {item.id: item for item in load_eval_dataset(refusal_dataset_path)}
    answerable_cases = {case["id"]: case for case in answerable_report["cases"]}
    refusal_cases = {case["id"]: case for case in refusal_report["cases"]}

    rows = []
    for case_id, (case_type, expected) in ANSWERABLE_CASES.items():
        case = answerable_cases[case_id]
        rows.append({
            "id": f"SUFF-{case_id}",
            "source_case_id": case_id,
            "question": case["question"],
            "case_type": case_type,
            "expected_decision": expected,
            "evidence": _evidence_bundle(case["retrieved"]),
        })
    for case_id in REFUSAL_CASES:
        case = refusal_cases[case_id]
        example = refusal_examples[case_id]
        rows.append({
            "id": f"SUFF-{case_id}",
            "source_case_id": case_id,
            "question": case["question"],
            "case_type": example.hard_negative_type,
            "expected_decision": "insufficient",
            "why_insufficient": example.why_unanswerable,
            "evidence": _evidence_bundle(case["retrieved"]),
        })
    return rows


def main() -> None:
    rows = build_dataset(
        "eval/reports/dev_v0_hybrid_rerank.json",
        "eval/reports/refusal_dev_v0_hybrid_rerank.json",
        "eval/datasets/refusal_dev_v0.jsonl",
    )
    output = Path("eval/datasets/sufficiency_dev_v0.jsonl")
    output.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    print(f"Wrote {output} ({len(rows)} cases)")


if __name__ == "__main__":
    main()
