from types import SimpleNamespace

from src.evidence import Evidence
from src.generator import Generator


class _Completions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="回答 [E1]"))],
            usage=usage,
        )


def test_cross_spec_prompt_prioritizes_complete_direct_requirements():
    completions = _Completions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    generator = Generator(client=client, model="test")
    evidence = Evidence("E1", "车辆基地应满足防洪、防淹要求。", "spec.pdf", 1, 1, 1)

    generator.generate_answer(
        "三份规范分别有哪些明确要求？",
        [evidence],
        scope_business_ids=("cn.a@2025", "cn.b@2022", "cn.c@2013"),
    )

    prompt = completions.calls[0]["messages"][1]["content"]
    assert "完整覆盖优先于分点数量限制" in prompt
    assert "不得为了简洁而遗漏" in prompt
    assert "cn.c@2013" in prompt
