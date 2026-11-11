"""Numeric and direct candidates from selected original PDF pages."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf

from eval.contract_v1 import TEST_CASE_VERSION, validate_test_case

ROOT = Path(__file__).resolve().parents[1]
DOCS = {d["spec_id"]: d for d in json.loads((ROOT / "data/spec_catalog.v1.json").read_text(encoding="utf-8"))["documents"]}
OUT = ROOT / "eval/datasets/independent_120_numeric_direct_batch5.jsonl"

# spec, PDF page, article, category, question, necessary facts, numeric constraints
SEEDS = [
    ("cn.beijing.db11t995", 55, "9.2.2", "数值、单位与条件", "DB11/T 995-2025 对有砟轨道路基面横坡与无砟轨道支承层外侧横向排水坡分别怎么要求？", ["有砟轨道路基面为三角形路拱，横坡不小于4%，曲线加宽仍保持三角形", "无砟宜为平面，支承层外侧宜设4%横向排水坡"], [("4", "%", ">=", "有砟路拱"), ("4", "%", "宜为", "无砟支承层外侧")]),
    ("cn.beijing.db11t995", 128, "16.2.15", "数值、单位与条件", "DB11/T 995-2025 对外部电源引入点功率因数下限和过补偿分别怎么规定？", ["引入点功率因数不低于0.9", "应避免过补偿"], [("0.9", "无量纲", ">=", "外部电源引入点")]),
    ("cn.beijing.db11t995", 173, "19.2.9", "数值、单位与条件", "DB11/T 995-2025 对自动扶梯和自动人行道节能运行速度相对于名义速度的上限是多少？", ["节能运行速度不大于各自名义速度的20%"], [("20", "%名义速度", "<=", "扶梯及人行道节能运行")]),
    ("cn.beijing.db11t995", 173, "19.2.10", "数值、单位与条件", "DB11/T 995-2025 对自动扶梯与自动人行道的倾斜角度分别规定了什么上限？", ["自动扶梯不应大于30°", "自动人行道不宜大于6°；注意应与宜的语气差别"], [("30", "°", "不应大于", "自动扶梯"), ("6", "°", "不宜大于", "自动人行道")]),
    ("cn.beijing.db11t995", 72, "11.1.4", "数值、单位与条件", "DB11/T 995-2025 对高架桥梁吊杆索、排水系统和球形钢支座的设计工作年限分别规定了什么下限？", ["吊杆索、斜拉索及伸缩缝不低于30年", "排水系统不低于15年", "球形钢支座不低于60年"], [("30", "年", ">=", "吊杆索"), ("15", "年", ">=", "排水系统"), ("60", "年", ">=", "球形钢支座")]),
    ("cn.beijing.db11t995", 55, "9.3.2", "数值、单位与条件", "DB11/T 995-2025 对无砟轨道路基基床表层和底层的最小厚度分别是多少？", ["表层不小于0.3m", "底层不小于1.5m"], [("0.3", "m", ">=", "无砟基床表层"), ("1.5", "m", ">=", "无砟基床底层")]),
    ("cn.beijing.db11t995", 173, "19.2.12", "数值、单位与条件", "DB11/T 995-2025 中，扶梯名义速度为0.5m/s与0.65m/s时，上下水平梯级数量分别至少多少块？", ["0.5m/s时上、下各不少于3块", "0.65m/s时上、下各不少于4块"], [("3", "块", ">=", "名义速度0.5m/s上下各"), ("4", "块", ">=", "名义速度0.65m/s上下各")]),
    ("cn.gb55033", 18, "4.1.2", "数值、单位与条件", "GB 55033-2022 对车辆最高运行速度与线路设计最高运行速度的比值下限是什么？", ["车辆最高运行速度不小于线路设计最高运行速度的1.1倍"], [("1.1", "倍", ">=", "车辆最高运行速度/线路设计最高运行速度")]),
    ("cn.gb55033", 18, "4.2.2", "数值、单位与条件", "GB 55033-2022 对车门有效净高度和自地板面计算的立席处净高分别有什么下限？", ["车门有效净高度不小于1.80m", "立席处净高不小于1.90m"], [("1.80", "m", ">=", "车门有效净高"), ("1.90", "m", ">=", "立席处距地板净高")]),
    ("cn.gb55033", 23, "5.3.3", "数值、单位与条件", "GB 55033-2022 对正线曲线和车站内曲线的未平衡横向加速度分别规定什么上限？车站内曲线超高还有什么上限？", ["正线曲线未平衡横向加速度不超过0.4m/s²", "车站内曲线未平衡横向加速度不超过0.3m/s²", "车站内曲线超高不超过15mm"], [("0.4", "m/s²", "<=", "正线曲线"), ("0.3", "m/s²", "<=", "车站内曲线"), ("15", "mm", "<=", "车站内曲线超高")]),
    ("cn.gb55033", 25, "5.4.4", "数值、单位与条件", "GB 55033-2022 对有轨电车岛式站台和侧式站台宽度分别规定了什么下限？", ["有轨电车岛式站台不小于5m", "有轨电车侧式站台不小于3m"], [("5", "m", ">=", "有轨电车岛式站台"), ("3", "m", ">=", "有轨电车侧式站台")]),
    ("cn.gb55033", 17, "3.0.11", "数值、单位与条件", "GB 55033-2022 对车辆基地库内检修高平台及安全栅栏距车辆轮廓的水平横向间隙规定什么范围？", ["高平台及安全栅栏水平横向间隙限定在80mm～120mm", "低平台采用车站停站站台限界"], [("80～120", "mm", "闭区间", "车辆基地检修高平台与安全栅栏")]),
    ("cn.gb50157", 73, "8.2.3", "数值、单位与条件", "GB 50157-2013 对路肩埋有设备和未埋设备时，路堤及路堑路肩宽度分别有什么下限？", ["埋有设备不小于0.6m", "无埋设设备不小于0.4m"], [("0.6", "m", ">=", "路肩埋设备"), ("0.4", "m", ">=", "路肩无埋设设备")]),
    ("cn.gb50157", 73, "8.2.5", "数值、单位与条件", "GB 50157-2013 对路基基床表层、底层厚度及计算起点分别如何规定？", ["表层不小于0.5m", "底层不小于1.5m", "基床厚度以路肩施工高程为计算起点"], [("0.5", "m", ">=", "基床表层"), ("1.5", "m", ">=", "基床底层")]),
    ("cn.gb50157", 128, "12.2.4", "数值、单位与条件", "GB 50157-2013 对防水混凝土环境温度上限，以及侵蚀性地层中现浇和装配式钢筋混凝土结构氯离子扩散系数分别有什么限制？", ["环境温度不得高于80℃", "侵蚀性地层防水混凝土氯离子扩散系数不宜大于4×10^-12m²/s", "装配式钢筋混凝土结构不宜大于3×10^-12m²/s"], [("80", "℃", "<=", "防水混凝土环境温度"), ("4×10^-12", "m²/s", "不宜大于", "侵蚀性地层防水混凝土"), ("3×10^-12", "m²/s", "不宜大于", "侵蚀性地层装配式结构")]),
    ("cn.gb50157", 161, "15.1.26", "数值、单位与条件", "GB 50157-2013 对低压配电电压采用什么数值？", ["低压配电电压采用220V/380V"], [("220/380", "V", "采用", "低压配电")]),
    ("cn.gb50157", 128, "12.2.5", "数值、单位与条件", "GB 50157-2013 对防水混凝土结构底板垫层的强度等级及一般、软弱土层最小厚度分别有什么要求？", ["垫层混凝土强度等级不小于C15", "一般情况厚度不小于100mm", "软弱土层厚度不小于150mm"], [("C15", "强度等级", ">=", "底板垫层"), ("100", "mm", ">=", "一般底板垫层"), ("150", "mm", ">=", "软弱土层底板垫层")]),
    ("cn.beijing.db11t995", 238, "31.1.1", "单规范直接查询", "DB11/T 995-2025 对沿线环境敏感点应依据什么资料采取环境保护措施？", ["依据环境敏感点分布、环评报告及文物保护有关要求采取措施"], []),
    ("cn.gb55033", 32, "6.3.6", "单规范直接查询", "GB 55033-2022 当联锁条件不符、存在敌对进路时，联锁设备应如何约束进路开通？", ["保证道岔、信号机和区段联锁关系正确", "联锁条件不符不应开通进路", "敌对进路相互照查、不得同时开通"], []),
    ("cn.gb55033", 31, "6.2.4", "单规范直接查询", "GB 55033-2022 对地下车站和区间通信电缆、光缆的防护层性能有什么要求？", ["防护层阻燃、低烟、无卤、防腐蚀、防鼠咬", "符合杂散电流腐蚀防护要求"], []),
    ("cn.gb50157", 242, "24.1.3", "单规范直接查询", "GB 50157-2013 对控制中心位置的选定提出哪些倾向？", ["宜靠近线路和车站", "接近监控对象中心地带", "位于便于运营管理的区域"], []),
    ("cn.gb50157", 249, "25.1.3", "单规范直接查询", "GB 50157-2013 对室外设置的自动扶梯及严寒地区的防护如何规定？", ["室外自动扶梯选室外型产品、上下平台设防滑措施", "严寒地区配备防冰雪积聚设施"], []),
    ("cn.beijing.db11t995", 106, "13.1.3", "数值、单位与条件", "DB11/T 995-2025 对桥面、建筑屋面及室内工程的防水设计工作年限分别规定什么下限？", ["桥面防水不低于15年", "建筑屋面防水不低于20年", "室内防水不低于25年"], [("15", "年", ">=", "桥面"), ("20", "年", ">=", "建筑屋面"), ("25", "年", ">=", "室内")]),
    ("cn.beijing.db11t995", 72, "11.1.15", "数值、单位与条件", "DB11/T 995-2025 对一般跨河桥梁与技术复杂、修复困难的大跨度桥梁的洪水频率分别如何规定？", ["跨河桥跨布置满足1/100设计洪水频率", "技术复杂、修复困难大跨度桥梁或特大桥按1/300洪水频率验算", "若观测或调查洪水频率小于前述值，采用观测或调查值"], [("1/100", "设计洪水频率", "满足", "一般跨河桥跨"), ("1/300", "洪水频率", "验算", "复杂大跨度桥或特大桥")]),
    ("cn.gb55033", 25, "5.4.7", "数值、单位与条件", "GB 55033-2022 对车站无障碍专用检票通道的数量和净宽有什么下限？", ["至少一处无障碍专用检票通道", "净宽不小于900mm"], [("1", "处", ">=", "无障碍专用检票通道"), ("900", "mm", ">=", "通道净宽")]),
    ("cn.gb50157", 168, "15.3.27", "数值、单位与条件", "GB 50157-2013 对地上区段架空接触网避雷器间距及另外两处设置位置怎么要求？", ["地上区段避雷器间距不大于300m", "隧道入口和为地上线供电的隔离开关处设置避雷器"], [("300", "m", "<=", "地上区段避雷器间距")]),
]


def page_text(doc: dict, page: int) -> str:
    if doc.get("ocr_artifact_path"):
        return json.loads((ROOT / doc["ocr_artifact_path"] / "pages" / f"{page:04}.json").read_text(encoding="utf-8"))["text"]
    return pymupdf.open(ROOT / doc["local_pdf_path"])[page - 1].get_text(sort=True)


def clause_excerpt(text: str, article: str) -> str:
    match = re.search(r"(?m)^\s*" + re.escape(article) + r"\s*", text)
    if not match:
        # Watermarks can precede the article number on the same extracted line.
        match = re.search(r"(?<![\d.])" + re.escape(article) + r"\s*", text)
    if not match:
        raise ValueError(f"article missing from PDF page: {article}")
    tail = text[match.end():]
    following = re.search(r"(?m)^\s*\d{1,2}\.\d{1,2}\.\d{1,3}\s*", tail)
    return (tail[:following.start() if following else 450]).strip()[:700]


def make(i: int, seed: tuple) -> dict:
    spec, page, article, category, question, points, numeric = seed
    doc = DOCS[spec]
    excerpt = clause_excerpt(page_text(doc, page), article)
    evidence = {"evidence_id": f"N{i:03d}-E1", "document_id": spec, "document_version": doc["edition_id"],
                "page": page, "article": article, "quote": excerpt}
    facts = [{"fact_id": f"F{n}", "description": fact} for n, fact in enumerate(points, 1)]
    return {"schema_version": TEST_CASE_VERSION, "case_id": f"I120-N{i:03d}", "dataset_role": "independent",
            "question": question, "query_scope": {"spec_ids": [spec], "edition_ids": [doc["edition_id"]]},
            "expected_action": "answer", "reference_answer": "；".join(points) + "。", "necessary_facts": facts,
            "evidence_groups": [{"fact_id": f["fact_id"], "alternatives": [{"scheme_id": "article", "all_of": [evidence]}]} for f in facts],
            "main_category": category, "tags": ["版本筛选"], "fact_group_id": f"{spec}@{doc['edition_id']}:{article}",
            "numeric_constraints": [{"value": val, "unit": unit, "comparison": comp, "condition": condition} for val, unit, comp, condition in numeric],
            "source_pdf_sha256": doc["pdf_sha256"], "source_excerpt": excerpt,
            "annotation_review": {"status": "pending", "reviewer_type": "ai", "reviewer": "Codex AI (draft author)",
                                  "reviewed_at": None, "human_approved": False,
                                  "notes": "Source page text checked; full visual/semantic and human audit pending."}}


def main() -> None:
    cases = [make(i, seed) for i, seed in enumerate(SEEDS, 1)]
    for case in cases:
        validate_test_case(case)
    OUT.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases), encoding="utf-8")
    print(f"{len(cases)} numeric/direct candidates -> {OUT}")


if __name__ == "__main__":
    main()
