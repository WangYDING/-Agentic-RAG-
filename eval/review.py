"""Human review templates and comparable-baseline differences (offline)."""
import argparse
import json
from pathlib import Path


REVIEW_SCALE = {
    "evidence_support": {0: "unsupported or contradictory", 1: "partly supported", 2: "fully supported"},
    "completeness": {0: "critical requirements missing", 1: "some requirements missing", 2: "all required points covered"},
    "numeric_conditions": {0: "incorrect number/unit/condition", 1: "partially correct", 2: "correct; null if not applicable"},
    "unsupported_facts": {0: "material outside facts", 1: "minor outside facts", 2: "no unsupported factual additions"},
}


def review_template(report):
    return {
        "dataset_sha256": report.get("provenance", {}).get("dataset_sha256"),
        "report_schema_version": report.get("report_schema_version"),
        "rubric": REVIEW_SCALE,
        "instructions": "Only a human reviewer may approve. null means unreviewed or not applicable, never a passing score.",
        "cases": [{
            "id": case["id"], "request_id": case.get("request_id"),
            "question": case["question"], "expected_answerability": case["expected_answerability"],
            "requirements": case.get("required_requirements", []),
            "key_points": case.get("key_answer_points", []),
            "numeric_expectations": case.get("numeric_expectations", []),
            "answer": case["final_answer_or_refusal"],
            "evidence": case["final_evidence_refs"],
            "review": case["human_review"],
        } for case in report["cases"]],
    }


def compare_reports(baseline, candidate):
    b = baseline.get("provenance", {})
    c = candidate.get("provenance", {})
    same = all(b.get(key) and b.get(key) == c.get(key) for key in ("dataset_sha256", "pdf_sha256"))
    same = same and baseline.get("report_schema_version") == candidate.get("report_schema_version")
    same = same and baseline.get("evidence_top_n") == candidate.get("evidence_top_n")
    differences = {}
    if same:
        for section in ("initial_rank_metrics", "retrieval_evidence", "agent_decision", "citation_validation"):
            differences[section] = {
                key: value - baseline[section][key]
                for key, value in candidate.get(section, {}).items()
                if type(value) in (int, float) and type(baseline.get(section, {}).get(key)) in (int, float)
            }
    return {
        "comparable": bool(same),
        "reason": "same dataset/PDF hashes, report schema and evidence count" if same else "dataset/PDF identity or metric definition differs or is unknown; no numeric delta computed",
        "deltas": differences,
        "environment_and_model_caveat": "Review provenance for hardware and provider model drift; comparable data alone does not establish causality.",
        "release_decision": "pending_human_review_and_real_deployment_baselines",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate")
    parser.add_argument("--baseline")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    result = compare_reports(json.loads(Path(args.baseline).read_text(encoding="utf-8")), candidate) if args.baseline else review_template(candidate)
    with open(args.output, "x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
