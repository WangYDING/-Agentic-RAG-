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
    assert "不受“2～3点”" in prompt
    assert "明显行列粘连" in prompt
    assert "cn.c@2013" in prompt


def test_generation_prompt_preserves_parallel_supported_measures_for_open_list():
    completions = _Completions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    generator = Generator(client=client, model="test")
    evidence = Evidence(
        "E1",
        "地下重点部位一级；区间附属结构不低于二级；高架桥面设柔性防水层并顺畅排水。",
        "spec.pdf", 26, 26, 1,
    )

    generator.generate_answer(
        "如何划分地下车站、区间隧道等结构的防水等级？", [evidence]
    )

    prompt = completions.calls[0]["messages"][1]["content"]
    assert "逐项检查该条文以分号或句号并列给出的直接规定" in prompt
    assert "不得因“2～3点”风格省略" in prompt
    assert "不得补写证据没有的内容" in prompt
    assert "即使该句未重复“等级”二字" in prompt
    assert "柔性防水层并顺畅排水" in prompt
