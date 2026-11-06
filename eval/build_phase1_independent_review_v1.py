from __future__ import annotations

import json
import re
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "eval/datasets/phase1_cross_spec_independent_v1.jsonl"
RESULT = ROOT / "eval/reports/phase1_cross_spec_independent_v1_20261106.json"
REVIEW = ROOT / "eval/reports/phase1_cross_spec_independent_v1_20261106.answer_review.json"
REPORT = ROOT / "docs/PHASE1_INDEPENDENT_ACCEPTANCE_2026-11-06.md"

JUDGMENTS = {
    **{f"P1-IND-{i:03d}": ("pass", "答案要点、数值、单位、条件与来源一致。") for i in range(1, 11)},
    "P1-IND-011": ("false_refusal", "候选池已有两份规范的设计年限条文，但最终遗漏 GB 50157-2013 第1.0.8条。"),
    "P1-IND-012": ("false_refusal", "候选池已有两份规范的轨距条文，但最终遗漏 GB 55033-2022 第2.1.2条。"),
    "P1-IND-013": ("incomplete", "遗漏 GB 55033-2022 的直接新风规定，且 GB 50157-2013 必要条文未进入候选池。"),
    "P1-IND-014": ("pass", "三份规范的动力损失与救援要求逐项对比完整。"),
    "P1-IND-015": ("pass", "运行时长及100%制动载荷条件正确。"),
    "P1-IND-016": ("incomplete", "遗漏 GB 55033-2022 第2.1.16条关于公共厕所的要求。"),
    "P1-IND-017": ("false_refusal", "候选池已有两份规范的疏散平台条文，最终遗漏 GB 55033-2022 第3.0.10条。"),
    "P1-IND-018": ("false_refusal", "候选池已有必要条文，最终遗漏 DB11/T 995-2025 第10.2.1条。"),
    "P1-IND-019": ("pass", "两份规范的二氧化碳日平均浓度数值和单位正确。"),
    "P1-IND-020": ("false_refusal", "候选池已有必要条文，最终遗漏 DB11/T 995-2025 第17.5.6条。"),
    "P1-IND-021": ("false_refusal", "最终证据已包含必要表格条文，仍被充分性判断拒答。"),
    "P1-IND-022": ("pass", "A/B型车两档曲线半径的表格值正确。"),
    "P1-IND-023": ("pass", "混凝土强度、100年耐久年限和伸缩缝间距完整。"),
    "P1-IND-024": ("pass", "制动载荷、急停、附加制动器和传动安全要求完整。"),
    "P1-IND-025": ("false_refusal", "候选池已有三份同号条文，最终丢失其中两份后拒答。"),
    "P1-IND-026": ("clarify_pass", "明确要求选择范围，检索和模型调用均为0。"),
    "P1-IND-027": ("clarify_pass", "同号条文范围不明时要求澄清，检索和模型调用均为0。"),
    "P1-IND-028": ("refuse_pass", "缺少确定出入口总数所需项目条件，拒答正确。"),
    "P1-IND-029": ("refuse_pass", "规范不能给出具体项目2035年实际客流及列车数，拒答正确。"),
    "P1-IND-030": ("refuse_pass", "规范不能提供当天实测浓度，拒答正确。"),
}


def key(item: dict) -> tuple[str, str]:
    return f"{item.get('spec_id')}@{item.get('edition_id')}", str(item.get("article_id"))


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * fraction + 0.999999) - 1))]


def main() -> None:
    dataset = {row["id"]: row for row in map(json.loads, DATASET.read_text(encoding="utf-8").splitlines())}
    run = json.loads(RESULT.read_text(encoding="utf-8"))
    reviewed = []
    for result in run["questions"]:
        gold = dataset[result["id"]]
        candidates = [item for call in result["retrieval_calls"] for item in call["candidates"]]
        candidate_keys = {key(item) for item in candidates}
        final_keys = {key(item) for item in result["final_evidence"]}
        required = {(bid, article) for bid, articles in gold["expected_articles_by_spec"].items() for article in articles}
        allowed = set(result["bound_scope"])
        citations = set(re.findall(r"\[E(\d+)\]", result["answer"] or ""))
        legal_citations = not citations or all(1 <= int(number) <= len(result["final_evidence"]) for number in citations)
        verdict, note = JUDGMENTS[result["id"]]
        reviewed.append({
            "id": result["id"], "expected_behavior": gold["expected_behavior"],
            "actual_result_type": result["result_type"], "review_verdict": verdict,
            "review_note": note, "candidate_complete": required <= candidate_keys,
            "candidate_missing": sorted(required - candidate_keys), "final_evidence_complete": required <= final_keys,
            "final_missing": sorted(required - final_keys),
            "scope_violations": sorted({bid for bid, _ in candidate_keys | final_keys if bid not in allowed}),
            "citation_legal": legal_citations, "request_id": result["request_id"],
            "metrics": result["request_metrics"],
        })

    metrics = [item["metrics"] for item in reviewed]
    answerable = [item for item in reviewed if dataset[item["id"]]["answerable"]]
    generated = [item for item in reviewed if item["actual_result_type"] == "answer"]
    latency = [item["total_ms"] for item in metrics]
    tokens = [item["token_usage"]["total"] for item in metrics]
    cost_by_scope = {}
    scope_groups = {
        "single_spec": [item for item in reviewed if len(dataset[item["id"]]["requested_scope"].get("spec_ids", [])) == 1],
        "cross_spec": [item for item in reviewed if len(dataset[item["id"]]["requested_scope"].get("spec_ids", [])) > 1],
        "clarification": [item for item in reviewed if not dataset[item["id"]]["requested_scope"].get("spec_ids", [])],
    }
    for label, selected in scope_groups.items():
        selected_metrics = [item["metrics"] for item in selected]
        selected_latency = [item["total_ms"] for item in selected_metrics]
        selected_tokens = [item["token_usage"]["total"] for item in selected_metrics]
        cost_by_scope[label] = {
            "count": len(selected),
            "latency_ms_mean": statistics.mean(selected_latency),
            "latency_ms_p50": percentile(selected_latency, .5),
            "latency_ms_p95": percentile(selected_latency, .95),
            "tokens_mean": statistics.mean(selected_tokens),
            "tokens_p50": percentile(selected_tokens, .5),
            "tokens_p95": percentile(selected_tokens, .95),
            "model_calls": sum(item["model_calls"] for item in selected_metrics),
        }
    summary = {
        "total": 30, "service_errors": sum(bool(item.get("error_code")) for item in metrics),
        "scope_violations": sum(bool(item["scope_violations"]) for item in reviewed),
        "candidate_complete": sum(item["candidate_complete"] for item in answerable),
        "candidate_denominator": 25, "false_refusals": sum(item["review_verdict"] == "false_refusal" for item in reviewed),
        "complete_answers": sum(item["review_verdict"] == "pass" for item in answerable),
        "answerable_denominator": 25, "false_accepts": 0,
        "clarifications_without_calls": sum(item["review_verdict"] == "clarify_pass" and item["metrics"]["model_calls"] == 0 for item in reviewed),
        "generated_answers": len(generated),
        "legal_citations": sum(item["citation_legal"] for item in generated),
        "correct_final_behavior": 30 - sum(item["review_verdict"] == "false_refusal" for item in reviewed),
        "critical_numeric_unit_condition_errors": 0, "unsupported_material_claims": 0,
        "latency_ms": {"total": sum(latency), "mean": statistics.mean(latency), "p50": percentile(latency, .5), "p95": percentile(latency, .95)},
        "tokens": {"total": sum(tokens), "mean": statistics.mean(tokens), "p50": percentile(tokens, .5), "p95": percentile(tokens, .95)},
        "model_calls": sum(item["model_calls"] for item in metrics),
        "cost_by_scope": cost_by_scope,
        "verdict": "未通过"
    }
    REVIEW.write_text(json.dumps({"reviewer": "Codex (AI)", "summary": summary, "questions": reviewed}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Phase 1 跨规范独立验收报告", "", "日期：2026-11-06", "",
        "## 结论", "", "**未通过。** 运行完整且无服务错误，范围边界和拒答安全性通过；但错误拒答、最终行为正确率和答案完整性未达到预设门槛。该数据集从本次运行起转为已见回归集。", "",
        "## 预设门槛对照", "", "| 指标 | 实际 | 门槛 | 结果 |", "| --- | ---: | ---: | --- |",
        f"| 服务错误 | {summary['service_errors']} | 0 | 通过 |",
        f"| 范围/版本越界 | {summary['scope_violations']} | 0 | 通过 |",
        f"| 澄清且零检索/零模型 | {summary['clarifications_without_calls']}/2 | 2/2 | 通过 |",
        f"| 错误接受 | {summary['false_accepts']}/3 | 0/3 | 通过 |",
        f"| 错误拒答 | {summary['false_refusals']}/25 | ≤2/25 | **未通过** |",
        f"| 最终行为正确 | {summary['correct_final_behavior']}/30 | ≥28/30 | **未通过** |",
        f"| 完整答案 | {summary['complete_answers']}/25 | ≥23/25 | **未通过** |",
        f"| 必要条文候选池完整 | {summary['candidate_complete']}/25 | ≥23/25 | 通过 |",
        f"| 已生成答案引用合法 | {summary['legal_citations']}/{summary['generated_answers']} | 100% | 通过 |",
        "| 关键数值/单位/条件错误 | 0 | 0 | 通过 |", "| 证据外实质事实 | 0 | 0 | 通过 |", "",
        "## 失败归因", "", "- 7 道错误拒答：P1-IND-011、012、017、018、020、021、025。除 021 外均是必要条文已在候选池、但未完整保留到最终证据；021 的最终证据已完整，仍被充分性判断拒绝。", "- 2 道不完整回答：P1-IND-013 同时存在单一召回缺失和最终证据遗漏；P1-IND-016 为最终证据遗漏。", "- 因而主要瓶颈是候选池之后的证据覆盖与充分性判定，不是范围过滤；候选必要条文覆盖已达 24/25，越界为 0。", "",
        "## 成本", "", f"- 总耗时 {summary['latency_ms']['total']/1000:.1f}s；平均 {summary['latency_ms']['mean']/1000:.1f}s；p50 {summary['latency_ms']['p50']/1000:.1f}s；p95 {summary['latency_ms']['p95']/1000:.1f}s。", f"- 总 token {summary['tokens']['total']:,}；平均 {summary['tokens']['mean']:.0f}；p50 {summary['tokens']['p50']:,}；p95 {summary['tokens']['p95']:,}；模型调用 {summary['model_calls']} 次。", "- 本轮按预设规则只报告成本，不设硬门槛。", "",
        "| 范围组 | 题数 | 平均耗时 | p95耗时 | 平均token | p95 token | 模型调用 |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        *[f"| {label} | {value['count']} | {value['latency_ms_mean']/1000:.1f}s | {value['latency_ms_p95']/1000:.1f}s | {value['tokens_mean']:.0f} | {value['tokens_p95']:.0f} | {value['model_calls']} |" for label, value in cost_by_scope.items()], "",
        "## 发布判断", "", "不应把阶段 1 标为通过或对外宣称独立质量达标。可以保留当前范围隔离、版本绑定、引用合法性和安全拒答能力；下一轮应针对证据选择和充分性判定修复。任何依据本报告进行的修改都必须把这 30 题视为已见回归题，新的独立验收需另建并冻结数据。", "",
        "逐题机器证据与人工判定见 `eval/reports/phase1_cross_spec_independent_v1_20261106.answer_review.json`。"
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
