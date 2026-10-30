import json
from dataclasses import dataclass

from openai import OpenAI

from src.evidence import Evidence, build_evidence_context

@dataclass(frozen=True)
class SufficiencyDecision:
    decision: str
    supported_evidence_ids: list[str]
    missing_requirements: list[str]
    reason: str


class EvidenceSufficiencyGrader:
    def __init__(
        self,
        client=None,
        model: str = "deepseek-chat",
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.client = client or OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model

    def grade(self, question: str, evidences: list[Evidence]) -> SufficiencyDecision:
        available_ids = {evidence.evidence_id for evidence in evidences}
        prompt = f"""判断下面的证据是否足以完整回答用户问题。

规则：
1. 只能使用提供的证据，不得使用自身知识或推测补全。
2. relevance 不等于 sufficiency。证据主题相关但缺少所问事实时，必须判为 insufficient。
3. 将问题拆分为所有必要子要求；任一子要求缺少证据，必须判为 insufficient。
4. sufficient 表示可以仅凭证据完整、确定地回答全部问题。
5. supported_evidence_ids 只能使用实际提供的证据编号。
6. 仅输出 JSON，不要输出 Markdown。

JSON 格式：
{{
  "decision": "sufficient 或 insufficient",
  "supported_evidence_ids": ["E1"],
  "missing_requirements": [],
  "reason": "简洁说明判断依据"
}}

用户问题：
{question}

证据：
{build_evidence_context(evidences)}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是严格的证据充分性判定器，只判断给定证据能否完整回答问题。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return self._parse(response.choices[0].message.content, available_ids)

    @staticmethod
    def _parse(content: str, available_ids: set[str]) -> SufficiencyDecision:
        data = json.loads(content)
        decision = data.get("decision")
        if decision not in {"sufficient", "insufficient"}:
            raise ValueError("decision must be 'sufficient' or 'insufficient'")
        supported = data.get("supported_evidence_ids")
        missing = data.get("missing_requirements")
        reason = data.get("reason")
        if not isinstance(supported, list) or not all(isinstance(item, str) for item in supported):
            raise ValueError("supported_evidence_ids must be a list of strings")
        if not set(supported).issubset(available_ids):
            raise ValueError("supported_evidence_ids contains an unknown evidence ID")
        if not isinstance(missing, list) or not all(isinstance(item, str) for item in missing):
            raise ValueError("missing_requirements must be a list of strings")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        return SufficiencyDecision(decision, supported, missing, reason)
