import json
import unittest
from types import SimpleNamespace

from src.evidence import Evidence
from src.evidence_sufficiency import EvidenceSufficiencyGrader
from src.reliability import InvalidModelResponseError


class FakeCompletions:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.payload)))])


class SequenceCompletions:
    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.contents.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class EvidenceSufficiencyGraderTest(unittest.TestCase):
    def setUp(self):
        self.evidence = Evidence("E1", "坡度不应超过40‰", "spec.pdf", 48, 48, 1, article_id="7.3.1")

    def test_parses_structured_decision(self):
        completions = FakeCompletions({
            "decision": "insufficient",
            "supported_evidence_ids": ["E1"],
            "missing_requirements": ["建设费用"],
            "reason": "证据仅支持坡度要求。",
        })
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        result = EvidenceSufficiencyGrader(client=client, model="test").grade("坡度和费用？", [self.evidence])

        self.assertEqual(result.decision, "insufficient")
        self.assertEqual(result.missing_requirements, ["建设费用"])
        self.assertEqual(completions.calls[0]["response_format"], {"type": "json_object"})
        self.assertEqual(completions.calls[0]["temperature"], 0)

    def test_complete_applicable_clause_does_not_require_invented_metrics(self):
        evidence = Evidence(
            "E1",
            (
                "5.6.9 司机室前端应装设可远近光变换的前照灯。"
                "前照灯在车辆前端紧急制停距离处照度不应小于2 lx。"
                "列车尾端应设有红色防护灯。"
                "车辆侧壁可设置显示车门开闭、制动缸缓解等指示灯。"
            ),
            "spec.pdf",
            39,
            39,
            569,
            article_id="5.6.9",
        )
        completions = FakeCompletions({
            "decision": "sufficient",
            "supported_evidence_ids": ["E1"],
            "missing_requirements": [],
            "reason": "适用条文已给出三类装置的全部配置与性能规定。",
        })
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        result = EvidenceSufficiencyGrader(client=client, model="test").grade(
            "司机室前照灯、列车尾灯和车辆侧壁指示灯有哪些配置与性能要求？",
            [evidence],
        )

        prompt = completions.calls[0]["messages"][1]["content"]
        self.assertEqual(result.decision, "sufficient")
        self.assertIn("不得自行增加数值指标、性能参数或验收条件", prompt)
        self.assertIn("适用证据没有为某对象规定额外指标", prompt)

    def test_shared_performance_qualifier_is_not_distributed_to_every_list_item(self):
        evidence = Evidence(
            "E1",
            (
                "司机室前端应装设可远近光变换的前照灯，照度不应小于2 lx。"
                "列车尾端应设有红色防护灯。"
                "车辆侧壁可设置显示车门开闭、制动缸缓解等指示灯。"
            ),
            "spec.pdf", 39, 39, 569, article_id="5.6.9",
        )
        completions = FakeCompletions({
            "decision": "insufficient",
            "supported_evidence_ids": ["E1"],
            "missing_requirements": ["列车尾灯的性能要求", "车辆侧壁指示灯的性能要求"],
            "reason": "模型把共享限定分配到了每个对象。",
        })
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        result = EvidenceSufficiencyGrader(client=client, model="test").grade(
            "司机室前照灯、列车尾灯和车辆侧壁指示灯有哪些配置与性能要求？",
            [evidence],
        )

        self.assertEqual(result.decision, "sufficient")
        self.assertEqual(result.missing_requirements, [])

    def test_explicit_missing_object_requirement_remains_insufficient(self):
        decision = EvidenceSufficiencyGrader._parse(
            json.dumps({
                "decision": "insufficient",
                "supported_evidence_ids": ["E1"],
                "missing_requirements": ["列车尾灯的性能要求"],
                "reason": "证据没有列车尾灯。",
            }),
            {"E1"},
        )
        evidence = Evidence(
            "E1", "司机室前端应装设前照灯。", "spec.pdf", 39, 39, 569
        )

        normalized = EvidenceSufficiencyGrader._normalize_distributed_performance_requirements(
            "司机室前照灯和列车尾灯有哪些配置与性能要求？",
            [evidence],
            decision,
        )

        self.assertEqual(normalized.decision, "insufficient")

    def test_open_provisions_query_does_not_require_cartesian_product(self):
        decision = EvidenceSufficiencyGrader._parse(
            json.dumps({
                "decision": "insufficient",
                "supported_evidence_ids": ["E1"],
                "missing_requirements": ["机械通风时司机室人均风量的规定"],
                "reason": "模型构造了场景对象全组合。",
            }),
            {"E1"},
        )
        evidence = Evidence(
            "E1",
            (
                "客室及司机室应根据需要设置通风、空调设施，并应符合下列规定："
                "机械通风时客室人均供风量不应少于20m³/h；"
                "空调时客室人均新风量不应少于10m³/h，司机室不应少于30m³/h。"
            ),
            "spec.pdf", 20, 20, 1,
        )

        normalized = EvidenceSufficiencyGrader._normalize_non_cartesian_enumeration(
            "对车辆机械通风、空调时客室及司机室人均风量有什么规定？",
            [evidence],
            decision,
        )

        self.assertEqual(normalized.decision, "sufficient")

    def test_explicit_per_combination_query_keeps_missing_combination(self):
        decision = EvidenceSufficiencyGrader._parse(
            json.dumps({
                "decision": "insufficient",
                "supported_evidence_ids": ["E1"],
                "missing_requirements": ["机械通风时司机室人均风量"],
                "reason": "明确要求的组合缺失。",
            }),
            {"E1"},
        )
        evidence = Evidence(
            "E1",
            "客室及司机室通风、空调应符合下列规定：机械通风时客室20；空调时客室10、司机室30。",
            "spec.pdf", 20, 20, 1,
        )

        normalized = EvidenceSufficiencyGrader._normalize_non_cartesian_enumeration(
            "机械通风、空调时客室及司机室各组合的风量分别是多少？",
            [evidence],
            decision,
        )

        self.assertEqual(normalized.decision, "insufficient")

    def test_cross_spec_comparison_allows_supported_asymmetry(self):
        decision = EvidenceSufficiencyGrader._parse(
            json.dumps({
                "decision": "insufficient",
                "supported_evidence_ids": ["E1", "E2"],
                "missing_requirements": ["DB11机械通风客室风量"],
                "reason": "模型要求形成对称矩阵。",
            }),
            {"E1", "E2"},
        )
        evidences = [
            Evidence(
                "E1", "客室空调新风12，紧急通风8，司机室新风30。",
                "a.pdf", 1, 1, 1, spec_id="cn.a", edition_id="2025",
            ),
            Evidence(
                "E2", "客室机械通风20，空调新风10，司机室新风30。",
                "b.pdf", 1, 1, 2, spec_id="cn.b", edition_id="2022",
            ),
        ]

        normalized = EvidenceSufficiencyGrader._normalize_cross_spec_asymmetry(
            "比较两份规范对客室机械通风、空调新风和司机室新风的数值差异",
            evidences,
            decision,
            ("cn.a@2025", "cn.b@2022"),
        )

        self.assertEqual(normalized.decision, "sufficient")

    def test_cross_spec_comparison_with_unrepresented_scope_remains_insufficient(self):
        decision = EvidenceSufficiencyGrader._parse(
            json.dumps({
                "decision": "insufficient",
                "supported_evidence_ids": ["E1"],
                "missing_requirements": ["第二份规范的全部相关规定"],
                "reason": "第二份规范没有相关证据。",
            }),
            {"E1"},
        )
        evidences = [Evidence(
            "E1", "客室空调新风12。", "a.pdf", 1, 1, 1,
            spec_id="cn.a", edition_id="2025",
        )]

        normalized = EvidenceSufficiencyGrader._normalize_cross_spec_asymmetry(
            "比较两份规范的客室新风差异",
            evidences,
            decision,
            ("cn.a@2025", "cn.b@2022"),
        )

        self.assertEqual(normalized.decision, "insufficient")

    def test_open_requirements_query_does_not_require_unstated_numeric_gap(self):
        decision = EvidenceSufficiencyGrader._parse(
            json.dumps({
                "decision": "insufficient",
                "supported_evidence_ids": ["E1"],
                "missing_requirements": [
                    "车库大门净距要求（证据仅规定大门高度按接触网限界确定，未给出净距数值）"
                ],
                "reason": "模型增加了数值要求。",
            }),
            {"E1"},
        )
        evidence = Evidence(
            "E1",
            "建筑限界应符合下列规定：车库大门高度应按接触网安装高度限界确定。",
            "spec.pdf", 42, 42, 1,
        )

        normalized = EvidenceSufficiencyGrader._normalize_unasked_numeric_detail(
            "库内平台、车库大门和信号设备有哪些净距要求？",
            [evidence],
            decision,
        )

        self.assertEqual(normalized.decision, "sufficient")

    def test_explicit_numeric_question_is_not_normalized(self):
        decision = EvidenceSufficiencyGrader._parse(
            json.dumps({
                "decision": "insufficient",
                "supported_evidence_ids": ["E1"],
                "missing_requirements": ["车库大门未给出具体净距数值"],
                "reason": "明确询问的数值缺失。",
            }),
            {"E1"},
        )
        evidence = Evidence(
            "E1", "建筑限界应符合下列规定：大门高度按接触网限界确定。",
            "spec.pdf", 42, 42, 1,
        )

        normalized = EvidenceSufficiencyGrader._normalize_unasked_numeric_detail(
            "车库大门的具体净距数值和限值是多少？", [evidence], decision
        )

        self.assertEqual(normalized.decision, "insufficient")

    def test_applicable_enumeration_can_cover_a_broader_category_name(self):
        evidence = Evidence(
            "E1",
            "司机室前端应设前照灯；列车尾端应设红色防护灯；侧壁可设车门状态指示灯。",
            "spec.pdf",
            39,
            39,
            569,
            article_id="5.6.9",
        )
        completions = FakeCompletions({
            "decision": "sufficient",
            "supported_evidence_ids": ["E1"],
            "missing_requirements": [],
            "reason": "适用条文已逐项展开照明和信号装置。",
        })
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        result = EvidenceSufficiencyGrader(client=client, model="test").grade(
            "车辆前后端照明、信号装置有哪些要求？", [evidence]
        )

        prompt = completions.calls[0]["messages"][1]["content"]
        self.assertEqual(result.decision, "sufficient")
        self.assertIn("不得再要求一个名称完全相同", prompt)
        self.assertIn("明确列出的具体对象若未在证据中出现", prompt)

    def test_explicit_project_condition_still_requires_support(self):
        evidence = Evidence(
            "E1",
            "6.3.11 设备地段应按安装位置及尺寸检算建筑限界，必要时局部加宽、加高。",
            "spec.pdf",
            42,
            42,
            6311,
            article_id="6.3.11",
        )
        completions = FakeCompletions({
            "decision": "insufficient",
            "supported_evidence_ids": ["E1"],
            "missing_requirements": ["本项目实际设备尺寸和最终加宽、加高量"],
            "reason": "证据只有通用原则，没有问题明确询问的项目实际值。",
        })
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        result = EvidenceSufficiencyGrader(client=client, model="test").grade(
            "设备安装时如何检算限界，本项目实际尺寸和最终加宽、加高量是多少？",
            [evidence],
        )

        prompt = completions.calls[0]["messages"][1]["content"]
        self.assertEqual(result.decision, "insufficient")
        self.assertEqual(
            result.missing_requirements,
            ["本项目实际设备尺寸和最终加宽、加高量"],
        )
        self.assertIn("问题明确要求的事实、数值、条件或对象", prompt)

    def test_cross_spec_question_does_not_require_every_topic_from_every_spec(self):
        completions = FakeCompletions({
            "decision": "sufficient",
            "supported_evidence_ids": ["E1"],
            "missing_requirements": [],
            "reason": "可按规范陈述已有直接规定，不补造交叉组合。",
        })
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        result = EvidenceSufficiencyGrader(client=client, model="test").grade(
            "关于穿越水域防淹和车辆基地防淹，各规范有哪些明确要求？",
            [self.evidence],
            scope_business_ids=("cn.a@2025", "cn.b@2022", "cn.c@2013"),
        )

        prompt = completions.calls[0]["messages"][1]["content"]
        self.assertEqual(result.decision, "sufficient")
        self.assertIn("不得推定每份规范都必须分别覆盖", prompt)
        self.assertIn("不能把这个模型自行添加的交叉组合列为缺失要求", prompt)
        self.assertIn("每份文档 × 每个主题", prompt)
        self.assertIn("作为答案内容，而不是 missing_requirement", prompt)
        self.assertIn("不得为了形成对称比较", prompt)

    def test_qualitative_requirement_does_not_invent_a_numeric_limit(self):
        evidence = Evidence(
            "E1",
            "疏散平台宽度按设备安装后的最小有效净宽控制，并应保证行车安全。",
            "spec.pdf",
            42,
            42,
            622,
            article_id="6.2.2",
        )
        completions = FakeCompletions({
            "decision": "sufficient",
            "supported_evidence_ids": ["E1"],
            "missing_requirements": [],
            "reason": "问题未询问数值，可按证据陈述定性控制要求。",
        })
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        result = EvidenceSufficiencyGrader(client=client, model="test").grade(
            "疏散平台宽度有什么要求？", [evidence]
        )

        prompt = completions.calls[0]["messages"][1]["content"]
        self.assertEqual(result.decision, "sufficient")
        self.assertIn("不得把“没有具体数值”另列为缺失", prompt)
        self.assertIn("明确问“数值、多少、限值是多少”", prompt)

    def test_explicit_absence_reporting_does_not_require_proving_full_text_absence(self):
        completions = FakeCompletions({
            "decision": "sufficient",
            "supported_evidence_ids": ["E1"],
            "missing_requirements": [],
            "reason": "可以审慎报告给定证据未找到直接规定。",
        })
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        result = EvidenceSufficiencyGrader(client=client, model="test").grade(
            "比较三份规范；没有直接规定的文档也要明确说明。",
            [self.evidence],
            scope_business_ids=("cn.a@2025", "cn.b@2022", "cn.c@2013"),
        )

        prompt = completions.calls[0]["messages"][1]["content"]
        self.assertEqual(result.decision, "sufficient")
        self.assertIn("不得要求额外证明规范全文不存在", prompt)
        self.assertIn("cn.c@2013", prompt)

    def test_rejects_unknown_evidence_id(self):
        content = json.dumps({
            "decision": "sufficient",
            "supported_evidence_ids": ["E2"],
            "missing_requirements": [],
            "reason": "supported",
        })

        with self.assertRaisesRegex(ValueError, "unknown evidence ID"):
            EvidenceSufficiencyGrader._parse(content, {"E1"})

    def test_rejects_contradictory_sufficient_fields(self):
        content = json.dumps({
            "decision": "sufficient",
            "supported_evidence_ids": ["E1"],
            "missing_requirements": ["仍缺少费用"],
            "reason": "contradictory",
        })

        with self.assertRaisesRegex(ValueError, "empty missing_requirements"):
            EvidenceSufficiencyGrader._parse(content, {"E1"})

    def test_rejects_insufficient_without_missing_requirements(self):
        content = json.dumps({
            "decision": "insufficient",
            "supported_evidence_ids": ["E1"],
            "missing_requirements": [],
            "reason": "missing detail omitted",
        })

        with self.assertRaisesRegex(ValueError, "requires missing_requirements"):
            EvidenceSufficiencyGrader._parse(content, {"E1"})

    def test_invalid_json_gets_one_correction_attempt(self):
        valid = json.dumps({
            "decision": "sufficient",
            "supported_evidence_ids": ["E1"],
            "missing_requirements": [],
            "reason": "supported",
        })
        completions = SequenceCompletions(["not-json", valid])
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        result = EvidenceSufficiencyGrader(client=client, model="test").grade(
            "坡度？", [self.evidence]
        )

        self.assertEqual(result.decision, "sufficient")
        self.assertEqual(len(completions.calls), 2)
        self.assertIn("上一响应不符合", completions.calls[1]["messages"][-1]["content"])

    def test_two_invalid_responses_fail_explicitly(self):
        completions = SequenceCompletions(["", "still-not-json"])
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

        with self.assertRaises(InvalidModelResponseError) as error:
            EvidenceSufficiencyGrader(client=client, model="test").grade(
                "坡度？", [self.evidence]
            )

        self.assertEqual(error.exception.code, "INVALID_MODEL_RESPONSE")
        self.assertEqual(len(completions.calls), 2)


if __name__ == "__main__":
    unittest.main()
