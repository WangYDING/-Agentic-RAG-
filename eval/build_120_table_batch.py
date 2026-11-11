"""Fifteen table candidates transcribed after rendered original-page inspection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from eval.contract_v1 import TEST_CASE_VERSION, validate_test_case

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "data/spec_catalog.v1.json").read_text(encoding="utf-8"))
DOCS = {d["spec_id"]: d for d in CATALOG["documents"]}
OUT = ROOT / "eval/datasets/independent_120_tables_batch2.jsonl"

# spec, PDF page(s), article, table, question, facts, visually transcribed excerpt, tags
ROWS = [
    ("cn.beijing.db11t995", [51], "8.2.6", "表8.2.6", "DB11/T 995-2025 表8.2.6中，矩形隧道或双线马蹄形隧道（仰拱回填）采用现浇式轨道道床时，一般或中等减振和高等或特殊减振的轨道结构高度各是多少？", ["现浇式、一般或中等减振为560mm", "现浇式、高等或特殊减振为750mm", "适用对象为矩形隧道或双线马蹄形隧道（仰拱回填）"], "矩形隧道、双线马蹄形隧道（仰拱回填）：现浇式轨道道床，一般或中等减振560，高等或特殊减振750（mm）。", []),
    ("cn.beijing.db11t995", [69], "10.10.3", "表10.10.3", "DB11/T 995-2025 表10.10.3把换乘路径沿路设施瓶颈处的最大等待人数分为哪三个评价等级？", ["小于50人为良好", "50～200人为一般", "大于200人为差", "评价范围为换乘路径沿路设施（站台、楼扶梯）"], "瓶颈设施最大等待人数（人）：<50 良好；50～200 一般；>200 差。", []),
    ("cn.beijing.db11t995", [173], "19.2.13", "表19.2.13", "DB11/T 995-2025 表19.2.13对提升高度 H 小于10m与不小于10m的自动扶梯，上导轨转弯半径分别规定了什么下限？", ["H<10m时上导轨转弯半径不小于2600mm", "H≥10m时上导轨转弯半径不小于3600mm"], "H<10m：上导轨转弯半径≥2600mm；H≥10m：≥3600mm。", []),
    ("cn.beijing.db11t995", [207], "27.6.13", "表27.6.13", "DB11/T 995-2025 表27.6.13中，月检库与临修库的车体与侧墙之间通道宽度最小值分别是多少？", ["月检库不小于3.0m", "临修库不小于3.5m", "所问项目是车体与侧墙之间通道宽度"], "车体与侧墙之间通道宽度（m）：月检库3.0；临修库3.5。", []),
    ("cn.beijing.db11t995", [216], "29.1.2", "表29.1.2", "DB11/T 995-2025 表29.1.2对公交换乘场站和公交车停靠站距车站出入口的换乘距离分别怎么要求？", ["公交车停靠站一般情况下不大于30m，条件受限时不大于50m", "公交换乘场站不大于100m", "公交换乘场站应结合需求及规划用地条件设置"], "公交车停靠站：一般情况下≤30m，条件受限时≤50m；公交换乘场站：≤100m。", []),
    ("cn.gb55033", [14], "3.0.5", "表3.0.5-1", "GB 55033-2022 表3.0.5-1中，非顶部授电、无安装设备时，市域快轨与地铁上部和侧面建筑限界距设备限界的最小安全间隙分别是多少？", ["市域快轨300mm", "地铁200mm", "前提为非顶部授电且无安装设备；部位为上部和侧面"], "非顶部授电且无安装设备：上部和侧面最小安全间隙，地铁200mm；市域快轨300mm。", []),
    ("cn.gb55033", [15], "3.0.5", "表3.0.5-2", "GB 55033-2022 表3.0.5-2中，车辆存在低于运行面以下部分且无安装设备时，跨座式单轨、中低速磁浮和 AGT 自动导向的下部最小安全间隙各是多少？", ["跨座式单轨100mm", "中低速磁浮100mm", "AGT自动导向100mm", "前提为车辆有低于运行面以下部分且无安装设备；地铁栏为空，不外推"], "下部最小安全间隙（mm）：跨座式单轨100、中低速磁浮100、AGT自动导向100；地铁栏为—。", []),
    ("cn.gb55033", [15], "3.0.6", "表3.0.6", "GB 55033-2022 表3.0.6中，两线间没有建（构）筑物时，市域快轨在140km/h和160km/h速度等级的设备限界之间安全间隙各是多少？", ["市域快轨140km/h为150mm", "市域快轨160km/h为200mm", "前提为双线区间两线间无建（构）筑物"], "市域快轨：140km/h 150mm；160km/h 200mm；双线区间两线间无建（构）筑物。", []),
    ("cn.gb55033", [16, 17], "3.0.8", "表3.0.8", "GB 55033-2022 表3.0.8及续表中，空车静止的地铁与悬浮静止的中低速磁浮，站台面和客室地板面的高差上限分别是多少？", ["地铁空车静止时不大于50mm", "中低速磁浮悬浮静止时不大于30mm", "任何工况下站台面不应高于客室地板面"], "地铁／空车静止：≤50mm；中低速磁浮／悬浮静止：≤30mm；续表跨PDF页16—17。", ["跨页表格"]),
    ("cn.gb55033", [17], "3.0.9", "表3.0.9", "GB 55033-2022 表3.0.9对直线车站市域快轨列车停站和越行时，站台屏蔽门与车体轮廓最宽处的间隙分别如何规定？", ["市域快轨停站不大于130mm", "市域快轨越行为150mm（表列值）", "适用直线车站屏蔽门与车体轮廓最宽处"], "市域快轨：停站≤130mm；越行150mm；直线车站屏蔽门与车体轮廓最宽处。", []),
    ("cn.gb50157", [73], "8.2.4", "表8.2.4", "仅按 GB 50157-2013 表8.2.4，曲线半径 R 不大于600m和大于600m且不大于800m时，路基面外侧加宽值分别是多少？", ["R≤600m加宽0.5m", "600m<R≤800m加宽0.4m", "单线加宽在曲线外侧，双线在外股曲线外侧"], "R≤600m：0.5m；600<R≤800m：0.4m；路基面外侧加宽值。", []),
    ("cn.gb50157", [113], "11.6.1", "表11.6.1", "仅按 GB 50157-2013 表11.6.1，盾构隧道管片与水中环境中的其他钢筋混凝土结构，最大计算裂缝宽度允许值分别是多少？", ["盾构隧道管片0.2mm", "其他结构水中环境为0.3mm"], "盾构隧道管片0.2mm；其他结构水中环境0.3mm；表注另有限制，应核对适用条件。", ["表注"]),
    ("cn.gb50157", [128], "12.2.1", "表12.2.1", "仅按 GB 50157-2013 表12.2.1，结构埋置深度 h 小于20m时，现浇混凝土结构与装配式钢筋混凝土结构的设计抗渗等级分别是多少？", ["h<20m现浇结构P8", "h<20m装配式钢筋混凝土结构P10"], "h<20m：现浇混凝土结构P8；装配式钢筋混凝土结构P10。", []),
    ("cn.gb50157", [260], "27.2.3", "表27.2.3", "仅按 GB 50157-2013 表27.2.3，车辆架修的走行里程、时间间隔和检修时间指标分别是多少？表注对检修时间如何说明？", ["架修走行里程60万km", "架修时间间隔5年", "架修检修时间20d", "表注称检修时间按部件互换修确定；时间间隔可用于可研阶段指标"], "架修：60万km、5年、20d；注1检修时间按部件互换修确定，注3可行性研究报告阶段可采用时间间隔指标。", ["表注"]),
    ("cn.gb50157", [293], "29.3.2", "表29.3.2", "仅按 GB 50157-2013 表29.3.2，地上线穿越1类声环境功能区的敏感点时，昼间与夜间环境噪声限值分别是多少？", ["1类声环境功能区敏感点昼间55dBA", "夜间45dBA", "无法满足标准要求时应采取降噪措施"], "1类：居住、医疗、文教、科研区的敏感点；昼间55dBA、夜间45dBA。", []),
]
NUMERIC = {
    1: [("560", "mm", "=", "现浇式、一般或中等减振、指定隧道形式"), ("750", "mm", "=", "现浇式、高等或特殊减振、指定隧道形式")],
    2: [("50", "人", "<", "瓶颈等待人数良好"), ("50～200", "人", "区间", "一般"), ("200", "人", ">", "差")],
    3: [("2600", "mm", ">=", "提升高度H<10m，上导轨"), ("3600", "mm", ">=", "H≥10m，上导轨")],
    4: [("3.0", "m", ">=", "月检库车体与侧墙通道"), ("3.5", "m", ">=", "临修库车体与侧墙通道")],
    5: [("30", "m", "<=", "公交车停靠站一般"), ("50", "m", "<=", "公交车停靠站条件受限"), ("100", "m", "<=", "公交换乘场站")],
    6: [("300", "mm", "最小", "市域快轨，非顶部授电且无设备，上部和侧面"), ("200", "mm", "最小", "地铁，同一前提")],
    7: [("100", "mm", "最小", "跨座式单轨、中低速磁浮、AGT自动导向，下部且无设备")],
    8: [("150", "mm", "安全间隙", "市域快轨140km/h，双线间无建构筑物"), ("200", "mm", "安全间隙", "市域快轨160km/h，同一前提")],
    9: [("50", "mm", "<=", "地铁空车静止"), ("30", "mm", "<=", "中低速磁浮悬浮静止")],
    10: [("130", "mm", "<=", "市域快轨直线站台停站"), ("150", "mm", "表列值", "市域快轨直线站台越行")],
    11: [("0.5", "m", "=", "R≤600m路基面外侧加宽"), ("0.4", "m", "=", "600m<R≤800m路基面外侧加宽")],
    12: [("0.2", "mm", "最大允许", "盾构隧道管片"), ("0.3", "mm", "最大允许", "其他钢筋混凝土结构的水中环境")],
    13: [("P8", "抗渗等级", "设计等级", "埋深h<20m现浇结构"), ("P10", "抗渗等级", "设计等级", "h<20m装配式结构")],
    14: [("60", "万km", "指标", "车辆架修走行里程"), ("5", "年", "指标", "架修时间间隔"), ("20", "d", "指标", "架修检修时间；表注")],
    15: [("55", "dBA", "限值", "1类声环境敏感点昼间"), ("45", "dBA", "限值", "1类声环境敏感点夜间")],
}


def make(index: int, row: tuple) -> dict:
    spec, pages, article, table, question, points, excerpt, tags = row
    doc = DOCS[spec]
    refs = [{"evidence_id": f"T{index:03d}-P{page}", "document_id": spec, "document_version": doc["edition_id"],
             "page": page, "article": article, "table": table, "quote": excerpt} for page in pages]
    facts = [{"fact_id": f"F{n}", "description": fact} for n, fact in enumerate(points, 1)]
    evidence_groups = []
    for fact_index, fact in enumerate(facts, 1):
        # The continuation row is on PDF page 17; the first row and preamble are on 16.
        fact_refs = [refs[1 if fact_index == 2 else 0]] if index == 9 else refs
        evidence_groups.append({"fact_id": fact["fact_id"], "alternatives": [{"scheme_id": "original-table", "all_of": fact_refs}]})
    return {
        "schema_version": TEST_CASE_VERSION, "case_id": f"I120-T{index:03d}", "dataset_role": "independent",
        "question": question, "query_scope": {"spec_ids": [spec], "edition_ids": [doc["edition_id"]]},
        "expected_action": "answer", "reference_answer": "；".join(points) + "。", "necessary_facts": facts,
        "evidence_groups": evidence_groups,
        "main_category": "表格查询", "tags": tags + ["版本筛选"], "fact_group_id": f"{spec}@{doc['edition_id']}:{table}",
        "numeric_constraints": [{"value": value, "unit": unit, "comparison": comparison, "condition": condition}
                                for value, unit, comparison, condition in NUMERIC[index]],
        "source_pdf_sha256": doc["pdf_sha256"], "source_excerpt_visual_transcription": excerpt,
        "source_review": {"reviewer": "Codex AI", "reviewer_type": "ai", "method": "rendered original PDF page inspection",
                          "pages": pages, "human_approved": False},
        "annotation_review": {"status": "pending", "reviewer_type": "ai", "reviewer": "Codex AI (draft author)",
                              "reviewed_at": None, "human_approved": False,
                              "notes": "Rendered PDF page inspected; full semantic overlap, table notes, numerical boundary and human review pending."},
    }


def main() -> None:
    for doc in DOCS.values():
        if hashlib.sha256((ROOT / doc["local_pdf_path"]).read_bytes()).hexdigest() != doc["pdf_sha256"]:
            raise ValueError(f"source changed: {doc['standard_code']}")
    cases = [make(i, row) for i, row in enumerate(ROWS, 1)]
    for case in cases:
        validate_test_case(case)
    OUT.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases), encoding="utf-8")
    print(f"{len(cases)} table candidates -> {OUT}")


if __name__ == "__main__":
    main()
