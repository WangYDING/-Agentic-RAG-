import argparse
import json
from collections import defaultdict
from pathlib import Path

from src.evidence import Evidence
from src.evidence_sufficiency import EvidenceSufficiencyGrader


def compute_metrics(cases: list[dict]) -> dict:
    tp = sum(case["expected_decision"] == "sufficient" and case["predicted_decision"] == "sufficient" for case in cases)
    tn = sum(case["expected_decision"] == "insufficient" and case["predicted_decision"] == "insufficient" for case in cases)
    fp = sum(case["expected_decision"] == "insufficient" and case["predicted_decision"] == "sufficient" for case in cases)
    fn = sum(case["expected_decision"] == "sufficient" and case["predicted_decision"] == "insufficient" for case in cases)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "count": len(cases),
        "accuracy": (tp + tn) / len(cases) if cases else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "false_accept_rate": fp / (fp + tn) if fp + tn else 0.0,
        "false_refusal_rate": fn / (fn + tp) if fn + tp else 0.0,
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
    }


def load_dataset(path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def to_evidence(item: dict) -> Evidence:
    return Evidence(
        evidence_id=item["evidence_id"], text=item["text"], source=item["source"],
        page_start=item.get("page_start"), page_end=item.get("page_end"),
        chunk_id=item["chunk_id"], content_type=item.get("content_type", "text"),
        article_id=item.get("article_id"), table_id=item.get("table_id"),
        display_ref=item.get("display_ref"), rerank_score=item.get("rerank_score"),
    )


def evaluate(dataset_path, grader=None) -> dict:
    grader = grader or EvidenceSufficiencyGrader()
    evaluated = []
    for row in load_dataset(dataset_path):
        decision = grader.grade(row["question"], [to_evidence(item) for item in row["evidence"]])
        evaluated.append({
            "id": row["id"],
            "source_case_id": row["source_case_id"],
            "case_type": row["case_type"],
            "expected_decision": row["expected_decision"],
            "predicted_decision": decision.decision,
            "supported_evidence_ids": decision.supported_evidence_ids,
            "missing_requirements": decision.missing_requirements,
            "reason": decision.reason,
        })
    groups = defaultdict(list)
    for case in evaluated:
        groups[case["case_type"]].append(case)
    return {
        "dataset_path": str(dataset_path),
        "overall": compute_metrics(evaluated),
        "by_case_type": {name: compute_metrics(cases) for name, cases in sorted(groups.items())},
        "cases": evaluated,
    }


def write_markdown(report: dict, path) -> None:
    metrics = report["overall"]
    lines = [
        "# Evidence Sufficiency Evaluation", "",
        f"- Cases: {metrics['count']}",
        f"- Accuracy: {metrics['accuracy']:.4f}",
        f"- Precision: {metrics['precision']:.4f}",
        f"- Recall: {metrics['recall']:.4f}",
        f"- F1: {metrics['f1']:.4f}",
        f"- False Accept Rate: {metrics['false_accept_rate']:.4f}",
        f"- False Refusal Rate: {metrics['false_refusal_rate']:.4f}",
        f"- Confusion Matrix: `{json.dumps(metrics['confusion_matrix'])}`", "",
        "## By Case Type", "",
        "| type | count | accuracy | FAR | FRR |", "|---|---:|---:|---:|---:|",
    ]
    for name, item in report["by_case_type"].items():
        lines.append(f"| {name} | {item['count']} | {item['accuracy']:.4f} | {item['false_accept_rate']:.4f} | {item['false_refusal_rate']:.4f} |")
    lines.extend(["", "## Cases", ""])
    for case in report["cases"]:
        marker = "PASS" if case["expected_decision"] == case["predicted_decision"] else "FAIL"
        lines.append(f"- {marker} `{case['source_case_id']}` ({case['case_type']}): expected={case['expected_decision']}, predicted={case['predicted_decision']}; {case['reason']}")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate evidence sufficiency grader.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    args = parser.parse_args()
    report = evaluate(args.dataset)
    Path(args.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, args.md_out)
    print(f"Wrote {args.json_out} and {args.md_out}")


if __name__ == "__main__":
    main()
