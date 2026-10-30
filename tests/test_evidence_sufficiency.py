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
