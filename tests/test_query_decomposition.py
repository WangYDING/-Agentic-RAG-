from src.query_decomposition import (
    decompose_retrieval_plan,
    decompose_retrieval_targets,
    focused_query_variants,
)


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


def test_expands_person_fresh_air_wording_without_assigning_a_role_or_specification():
    assert focused_query_variants(["区间人员新风量"]) == [
        "区间 人员 新风量 新鲜空气量 乘客 工作人员 每小时"
    ]


def test_comparison_inherits_shared_predicate_but_binds_extra_only_to_predecessor():
    query = "比较 GB 55033-2022 与 GB 50157-2013 的设计年限规定，并指出前者额外提出的运能要求。"

    plan = decompose_retrieval_plan(query)

    assert plan.targets == (
        "GB55033-2022设计年限",
        "GB50157-2013设计年限",
        "GB55033-2022运能",
    )
    assert "GB50157-2013运能" not in plan.targets
    assert plan.reason is None


def test_parallel_scenes_inherit_metric_without_guessing_specification_identity():
    query = "三份规范对区间、车站公共区以及设备管理用房人员新风量分别有哪些直接规定？请区分使用场景。"

    plan = decompose_retrieval_plan(query)

    assert plan.targets == (
        "区间人员新风量",
        "车站公共区人员新风量",
        "设备管理用房人员新风量",
    )
    assert all("GB" not in target and "DB" not in target for target in plan.targets)
    assert plan.reason is None


def test_ambiguous_parallel_scenes_fall_back_without_inventing_mapping():
    plan = decompose_retrieval_plan("三份规范对区间、车站和车辆基地分别有哪些特殊内容？")

    assert plan.targets == ()
    assert plan.reason == "parallel_target_not_uniquely_parsed"
