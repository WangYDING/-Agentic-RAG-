import json
import unittest
from types import SimpleNamespace

from src.evidence import Evidence
from src.evidence_sufficiency import EvidenceSufficiencyGrader


class FakeCompletions:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.payload)))])


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


if __name__ == "__main__":
    unittest.main()
