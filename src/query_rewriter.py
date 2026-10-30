from openai import OpenAI

from src.reliability import (
    CallBudget,
    CallPolicy,
    InvalidModelResponseError,
    execute_model_call,
)


class QueryRewriter:
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

    def rewrite(
        self,
        query: str,
        chat_history: list[dict] = None,
        *,
        budget: CallBudget | None = None,
    ) -> str:
        history_text = ""
        if chat_history:
            history_parts = []
            for msg in chat_history:
                role_name = "用户" if msg["role"] == "user" else "系统"
                history_parts.append(f"{role_name}：{msg['content']}")
            history_text = "\n".join(history_parts)

        prompt = f"""
你是一个查询改写助手，负责将用户当前问题改写为“适合文档检索的完整问题”。

要求：
1. 保留用户原始意图，不要改变问题含义
2. 若当前问题存在代词、省略或上下文依赖，请结合历史对话补全主语和关键信息
3. 改写后的问题应简洁、完整、明确，适合用于知识库检索
4. 只输出改写后的问题，不要输出解释，不要加引号
5. 如果当前问题已经足够清晰，就直接原样输出或做轻微优化

历史对话：
{history_text}

当前问题：
{query}

改写后的检索问题：
"""

        active_budget = budget or CallBudget()
        response = execute_model_call(
            lambda timeout: self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个严谨的查询改写助手。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                timeout=timeout,
            ),
            operation="查询改写",
            budget=active_budget,
            policy=self.call_policy,
        )
        active_budget.record_usage(response)
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError) as exc:
            raise InvalidModelResponseError("missing rewrite content") from exc
        if not isinstance(content, str) or not content.strip():
            raise InvalidModelResponseError("empty rewrite content")
        return content.strip()
