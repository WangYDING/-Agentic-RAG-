"""Hand-authored source-backed first batch; never calls the candidate RAG."""
from __future__ import annotations

import json
from pathlib import Path

from eval.contract_v1 import TEST_CASE_VERSION, validate_test_case


BASE = Path(__file__).resolve().parents[1]
LEADS = json.loads((BASE / "eval/datasets/independent_120_source_leads.json").read_text(encoding="utf-8"))["leads"]
LOOKUP = {(x["document_id"], x["article"]): x for x in LEADS}
OUT = BASE / "eval/datasets/independent_120_candidates_batch1.jsonl"

# Each answer and fact was transcribed from the indicated original PDF/OCR page.
# These are deliberately pending independent PDF-page/semantic review.
SEEDS = [
    ("cn.beijing.db11t995", "3.0.3", "单规范直接查询", "DB11/T 995-2025 对线网中的换乘车站规划、设计和建设有什么要求？", ["换乘车站统一规划、同步设计", "同期批复宜同期建设", "与远期线换乘应预留工程实施条件"]),
    ("cn.beijing.db11t995", "9.1.2", "单规范直接查询", "DB11/T 995-2025 要求依据哪些因素确定路肩高程，并满足什么稳定性要求？", ["综合洪水频率、洪水位或地表积水水位及冻胀因素确定", "满足水和温度稳定性要求"]),
    ("cn.beijing.db11t995", "16.1.4", "单规范直接查询", "DB11/T 995-2025 如何划分牵引用电负荷与动力照明等用电负荷的等级？", ["牵引用电负荷为一级", "动力照明等分一级、二级、三级"]),
    ("cn.beijing.db11t995", "29.1.1", "单规范直接查询", "DB11/T 995-2025 对车站交通接驳设施的设计优先顺序如何规定？", ["步行", "非机动车", "公交车", "出租车（含小汽车）临停", "小汽车停车；上述顺序为宜采用的优先顺序"]),
    ("cn.beijing.db11t995", "8.1.5", "单规范直接查询", "DB11/T 995-2025 对轨道结构设计中的智能化配备提出什么要求？", ["结合智能化要求", "配备必要的监测、检测、维修设备"]),
    ("cn.beijing.db11t995", "14.1.4", "单规范直接查询", "DB11/T 995-2025 选择地下线路空调系统制式时应考虑哪些因素，如何确定？", ["结合线路运力、气候条件、人员舒适性、运行及维护费用等", "进行综合技术经济比较确定"]),
    ("cn.gb55033", "6.1.7", "数值、单位与条件", "GB 55033-2022 中，变电所配电装置超过什么长度时柜后通道要设几个出口？低压装置后通道出口间距上限是多少？", ["配电装置长度大于6m（严格大于）", "柜（屏）后通道设2个出口", "低压装置后通道出口之间距离不大于15m"]),
    ("cn.gb55033", "5.3.4", "数值、单位与条件", "GB 55033-2022 对钢轮钢轨系统正线、配线、试车线和牵出线尽端车挡的撞击荷载能力如何规定？", ["轨道尽端应设置车挡", "列举线路的车挡可承受列车以25km/h速度撞击时的冲击荷载"]),
    ("cn.gb55033", "5.3.11", "数值、单位与条件", "GB 55033-2022 对有砟轨道线路工后沉降量、路桥过渡段沉降量及沉降速率的上限分别是什么？", ["有砟线路工后沉降不大于200mm", "路桥过渡段不大于100mm", "沉降速率不大于50mm/年"]),
    ("cn.gb55033", "6.2.5", "单规范直接查询", "GB 55033-2022 对光缆引入室内时的接头及金属护层、加强芯有什么要求？", ["应做绝缘接头", "室内外金属护层及金属加强芯断开并彼此绝缘"]),
    ("cn.gb55033", "6.3.8", "单规范直接查询", "GB 55033-2022 如何按车载防护和车内信号配置确定主体信号？地面主体信号熄灭时如何处理？", ["配置列车自动防护设备和车内信号装置时以车内信号为主体", "未配置时以地面信号为主体", "地面主体信号熄灭视为禁止信号"]),
    ("cn.gb55033", "4.3.4", "单规范直接查询", "GB 55033-2022 对客室侧门没有全部关闭时的列车启动与隔离运行如何规定？", ["侧门未全部关闭不能正常启动", "允许隔离功能在规定的限速模式下运行"]),
    ("cn.gb50157", "8.1.5", "单规范直接查询", "GB 50157-2013 对取土场、弃土场的边坡稳定和挡护提出什么要求？", ["不得影响山体或边坡稳定", "采取确保边坡稳定且符合环保要求的挡护措施"]),
    ("cn.gb50157", "15.1.3", "单规范直接查询", "仅按 GB 50157-2013，地铁外部电源方案的设计依据及可采用的供电方式是什么？", ["依据线网规划、城市电网现状及规划、城市规划", "可采用集中式、分散式或混合式供电"]),
    ("cn.gb50157", "25.1.7", "单规范直接查询", "GB 50157-2013 对自动扶梯和自动人行道机坑排水及扶梯油水分离设备有什么规定？", ["机坑内应采用重力流排水", "无重力流条件时机坑外设集水坑和排水设施", "自动扶梯配置油水分离设备"]),
    ("cn.gb50157", "23.1.2", "单规范直接查询", "GB 50157-2013 对门禁系统的基本功能与按运营需要增设的功能如何规定？", ["具有出入口监控和安全管理功能", "可根据运营管理需要设置其他功能"]),
    ("cn.gb50157", "17.1.3", "单规范直接查询", "仅按 GB 50157-2013，ATP 系统、设备和电路的安全原则及设备认证要求是什么？", ["ATP系统、设备及电路符合故障导向安全原则", "采用的安全系统、设备经过安全认证"]),
    ("cn.gb50157", "7.1.4", "单规范直接查询", "GB 50157-2013 对轨道结构部件选型的维修、标准化及全线统一提出什么要求？", ["满足使用功能前提下实现少维修、标准化、系列化", "宜统一全线轨道部件"]),
    ("cn.beijing.db11t995", "27.1.1", "单规范直接查询", "DB11/T 995-2025 对车辆基地的基本组成及可按需设置的设施分别有什么规定？", ["基本组成含车辆运用、检修、综合维修及必要办公生活设施", "按需要可设置物资总库和培训设施"]),
    ("cn.beijing.db11t995", "3.0.1", "单规范直接查询", "DB11/T 995-2025 对工程设计与城市及线网规划的关系有什么要求？", ["符合城市总体、轨道交通线网及近期建设规划等", "线路总体布局注重服务中心城区和规划重要地区及客流效益"]),
    ("cn.beijing.db11t995", "26.1.1", "单规范直接查询", "DB11/T 995-2025 对信息化建设的原则和系统特性如何要求？", ["统一规划、统一标准、资源共享", "安全、可靠、先进、可扩展"]),
    ("cn.gb55033", "6.1.8", "单规范直接查询", "GB 55033-2022 对地下使用的电气设备和材料选型提出哪些性能要求？", ["选择低损耗、低噪声、防潮、无自爆、低烟、无卤、阻燃或耐火的定型产品"]),
    ("cn.gb50157", "14.1.1", "单规范直接查询", "GB 50157-2013 对地铁给水系统供水性能和节水原则有哪些要求？", ["满足生产、生活、消防用水的水量、水压、水质", "坚持综合利用和节约用水"]),
]
NUMERIC = {
    7: [
        {"value": "6", "unit": "m", "comparison": ">", "condition": "变电所配电装置长度；触发柜后通道2个出口"},
        {"value": "2", "unit": "个", "comparison": "=", "condition": "配电装置长度大于6m时柜（屏）后通道出口"},
        {"value": "15", "unit": "m", "comparison": "<=", "condition": "低压电气装置后面通道的出口间距"},
    ],
    8: [{"value": "25", "unit": "km/h", "comparison": "design_impact_speed", "condition": "钢轮钢轨系统正线、配线、试车线及牵出线的车挡"}],
    9: [
        {"value": "200", "unit": "mm", "comparison": "<=", "condition": "有砟轨道线路工后沉降"},
        {"value": "100", "unit": "mm", "comparison": "<=", "condition": "有砟轨道路桥过渡段"},
        {"value": "50", "unit": "mm/年", "comparison": "<=", "condition": "有砟轨道沉降速率"},
    ],
}


def make_case(index: int, seed: tuple) -> dict:
    spec, article, category, question, points = seed
    source = LOOKUP[spec, article]
    edition = source["document_version"]
    evidence = {
        "evidence_id": f"C{index:03d}-E1", "document_id": spec,
        "document_version": edition, "page": source["pdf_page"], "article": article,
        "quote": source["source_excerpt_unverified"],
    }
    facts = [{"fact_id": f"F{i}", "description": point} for i, point in enumerate(points, 1)]
    return {
        "schema_version": TEST_CASE_VERSION, "case_id": f"I120-C{index:03d}",
        "dataset_role": "independent", "question": question,
        "query_scope": {"spec_ids": [spec], "edition_ids": [edition]},
        "expected_action": "answer", "reference_answer": "；".join(points) + "。",
        "necessary_facts": facts,
        "evidence_groups": [{"fact_id": f["fact_id"], "alternatives": [{"scheme_id": "source-page-v1", "all_of": [evidence]}]} for f in facts],
        "main_category": category, "tags": ["版本筛选"], "fact_group_id": f"{spec}@{edition}:{article}",
        "source_pdf_sha256": source["pdf_sha256"], "source_excerpt": source["source_excerpt_unverified"],
        "numeric_constraints": NUMERIC.get(index, []), "reason_for_refusal_or_clarification": None,
        "annotation_review": {"status": "pending", "reviewer_type": "ai", "reviewer": "Codex AI (draft author)",
                              "reviewed_at": None, "human_approved": False,
                              "notes": "Grounded in local PDF/OCR text; independent page-image, condition, and semantic-overlap review pending."},
        "overlap_review": {"status": "pending_semantic_review", "known_overlap_ids": []},
    }


def main() -> None:
    cases = [make_case(i, seed) for i, seed in enumerate(SEEDS, 1)]
    for case in cases:
        validate_test_case(case)
    OUT.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases), encoding="utf-8")
    print(f"{len(cases)} draft answer cases -> {OUT}")


if __name__ == "__main__":
    main()
