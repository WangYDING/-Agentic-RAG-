from openai import OpenAI

from src.evidence import Evidence, build_evidence_context
from src.reliability import (
    CallBudget,
    CallPolicy,
    InvalidModelResponseError,
    execute_model_call,
)

class Generator:
    def __init__(
        self,
        client=None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "deepseek-chat",
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

    def generate_answer(
        self,
        query: str,
        evidences: list[Evidence],
        chat_history: list[dict] = None,
        *,
        budget: CallBudget | None = None,
        scope_business_ids: tuple[str, ...] = (),
    ) -> str:
        context = build_evidence_context(evidences)
        scope_instructions = ""
        scope_context = ""
        if scope_business_ids:
            scope_instructions = """
11. 跨规范问题中，不要假定每份规范都覆盖每个并列主题；按规范分别陈述已有直接规定。某规范对某主题没有对应片段时，只能说“给定证据未找到直接规定”，不得据此推断规范全文不存在规定
12. 对跨规范、多子要求问题，完整覆盖优先于分点数量限制；应逐份规范核对每个有直接证据的子要求，不得为了简洁而遗漏适用证据中直接回答问题的条文
13. 跨规范问题不受“2～3点”或“留待后续追问”的简略风格限制；引用某条文时，应保留其中与当前问题直接相关的对象、数值、适用条件和并列安全要求
14. 若表格文本存在明显行列粘连、无法唯一对应的单元格，且用户没有明确询问该单元格数值，不要主动展开该可疑数值；只陈述能可靠对应的表号和直接规定
"""
            scope_context = (
                "\n本次已绑定查询范围（用于逐份组织答案，不代表这些规范都有直接证据）：\n"
                + ", ".join(scope_business_ids)
                + "\n"
            )

        history_text = ""
        if chat_history:
            history_parts = []
            for msg in chat_history:
                role_name = "用户" if msg["role"] == "user" else "系统"
                history_parts.append(f"{role_name}：{msg['content']}")
            history_text = "\n".join(history_parts)

        prompt = f"""
你是一名专业的工程规范问答助手。
请基于给定的参考片段回答问题，严禁编造片段中不存在的信息。
每一个事实性规范结论必须引用证据编号，例如 [E1]、[E2]。

【回答优先级】
1. 正确性 > 问题贴合度 > 完整性 > 简洁性

【回答要求】
1. 以当前问题为中心回答，优先提供直接相关信息
2. 可适度补充必要的背景或关键要点，但不要展开用户尚未追问的细节
3. 先用一句话给出核心结论（必须简洁）
4. 然后按问题粒度分点说明；如果问题本身较简单，分点不超过3点
5. 避免重复表达，不要把同一信息拆成多个相似条目
6. 使用工程规范语言（如“应”“不得”“不应大于”等）
7. 不要逐句复述原文，而是进行结构化总结
8. 若信息不足，明确说明：“给定片段未提供完整信息”
9. 若问题依赖上下文，请结合历史问题理解指代
10. 引用只能使用参考证据中真实存在的编号，不得编造 [E4]、[E99] 等不存在的编号
{scope_instructions}

【输出风格要求】
- 如果用户问“有什么要求”，先概括总体要求，再列最关键的2~3点
- 如果用户追问“验收标准”“定量指标”等细项，再单独展开对应内容
- 不要在第一轮回答中把后续可能追问的所有内容一次性说完

【禁止行为】
- 不得编造规范条文
- 不得添加片段中不存在的数值或条件
- 不要输出“根据上述内容”等废话

历史对话：
{history_text}

用户当前问题：
{query}
{scope_context}

参考片段：
{context}

请给出回答：
"""

        active_budget = budget or CallBudget()
        response = execute_model_call(
            lambda timeout: self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个严谨的专业文档问答助手。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                timeout=timeout,
            ),
            operation="生成",
            budget=active_budget,
            policy=self.call_policy,
        )
        active_budget.record_usage(response)
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError) as exc:
            raise InvalidModelResponseError("missing completion content") from exc
        if not isinstance(content, str) or not content.strip():
            raise InvalidModelResponseError("empty completion content")
        return content.strip()
