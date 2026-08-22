class ChatMemory:
    def __init__(self, max_turns: int = 3):
        """
        max_turns: 最多保留多少轮用户-助手对话
        """
        self.max_turns = max_turns
        self.history = []

    def add_user_message(self, message: str):
        self.history.append({"role": "user", "content": message})
        self._trim_history()

    def add_assistant_message(self, message: str):
        self.history.append({"role": "assistant", "content": message})
        self._trim_history()

    def get_recent_history(self) -> list[dict]:
        return self.history

    def build_context_query(self, current_query: str) -> str:
        """
        将最近对话历史和当前问题拼接成增强检索query
        """
        recent_messages = self.history[-2 * self.max_turns:]  # 最近若干条消息
        context_parts = []

        for msg in recent_messages:
            if msg["role"] == "user":
                context_parts.append(f"用户之前问：{msg['content']}")
            elif msg["role"] == "assistant":
                context_parts.append(f"系统之前回答：{msg['content']}")

        context_parts.append(f"当前问题：{current_query}")

        return "\n".join(context_parts)

    def _trim_history(self):
        max_messages = self.max_turns * 2
        if len(self.history) > max_messages:
            self.history = self.history[-max_messages:]