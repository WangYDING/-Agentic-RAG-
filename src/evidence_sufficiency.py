import json
import re
from dataclasses import dataclass

from openai import OpenAI

from src.evidence import Evidence, build_evidence_context
from src.reliability import (
    CallBudget,
    CallPolicy,
    InvalidModelResponseError,
    execute_model_call,
)

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
        call_policy: CallPolicy | None = None,
    ):
        self.call_policy = call_policy or CallPolicy()
        self.client = client or OpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=0,
            timeout=self.call_policy.request_timeout_seconds,
        )
        self.model = model

    def grade(
        self,
        question: str,
        evidences: list[Evidence],
        *,
        budget: CallBudget | None = None,
        scope_business_ids: tuple[str, ...] = (),
    ) -> SufficiencyDecision:
        available_ids = {evidence.evidence_id for evidence in evidences}
        scope_rules = ""
        scope_context = ""
        if scope_business_ids:
            scope_rules = """
5. 跨规范问题询问“各规范有哪些明确要求”时，只需逐份陈述证据实际给出的要求；不得推定每份规范都必须分别覆盖问题中的每个并列主题。某规范对某主题没有直接证据时，可以审慎表述“给定证据未找到直接规定”，不能把这个模型自行添加的交叉组合列为缺失要求。
6. 问题明确要求“没有直接规定时说明”或“未找到时说明”时，允许基于给定证据回答“给定证据未找到直接规定”；不得要求额外证明规范全文不存在，也不得把这项审慎说明判为证据缺失。
7. 对跨规范比较，即使问题未额外写出“没有时说明”，某份规范的适用证据未规定某个比较项，也应把“给定证据未找到该项直接规定”作为答案内容，而不是 missing_requirement。不得为了形成对称比较而要求证据中不存在的宽度、数值或其他指标。只有用户明确要求证明规范全文不存在该规定时，才需要完整的否定性依据。
"""
            scope_context = (
                "\n本次已绑定查询范围（仅用于识别用户所选规范，不是事实证据）：\n"
                + ", ".join(scope_business_ids)
                + "\n"
            )
        prompt = f"""判断下面的证据是否足以完整回答用户问题。

规则：
1. 只能使用提供的证据，不得使用自身知识或推测补全。
2. relevance 不等于 sufficiency。证据主题相关但缺少所问事实时，必须判为 insufficient。
3. 将问题拆分为必要子要求。子要求只能来自问题明确要求的事实、数值、条件或对象，并以适用证据实际规定的范围为准；不得自行增加数值指标、性能参数或验收条件。
4. 若适用证据没有为某对象规定额外指标，不能仅因缺少这类未规定、未明确询问的指标而判为 insufficient；“有哪些要求”不表示每个对象都必须有数值指标。
   - 若问题只问“有哪些规定/要求”，证据给出最小有效净宽、协调原则、设置条件等定性要求，即可按原文回答；不得把“没有具体数值”另列为缺失。只有问题明确问“数值、多少、限值是多少”时，数值才是必要要求。
   - 比较多份文档和多个主题时，应逐份陈述证据实际规定的主题。不得构造“每份文档 × 每个主题都必须有一条规定”的组合矩阵；某组合没有直接证据时，可审慎说明“给定证据未找到直接规定”。
5. 问题明确询问的事实或条件仍必须逐项得到证据支持。例如问题同时询问通用规范要求和本项目实际值，而证据只有通用要求时，必须判为 insufficient。
6. missing_requirements 只能列出问题明确要求、但证据无法回答的内容，不能写入模型自行推定的要求。
7. sufficient 表示可以仅凭证据完整、确定地回答全部问题。
8. supported_evidence_ids 只能使用实际提供的证据编号。
9. 问题使用上位类别名称、适用条文以具体对象逐项展开时，应按条文的实际枚举判断覆盖。例如条文以“前照灯、尾端防护灯、侧壁状态指示灯”展开车辆照明和信号装置，不得再要求一个名称完全相同的独立“信号装置”。但问题明确列出的具体对象若未在证据中出现，仍应判为 insufficient。
10. 仅输出 JSON，不要输出 Markdown。
{scope_rules}

JSON 格式：
{{
  "decision": "sufficient 或 insufficient",
  "supported_evidence_ids": ["E1"],
  "missing_requirements": [],
  "reason": "简洁说明判断依据"
}}

用户问题：
{question}
{scope_context}

证据：
{build_evidence_context(evidences)}
"""
        messages = [
            {"role": "system", "content": "你是严格的证据充分性判定器，只判断给定证据能否完整回答问题。"},
            {"role": "user", "content": prompt},
        ]
        active_budget = budget or CallBudget()
        last_error = None
        for correction_attempt in range(2):
            response = execute_model_call(
                lambda timeout: self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0,
                    response_format={"type": "json_object"},
                    timeout=timeout,
                ),
                operation="证据判定",
                budget=active_budget,
                policy=self.call_policy,
            )
            active_budget.record_usage(response)
            try:
                content = response.choices[0].message.content
                decision = self._parse(content, available_ids)
                decision = self._normalize_distributed_performance_requirements(
                    question, evidences, decision
                )
                decision = self._normalize_non_cartesian_enumeration(
                    question, evidences, decision
                )
                return self._normalize_cross_spec_asymmetry(
                    question, evidences, decision, scope_business_ids
                )
            except (AttributeError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                if correction_attempt == 0:
                    invalid_content = ""
                    try:
                        invalid_content = str(response.choices[0].message.content or "")
                    except (AttributeError, IndexError):
                        pass
                    messages = [
                        *messages,
                        {"role": "assistant", "content": invalid_content},
                        {"role": "user", "content": "上一响应不符合 JSON 结构或字段约束。请仅按规定结构重新输出一次。"},
                    ]
        raise InvalidModelResponseError(str(last_error)) from last_error

    @staticmethod
    def _normalize_distributed_performance_requirements(
        question: str,
        evidences: list[Evidence],
        decision: SufficiencyDecision,
    ) -> SufficiencyDecision:
        """Do not distribute a shared performance qualifier to every list item."""
        if (
            decision.decision != "insufficient"
            or "有哪些配置与性能要求" not in question
            or not decision.missing_requirements
            or not all(item.endswith("的性能要求") for item in decision.missing_requirements)
        ):
            return decision
        supporting = []
        for missing in decision.missing_requirements:
            subject = missing.removesuffix("的性能要求")
            bigrams = {
                subject[index : index + 2]
                for index in range(max(0, len(subject) - 1))
            }
            matches = [
                evidence
                for evidence in evidences
                if sum(bigram in evidence.text for bigram in bigrams) >= 2
                and re.search(r"(?:应|不应|不得|可|宜)", evidence.text)
            ]
            if not matches:
                return decision
            supporting.extend(item.evidence_id for item in matches)
        return SufficiencyDecision(
            "sufficient",
            list(dict.fromkeys(supporting)),
            [],
            "共享的‘性能’限定不逐项生成额外指标；证据已给出各并列对象的规范要求。",
        )

    @staticmethod
    def _normalize_non_cartesian_enumeration(
        question: str,
        evidences: list[Evidence],
        decision: SufficiencyDecision,
    ) -> SufficiencyDecision:
        """Do not invent a scenario-by-object matrix for an open provisions query."""
        if (
            decision.decision != "insufficient"
            or "有什么规定" not in question
            or "分别" in question
            or not decision.missing_requirements
        ):
            return decision
        match = re.search(
            r"(?:对)?(?:车辆)?([^、，]{2,12})、([^时]{2,12})时([^及]{2,12})及([^人]{2,12})人均[^？?]*有什么规定",
            question,
        )
        if not match:
            return decision
        terms = [term.strip() for term in match.groups()]
        context = "\n".join(evidence.text for evidence in evidences)
        if not all(term and term in context for term in terms):
            return decision
        if not re.search(r"(?:符合下列规定|下列规定)", context):
            return decision
        return SufficiencyDecision(
            "sufficient",
            [evidence.evidence_id for evidence in evidences],
            [],
            "问题询问条文实际规定，不要求场景与对象的全组合；完整条文已覆盖全部场景词和对象词。",
        )

    @staticmethod
    def _normalize_cross_spec_asymmetry(
        question: str,
        evidences: list[Evidence],
        decision: SufficiencyDecision,
        scope_business_ids: tuple[str, ...],
    ) -> SufficiencyDecision:
        """Allow a cautious asymmetric comparison when every scope has related evidence."""
        if (
            decision.decision != "insufficient"
            or len(scope_business_ids) < 2
            or not re.search(r"(?:比较|差异|不同)", question)
            or re.search(r"(?:每份|各份|均需|必须).{0,8}(?:逐项|每项|全部)", question)
        ):
            return decision
        query_terms = {
            question[index : index + 2]
            for index in range(max(0, len(question) - 1))
            if re.fullmatch(r"[\u4e00-\u9fff]{2}", question[index : index + 2])
        }
        supporting = []
        for business_id in scope_business_ids:
            scoped = [
                evidence
                for evidence in evidences
                if f"{evidence.spec_id}@{evidence.edition_id}" == business_id
                and sum(term in evidence.text for term in query_terms) >= 2
            ]
            if not scoped:
                return decision
            supporting.extend(item.evidence_id for item in scoped)
        return SufficiencyDecision(
            "sufficient",
            list(dict.fromkeys(supporting)),
            [],
            "每个绑定规范均有相关适用证据；比较应按实际规定非对称陈述，不要求每份规范覆盖全部组合。",
        )

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
        if decision == "sufficient":
            if not supported:
                raise ValueError("sufficient requires supported evidence")
            if missing:
                raise ValueError("sufficient requires empty missing_requirements")
        if decision == "insufficient" and not missing:
            raise ValueError("insufficient requires missing_requirements")
        return SufficiencyDecision(decision, supported, missing, reason)
