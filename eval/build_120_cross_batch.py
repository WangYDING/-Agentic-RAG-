"""Source grounded cross-spec comparison candidates; no RAG interaction."""
from __future__ import annotations

import json
from pathlib import Path

from eval.contract_v1 import TEST_CASE_VERSION, validate_test_case

ROOT = Path(__file__).resolve().parents[1]
LEADS = json.loads((ROOT / "eval/datasets/independent_120_source_leads.json").read_text(encoding="utf-8"))["leads"]
SOURCE = {(x["document_id"], x["article"]): x for x in LEADS}
OUT = ROOT / "eval/datasets/independent_120_cross_batch3.jsonl"

# question, first source/fact, second source/fact. Each fact has its own source.
PAIRS = [
    ("DB11/T 995-2025 与 GB 50157-2013 对给水水源分别如何规定？北京标准还要求如何使用自来水水压？", ("cn.beijing.db11t995", "15.1.1", "采用城市自来水并充分利用其水压；无自来水时采用其他可靠水源"), ("cn.gb50157", "14.1.2", "采用城市自来水；沿线无自来水时采用其他可靠水源")),
    ("两份设计标准 DB11/T 995-2025 与 GB 50157-2013 对综合监控系统的设置及运营需求分别如何表述？", ("cn.beijing.db11t995", "20.1.1", "宜设置综合监控并采集行车、设备、客流等信息，满足行车指挥、设备监控、防灾、能源和乘客服务等需求"), ("cn.gb50157", "20.1.1", "宜设置综合监控系统(ISCS)，满足行车指挥、防灾安全和乘客服务等运营管理需要")),
    ("DB11/T 995-2025 与 GB 50157-2013 对环境与设备监控系统的设置原则分别有什么要求？", ("cn.beijing.db11t995", "21.1.1", "应设置系统，遵循集中管理、分散控制、资源共享"), ("cn.gb50157", "21.1.1", "针对地铁特点、敷设方式及地域气候设置相应BAS系统")),
    ("DB11/T 995-2025 与 GB 50157-2013 对乘客信息系统设置及乘客可获取的信息分别如何规定？", ("cn.beijing.db11t995", "23.1.1", "应设置并提供到达预告、换乘、时间等乘车信息，还可播放新闻、天气、公益广告"), ("cn.gb50157", "22.1.1", "应设置PIS并保证乘客乘车过程中及时获取相关信息")),
    ("DB11/T 995-2025 与 GB 50157-2013 对自动售检票系统的基本要求分别是什么？", ("cn.beijing.db11t995", "24.1.1", "应设置自动售检票，实现售票、检票、计费、收费、统计、结算全过程自动化管理"), ("cn.gb50157", "18.1.2", "满足线网运营和管理需要，系统技术条件一致或兼容")),
    ("DB11/T 995-2025 与 GB 50157-2013 对控制中心的管理范围和设置依据分别怎么说？", ("cn.beijing.db11t995", "28.1.1", "OCC负责日常运营和灾害应急，对列车、车站和车辆基地统一指挥调度，并监视控制机电设备"), ("cn.gb50157", "24.1.2", "控制中心可管理单条或多条线路；建设模式和规模依据线网规划及线路情况")),
    ("DB11/T 995-2025 与 GB 50157-2013 对站台门类型的选定因素分别怎么要求？北京标准对地下、地上站还提出什么倾向？", ("cn.beijing.db11t995", "19.1.2", "依据气候、建筑形式、通风空调制式和服务水平；地下宜全高封闭，地上宜半高"), ("cn.gb50157", "26.1.3", "综合气候环境、建筑形式、服务水平和通风空调制式选型")),
    ("DB11/T 995-2025 与 GB 50157-2013 各自列出哪些适用的地下结构施工方法？", ("cn.beijing.db11t995", "12.1.1", "地下结构章节含明挖、盖挖逆作、矿山、盾构、顶管等"), ("cn.gb50157", "11.1.1", "含明挖或盖挖、矿山或盾构暗挖，以及沉埋、顶进等特殊方法")),
    ("DB11/T 995-2025 与 GB 50157-2013 对通信系统的互联互通分别有哪些表述？", ("cn.beijing.db11t995", "17.1.2", "满足运营、公安、政务及与其他制式轨道交通互联互通的通信要求"), ("cn.gb50157", "16.1.2", "与已建线路必要互联互通，并为后续线路接入预留条件")),
    ("DB11/T 995-2025 与 GB 50157-2013 对通风空调供暖系统要保障的内部空气环境分别列了哪些要素？", ("cn.beijing.db11t995", "14.1.2", "列出空气质量、温度、湿度、气流组织、速度和噪声，保障人员及设备需要"), ("cn.gb50157", "13.1.3", "还明确列出压力变化，并保障人员及设备需要")),
    ("DB11/T 995-2025 与 GB 50157-2013 对车站规模和车站设计的考虑因素及目标分别如何规定？", ("cn.beijing.db11t995", "10.1.2", "规模与设施标准结合车站分级、客流特征、预测客流、系统能力和运营工况确定"), ("cn.gb50157", "9.1.2", "满足客流和乘降安全、快速疏导、紧凑易管理及通风照明卫生防灾设施")),
    ("DB11/T 995-2025 与 GB 50157-2013 对轨道结构类型选定和承载设计分别有什么原则？", ("cn.beijing.db11t995", "8.1.2", "类型结合线网使用条件和养护维修需求，经技术经济比选确定"), ("cn.gb50157", "7.1.2", "依车辆运行条件确定承载力，并符合质量均衡、弹性连续、结构等强和匹配原则")),
    ("DB11/T 995-2025 与 GB 50157-2013 各要求在哪些场所设置火灾自动报警系统？请分别列明，避免把不同清单混为一条。", ("cn.beijing.db11t995", "22.1.1", "含车站、地下区间隧道、区间变电所、区间风井和系统设备用房、主变电所、车辆基地"), ("cn.gb50157", "19.1.1", "含车站、区间隧道、区间变电所和系统设备用房、主变电所、集中冷站、控制中心、车辆基地")),
    ("DB11/T 995-2025 与 GB 55033-2022 在选线面对不良地质时分别提出什么要求？", ("cn.beijing.db11t995", "7.1.3", "地下线选线结合地质、水位、施工、结构和市政设施，规避不良地层"), ("cn.gb55033", "5.2.2", "选线应规避不良工程和水文地质；不可规避时采取确保安全措施并符合施工安全、环保、资源保护")),
    ("DB11/T 995-2025 与 GB 55033-2022 对路基主体工程的性能和防洪防涝分别如何要求？", ("cn.beijing.db11t995", "9.1.1", "以地质水文勘察为依据，满足强度、稳定、耐久、防洪防涝和防排地下水"), ("cn.gb55033", "5.3.10", "路基有足够承载力、稳定性和耐久性并满足防洪防涝")),
    ("DB11/T 995-2025 与 GB 55033-2022 对通信系统的用途和非正常情况分别如何规定？", ("cn.beijing.db11t995", "17.1.1", "通信服务运输效率、行车安全、管理与语音数据图像信息传递，强调可靠合理成熟"), ("cn.gb55033", "6.2.1", "正常时传送运营、指挥、监控、防灾信息，紧急时作为抢险救灾通信手段")),
    ("GB 55033-2022 与 GB 50157-2013 对信号系统的基本功能分别如何规定？", ("cn.gb55033", "6.3.1", "应具备指挥、监视、控制、安全防护、联锁及降级运行能力"), ("cn.gb50157", "17.1.1", "由行车指挥和列车运行控制设备组成，设置故障监测和报警设备")),
    ("GB 55033-2022 与 GB 50157-2013 对线路运量等级与速度目标的确定分别依据什么？", ("cn.gb55033", "5.2.1", "依据功能定位、预测客流量和线路性质"), ("cn.gb50157", "6.1.2", "依据线网地位、客流特征及功能定位确定线路性质、运量等级和速度目标")),
    ("GB 55033-2022 与 GB 50157-2013 对地下结构设计的地质与施工选择分别有什么要求？", ("cn.gb55033", "5.1.2", "结合工程水文地质、气候、地形、荷载和施工，经技术经济评价选结构与施工方法"), ("cn.gb50157", "11.1.2", "依据地质勘察资料，按阶段及施工方法确定勘察内容并用施工观察监测反馈验证")),
    ("GB 55033-2022 与 GB 50157-2013 对高架桥梁跨越条件和结构性能分别有哪些要求？", ("cn.gb55033", "5.1.4", "与道路、铁路立交或跨河时，桥下净空满足行车、排洪和通航"), ("cn.gb50157", "10.1.2", "桥梁满足运行安全和舒适、强度、竖横刚度、整体性与稳定性")),
    ("DB11/T 995-2025 与 GB 50157-2013 对车站与城市周边空间关系分别有什么设计要求？", ("cn.beijing.db11t995", "10.1.1", "车站与周边建筑、地下空间、市政管线和景观协调，并做好换乘衔接和一体化规划"), ("cn.gb50157", "9.1.1", "总体布局符合城市与综合交通规划、环保和景观要求，并处理与道路管线构筑物和施工交通关系")),
    ("DB11/T 995-2025 与 GB 50157-2013 对车辆基地组成分别如何列举？", ("cn.beijing.db11t995", "27.1.1", "包括运用、检修、综合维修及必要办公生活设施；物资总库和培训可按需设置"), ("cn.gb50157", "27.1.1", "包括车辆段（停车场）、综合维修中心、物资总库、培训中心及其他配套设施")),
    ("GB 55033-2022 与 GB 50157-2013 对轨道结构的性能与设计原则分别提出什么要求？", ("cn.gb55033", "5.3.1", "有强度、稳定、耐久和弹性，保证平稳安全并结合措施减振降噪"), ("cn.gb50157", "7.1.2", "按运行条件确定承载能力，符合质量均衡、弹性连续、结构等强和匹配原则")),
    ("DB11/T 995-2025 与 GB 50157-2013 对综合监控系统的集成与互联对象分别如何规定？", ("cn.beijing.db11t995", "20.1.3", "集成电力、环境设备及屏蔽门系统；广播、视频、乘客信息等宜互联，火灾报警及列车监控可集成或互联"), ("cn.gb50157", "20.1.3", "集成电力、环境设备及站台门控制，宜互联广播、视频、乘客信息、时钟、自动售检票和门禁等")),
]


def make(index: int, item: tuple) -> dict:
    question, first, second = item
    sources = [SOURCE[spec, article] for spec, article, _ in (first, second)]
    facts = [{"fact_id": f"F{i}", "description": seed[2]} for i, seed in enumerate((first, second), 1)]
    groups = []
    for i, (seed, source) in enumerate(zip((first, second), sources, strict=True), 1):
        spec, article, _ = seed
        groups.append({"fact_id": f"F{i}", "alternatives": [{"scheme_id": "source-clause-v1", "all_of": [{
            "evidence_id": f"X{index:03d}-E{i}", "document_id": spec,
            "document_version": source["document_version"], "page": source["pdf_page"],
            "article": article, "quote": source["source_excerpt_unverified"],
        }]}]})
    return {
        "schema_version": TEST_CASE_VERSION, "case_id": f"I120-X{index:03d}", "dataset_role": "independent",
        "question": question,
        "query_scope": {"spec_ids": [x["document_id"] for x in sources], "edition_ids": [x["document_version"] for x in sources]},
        "expected_action": "answer", "reference_answer": "；".join(
            f"{spec}@{SOURCE[spec, article]['document_version']}：{fact}" for spec, article, fact in (first, second)) + "。",
        "necessary_facts": facts, "evidence_groups": groups, "main_category": "跨规范查询与比较",
        "tags": ["版本筛选", "同号条文"] if first[1] == second[1] else ["版本筛选"],
        "fact_group_id": "cross:" + "+".join(f"{spec}:{article}" for spec, article, _ in (first, second)),
        "source_pdf_sha256": [x["pdf_sha256"] for x in sources],
        "annotation_review": {"status": "pending", "reviewer_type": "ai", "reviewer": "Codex AI (draft author)",
                              "reviewed_at": None, "human_approved": False,
                              "notes": "Original local PDF/OCR clause text used; compare full pages, supersession, and semantic overlap before approval."},
    }


def main() -> None:
    cases = [make(i, item) for i, item in enumerate(PAIRS, 1)]
    for case in cases:
        validate_test_case(case)
    OUT.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases), encoding="utf-8")
    print(f"{len(cases)} cross-spec candidates -> {OUT}")


if __name__ == "__main__":
    main()
