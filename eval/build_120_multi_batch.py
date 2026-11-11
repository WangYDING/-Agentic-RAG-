"""Multi-clause candidate questions; all locations require later independent review."""
from __future__ import annotations

import json
from pathlib import Path

from eval.contract_v1 import TEST_CASE_VERSION, validate_test_case

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {(x["document_id"], x["article"]): x for x in json.loads((ROOT / "eval/datasets/independent_120_source_leads.json").read_text(encoding="utf-8"))["leads"]}
OUT = ROOT / "eval/datasets/independent_120_multi_batch4.jsonl"

# One document, two distinct article locations, one fact per article.
SEEDS = [
    ("cn.beijing.db11t995", "4.1.2", "4.1.4", "DB11/T 995-2025 对网络化客流下的运营组织，以及运输能力和列车编组分别有什么要求？", "运营组织设计满足网络化客流的运输能力、行车组织和灵活性需求", "运输能力满足预测客流、预留发展空间；编组和交路符合客流分布并衔接相邻线路"),
    ("cn.beijing.db11t995", "5.1.2", "5.1.5", "DB11/T 995-2025 对车辆选型统一和车辆减振、降噪及防水分别怎样规定？", "同运量等级线路选型应一致；同线及互联互通需求线路宜车型统一", "车辆减振降噪、防雨雪；相关设备防水，洗车不得渗入"),
    ("cn.beijing.db11t995", "6.1.2", "6.1.3", "DB11/T 995-2025 如何分类计算车辆限界，建筑限界又不应包含哪些误差和变形因素？", "车辆限界按隧道内外分别计算，并区分区间、站台计算长度内及基地", "建筑限界不包括测量、施工误差及结构沉降、位移变形"),
    ("cn.beijing.db11t995", "18.1.1", "18.1.4", "DB11/T 995-2025 对信号系统的运营目标和涉及行车安全设备的安全原则分别有什么要求？", "信号系统满足行车组织管理、安全、效率及智慧化需求", "涉及行车安全的系统设备电路符合故障安全原则，安全设备经过认证"),
    ("cn.gb55033", "3.0.1", "3.0.2", "GB 55033-2022 如何确定三种限界，车辆及轨行区设施在运行中又应满足什么安全约束？", "根据车辆类型和运行工况确定车辆、设备、建筑限界", "车辆不超相应限界，设施符合限界；运行状态不得相互接触，但受电弓/集电靴正常受流接触除外"),
    ("cn.gb55033", "4.5.2", "4.5.4", "GB 55033-2022 对列车乘客紧急报警通信，以及地下固定编组列车、单轨和全自动列车的应急设施分别有什么要求？", "客室紧急报警及联络装置，值守人员与乘客通话最高优先权", "地下固定编组车辆贯通；单轨车门缓降并具纵横向救援；全自动列车具人工操控设备"),
    ("cn.gb55033", "5.2.4", "5.2.5", "GB 55033-2022 对线路与道路交叉，以及全封闭线路正线间、正支线接轨点分别如何规定？", "全封闭与道路立交；部分封闭确需平交时核算行车和能力并设防护", "全封闭正线间及正支线接轨点选在车站，进站方向设平行进路"),
    ("cn.gb55033", "6.1.5", "6.1.6", "GB 55033-2022 对变电所两路进线各自容量，以及地面变电所选址需避开的环境分别有什么要求？", "两路进线中每一路满足高峰小时全部一、二级负荷", "地面变电所避开易燃、易爆、腐蚀性气体等危及设备安全场所"),
    ("cn.gb55033", "6.3.2", "6.3.4", "GB 55033-2022 对全封闭和部分封闭线路的列车安全防护，以及无防护人工驾驶的授权分别有什么要求？", "全封闭配列车自动防护；部分封闭根据间隔速度及封闭状态采取技术措施", "全封闭列车采用无防护人工驾驶模式须授权并表征授权及操作"),
    ("cn.gb50157", "3.1.1", "3.1.2", "GB 50157-2013 对运营组织设计依据和客流预测的时段、风险分析分别有什么要求？", "按线网规划、预测客流和出行需求形成运营概念、规模及模式", "基于线网和建设时序、沿线发展预测初期近期远期客流并分析变化风险"),
    ("cn.gb50157", "5.1.2", "5.1.4", "GB 50157-2013 如何按区域划分车辆限界，并如何按地上地下和隧道形状划分建筑限界？", "车辆限界可按隧道内外或区间、站台长度内、基地划分", "建筑限界分隧道、高架、地面；隧道又分矩形、马蹄形、圆形"),
    ("cn.gb50157", "12.1.1", "12.1.2", "GB 50157-2013 对地下工程防水的总体原则，以及确定防水设计方案时的环境和水源分析分别有什么要求？", "以防为主、刚柔结合、多道设防、因地制宜和综合治理", "依据气候、地质水文、结构、施工和使用条件，分析地表水、地下水、毛细水及管线渗漏影响"),
    ("cn.gb50157", "16.1.1", "16.1.2", "GB 50157-2013 对通信系统的基本作用，以及与既有和未来线路互联互通分别有什么要求？", "适应运输、安全、管理及语音数据图像传递，可靠、合理、成熟、经济", "与既有线路必要互联互通并为未来线路接入预留"),
    ("cn.gb50157", "23.1.1", "23.1.2", "GB 50157-2013 对哪些门应设置门禁，门禁系统应具备哪些基本功能？", "涉及安全的重要设施通道门、系统设备用房门、管理用房门设门禁", "具有出入口监控和安全管理功能，可按运营需要扩展"),
    ("cn.gb50157", "27.1.1", "29.1.1", "GB 50157-2013 对车辆基地设计范围和地铁工程污染物排放及环境质量分别提出什么要求？", "基地包括车辆段、维修中心、物资总库、培训及配套设施", "设计满足国家地方排放标准及环境功能区划、环境质量要求"),
    ("cn.gb55033", "5.3.1", "5.3.2", "GB 55033-2022 对轨道结构的性能，以及钢轮钢轨系统钢轨与车轮的匹配分别怎么要求？", "轨道结构有足够强度、稳定性、耐久性和弹性，保障平稳安全及减振降噪", "钢轨断面、轨底坡、硬度匹配车轮踏面，提供足够支撑刚度与导向"),
    ("cn.beijing.db11t995", "25.1.1", "26.1.1", "DB11/T 995-2025 对门禁、周界及安检的安全等级依据，以及信息化建设原则分别有什么规定？", "门禁、周界与安检安全等级应符合GB/T 22239、28448、25070相关要求，具体等级未由本条给出", "信息化遵循统一规划、统一标准、资源共享，并满足安全可靠先进可扩展"),
    ("cn.gb50157", "4.1.2", "4.1.5", "GB 50157-2013 对车辆的全寿命安全和故障救助条件，以及选定车辆类型时考虑的因素分别怎样规定？", "车辆寿命周期正常运行保障行车和人身安全，故障事故灾难时具救助条件", "按预测客流、环境、线路条件及运能要求等综合比较选择车辆类型"),
    ("cn.gb55033", "5.3.7", "6.1.10", "GB 55033-2022 对采用直流牵引、走行轨回流系统的轨道回流与供电接地分别提出什么要求？", "回流走行轨减少纵向电阻、与周围结构良好绝缘并按牵引供电区间设置绝缘分断", "直流牵引供电为不接地双导线系统，正负极均不接地，接地系统与回流回路不直接连接"),
    ("cn.beijing.db11t995", "13.1.3", "13.1.4", "DB11/T 995-2025 对地下工程防水设计工作年限与车站、人行通道的防水等级分别有什么要求？", "地下工程防水设计工作年限不低于结构设计工作年限", "车站、人行通道和机电设备集中区段防水等级为一级"),
    ("cn.beijing.db11t995", "20.1.3", "21.1.2", "DB11/T 995-2025 对综合监控系统集成的核心系统，以及环境与设备监控系统覆盖范围分别怎么规定？", "综合监控集成电力、环境设备及站台屏蔽门系统", "环境设备监控包括车站、区间风井、区间变电所、区间隧道；基地和控制中心可按需独立管理"),
    ("cn.gb55033", "6.1.9", "6.1.10", "GB 55033-2022 对正线接触网供电方式与直流牵引供电系统的接地分别有什么要求？", "正线接触网应实行双边供电", "直流牵引供电为不接地双导线制，正负极均不接地"),
    ("cn.gb50157", "15.1.2", "15.1.3", "GB 50157-2013 对供电系统组成和外部电源方案的可选形式分别怎么规定？", "供电包括外部电源、主变电所、牵引供电、动力照明和电力监控等", "外部电源可采用集中、分散或混合供电，结合线网和城市电网规划设计"),
]


def make(i: int, seed: tuple) -> dict:
    spec, first_article, second_article, question, first_fact, second_fact = seed
    sources = [SOURCE[spec, first_article], SOURCE[spec, second_article]]
    facts = [{"fact_id": "F1", "description": first_fact}, {"fact_id": "F2", "description": second_fact}]
    groups = []
    for n, source in enumerate(sources, 1):
        groups.append({"fact_id": f"F{n}", "alternatives": [{"scheme_id": "source-clause", "all_of": [{
            "evidence_id": f"M{i:03d}-E{n}", "document_id": spec,
            "document_version": source["document_version"], "page": source["pdf_page"],
            "article": source["article"], "quote": source["source_excerpt_unverified"],
        }]}]})
    return {"schema_version": TEST_CASE_VERSION, "case_id": f"I120-M{i:03d}", "dataset_role": "independent",
            "question": question, "query_scope": {"spec_ids": [spec], "edition_ids": [sources[0]["document_version"]]},
            "expected_action": "answer", "reference_answer": f"{first_fact}；{second_fact}。",
            "necessary_facts": facts, "evidence_groups": groups, "main_category": "单规范多证据组合",
            "tags": ["版本筛选"], "fact_group_id": f"{spec}:{first_article}+{second_article}",
            "source_pdf_sha256": sources[0]["pdf_sha256"],
            "annotation_review": {"status": "pending", "reviewer_type": "ai", "reviewer": "Codex AI (draft author)",
                                  "reviewed_at": None, "human_approved": False,
                                  "notes": "Check both full original clauses, historical semantic overlap and cross-clause necessity before approval."}}


def main() -> None:
    cases = [make(i, seed) for i, seed in enumerate(SEEDS, 1)]
    for case in cases:
        validate_test_case(case)
    OUT.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases), encoding="utf-8")
    print(f"{len(cases)} multi-evidence candidates -> {OUT}")


if __name__ == "__main__":
    main()
