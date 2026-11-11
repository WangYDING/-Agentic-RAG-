"""Draft behavior controls for source and business-rule adjudication; no RAG calls."""
from __future__ import annotations

import json
from pathlib import Path

from eval.contract_v1 import TEST_CASE_VERSION, validate_test_case

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "eval/datasets/independent_120_behavior_candidates.jsonl"
LEADS = json.loads((BASE / "eval/datasets/independent_120_source_leads.json").read_text(encoding="utf-8"))["leads"]
LOOKUP = {(item["document_id"], item["article"]): item for item in LEADS}
LOOKUP[("cn.beijing.db11t995", "16.3.4")] = {
    "document_id": "cn.beijing.db11t995", "document_version": "2025", "pdf_page": 128,
    "article": "16.3.4", "source_excerpt_unverified": "最大牵引负荷应根据客流控制期高峰小时的列车编组、行车交路、旅行速度、车辆特性及线路条件等进行计算确定。",
}
SUPPORT = {
    7: ("cn.beijing.db11t995", "16.3.4"),
    8: ("cn.beijing.db11t995", "9.1.2"), 9: ("cn.gb55033", "5.3.11"),
    10: ("cn.gb55033", "6.1.7"), 11: ("cn.gb55033", "3.0.9"),
    12: ("cn.beijing.db11t995", "13.1.4"),
    13: ("cn.gb55033", "5.3.11"), 14: ("cn.gb55033", "5.3.4"),
    15: ("cn.gb55033", "6.2.5"), 16: ("cn.beijing.db11t995", "9.1.2"),
    17: ("cn.beijing.db11t995", "29.1.1"), 18: ("cn.gb50157", "25.1.7"),
    19: ("cn.gb50157", "15.1.3"), 20: ("cn.beijing.db11t995", "16.1.4"),
}

# A refusal concerns the requested *specific conclusion*. Conditional requirements
# may still be quoted in a real response; reviewers must decide whether the
# business action should be refuse or partial answer before freezing.
REFUSALS = [
    ("no_corpus_fact", "仅依据三份设计规范，2026年北京地铁全网实际票务收入是多少元？", "三份设计规范不是运营收入报表；需官方财务数据。"),
    ("no_corpus_fact", "仅依据三份设计规范，2026年北京地铁各线路实际发生了多少起运营事故？", "设计规范不提供年度事故统计；需运营事故记录。"),
    ("no_corpus_fact", "仅依据三份设计规范，2026年北京市每个地铁站的实际日均进站人数是多少？", "规范不提供逐站实时或年度客流实测台账。"),
    ("no_corpus_fact", "仅依据三份设计规范，现任各线路运营公司的总经理姓名分别是什么？", "规范无公司人事名单；该事实还会随时间变化。"),
    ("no_corpus_fact", "仅依据三份设计规范，2026年每条地铁线路的实际电费支出是多少？", "规范无逐线财务账目。"),
    ("no_corpus_fact", "仅依据三份设计规范，当前每个地铁站的广告位合同价格分别是多少？", "规范无广告合同或现行报价。"),
    ("missing_project_data", "某未提供线路设计资料的地铁项目，其牵引用电负荷实际峰值是多少MW？请直接给出项目数值。", "需该项目供电设计或测算数据；负荷等级规定不能推出峰值。"),
    ("missing_project_data", "某未提供勘察报告的路基，路肩设计高程最终应定为多少米？", "需洪水位、积水位、冻胀及高程基准等项目数据。"),
    ("missing_project_data", "某未提供实测资料的线路，路桥过渡段工后沉降是否已经合格？", "需轨道形式、实测沉降及适用条件。"),
    ("missing_project_data", "某未提供尺寸图的变电所柜后通道，现有一个出口是否符合要求？", "需配电装置长度及通道布置尺寸。"),
    ("missing_project_data", "某未提供线路参数的工程，站台屏蔽门与车体之间的现状间隙是否合格？", "需车辆类型、运行状态、设计/测量间隙。"),
    ("missing_project_data", "某未提供建筑和设备图纸的车站，出入口的防水设计是否已满足规范？", "需具体结构、设计和现场参数；规范条件本身不证明项目合格。"),
    ("partial_support", "仅凭 GB 55033-2022 的有砟线路工后沉降限值，能否判定未提供实测沉降的甲线路合格？请给出具体合格结论。", "规范支持限值，但缺甲线路轨道及实测沉降，不能作具体合格判定。"),
    ("partial_support", "仅凭 GB 55033-2022 的车挡耐撞设计要求，能否断定未提供设备及验收资料的乙线现用车挡合格？", "规范支持车挡设计能力要求，不支持乙线设备实际性能或验收结论。"),
    ("partial_support", "仅凭 GB 55033-2022 的光缆绝缘要求，能否认定未提供施工验收资料的丙站光缆已通过验收？", "规范支持绝缘要求，不证明丙站工程已验收。"),
    ("partial_support", "仅凭 DB11/T 995-2025 的路肩高程确定依据，能否判定未提供水文勘测资料的丁区间既有路肩高程合格？", "规范支持确定依据，缺现场水文及设计/实测高程，不能判定。"),
    ("partial_support", "仅凭 DB11/T 995-2025 的交通接驳优先顺序，能否判定未提供设施图的戊站接驳布局已经符合要求？", "规范支持优先顺序，不证明戊站实际设施布局。"),
    ("partial_support", "仅凭 GB 50157-2013 的扶梯机坑排水要求，能否认定未提供竣工资料的己站排水和油水分离设施合格？", "规范支持设计要求，不证明己站设施安装或性能。"),
    ("partial_support", "仅凭 GB 50157-2013 列出的外部电源方案形式，能否断定未提供设计文件的庚线路最终采用了混合式供电？", "规范列出可选形式，不确定庚线路选择。"),
    ("partial_support", "仅凭 DB11/T 995-2025 的牵引用电负荷等级规定，能否判定未提供负荷设计资料的辛线路供电配置已经合规？", "规范支持负荷等级，不足以判定辛线路的具体配置。"),
]

# Each ambiguity must be checked against the actual business policy and all
# relevant source rows. Several prompts deliberately share the same mechanism;
# fact_group_id makes that dependence explicit so they cannot all survive.
CLARIFICATIONS = [
    ("GB 55033-2022 的直线车站站台屏蔽门与车体最宽处间隙限值是多少？请给出一个适用数值。", {"spec_ids": ["cn.gb55033"], "edition_ids": ["2022"]}, "需车辆类别及停站/越行；表3.0.9不同列、行数值不同。", "cn.gb55033@2022:3.0.9", [17]),
    ("GB 55033-2022 的路基工后沉降量上限是多少？请给出一个适用数值。", {"spec_ids": ["cn.gb55033"], "edition_ids": ["2022"]}, "需区分有砟/无砟及是否路桥过渡段；5.3.11的限值不同。", "cn.gb55033@2022:5.3.11", [24]),
    ("GB 55033-2022 的建筑限界上部和侧面距设备限界最小安全间隙是多少？请给出一个数值。", {"spec_ids": ["cn.gb55033"], "edition_ids": ["2022"]}, "需交通制式和供电/设备条件；表3.0.5-1不同类别数值不同。", "cn.gb55033@2022:3.0.5", [14]),
    ("GB 55033-2022 规定的车站站台面与车辆客室地板面高差是多少？请给出适用上限。", {"spec_ids": ["cn.gb55033"], "edition_ids": ["2022"]}, "需车辆类型和工况；表3.0.8跨页有不同限值。", "cn.gb55033@2022:3.0.8", [16, 17]),
    ("GB 55033-2022 中，车站疏散相关最小安全间隙是多少？只给出适用于本项目的一项。", {"spec_ids": ["cn.gb55033"], "edition_ids": ["2022"]}, "需明确所指对象和设施布置；3.0.6不同间隙条件不同。", "cn.gb55033@2022:3.0.6", [15]),
    ("DB11/T 995-2025 中，当前结构构件应采用多少年设计工作年限？请给本构件的单一数值。", {"spec_ids": ["cn.beijing.db11t995"], "edition_ids": ["2025"]}, "需构件类别、可更换性及对运营安全影响；3.0.13分档。", "cn.beijing.db11t995@2025:3.0.13", [29]),
    ("只给出 DB11/T 995 对路肩高程的适用规定。", {"spec_ids": ["cn.beijing.db11t995"], "edition_ids": []}, "当前业务解析对仅规范 ID 请求版本或适用日期；需确认公开输入可达。", "scope:db11t995-edition", []),
    ("只给出 GB 50157 对自动扶梯机坑排水的适用规定。", {"spec_ids": ["cn.gb50157"], "edition_ids": []}, "当前业务解析对仅规范 ID 请求版本或适用日期；与上一题同机制，二选一。", "scope:edition-required", []),
    ("只给出 GB 55033 对车挡的适用规定。", {"spec_ids": ["cn.gb55033"], "edition_ids": []}, "当前业务解析对仅规范 ID 请求版本或适用日期；与上一题同机制，二选一。", "scope:edition-required", []),
    ("请只针对我选定的规范回答轨道尽端车挡要求。", {"spec_ids": [], "edition_ids": []}, "当前适配器空范围为 unspecified，业务要求先选全部三份或指定规范版本；如显式全库方式接通须重判。", "scope:unspecified", []),
    ("DB11/T 995-2025 中，车站步行接驳比例是多少？请给这个车站的适用范围。", {"spec_ids": ["cn.beijing.db11t995"], "edition_ids": ["2025"]}, "表29.1.3按区域、车站类型给出不同区间；缺车站区域与类型。", "cn.beijing.db11t995@2025:表29.1.3", [216]),
    ("GB 50157-2013 中，车辆车体基本长度是多少毫米？请给适用的一个数值。", {"spec_ids": ["cn.gb50157"], "edition_ids": ["2013"]}, "表4.1.5区分A/B型及无司机室/单司机室，车体基本长度不同。", "cn.gb50157@2013:表4.1.5", [35]),
    ("GB 50157-2013 中，控制室屏面到墙的最小距离是多少？请给一个适用数值。", {"spec_ids": ["cn.gb50157"], "edition_ids": ["2013"]}, "表15.2.16屏正面至墙与屏背面至墙不同，屏正面还有人员值守表注。", "cn.gb50157@2013:表15.2.16", [163]),
    ("GB 50157-2013 中，车体与侧墙之间的通道宽度是多少米？请给本车库的适用数值。", {"spec_ids": ["cn.gb50157"], "edition_ids": ["2013"]}, "表27.3.14按停车库、列检库、月检库等车库种类给不同数值，部分格有括号及表注。", "cn.gb50157@2013:表27.3.14", [268]),
    ("GB 50157-2013 中，地面或高架车站的火灾自动报警系统保护等级是一级还是二级？请给这个车站的结论。", {"spec_ids": ["cn.gb50157"], "edition_ids": ["2013"]}, "19.1.2按是否集中空调/每层封闭建筑面积超过2000m²、是否超过3000m²分级；需项目条件。", "cn.gb50157@2013:19.1.2", [211]),
    ("GB 55033-2022 中，直线站台边缘与车辆轮廓线的水平间隙是多少？只给本项目适用的数值。", {"spec_ids": ["cn.gb55033"], "edition_ids": ["2022"]}, "表3.0.7区分车辆制式、速度等级和地铁车门形式；缺这些条件且表的某些格留空。", "cn.gb55033@2022:表3.0.7", [16]),
    ("DB11/T 995-2025 中，每公里轨枕和扣件应设置多少组？请给本线路适用的一项。", {"spec_ids": ["cn.beijing.db11t995"], "edition_ids": ["2025"]}, "表8.2.7按道床形式、正线/配线及曲线半径或坡度给不同组数/范围。", "cn.beijing.db11t995@2025:表8.2.7", [51]),
    ("GB 50157-2013 中，钢筋保护层厚度是多少毫米？请给本环境适用的值。", {"spec_ids": ["cn.gb50157"], "edition_ids": ["2013"]}, "表10.5.9-2按氯化物环境及混凝土等级给60/55mm，续表10.5.9-1和表10.5.9-3还有其他环境与表注，缺环境及材料条件。", "cn.gb50157@2013:表10.5.9-1/2/3", [99, 100]),
    ("GB 50157-2013 中，电缆支架之间的最小距离是多少毫米？只给本电缆布置适用的值。", {"spec_ids": ["cn.gb50157"], "edition_ids": ["2013"]}, "表15.4.3跨页，电力与控制电缆、通道/电缆沟及水平/垂直布置对应不同值或空白格。", "cn.gb50157@2013:表15.4.3", [168, 169]),
]


def main() -> None:
    rows = []
    for i, (kind, question, reason) in enumerate(REFUSALS, 1):
        support = LOOKUP.get(SUPPORT.get(i))
        if support:
            scope = {"spec_ids": [support["document_id"]], "edition_ids": [support["document_version"]]}
        elif kind == "no_corpus_fact":
            scope = {"spec_ids": ["cn.beijing.db11t995", "cn.gb55033", "cn.gb50157"], "edition_ids": ["2025", "2022", "2013"]}
        else:
            scope = {"spec_ids": ["cn.beijing.db11t995"], "edition_ids": ["2025"]}
        rows.append({
            "schema_version": TEST_CASE_VERSION, "case_id": f"I120-R{i:03d}", "dataset_role": "independent",
            "question": question, "query_scope": scope,
            "expected_action": "refuse", "reference_answer": None, "necessary_facts": [], "evidence_groups": [],
            "main_category": "应拒答问题", "refusal_subtype": kind, "tags": ["部分支持"] if kind == "partial_support" else [],
            "fact_group_id": f"refusal:{kind}:{i}", "reason_for_refusal_or_clarification": reason,
            "supported_source_references": [{"document_id": support["document_id"], "document_version": support["document_version"],
                                              "pdf_page": support["pdf_page"], "article": support["article"],
                                              "source_excerpt": support["source_excerpt_unverified"]}] if support else [],
            "annotation_review": {"status": "pending", "reviewer_type": "ai", "reviewer": "Codex AI (draft author)", "reviewed_at": None, "human_approved": False,
                                  "notes": "Source-wide negative check and partial-answer action policy pending; do not freeze."},
        })
    for i, (question, scope, reason, group, pages) in enumerate(CLARIFICATIONS, 1):
        rows.append({
            "schema_version": TEST_CASE_VERSION, "case_id": f"I120-Q{i:03d}", "dataset_role": "independent",
            "question": question, "query_scope": scope, "expected_action": "clarify", "reference_answer": None,
            "necessary_facts": [], "evidence_groups": [], "main_category": "应澄清问题", "tags": ["版本筛选"] if group.startswith("scope:") else ["表格查询"],
            "fact_group_id": group, "ambiguity_source_pages": pages, "reason_for_refusal_or_clarification": reason,
            "annotation_review": {"status": "pending", "reviewer_type": "ai", "reviewer": "Codex AI (draft author)", "reviewed_at": None, "human_approved": False,
                                  "notes": "Must confirm missing condition cannot be handled by conditional answer or business default."},
        })
    for item in rows:
        validate_test_case(item)
    OUT.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows), encoding="utf-8")
    print(f"{len(rows)} draft behavior controls -> {OUT}")


if __name__ == "__main__":
    main()
