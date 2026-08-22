import json
from pathlib import Path


def write_json_report(report: dict, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)


def write_markdown_report(report: dict, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Retrieval Evaluation Report",
        "",
        f"- Dataset: `{report['dataset_path']}`",
        f"- Mode: `{report['mode']}`",
        f"- Cases: `{report['overall']['count']}`",
        "",
        "## Overall",
        "",
        _metrics_table(report["overall"]),
        "",
        "## By Question Type",
        "",
    ]
    for question_type, metrics in report["by_question_type"].items():
        lines.extend([f"### {question_type}", "", _metrics_table(metrics), ""])
    lines.extend(["## Per Case", ""])
    for case in report["cases"]:
        first_hit = next((item["rank"] for item in case["retrieved"] if item["hit"]), None)
        lines.append(f"- `{case['id']}` ({case['question_type']}): first_hit_rank={first_hit}")
    path.write_text("\n".join(lines), encoding="utf-8")


def _metrics_table(metrics: dict) -> str:
    keys = [
        "recall@1",
        "recall@3",
        "recall@5",
        "recall@10",
        "mrr@10",
        "hitrate@1",
        "hitrate@3",
        "hitrate@5",
        "hitrate@10",
    ]
    header = "| metric | value |\n|---|---:|"
    rows = [f"| {key} | {metrics.get(key, 0):.4f} |" for key in keys]
    return "\n".join([header] + rows)
