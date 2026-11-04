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
