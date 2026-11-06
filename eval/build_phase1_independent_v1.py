from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "eval/datasets/phase1_cross_spec_independent_v1.jsonl"
REVIEW = ROOT / "eval/reviews/phase1_cross_spec_independent_v1_source_review.json"

DB = "cn.beijing.db11t995@2025"
GB55 = "cn.gb55033@2022"
GB50 = "cn.gb50157@2013"


def ref(business_id: str, page: int, article: str, excerpt: str, table: str | None = None):
    return {
        "business_id": business_id,
        "pdf_page": page,
        "article": article,
        "table": table,
        "source_excerpt": excerpt,
    }


def scope(*business_ids: str):
    return {
        "spec_ids": [item.rsplit("@", 1)[0] for item in business_ids],
        "edition_ids": [item.rsplit("@", 1)[1] for item in business_ids],
    }


def item(
    case_id: str,
    category: str,
    question: str,
    business_ids: tuple[str, ...],
    behavior: str,
    answer: str,
    requirements: list[str],
    references: list[dict],
    numeric: list[dict] | None = None,
    *,
    answerable: bool = True,
    why_unanswerable: str | None = None,
):
    expected = {business_id: [] for business_id in business_ids}
    for source in references:
        expected.setdefault(source["business_id"], []).append(source["article"])
    return {
        "id": case_id,
        "dataset_id": "phase1_cross_spec_independent_v1",
        "category": category,
        "question": question,
        "requested_scope": scope(*business_ids),
        "expected_behavior": behavior,
        "answerable": answerable,
        "expected_spec_editions": list(business_ids),
        "expected_articles_by_spec": expected,
        "gold_answer": answer,
        "required_requirements": requirements,
        "numeric_expectations": numeric or [],
        "source_references": references,
        "why_unanswerable": why_unanswerable,
        "annotation_review": {
            "status": "approved",
            "reviewer": "Codex (AI; user-authorized PDF content reviewer)",
            "reviewed_at": "2026-11-06",
            "notes": (
                "Question, answerability, PDF page, article/table, answer points, "
                "numbers, units and conditions were checked against rendered source pages. "
                "This is not a licensed domain-expert sign-off. No candidate-system answers "
                "were run or inspected before this review."
            ),
        },
    }


CASES = [
    item(
        "P1-IND-001", "single_spec_numeric", "仅依据 GB 55033-2022，城市轨道交通工程的设计年限和运能储备怎样规定？",
        (GB55,), "answer", "以建成通车年为基准，初期3年、近期10年、远期25年；设计运能满足预测需求并留不小于10%的储备。",
        ["初期、近期、远期年限", "运能储备下限及前提"],
        [ref(GB55, 6, "2.1.5", "初期3年、近期10年、远期25年；运能储备不小于10%。")],
        [{"value": "3/10/25", "unit": "年", "conditions": ["以建成通车年为基准"]}, {"value": "10", "unit": "%", "conditions": ["运能储备下限"]}],
    ),
    item(
        "P1-IND-002", "single_spec_numeric", "GB 55033-2022 对轨道交通工程安全保护区的外扩范围分别如何规定？",
        (GB55,), "answer", "附属设施10m，地面/高架及车辆基地30m，地下车站与隧道50m，穿跨水域隧道或桥梁100m。",
        ["四类对象与对应距离"],
        [ref(GB55, 8, "2.1.21", "附属设施10m；地面高架和车辆基地30m；地下车站隧道50m；穿跨水域100m。")],
        [{"value": "10/30/50/100", "unit": "m", "conditions": ["分别对应四类保护对象"]}],
    ),
    item(
        "P1-IND-003", "single_spec_multi_requirement", "GB 55033-2022 规定城市轨道交通投入载客运营前必须同时具备哪些条件？",
        (GB55,), "answer", "完成单位工程、项目工程和竣工验收；不载客试运行不少于90d；通过运营前安全评估。",
        ["三类验收", "不载客试运行时长", "运营前安全评估"],
        [ref(GB55, 9, "2.1.26", "完成验收，不载客试运行不少于90d，通过运营前安全评估。")],
        [{"value": "90", "unit": "d", "conditions": ["不载客试运行下限"]}],
    ),
    item(
        "P1-IND-004", "single_spec_numeric", "GB 55033-2022 对走行轨回流网纵向电阻和两种防护方案的过渡电阻有哪些定量要求？",
        (GB55,), "answer", "纵向电阻小于0.01Ω/km；加强绝缘方案过渡电阻不低于150Ω·km；绝缘与排流结合方案不低于15Ω·km。",
        ["纵向电阻上限", "两种方案的过渡电阻下限"],
        [ref(GB55, 11, "2.3.5", "纵向电阻小于0.01Ω/km；过渡电阻分别不低于150Ω·km和15Ω·km。")],
        [{"value": "0.01", "unit": "Ω/km", "conditions": ["走行轨回流网纵向电阻上限"]}, {"value": "150/15", "unit": "Ω·km", "conditions": ["加强绝缘/绝缘与排流结合"]}],
    ),
    item(
        "P1-IND-005", "single_spec_numeric", "GB 55033-2022 对通风开式、闭式运行和空调方式的人均新鲜空气量分别有什么要求？",
        (GB55,), "answer", "通风开式不少于30m³/(人·h)；闭式和空调均不少于12.6m³/(人·h)，且新风量不少于总送风量10%。",
        ["开式数值", "闭式数值及比例", "空调数值及比例"],
        [ref(GB55, 34, "6.4.9", "开式30m³，闭式12.6m³且不低于总送风量10%。"), ref(GB55, 34, "6.4.10", "空调方式12.6m³且不低于总送风量10%。")],
        [{"value": "30/12.6", "unit": "m³/(人·h)", "conditions": ["开式/闭式与空调"]}, {"value": "10", "unit": "%", "conditions": ["闭式与空调的新风比例下限"]}],
    ),
    item(
        "P1-IND-006", "single_spec_numeric", "仅依据 GB 50157-2013，地铁工程初期、近期和远期设计年限如何确定？",
        (GB50,), "answer", "可分别按建成通车后第3年、第10年和第25年确定。",
        ["三个设计年限及基准"], [ref(GB50, 20, "1.0.8", "初期第3年、近期第10年、远期第25年。")],
        [{"value": "3/10/25", "unit": "年", "conditions": ["建成通车后"]}],
    ),
    item(
        "P1-IND-007", "single_spec_article", "GB 50157-2013 对车站公共厕所及管理人员厕所的关系怎样规定？",
        (GB50,), "answer", "车站应设置公共厕所，管理人员厕所不宜与公共厕所合用。",
        ["公共厕所设置", "管理人员厕所不宜合用"], [ref(GB50, 80, "9.2.6", "车站应设置公共厕所，管理人员厕所不宜与公共厕所合用。")],
    ),
    item(
        "P1-IND-008", "single_spec_table", "DB11/T 995-2025 中，周边规划实施率低于40%时，枢纽级/城市级和区域级/街区级车站附属结建率建议值分别是多少？",
        (DB,), "answer", "分别为90%和70%。",
        ["两类车站的结建率及实施率条件"], [ref(DB, 59, "10.2.1", "表10.2.1：实施率低于40%时分别为90%和70%。", "表10.2.1")],
        [{"value": "90/70", "unit": "%", "conditions": ["周边规划实施率低于40%", "枢纽级/城市级与区域级/街区级"]}],
    ),
    item(
        "P1-IND-009", "single_spec_numeric", "DB11/T 995-2025 对专用通信录音录像保存时间有哪些明确下限？",
        (DB,), "answer", "乘客求助录音录像不少于90d，其他录音录像不少于365d。",
        ["乘客求助保存时间", "其他记录保存时间"], [ref(DB, 146, "17.2.6", "乘客求助不少于90d，其他保存时间不少于365d。")],
        [{"value": "90/365", "unit": "d", "conditions": ["乘客求助/其他录音录像"]}],
    ),
    item(
        "P1-IND-010", "single_spec_numeric", "DB11/T 995-2025 的车站自动售检票系统应能查询多长时间的运营数据，通信恢复后还应做什么？",
        (DB,), "answer", "应能查询至少90d运营数据，并具备数据恢复功能，在恢复通信后上传或转发相应数据。",
        ["查询时长", "恢复通信后的数据处理"], [ref(DB, 190, "24.4.2", "查询至少90d运营数据；恢复通信后上传或转发相应数据。")],
        [{"value": "90", "unit": "d", "conditions": ["可查询运营数据的下限"]}],
    ),
    item(
        "P1-IND-011", "cross_spec_comparison", "比较 GB 55033-2022 与 GB 50157-2013 的设计年限规定，并指出前者额外提出的运能要求。",
        (GB55, GB50), "answer", "两者均为通车后3/10/25年；GB 55033 另要求满足预测需求并留不小于10%运能储备。",
        ["两规范年限", "GB 55033额外运能储备"], [ref(GB55, 6, "2.1.5", "3/10/25年且运能储备不小于10%。"), ref(GB50, 20, "1.0.8", "3/10/25年。")],
        [{"value": "3/10/25", "unit": "年", "conditions": ["建成通车后"]}, {"value": "10", "unit": "%", "conditions": ["GB 55033运能储备"]}],
    ),
    item(
        "P1-IND-012", "cross_spec_table", "三份规范对1435mm标准轨距及小半径曲线轨距加宽分别给出了什么直接规定？",
        (DB, GB55, GB50), "answer", "三者均明确1435mm；DB11和GB 50157还规定半径小于250m时加宽，并分别由表8.2.2、表7.2.2给出取值。",
        ["三份规范的1435mm", "两份设计标准的小半径加宽及表号"], [ref(DB, 50, "8.2.2", "1435mm；R<250m按表8.2.2加宽。", "表8.2.2"), ref(GB55, 6, "2.1.2", "钢轮钢轨系统采用1435mm标准轨距。"), ref(GB50, 64, "7.2.2", "1435mm；R<250m按表7.2.2加宽。", "表7.2.2")],
        [{"value": "1435", "unit": "mm", "conditions": ["标准轨距"]}, {"value": "250", "unit": "m", "conditions": ["需要轨距加宽的曲线半径阈值"]}],
    ),
    item(
        "P1-IND-013", "cross_spec_multi_evidence", "三份规范对区间、车站公共区以及设备管理用房人员新风量分别有哪些直接规定？请区分使用场景。",
        (DB, GB55, GB50), "answer", "DB11规定区间和地下车站公共区每乘客20m³/h、设备管理用房每工作人员30m³/h；GB 50157规定区间12.6m³/h、开式30/闭式12.6且10%、设备管理用房30且10%；GB 55033规定通风开式30/闭式12.6且10%，空调12.6且10%。",
        ["逐规范区分场景", "全部数值与比例"], [ref(DB, 116, "14.2.11", "区间20、公共区20、设备管理用房30m³/h。"), ref(GB55, 34, "6.4.9", "开式30、闭式12.6m³/h且10%。"), ref(GB55, 34, "6.4.10", "空调12.6m³/h且10%。"), ref(GB50, 140, "13.2.4", "区间12.6m³/h。"), ref(GB50, 141, "13.2.17", "开式30、闭式12.6m³/h且10%。"), ref(GB50, 143, "13.2.33", "设备管理用房30m³/h且10%。")],
        [{"value": "12.6/20/30", "unit": "m³/(人·h)", "conditions": ["按规范及使用场景区分"]}, {"value": "10", "unit": "%", "conditions": ["部分闭式/空调/设备用房新风比例"]}],
    ),
    item(
        "P1-IND-014", "cross_spec_multi_evidence", "三份规范对列车丧失1/4、1/3、1/2动力后的运行与救援能力有何异同？",
        (DB, GB55, GB50), "answer", "DB11细分动拖比及1/3动力并规定清客回库；GB 55033和GB 50157均规定1/4维持到终点、1/2在最大坡道启动并到最近车站，并规定空载列车救援能力。",
        ["逐规范1/4要求", "DB11的1/3", "1/2及救援差异"], [ref(DB, 37, "5.4.8", "丧失1/4、1/3、1/2动力及救援要求。"), ref(GB55, 19, "4.3.5", "1/4到终点、1/2到最近车站及空载救援。"), ref(GB50, 38, "4.1.19", "1/4到终点、1/2到最近车站及空载救援。")],
        [{"value": "1/4,1/3,1/2", "unit": "动力比例", "conditions": ["超员载荷及最大坡道等条件"]}],
    ),
    item(
        "P1-IND-015", "cross_spec_numeric", "GB 55033-2022 与 GB 50157-2013 对自动扶梯连续运行强度怎样规定？后者还增加了什么制动载荷条件？",
        (GB55, GB50), "answer", "两者均为每天不少于20h、每周不少于140h；GB 50157还要求每3h能以100%制动载荷连续运行1h。",
        ["日/周运行时间", "GB 50157额外制动载荷条件"], [ref(GB55, 38, "6.9.2", "每天20h、每周140h。"), ref(GB50, 249, "25.1.8", "每天20h、每周140h，每3h以100%制动载荷运行1h。")],
        [{"value": "20/140", "unit": "h", "conditions": ["每天/每周"]}, {"value": "3/1/100", "unit": "h/h/%", "conditions": ["GB 50157制动载荷运行"]}],
    ),
    item(
        "P1-IND-016", "cross_spec_explicit_absence", "三份规范对车站公共厕所分别有什么直接规定？给定证据未找到直接规定时请审慎说明。",
        (DB, GB55, GB50), "answer", "GB 55033要求全封闭运行车站设置公共厕所；GB 50157要求车站设置公共厕所且管理人员厕所不宜合用；DB11给定证据未找到直接规定。",
        ["两份有规定规范的差异", "DB11审慎未找到"], [ref(GB55, 7, "2.1.16", "全封闭运行车站应设置公共厕所。"), ref(GB50, 80, "9.2.6", "车站应设置公共厕所，管理人员厕所不宜合用。")],
    ),
    item(
        "P1-IND-017", "cross_spec_table", "DB11/T 995-2025 与 GB 55033-2022 对区间纵向疏散平台的宽度、高差和间隙分别怎样规定？",
        (DB, GB55), "answer", "DB11按单/双线和一般/困难情况给出600～1000mm宽度，顶面距轨面宜950mm，设备限界间隙不小于50mm，车辆轮廓水平距离直线不宜大于150mm、曲线不宜大于300mm；GB 55033规定平台低于车厢地板150～200mm，曲线车辆轮廓间隙不大于300mm。",
        ["DB11表格宽度", "DB11高程和间隙", "GB 55033高差和曲线间隙"], [ref(DB, 40, "6.2.2", "表6.2.2及950/50/150/300mm。", "表6.2.2"), ref(GB55, 17, "3.0.10", "低于车厢地板150～200mm，曲线间隙不大于300mm。")],
        [{"value": "600/800/1000", "unit": "mm", "conditions": ["DB11单/双线及一般/困难情况"]}, {"value": "150-200/300", "unit": "mm", "conditions": ["GB 55033平台高差/曲线间隙"]}],
    ),
    item(
        "P1-IND-018", "cross_spec_comparison", "DB11/T 995-2025 与 GB 55033-2022 对车站出入口数量和周边协调分别提出了什么要求？",
        (DB, GB55), "answer", "DB11要求按车站层级确定数量、连通率和结建率，并给出部分比例；GB 55033要求合理确定数量和用地范围，与周边用地、建筑、道路协调，保障客流顺畅且不影响道路。",
        ["DB11分级和比例", "GB 55033周边协调"], [ref(DB, 59, "10.2.1", "按四个层级确定数量、连通率和结建率。"), ref(GB55, 9, "2.1.30", "合理确定数量和用地范围并与周边协调。")],
    ),
    item(
        "P1-IND-019", "cross_spec_numeric", "GB 55033-2022 与 GB 50157-2013 对地下车站公共区二氧化碳日平均浓度上限分别是多少？仅陈述各自文本。",
        (GB55, GB50), "answer", "GB 55033为小于0.15%；GB 50157为小于1.5%。",
        ["逐规范数值，不自行调和冲突"], [ref(GB55, 34, "6.4.11", "二氧化碳日平均浓度小于0.15%。"), ref(GB50, 142, "13.2.19", "二氧化碳日平均浓度小于1.5%。")],
        [{"value": "0.15/1.5", "unit": "%", "conditions": ["分别对应GB 55033/GB 50157"]}],
    ),
    item(
        "P1-IND-020", "cross_spec_numeric", "DB11/T 995-2025 与 GB 55033-2022 对通信后备供电时间有什么直接要求？",
        (DB, GB55), "answer", "DB11民用传输系统不间断电源后备供电不少于2h；GB 55033通信电源后备供电不少于2h，并要求集中监控、不间断无瞬变供电、接地安全和防雷。",
        ["两规范2h及各自对象", "GB 55033附加条件"], [ref(DB, 150, "17.5.6", "民用传输系统不间断电源后备供电不少于2h。"), ref(GB55, 31, "6.2.3", "通信电源后备供电不少于2h，并有监控、接地、防雷要求。")],
        [{"value": "2", "unit": "h", "conditions": ["后备供电下限，注意适用对象"]}],
    ),
    item(
        "P1-IND-021", "table_lookup", "GB 55033-2022 表3.0.4中，密闭性车体在140km/h和160km/h速度等级下的车辆断面与隧道净断面面积之比分别应满足什么值？",
        (GB55,), "answer", "分别小于0.35和小于0.29。",
        ["两个速度等级对应的面积比"], [ref(GB55, 14, "3.0.4", "密闭性车体140km/h<0.35，160km/h<0.29。", "表3.0.4")],
        [{"value": "0.35/0.29", "unit": "比值", "conditions": ["密闭性车体140/160km/h"]}],
    ),
    item(
        "P1-IND-022", "table_lookup", "DB11/T 995-2025 表8.2.2中，曲线半径250m＞R≥200m与200m＞R≥150m时，A型车和B型车轨距加宽值分别是多少？",
        (DB,), "answer", "250m＞R≥200m时A型车5mm、B型车不加宽；200m＞R≥150m时A型车10mm、B型车5mm。",
        ["两行、两车型及不适用单元格"], [ref(DB, 50, "8.2.2", "表8.2.2两档半径对应A/B型车加宽值。", "表8.2.2")],
        [{"value": "5/10/5", "unit": "mm", "conditions": ["两档曲线半径和A/B型车"]}],
    ),
    item(
        "P1-IND-023", "multi_numeric", "GB 50157-2013 对无砟道床混凝土强度、耐久年限和伸缩缝间距有哪些定量要求？",
        (GB50,), "answer", "隧道/U形地段不低于C35，高架/地面不低于C40，耐久100年；隧道伸缩缝不宜大于12.5m，U形、洞口50m内、高架和库内不宜大于6m。",
        ["两类混凝土等级", "100年耐久", "两类伸缩缝间距及适用场景"], [ref(GB50, 68, "7.4.1", "C35/C40、100年、12.5m/6m及适用场景。")],
        [{"value": "C35/C40", "unit": "强度等级", "conditions": ["隧道/U形与高架/地面"]}, {"value": "100", "unit": "年", "conditions": ["耐久性"]}, {"value": "12.5/6", "unit": "m", "conditions": ["不同地段伸缩缝间距"]}],
    ),
    item(
        "P1-IND-024", "multi_requirement", "GB 55033-2022 对公共交通重载型自动扶梯的制动载荷连续运行、紧急停止和传动安全有哪些要求？",
        (GB55,), "answer", "任意3h内以100%制动载荷连续运行不少于1h；设置紧急停止开关和附加制动器；主驱动链安全系数不小于8，链条不少于2排，三角皮带不少于3根。",
        ["3h/1h/100%", "紧急停止与附加制动器", "安全系数和传动件数量"], [ref(GB55, 38, "6.9.3", "任意3h内100%制动载荷1h；紧急停止、附加制动器；安全系数及链/带数量。")],
        [{"value": "3/1/100", "unit": "h/h/%", "conditions": ["制动载荷连续运行"]}, {"value": "8/2/3", "unit": "系数/排/根", "conditions": ["主驱动链、链条、三角皮带"]}],
    ),
    item(
        "P1-IND-025", "same_article_isolation", "请分别说明三份规范各自第6.2.3条的主题和核心要求，不要把同号条文混在一起。",
        (DB, GB55, GB50), "answer", "DB11为隧道阻塞比表；GB 50157为曲线间夹直线；GB 55033为通信电源及2h后备供电。",
        ["三份6.2.3分别陈述", "规范身份和页码不串引"], [ref(DB, 40, "6.2.3", "隧道阻塞比：110km/h≤0.45，120km/h≤0.4。", "表6.2.3"), ref(GB55, 31, "6.2.3", "通信电源集中监控、不间断供电、后备2h、接地与防雷。"), ref(GB50, 57, "6.2.3", "曲线间夹直线设计及表6.2.3。", "表6.2.3")],
        [{"value": "0.45/0.4/2", "unit": "比值/比值/h", "conditions": ["分别属于DB11阻塞比与GB 55033后备供电"]}],
    ),
    item(
        "P1-IND-026", "version_ambiguous", "地铁设计规范对地下车站二氧化碳浓度怎么规定？",
        (), "clarify_scope", "应先要求用户明确规范编号、版本及适用项目条件。", ["不得猜测版本或适用性"], [], answerable=False,
        why_unanswerable="规范版本和项目适用条件未明确，必须先澄清。",
    ),
    item(
        "P1-IND-027", "scope_ambiguous", "第6.2.3条规定了什么？",
        (), "clarify_scope", "应先要求用户选择规范和版本。", ["不得把三份同号条文混合"], [], answerable=False,
        why_unanswerable="三份规范均存在第6.2.3条且主题不同。",
    ),
    item(
        "P1-IND-028", "partial_support_unanswerable", "仅依据 DB11/T 995-2025 和 GB 55033-2022，某个尚未给出层级、周边规划实施率和场地条件的车站究竟应设置几个出入口？",
        (DB, GB55), "refuse", "规范只给出分级、协调和比例原则；缺少项目层级、实施率、客流与场地条件，不能确定具体数量。",
        ["说明已有原则", "明确缺少项目条件", "不得给出具体数量"], [ref(DB, 59, "10.2.1", "按层级确定数量、连通率和结建率。"), ref(GB55, 9, "2.1.30", "合理确定出入口数量并与周边协调。")], answerable=False,
        why_unanswerable="缺少车站层级、周边规划实施率、客流和场地条件，规范不能直接给出项目数量。",
    ),
    item(
        "P1-IND-029", "unanswerable_project_fact", "在三份规范范围内，某拟建线路2035年的实际单向高峰小时客流量和所需列车数分别是多少？",
        (DB, GB55, GB50), "refuse", "规范提供设计原则但不包含该项目的预测客流和列车配置数据。",
        ["拒绝补造项目预测值", "区分规范原则与项目数据"], [], answerable=False,
        why_unanswerable="项目预测客流及列车配置不在三份规范中。",
    ),
    item(
        "P1-IND-030", "unanswerable_measured_fact", "仅依据 GB 55033-2022，某地下车站今天实测的二氧化碳日平均浓度是多少，是否合格？",
        (GB55,), "refuse", "规范给出0.15%限值，但未提供该车站实测值，不能判断实际值或合格性。",
        ["说明规范限值", "明确实测值缺失", "不得判断合格"], [ref(GB55, 34, "6.4.11", "二氧化碳日平均浓度应小于0.15%。")],
        [{"value": "0.15", "unit": "%", "conditions": ["规范限值，不是项目实测值"]}], answerable=False,
        why_unanswerable="缺少目标车站实测数据。",
    ),
]


def main() -> None:
    DATASET.parent.mkdir(parents=True, exist_ok=True)
    DATASET.write_text(
        "".join(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n" for case in CASES),
        encoding="utf-8",
        newline="\n",
    )
    review_cases = []
    for case in CASES:
        review_cases.append(
            {
                "id": case["id"],
                "verdict": "approved",
                "answerable": case["answerable"],
                "expected_behavior": case["expected_behavior"],
                "checks": {
                    "question_is_new_and_not_a_rewrite_of_phase1_development_examples": "pass",
                    "scope_and_version": "pass",
                    "answerability_or_clarification_boundary": "pass",
                    "pdf_page_article_or_table": "pass",
                    "required_answer_points": "pass",
                    "numeric_values_units_conditions": "pass",
                },
                "references": case["source_references"],
                "visually_reviewed_pages": sorted(
                    {f"{source['business_id']}#pdf-page-{source['pdf_page']}" for source in case["source_references"]}
                ),
                "system_answer_inspected": False,
            }
        )
    REVIEW.write_text(
        json.dumps(
            {
                "dataset_id": "phase1_cross_spec_independent_v1",
                "reviewed_at": "2026-11-06",
                "reviewer": "Codex (AI; user-authorized PDF content reviewer)",
                "reviewer_type": "AI",
                "licensed_domain_expert": False,
                "candidate_system_answers_run_or_inspected": False,
                "source_files": {
                    DB: {"pdf": "data/raw/城市轨道交通工程设计标准.pdf", "sha256": "e5ca2388ad68ed7b21b6092e66c12a73c74c17de8b532bef91c5b2ea57be78f7"},
                    GB55: {"pdf": "data/raw/GB55033-2022_城市轨道交通工程项目规范.pdf", "sha256": "907ffd92c569f79f163121904cccce69bc20905f9563854960bd184ca76f6fef"},
                    GB50: {"pdf": "data/raw/GB50157-2013_地铁设计规范.pdf", "sha256": "a1130f89afba11f00fdb3353375aa1c424b4eb44d462ee6bd1de2835c235dab3"},
                },
                "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
                "case_count": len(CASES),
                "approved": len(CASES),
                "rejected": 0,
                "limitations": [
                    "AI content review; not a licensed domain-expert sign-off.",
                    "Rendered PDF pages were checked for layout, tables, numbers, units and conditions.",
                    "No candidate-system retrieval, grader or generation result was run or inspected before review and first commit.",
                ],
                "cases": review_cases,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {len(CASES)} cases sha256={hashlib.sha256(DATASET.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
