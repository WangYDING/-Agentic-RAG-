import unittest

from src.evidence_retention import (
    RequirementSource,
    build_retry_query,
    parse_evidence_requirements,
    select_retained_article_groups,
)


def candidate(spec, edition, article, chunk_id, text, *, complete=True):
    return {
        "spec_id": spec,
        "edition_id": edition,
        "standard_code": {
            ("cn.gb55033", "2022"): "GB 55033-2022",
            ("cn.gb50157", "2013"): "GB 50157-2013",
        }.get((spec, edition), f"{spec}-{edition}"),
        "article_id": article,
        "chunk_id": chunk_id,
        "text": text,
        "source": f"{spec}.pdf",
        "article_group_complete": complete,
    }


class EvidenceRequirementTest(unittest.TestCase):
    def test_comparison_requirements_keep_shared_topic_and_predecessor_only_extra(self):
        parsed = parse_evidence_requirements(
            "比较 GB 55033-2022 与 GB 50157-2013 的设计年限规定，并指出前者额外提出的运能要求。",
            [],
            ("cn.gb55033@2022", "cn.gb50157@2013"),
        )

        requirements = {
            (item.business_id, item.subrequirement)
            for item in parsed.question_requirements
        }
        self.assertIn(("cn.gb55033@2022", "GB55033-2022设计年限"), requirements)
        self.assertIn(("cn.gb50157@2013", "GB50157-2013设计年限"), requirements)
        self.assertIn(("cn.gb55033@2022", "GB55033-2022运能"), requirements)
        self.assertNotIn(("cn.gb50157@2013", "GB50157-2013运能"), requirements)

    def test_parallel_scenes_expand_across_bound_scope_without_guessing_mapping(self):
        scope = (
            "cn.beijing.db11t995@2025",
            "cn.gb55033@2022",
            "cn.gb50157@2013",
        )
        parsed = parse_evidence_requirements(
            "三份规范对区间、车站公共区以及设备管理用房人员新风量分别有哪些直接规定？",
            [],
            scope,
        )

        self.assertEqual(len(parsed.question_requirements), 9)
        self.assertEqual(
            {
                (item.business_id, item.subrequirement)
                for item in parsed.question_requirements
            },
            {
                (business_id, target)
                for business_id in scope
                for target in (
                    "区间人员新风量",
                    "车站公共区人员新风量",
                    "设备管理用房人员新风量",
                )
            },
        )

    def test_question_requirement_is_authoritative_and_explicit_article_is_parsed(self):
        parsed = parse_evidence_requirements(
            "请说明GB 55033-2022第2.1.5条规定的设计年限要求。",
            [],
            ("cn.gb55033@2022",),
        )

        self.assertEqual(len(parsed.question_requirements), 1)
        requirement = parsed.question_requirements[0]
        self.assertEqual(requirement.source, RequirementSource.QUESTION)
        self.assertEqual(requirement.business_id, "cn.gb55033@2022")
        self.assertEqual(requirement.article_id, "2.1.5")
        self.assertTrue(requirement.authoritative)

    def test_grader_only_requirement_is_retry_hint_not_authoritative(self):
        parsed = parse_evidence_requirements(
            "GB 55033-2022对设计年限有什么规定？",
            ["还必须提供GB 55033-2022的施工验收指标"],
            ("cn.gb55033@2022",),
        )

        grader_requirement = parsed.grader_requirements[0]
        self.assertEqual(grader_requirement.source, RequirementSource.GRADER)
        self.assertFalse(grader_requirement.authoritative)
        self.assertEqual(grader_requirement.status, "grader_only")

    def test_local_standard_code_maps_to_nested_business_id(self):
        parsed = parse_evidence_requirements(
            "DB11/T 995-2025对车站出入口数量有什么要求？",
            [],
            ("cn.beijing.db11t995@2025", "cn.gb55033@2022"),
        )

        self.assertEqual(
            parsed.question_requirements[0].business_id,
            "cn.beijing.db11t995@2025",
        )

    def test_each_scoped_specification_expands_explicit_same_article_request(self):
        scope = (
            "cn.beijing.db11t995@2025",
            "cn.gb50157@2013",
            "cn.gb55033@2022",
        )
        parsed = parse_evidence_requirements(
            "请分别说明三份规范各自第6.2.3条的核心要求。",
            [],
            scope,
        )

        self.assertEqual(
            {item.business_id for item in parsed.question_requirements},
            set(scope),
        )
        self.assertTrue(all(item.article_id == "6.2.3" for item in parsed.question_requirements))

    def test_grader_enumeration_stays_one_retry_hint(self):
        parsed = parse_evidence_requirements(
            "GB 50157-2013的设计年限如何划分？",
            ["缺少GB 50157-2013初期、近期、远期的设计年限划分"],
            ("cn.gb50157@2013",),
        )

        self.assertEqual(len(parsed.grader_requirements), 1)
        self.assertIn("初期、近期、远期", parsed.grader_requirements[0].subrequirement)

    def test_retry_query_removes_grader_verdict_commentary(self):
        parsed = parse_evidence_requirements(
            "比较GB 50157-2013的设计年限规定。",
            [
                "GB 50157-2013关于设计年限的具体规定（如初期、近期、远期），"
                "现有证据仅出现工程设计年限一词，无法完整比较"
            ],
            ("cn.gb50157@2013",),
        )

        retry_query = build_retry_query(parsed, "fallback")

        self.assertIn("初期、近期、远期", retry_query)
        self.assertNotIn("现有证据", retry_query)
        self.assertNotIn("无法完整比较", retry_query)


class ArticleRetentionTest(unittest.TestCase):
    def test_distant_commentary_with_same_article_number_is_a_separate_group(self):
        candidates = [
            candidate(
                "cn.db", "2025", "14.2.11", 100,
                "人员新风量：区间、公共区和设备管理用房分别规定。",
            ),
            candidate(
                "cn.db", "2025", "14.2.11", 300,
                "条文说明：介绍人员新风量标准的编制背景。",
            ),
            candidate(
                "cn.db", "2025", "14.2.11", 301,
                "条文说明续页。",
            ),
        ]
        parsed = parse_evidence_requirements(
            "DB-2025的区间人员新风量有什么要求？",
            [],
            ("cn.db@2025",),
        )

        decision = select_retained_article_groups(
            parsed,
            candidates,
            reranked=candidates,
            evidence_limit=2,
            allowed_business_ids=("cn.db@2025",),
        )

        self.assertEqual(decision.retained_groups[0].chunk_ids, (100,))
    def test_direct_design_year_phrase_excludes_scattered_design_and_year_terms(self):
        candidates = [
            candidate(
                "cn.gb50157", "2013", "1.0.8", 8,
                "地铁工程的设计年限应分为初期、近期、远期。",
            ),
            candidate(
                "cn.gb50157", "2013", "3.2.2", 32,
                "系统设计能力应满足相应年限设计运输能力的需要。",
            ),
            candidate(
                "cn.gb50157", "2013", "11.1.6", 116,
                "结构构件应按设计使用年限100年进行耐久性设计。",
            ),
        ]
        parsed = parse_evidence_requirements(
            "比较GB 55033-2022与GB 50157-2013的设计年限规定，并指出前者运能要求。",
            [],
            ("cn.gb55033@2022", "cn.gb50157@2013"),
        )

        decision = select_retained_article_groups(
            parsed,
            candidates,
            reranked=candidates,
            evidence_limit=3,
            allowed_business_ids=("cn.gb50157@2013",),
        )

        self.assertEqual(
            {group.article_id for group in decision.retained_groups},
            {"1.0.8"},
        )

    def test_fresh_air_synonyms_select_distinct_scene_articles(self):
        candidates = [
            candidate(
                "cn.gb50157", "2013", "13.2.4", 4,
                "区间隧道内每个乘客每小时需供应的新鲜空气量不应少于12.6m³。",
            ),
            candidate(
                "cn.gb50157", "2013", "13.2.17", 17,
                "车站公共区每个乘客每小时需供应的新鲜空气量不应少于30m³。",
            ),
            candidate(
                "cn.gb50157", "2013", "13.2.33", 33,
                "设备与管理用房内每个工作人员每小时需供应的新鲜空气量不应少于30m³。",
            ),
        ]
        parsed = parse_evidence_requirements(
            "三份规范对区间、车站公共区以及设备管理用房人员新风量分别有哪些直接规定？",
            [],
            ("cn.gb50157@2013",),
        )

        decision = select_retained_article_groups(
            parsed,
            candidates,
            reranked=list(reversed(candidates)),
            evidence_limit=3,
            allowed_business_ids=("cn.gb50157@2013",),
        )

        self.assertEqual(
            {group.article_id for group in decision.retained_groups},
            {"13.2.4", "13.2.17", "13.2.33"},
        )
    def test_specific_design_year_terms_exclude_capacity_article_competitor(self):
        candidates = [
            candidate(
                "cn.gb50157", "2013", "1.0.8", 8,
                "设计年限分为初期、近期、远期，分别为通车后第3年、第10年、第25年。",
            ),
            candidate(
                "cn.gb50157", "2013", "3.2.2", 32,
                "系统设计能力应满足相应年限设计运输能力的需要。",
            ),
        ]
        parsed = parse_evidence_requirements(
            "比较GB 50157-2013的设计年限规定。",
            ["缺少GB 50157-2013初期、近期、远期的设计年限划分"],
            ("cn.gb50157@2013",),
        )

        decision = select_retained_article_groups(
            parsed,
            candidates,
            reranked=[candidates[1], candidates[0]],
            evidence_limit=2,
            allowed_business_ids=("cn.gb50157@2013",),
        )

        self.assertIn("1.0.8", {group.article_id for group in decision.retained_groups})

    def test_preserved_ind011_candidate_pool_retains_both_design_year_articles(self):
        candidates = [
            candidate(
                "cn.gb55033", "2022", "2.1.5", 17,
                "设计年限以通车年为基准，初期3年、近期10年、远期25年，运能储备不小于10%。",
            ),
            candidate(
                "cn.gb50157", "2013", "1.0.8", 62,
                "地铁工程设计年限分为初期、近期、远期，分别为通车后第3、10、25年。",
            ),
            candidate(
                "cn.gb50157", "2013", "3.2.2", 150,
                "系统设计能力应满足相应年限设计运输能力的需要。",
            ),
        ]
        parsed = parse_evidence_requirements(
            "比较GB 55033-2022与GB 50157-2013的设计年限，并指出前者运能要求。",
            ["GB 50157-2013初期、近期、远期的设计年限划分"],
            ("cn.gb55033@2022", "cn.gb50157@2013"),
        )

        decision = select_retained_article_groups(
            parsed,
            candidates,
            reranked=[candidates[0], candidates[2], candidates[1]],
            evidence_limit=4,
            allowed_business_ids=("cn.gb55033@2022", "cn.gb50157@2013"),
        )

        retained = {(group.business_id, group.article_id) for group in decision.retained_groups}
        self.assertIn(("cn.gb55033@2022", "2.1.5"), retained)
        self.assertIn(("cn.gb50157@2013", "1.0.8"), retained)
    def test_unique_direct_complete_group_is_retained_with_all_chunks(self):
        candidates = [
            candidate("cn.gb55033", "2022", "2.1.5", 10, "设计使用年限应为100年。"),
            candidate("cn.gb55033", "2022", "2.1.5", 11, "结构构件应满足耐久性要求。"),
            candidate("cn.gb55033", "2022", "9.9.9", 20, "一般设计规定。"),
        ]
        parsed = parse_evidence_requirements(
            "GB 55033-2022的设计使用年限和耐久性有什么要求？",
            ["缺少GB 55033-2022设计使用年限和耐久性要求"],
            ("cn.gb55033@2022",),
        )

        decision = select_retained_article_groups(
            parsed,
            candidates,
            reranked=[candidates[2], candidates[0], candidates[1]],
            evidence_limit=3,
            allowed_business_ids=("cn.gb55033@2022",),
        )

        self.assertEqual([item["chunk_id"] for item in decision.selected], [10, 11, 20])
        self.assertEqual(decision.retained_groups[0].article_id, "2.1.5")
        self.assertEqual(decision.retained_groups[0].basis, "unique_direct_coverage")

    def test_current_request_limit_above_three_is_respected(self):
        candidates = [
            candidate("cn.gb55033", "2022", f"2.1.{index}", index, f"专项要求{index}")
            for index in range(1, 7)
        ]
        parsed = parse_evidence_requirements(
            "GB 55033-2022的专项要求1是什么？",
            [],
            ("cn.gb55033@2022",),
        )

        decision = select_retained_article_groups(
            parsed,
            candidates,
            reranked=candidates,
            evidence_limit=6,
            allowed_business_ids=("cn.gb55033@2022",),
        )

        self.assertEqual(len(decision.selected), 6)

    def test_ambiguous_direct_groups_remain_unlocked(self):
        candidates = [
            candidate("cn.gb55033", "2022", "2.1.5", 1, "设计年限应满足工程要求。"),
            candidate("cn.gb55033", "2022", "2.1.6", 2, "设计年限应根据结构确定。"),
        ]
        parsed = parse_evidence_requirements(
            "GB 55033-2022的设计年限有什么要求？",
            ["缺少GB 55033-2022设计年限要求"],
            ("cn.gb55033@2022",),
        )

        decision = select_retained_article_groups(
            parsed,
            candidates,
            reranked=candidates,
            evidence_limit=2,
            allowed_business_ids=("cn.gb55033@2022",),
        )

        self.assertEqual(decision.retained_groups, ())
        self.assertIn("not_unique", {item.reason for item in decision.fallbacks})

    def test_incomplete_or_out_of_scope_group_is_not_retained(self):
        candidates = [
            candidate(
                "cn.gb55033", "2022", "2.1.5", 1, "设计使用年限要求。", complete=False
            ),
            candidate("cn.gb50157", "2013", "1.0.8", 2, "设计使用年限要求。"),
        ]
        parsed = parse_evidence_requirements(
            "GB 55033-2022的设计使用年限有什么要求？",
            ["缺少GB 55033-2022设计使用年限要求"],
            ("cn.gb55033@2022",),
        )

        decision = select_retained_article_groups(
            parsed,
            candidates,
            reranked=candidates,
            evidence_limit=2,
            allowed_business_ids=("cn.gb55033@2022",),
        )

        self.assertEqual(decision.retained_groups, ())
        reasons = {item.reason for item in decision.fallbacks}
        self.assertIn("incomplete_article_group", reasons)
        self.assertTrue(all(
            f"{item['spec_id']}@{item['edition_id']}" == "cn.gb55033@2022"
            for item in decision.selected
        ))

    def test_grader_only_requirement_cannot_reserve_a_slot(self):
        candidates = [
            candidate("cn.gb55033", "2022", "2.1.5", 1, "设计年限应为100年。"),
            candidate("cn.gb55033", "2022", "8.8.8", 2, "施工验收指标。"),
        ]
        parsed = parse_evidence_requirements(
            "GB 55033-2022的设计年限是什么？",
            ["还缺少GB 55033-2022施工验收指标"],
            ("cn.gb55033@2022",),
        )

        decision = select_retained_article_groups(
            parsed,
            candidates,
            reranked=[candidates[0], candidates[1]],
            evidence_limit=1,
            allowed_business_ids=("cn.gb55033@2022",),
        )

        self.assertEqual(decision.selected[0]["article_id"], "2.1.5")
        self.assertNotIn("8.8.8", {group.article_id for group in decision.retained_groups})


if __name__ == "__main__":
    unittest.main()
