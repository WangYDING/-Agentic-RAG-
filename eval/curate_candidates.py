"""Curate and source-verify phase-6 candidate datasets without running the RAG system."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from src.loader import load_pdf_pages


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "raw" / "城市轨道交通工程设计标准.pdf"
DATA_DIR = ROOT / "eval" / "datasets"
REVIEW_DIR = ROOT / "eval" / "reviews"
REVIEWER = "Codex AI-assisted source verification"
REVIEWED_AT = "2026-10-31"


QUESTIONS = {
    "REG-001": "运营组织设计和运营设计规模分别应依据哪些因素确定？",
    "REG-003": "线路运营模式选择及系统设计最大能力有哪些要求？",
    "REG-004": "单一交路、多交路和支线的系统设计最大能力分别有什么下限要求？",
    "REG-005": "设计最高运行速度和跨线运行线路交汇点应如何确定与设置？",
    "REG-006": "跨线运行线路的交汇点及区间接轨安全线应如何设置？",
    "REG-008": "普线和快线在单一交路、多交路条件下的高峰和平峰运行间隔上限分别是多少？",
    "REG-009": "非全自动和全自动运行线路的开关门及附加时间有何要求？",
    "REG-010": "快慢车运营的停站方案、越行次数和到发间隔有哪些要求？",
    "REG-011": "灵活编组运营可以采用哪些方式，解编重联作业区和乘客信息应如何设置？",
    "REG-012": "跨线运营在贯通运行、技术标准和高峰小时行车对数方面有哪些要求？",
    "REG-013": "折返线的能力、位置和应急检修条件有哪些要求？",
    "REG-014": "停车线和单渡线的间距、功能及特殊区段设置有哪些要求？",
    "REG-015": "快慢车线路的越行站、避让线及有效长度应如何确定？",
    "REG-016": "互联互通联络线和资源共享型联络线分别应如何设置？",
    "REG-017": "哪些接轨场景必须设置安全线？",
    "REG-018": "车站管理用房应如何按站区和车站类型配置？",
    "REG-019": "车辆防雨雪和洗车防水有哪些要求？",
    "REG-020": "车辆密封和电气设备外壳防护应符合哪些标准与要求？",
    "REG-021": "车辆最高运行、通过洗车机和联挂时的速度要求分别是什么？",
    "REG-022": "列车在丧失不同比例动力以及救援无动力列车时应具备哪些能力？",
    "REG-023": "密封性列车的动态密封指数和压力下降时间有什么要求？",
    "REG-024": "转向架结构、轴箱定位和车轮选型有哪些要求？",
    "REG-025": "列车控制及监控系统应具备哪些功能、可靠性和数据保存能力？",
    "REG-026": "车辆空调在制冷、新风、紧急通风和采暖方面有哪些定量要求？",
    "REG-027": "车辆结构材料、电线电缆和防火标准有哪些要求？",
    "IND-001": "客室车门安全联锁与车辆前后端照明、信号装置分别有哪些要求？",
    "IND-002": "司机室前照灯、列车尾灯和车辆侧壁指示灯有哪些配置与性能要求？",
    "IND-003": "全自动运行列车应具备哪些功能，限界坐标系又应如何建立？",
    "IND-005": "人防隔断门或防淹门的建筑限界，以及设备安装地段的限界检算有哪些要求？",
    "IND-007": "车辆基地库内平台、车库大门和信号设备与车辆轮廓或设备限界之间有哪些净距要求？",
    "IND-008": "区间隧道的强弱电设备、消防水管、疏散平台和射流风机应如何布置？",
    "IND-009": "大坡段与小半径曲线、新建线与既有线贯通时的纵坡确定有哪些限制？",
    "IND-010": "竖曲线与缓和曲线重叠有哪些限制，整体道床重叠时超高顺坡率上限是多少？",
    "IND-011": "轨道结构部件、工程材料和新产品选用有哪些原则？",
    "IND-012": "无砟轨道扣件的弹性、刚度、动静比、绝缘和防腐要求是什么？",
    "IND-013": "地下线、高架线、地面线和车场库内线应选用何种道床，并有哪些控制与防护要求？",
    "IND-014": "无砟与有砟道床、不同减振地段之间的过渡段应如何设置？",
    "IND-015": "高架线无缝线路的受力检算、断缝宽度、调节器和钢轨接头位置有哪些要求？",
    "IND-016": "减振轨道措施的位置和方案应依据哪些评价文件确定？",
    "IND-017": "高架线防脱护轨应设置在哪些位置和范围？",
}


NUMERIC_CORRECTIONS = {
    "REG-010": [
        ("2", "次", "主要通勤起止点范围内，慢车被快车越行的次数不宜大于两次"),
        ("2", "min", "慢车待避不停站快车时的总停站时间不宜大于2min"),
        ("1", "min", "快车在越行站超过慢车时，慢车与快车的到通间隔不宜小于1min"),
    ],
    "REG-012": [
        ("6", "对/h", "跨线列车在客流高断面范围内的高峰小时行车对数下限"),
        ("1/3", "无量纲比例", "跨线列车在低断面范围内的高峰小时行车量不宜低于本线总行车量的1/3"),
    ],
    "REG-022": [
        ("1/4及以下", "无量纲比例", "AW3工况下丧失动力的比例；动拖比大于1:1时维持全天运营，动拖比1:1时维持运行到终点"),
        ("1/3", "无量纲比例", "AW3工况下丧失动力的比例；列车应能在正线最大坡道上启动并维持运行到终点"),
        ("1/2", "无量纲比例", "AW3工况下丧失动力的比例；列车应能在正线最大坡道上启动并运行至下一车站清客后回库"),
    ],
    "REG-023": [
        ("6", "s", "动态密封指数τ应大于6s"),
        ("120", "km/h", "适用于120km/h等级车辆"),
        ("2,100", "Pa", "车厢内空气压力的起始值"),
        ("1,000", "Pa", "车厢内空气压力的终止值"),
        ("15", "s", "压力由2,100Pa降至1,000Pa的时间不应小于15s"),
    ],
    "REG-025": [("6", "个月", "断电后数据存储时间不宜小于6个月")],
    "REG-026": [
        ("33", "℃", "制冷能力考核时的环境温度"),
        ("27±1", "℃", "环境温度为33℃时的客室温度上限"),
        ("12", "m³/(人·h)", "客室按定员载客人数计的人均新风量下限；规范原文表述为人均不应少于12m³/h"),
        ("8", "m³/(人·h)", "紧急通风人均通风量下限；规范原文表述为人均不应少于8m³/h"),
        ("30", "m³/(人·h)", "制冷时司机室人均新风量下限；规范原文表述为人均不应少于30m³/h"),
        ("0", "℃", "采暖能力考核时的车外环境温度"),
        ("18", "℃", "采暖运行时司机室温度下限"),
        ("15", "℃", "采暖运行时空车客室温度下限"),
    ],
    "IND-010": [
        ("400", "m", "整体道床曲线半径低于400m时宜避免竖缓重叠"),
        ("2.0", "‰", "竖曲线与缓和曲线重叠时的超高顺坡率上限"),
    ],
    "IND-012": [
        ("20～40", "kN/mm", "无砟道床一般地段扣件节点垂向静刚度"),
        ("1.4", "无量纲", "扣件节点动静比上限"),
        ("10^8", "Ω", "单个扣件节点绝缘部件工作电阻下限"),
    ],
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text).replace(",", "，")


def _atomize(answer: str) -> list[str]:
    points = []
    for section in answer.splitlines():
        section = _clean(section)
        section = re.sub(r"([：；])\s*(?=\d+\s+)", r"\1\n", section)
        for part in re.split(r"[\n。；]+", section):
            part = re.sub(r"^\d+\s+", "", part).strip(" ：；。")
            if not part or part.endswith("符合下列规定"):
                continue
            points.append(part)
    return points


def _review() -> dict:
    return {
        "status": "source_verified",
        "reviewer": REVIEWER,
        "reviewed_at": REVIEWED_AT,
        "notes": (
            "AI-assisted verification against the repository PDF: page, clause/table, "
            "answer text and numeric units checked. Human approval is still required before freeze."
        ),
    }


def _table_reg_002() -> dict:
    answer = (
        "表5.3.1显示：A型车和B型车的车轴数均为4。"
        "无司机室车辆车体基本长度分别为21,880mm和19,000mm，带司机室车辆分别为23,600/24,380mm和19,500mm。"
        "无司机室车辆车钩连接中心点间距离分别为22,800mm和19,520mm，带司机室车辆分别为24,400/25,080mm和20,020mm。"
        "A型车带司机室车辆的两组备选长度应根据灵活编组站台屏蔽门对位要求选择。"
    )
    return {
        "question": "A型车和B型车的车轴数、车体基本长度及车钩连接中心点间距离分别是多少？",
        "question_type": "table_lookup",
        "answerable": True,
        "gold_answer": answer,
        "gold_evidence": [
            {"document": "城市轨道交通工程设计标准.pdf", "page": 35, "article": None, "table": "表5.3.1"},
            {"document": "城市轨道交通工程设计标准.pdf", "page": 36, "article": None, "table": "表5.3.1"},
        ],
        "required_requirements": [
            "分别给出A型车和B型车的车轴数",
            "区分有无司机室，给出两种车型的车体基本长度",
            "区分有无司机室，给出两种车型的车钩连接中心点间距离",
            "说明A型车带司机室车辆两组备选长度的适用条件",
        ],
        "key_answer_points": _atomize(answer),
        "numeric_expectations": [
            {"value": "4", "unit": "轴", "conditions": ["A型车和B型车的车轴数"]},
            {"value": "21,880", "unit": "mm", "conditions": ["A型车无司机室车辆车体基本长度"]},
            {"value": "19,000", "unit": "mm", "conditions": ["B型车无司机室车辆车体基本长度"]},
            {"value": "23,600或24,380", "unit": "mm", "conditions": ["A型车带司机室车辆车体基本长度；按灵活编组站台屏蔽门对位要求选择"]},
            {"value": "19,500", "unit": "mm", "conditions": ["B型车带司机室车辆车体基本长度"]},
            {"value": "22,800", "unit": "mm", "conditions": ["A型车无司机室车辆车钩连接中心点间距离"]},
            {"value": "19,520", "unit": "mm", "conditions": ["B型车无司机室车辆车钩连接中心点间距离"]},
            {"value": "24,400或25,080", "unit": "mm", "conditions": ["A型车带司机室车辆车钩连接中心点间距离；按灵活编组站台屏蔽门对位要求选择"]},
            {"value": "20,020", "unit": "mm", "conditions": ["B型车带司机室车辆车钩连接中心点间距离"]},
        ],
        "source_excerpt": "表5.3.1 主要技术规格：车轴数、车体基本长度、车钩连接中心点间距离。",
    }


def _table_ind_004() -> dict:
    answer = (
        "表6.3.1显示：行车方向右侧限界至线路中心线距离，A型车、B1型车、B2型车分别为2200mm、2100mm、2100mm。"
        "行车方向左侧设置纵向辅助疏散平台时分别为2500mm、2400mm、2400mm。"
        "左侧不设纵向辅助疏散平台时分别为2100mm、2000mm、2000mm。"
    )
    return {
        "question": "直线地段单线矩形隧道中，A型车、B1型车和B2型车在左右侧不同疏散平台条件下的建筑限界宽度分别是多少？",
        "question_type": "table_lookup",
        "answerable": True,
        "gold_answer": answer,
        "gold_evidence": [
            {"document": "城市轨道交通工程设计标准.pdf", "page": 41, "article": None, "table": "表6.3.1"}
        ],
        "required_requirements": [
            "给出行车方向右侧三种车型的限界距离",
            "给出左侧设纵向辅助疏散平台时三种车型的限界距离",
            "给出左侧不设纵向辅助疏散平台时三种车型的限界距离",
        ],
        "key_answer_points": _atomize(answer),
        "numeric_expectations": [
            {"value": "2200", "unit": "mm", "conditions": ["行车方向右侧，A型车"]},
            {"value": "2100", "unit": "mm", "conditions": ["行车方向右侧，B1型车或B2型车"]},
            {"value": "2500", "unit": "mm", "conditions": ["行车方向左侧设纵向辅助疏散平台，A型车"]},
            {"value": "2400", "unit": "mm", "conditions": ["行车方向左侧设纵向辅助疏散平台，B1型车或B2型车"]},
            {"value": "2100", "unit": "mm", "conditions": ["行车方向左侧无纵向辅助疏散平台，A型车"]},
            {"value": "2000", "unit": "mm", "conditions": ["行车方向左侧无纵向辅助疏散平台，B1型车或B2型车"]},
        ],
        "source_excerpt": "表6.3.1 直线地段单线矩形隧道建筑限界宽度取值表（mm）。",
    }


def _partial_reg_007(row: dict) -> dict:
    supported = _clean(row.get("source_excerpt") or row["gold_answer"].split(" 规范未提供", 1)[0])
    answer = supported + " 规范未提供本项目最终采用的交路方案和实际交路数量，因此不能完整回答项目实施结果。"
    return {
        "question": "规范对列车运行交路有什么要求？本项目最终采用哪种交路方案、实际设置多少个交路？",
        "question_type": "partial_support_unanswerable",
        "answerable": False,
        "gold_answer": answer,
        "gold_evidence": row["gold_evidence"],
        "required_requirements": [
            "说明规范对运行交路确定和交路数量的要求",
            "识别项目最终方案和实际交路数量不在规范中，拒绝编造",
        ],
        "key_answer_points": [supported, "规范不能给出本项目最终交路方案和实际交路数量"],
        "numeric_expectations": [],
        "hard_negative_type": "partial_support_project_specific",
        "why_unanswerable": "规范仅支持通用设计要求，不包含本项目最终实施方案和实际交路数量。",
        "source_excerpt": row.get("source_excerpt", supported),
    }


def _partial_ind_006(row: dict) -> dict:
    supported = _clean(row.get("source_excerpt") or row["gold_answer"].split(" 规范未给出", 1)[0])
    answer = supported + " 规范未给出本项目实际设备尺寸和最终加宽、加高量，因此不能完整回答项目实施值。"
    return {
        "question": "安装射流风机、风管和配电柜等设备时应怎样检算建筑限界？本项目实际设备尺寸和最终加宽、加高量是多少？",
        "question_type": "partial_support_unanswerable",
        "answerable": False,
        "gold_answer": answer,
        "gold_evidence": row["gold_evidence"],
        "required_requirements": [
            "说明设备安装地段的建筑限界检算与处置要求",
            "识别项目实际设备尺寸和最终加宽、加高量不在规范中，拒绝编造",
        ],
        "key_answer_points": [supported, "规范不能给出本项目实际设备尺寸和最终加宽、加高量"],
        "numeric_expectations": [],
        "hard_negative_type": "partial_support_project_specific",
        "why_unanswerable": "规范提供通用检算原则，但不包含本项目设备尺寸和最终工程处置量。",
        "source_excerpt": row.get("source_excerpt", supported),
    }


def _load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _curate_row(row: dict) -> dict:
    row = dict(row)
    if row["id"] == "REG-002":
        row.update(_table_reg_002())
    elif row["id"] == "IND-004":
        row.update(_table_ind_004())
    elif row["id"] == "REG-007":
        row.update(_partial_reg_007(row))
    elif row["id"] == "IND-006":
        row.update(_partial_ind_006(row))
    elif row["id"] in QUESTIONS:
        row["question"] = QUESTIONS[row["id"]]

    row["gold_answer"] = _clean(row.get("gold_answer", ""))
    row["source_excerpt"] = _clean(row.get("source_excerpt", ""))
    if row["answerable"] and row["id"] not in {"REG-002", "IND-004"}:
        row["key_answer_points"] = _atomize(row["gold_answer"])
        row["required_requirements"] = [f"覆盖要点：{point}" for point in row["key_answer_points"]]
    if row["id"] in NUMERIC_CORRECTIONS:
        row["numeric_expectations"] = [
            {"value": value, "unit": unit, "conditions": [condition]}
            for value, unit, condition in NUMERIC_CORRECTIONS[row["id"]]
        ]
    row["annotation_review"] = _review()
    return row


def _verify_sources(rows: list[dict], pages: dict[int, object]) -> list[dict]:
    results = []
    for row in rows:
        refs = row.get("gold_evidence", [])
        checks = []
        for ref in refs:
            page = pages[ref["page"]]
            article = ref.get("article")
            table = ref.get("table")
            checks.append(
                {
                    "page": ref["page"],
                    "article": article,
                    "table": table,
                    "article_found": article is None or article in page.text,
                    "table_found": table is None
                    or any(item.metadata.table_id == table for item in page.tables),
                }
            )
        source_text = "".join(pages[ref["page"]].text for ref in refs)
        answer_points_found = None
        if row["answerable"] and not any(ref.get("table") for ref in refs):
            answer_points_found = all(
                _norm(point) in _norm(source_text) for point in row["key_answer_points"]
            )
        passed = all(
            check["article_found"] and check["table_found"] for check in checks
        ) and answer_points_found is not False
        results.append(
            {
                "id": row["id"],
                "passed": passed,
                "reference_checks": checks,
                "answer_points_found": answer_points_found,
            }
        )
    return results


def _write_manifest(data_path: Path) -> None:
    manifest_path = data_path.with_suffix(".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = _load_rows(data_path)
    manifest["version"] = "0.2-source-verified"
    manifest["sha256"] = _sha256(data_path)
    manifest["count"] = len(rows)
    manifest["type_distribution"] = dict(Counter(row["question_type"] for row in rows))
    manifest["notes"] = (
        "AI-assisted source verification completed against the repository PDF on 2026-10-31. "
        "Questions were naturalized, rubrics atomized, numeric units corrected, and dedicated table/partial-support cases added. "
        "Dataset remains draft: source_verified is not human approval; independent data must not be run before human approval, acceptance criteria, and freeze."
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def curate(write: bool) -> dict:
    _, loaded_pages = load_pdf_pages(str(PDF_PATH))
    pages = {page.metadata.page_number: page for page in loaded_pages}
    files = [
        DATA_DIR / "regression_v1_draft.jsonl",
        DATA_DIR / "independent_v2_draft.jsonl",
    ]
    all_results = []
    output_rows = {}
    for path in files:
        rows = [_curate_row(row) for row in _load_rows(path)]
        output_rows[path] = rows
        all_results.extend(_verify_sources(rows, pages))
    failed = [result for result in all_results if not result["passed"]]
    if failed:
        raise ValueError(f"source verification failed: {[item['id'] for item in failed]}")

    report = {
        "reviewed_at": REVIEWED_AT,
        "reviewer": REVIEWER,
        "scope": "PDF source, page, article/table, answer points, numeric units, question/rubric quality",
        "result": "source_verified",
        "case_count": len(all_results),
        "passed": len(all_results),
        "failed": 0,
        "human_approval_required": True,
        "independent_dataset_executed": False,
        "cases": all_results,
    }
    if write:
        for path, rows in output_rows.items():
            path.write_text(
                "".join(
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                    for row in rows
                ),
                encoding="utf-8",
            )
            _write_manifest(path)
        REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        (REVIEW_DIR / "candidate_source_review_2026-10-31.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write curated datasets, manifests and review report")
    args = parser.parse_args()
    report = curate(args.write)
    print(json.dumps({key: report[key] for key in ("result", "case_count", "passed", "failed", "human_approval_required")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
