from src.query_decomposition import decompose_retrieval_targets, focused_query_variants


def test_splits_scope_and_speed_without_document_names():
    query = "三份规范对适用范围或线路最高运行速度分别怎样规定？仅陈述各文档明确给出的内容。"
    assert decompose_retrieval_targets(query) == ["适用范围", "线路最高运行速度"]


def test_splits_water_crossing_and_depot_flood_requirements():
    query = "关于地下工程穿越水域时的防淹，以及车辆基地防洪防淹，三份规范分别有哪些明确要求？"
    assert decompose_retrieval_targets(query) == [
        "地下工程穿越水域时的防淹",
        "车辆基地防洪防淹",
    ]


def test_does_not_split_single_requirement_or_invent_targets():
    assert decompose_retrieval_targets("仅依据 GB 55033-2022，消防疏散有哪些要求？") == []
    assert decompose_retrieval_targets("第 6.1.1 条规定了什么？") == []


def test_adds_general_natural_hazard_terms_without_document_or_article_ids():
    targets = ["地下工程穿越水域时的防淹", "车辆基地防洪防淹"]
    assert focused_query_variants(targets) == [
        targets[0],
        "防止自然灾害 防内涝 防洪 防淹",
        targets[1],
    ]


def test_expands_applicability_language_without_article_ids():
    assert focused_query_variants(["适用范围", "线路最高运行速度"]) == [
        "本标准适用于 本规范适用于 必须执行本规范",
        "线路最高运行速度",
    ]
