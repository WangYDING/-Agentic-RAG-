import unittest
from types import SimpleNamespace

from src.agent_workflow import AgentWorkflow, REFUSAL_MESSAGE
from src.reliability import ReliabilityError


def result(chunk_id, text=None):
    return {
        "text": text or f"evidence {chunk_id}",
        "source": "spec.pdf",
        "chunk_id": chunk_id,
        "page_start": chunk_id + 1,
        "article_id": f"1.1.{chunk_id}",
    }


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def retrieve(self, query, top_k):
        self.calls.append((query, top_k))
        offset = 0 if len(self.calls) == 1 else 10
        return [result(offset + index) for index in range(3)]


class FakeReranker:
    def __init__(self):
        self.calls = []

    def rerank(self, query, results, top_n):
        self.calls.append((query, list(results), top_n))
        return results[:top_n]


class ScoringReranker:
    supports_score_cache = True

    def __init__(self, scores=None):
        self.scores = scores or {}
        self.score_calls = []

    def score_candidates(self, query, results):
        self.score_calls.append((query, [item.copy() for item in results]))
        return [
            {
                **item,
                "rerank_score": float(
                    self.scores.get((query, item["text"]), len(item["text"]))
                ),
            }
            for item in results
        ]

    @staticmethod
    def select_top(scored_results, top_n=3):
        return sorted(
            scored_results,
            key=lambda item: item["rerank_score"],
            reverse=True,
        )[:top_n]

    def rerank(self, query, results, top_n=3):
        return self.select_top(self.score_candidates(query, results), top_n)


class OverlapRetriever:
    def __init__(self):
        self.calls = []

    def retrieve(self, query, top_k):
        self.calls.append((query, top_k))
        ids = [0, 1, 2] if len(self.calls) % 2 else [1, 2, 3]
        return [result(chunk_id) for chunk_id in ids]


class FakeGrader:
    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.calls = []

    def grade(self, query, evidences, *, budget=None, scope_business_ids=()):
        if budget is not None:
            budget.consume()
        self.calls.append((query, list(evidences)))
        item = self.decisions.pop(0)
        decision, missing = item[:2]
        supported = item[2] if len(item) > 2 else []
        return SimpleNamespace(
            decision=decision,
            missing_requirements=missing,
            supported_evidence_ids=supported,
        )


class FakeGenerator:
    def __init__(self, answer="answer [E1]"):
        self.calls = []
        self.answer = answer

    def generate_answer(
        self, query, evidences, chat_history, *, budget=None, scope_business_ids=()
    ):
        if budget is not None:
            budget.consume()
        self.calls.append((query, list(evidences), list(chat_history)))
        return self.answer


class FakeRewriter:
    def __init__(self):
        self.calls = []

    def rewrite(self, query, chat_history, *, budget=None):
        if budget is not None:
            budget.consume()
        self.calls.append((query, list(chat_history)))
        return "targeted retry query"


class AgentWorkflowTest(unittest.TestCase):
    def build(self, decisions, rewriter=None):
        self.retriever = FakeRetriever()
        self.reranker = FakeReranker()
        self.grader = FakeGrader(decisions)
        self.generator = FakeGenerator()
        return AgentWorkflow(self.retriever, self.reranker, self.grader, self.generator, rewriter)

    def test_first_grade_sufficient_answers_without_retry_and_validates_citations(self):
        response = self.build([("sufficient", [])]).run("question")

        self.assertEqual(response.state.retry_count, 0)
        self.assertEqual(response.state.final_action, "answer")
        self.assertEqual(response.result_type, "answer")
        self.assertEqual([item["step"] for item in response.state.trace], ["retrieve", "grade", "answer", "citation_validation"])
        self.assertTrue(response.state.citation_validation.valid)
        self.assertEqual(len(self.retriever.calls), 1)
        self.assertEqual(len(self.generator.calls), 1)

    def test_retry_once_then_answer_when_second_grade_is_sufficient(self):
        rewriter = FakeRewriter()
        response = self.build([("insufficient", ["second requirement"]), ("sufficient", [])], rewriter).run("question")

        self.assertEqual(response.state.retry_count, 1)
        self.assertEqual(response.state.rewritten_query, "second requirement")
        self.assertEqual(response.state.final_action, "answer")
        self.assertEqual(
            [item["step"] for item in response.state.trace],
            [
                "retrieve", "grade", "parse_evidence_requirements", "retry",
                "retrieve", "retain_article_groups", "verify_final_evidence_context",
                "grade", "answer", "citation_validation",
            ],
        )
        self.assertEqual(rewriter.calls, [])
        self.assertEqual(len(self.generator.calls), 1)
        self.assertEqual(len(self.reranker.calls[1][1]), 3)
        self.assertEqual(len(self.reranker.calls[2][1]), 6)

    def test_retry_preserves_top_evidence_for_missing_requirement(self):
        workflow = self.build(
            [("insufficient", ["missing facet"]), ("sufficient", [])]
        )

        class FocusAwareReranker(FakeReranker):
            def rerank(self, query, results, top_n):
                self.calls.append((query, list(results), top_n))
                if query == "missing facet":
                    return list(reversed(results))[:top_n]
                return results[:top_n]

        self.reranker = FocusAwareReranker()
        workflow.reranker = self.reranker

        response = workflow.run("question")

        self.assertEqual(response.result_type, "answer")
        second_grade_evidence = self.grader.calls[1][1]
        self.assertEqual([item.chunk_id for item in second_grade_evidence], [0, 1, 12])

    def test_retry_reranks_same_article_neighbor_for_split_evidence(self):
        workflow = self.build(
            [("insufficient", ["missing facet"]), ("sufficient", [])]
        )

        def expand_neighbors(results):
            return [*results, result(13, "exact missing facet")]

        self.retriever.expand_neighbors = expand_neighbors

        class NeighborAwareReranker(FakeReranker):
            def rerank(self, query, results, top_n):
                self.calls.append((query, list(results), top_n))
                if query == "missing facet" and any(
                    item["chunk_id"] == 13 for item in results
                ):
                    ranked = sorted(
                        results, key=lambda item: item["chunk_id"] == 13, reverse=True
                    )
                    return ranked[:top_n]
                return results[:top_n]

        self.reranker = NeighborAwareReranker()
        workflow.reranker = self.reranker

        response = workflow.run("question")

        self.assertEqual(response.result_type, "answer")
        second_grade_evidence = self.grader.calls[1][1]
        self.assertEqual([item.chunk_id for item in second_grade_evidence], [0, 13, 10])

    def test_requirement_coverage_keeps_distinct_facets_within_top_three(self):
        candidates = [
            result(1, "车门安全联锁要求"),
            result(2, "前照灯尾灯和侧壁指示灯要求"),
            result(3, "无关的信号设备接地要求"),
            result(4, "车门安全联锁要求"),
        ]
        scores = {
            ("完整问题", "车门安全联锁要求"): 0.98,
            ("完整问题", "前照灯尾灯和侧壁指示灯要求"): 0.70,
            ("完整问题", "无关的信号设备接地要求"): 0.99,
            ("缺少车门联锁", "车门安全联锁要求"): 0.99,
            ("缺少车门联锁", "前照灯尾灯和侧壁指示灯要求"): 0.10,
            ("缺少车门联锁", "无关的信号设备接地要求"): 0.05,
            ("缺少车灯要求", "前照灯尾灯和侧壁指示灯要求"): 0.99,
            ("缺少车灯要求", "车门安全联锁要求"): 0.10,
            ("缺少车灯要求", "无关的信号设备接地要求"): 0.05,
        }
        workflow = AgentWorkflow(
            FakeRetriever(),
            ScoringReranker(scores),
            FakeGrader([]),
            FakeGenerator(),
        )

        selected = workflow._select_requirement_coverage(
            "完整问题",
            candidates,
            ["缺少车门联锁、缺少车灯要求"],
            top_n=3,
            score_cache={},
        )

        self.assertEqual(selected[0]["chunk_id"], 3)
        self.assertEqual({item["chunk_id"] for item in selected[1:]}, {1, 2})

    def test_requirement_coverage_deduplicates_identical_evidence(self):
        candidates = [
            result(1, "同一条文内容"),
            result(2, "同一条文内容"),
            result(3, "另一必要条文"),
            result(4, "无关候选"),
        ]
        scores = {
            ("完整问题", "同一条文内容"): 0.99,
            ("完整问题", "另一必要条文"): 0.60,
            ("完整问题", "无关候选"): 0.80,
            ("要求一", "同一条文内容"): 0.99,
            ("要求一", "另一必要条文"): 0.10,
            ("要求一", "无关候选"): 0.05,
            ("要求二", "另一必要条文"): 0.99,
            ("要求二", "同一条文内容"): 0.10,
            ("要求二", "无关候选"): 0.05,
        }
        workflow = AgentWorkflow(
            FakeRetriever(),
            ScoringReranker(scores),
            FakeGrader([]),
            FakeGenerator(),
        )

        selected = workflow._select_requirement_coverage(
            "完整问题",
            candidates,
            ["要求一", "要求二"],
            top_n=3,
            score_cache={},
        )

        self.assertEqual(selected[0]["chunk_id"], 4)
        self.assertEqual({item["chunk_id"] for item in selected[1:]}, {1, 3})

    def test_requirement_coverage_cannot_create_missing_evidence(self):
        candidates = [result(1, "只有通用规范要求"), result(2, "无关候选")]
        workflow = AgentWorkflow(
            FakeRetriever(),
            ScoringReranker(),
            FakeGrader([]),
            FakeGenerator(),
        )

        selected = workflow._select_requirement_coverage(
            "规范要求和本项目实际值是什么？",
            candidates,
            ["本项目实际值"],
            top_n=3,
            score_cache={},
        )

        self.assertEqual(
            {item["chunk_id"] for item in selected},
            {1, 2},
        )
        self.assertTrue(
            all(item["text"] in {candidate["text"] for candidate in candidates} for item in selected)
        )

    def test_retry_protects_previously_supported_evidence(self):
        workflow = self.build(
            [
                ("insufficient", ["missing facet"], ["E1"]),
                ("sufficient", [], ["E1", "E3"]),
            ]
        )

        class FocusAwareReranker(FakeReranker):
            def rerank(self, query, results, top_n):
                self.calls.append((query, list(results), top_n))
                if query == "missing facet":
                    return list(reversed(results))[:top_n]
                return results[:top_n]

        self.reranker = FocusAwareReranker()
        workflow.reranker = self.reranker

        response = workflow.run("question")

        self.assertEqual(response.result_type, "answer")
        second_grade_evidence = self.grader.calls[1][1]
        self.assertIn(0, [item.chunk_id for item in second_grade_evidence])
        self.assertIn(12, [item.chunk_id for item in second_grade_evidence])

    def test_protected_and_coverage_evidence_never_exceed_top_n(self):
        candidates = [result(index) for index in range(6)]
        workflow = AgentWorkflow(
            FakeRetriever(),
            ScoringReranker(),
            FakeGrader([]),
            FakeGenerator(),
        )

        selected = workflow._select_requirement_coverage(
            "完整问题",
            candidates,
            ["要求一", "要求二"],
            top_n=3,
            score_cache={},
            preferred=candidates[3:5],
            protected=candidates[:1],
        )

        self.assertEqual(len(selected), 3)

    def test_two_insufficient_grades_refuse_without_generator(self):
        response = self.build([
            ("insufficient", ["cost"]),
            ("insufficient", ["project cost"]),
            ("insufficient", ["confirmed project cost"]),
        ]).run("question")

        self.assertEqual(response.state.retry_count, 1)
        self.assertEqual(response.state.final_action, "refuse")
        self.assertEqual(response.result_type, "refuse")
        self.assertTrue(response.answer.startswith(REFUSAL_MESSAGE))
        self.assertIn("confirmed project cost", response.answer)
        self.assertEqual(self.generator.calls, [])
        self.assertEqual(len(self.retriever.calls), 2)
        self.assertEqual(len(self.grader.calls), 3)
        self.assertEqual(
            [item["step"] for item in response.state.trace],
            [
                "retrieve", "grade", "parse_evidence_requirements", "retry",
                "retrieve", "retain_article_groups", "verify_final_evidence_context",
                "grade", "confirm_grade", "refuse",
            ],
        )

    def test_confirmation_grade_recovers_stochastic_false_refusal(self):
        response = self.build([
            ("insufficient", ["facet"]),
            ("insufficient", ["invented metric"]),
            ("sufficient", []),
        ]).run("question")

        self.assertEqual(response.result_type, "answer")
        self.assertEqual(len(self.grader.calls), 3)
        self.assertIn("confirm_grade", [item["step"] for item in response.state.trace])
        self.assertEqual(len(self.generator.calls), 1)

    def test_invalid_citation_is_blocked_as_error(self):
        workflow = self.build([("sufficient", [])])
        workflow.generator.answer = "answer [E99]"

        response = workflow.run("question")

        self.assertEqual(response.result_type, "error")
        self.assertEqual(response.error_code, "INVALID_CITATION")
        self.assertEqual(response.state.final_action, "error")
        self.assertNotIn("answer [E99]", response.answer)

    def test_retry_limit_cannot_exceed_one(self):
        with self.assertRaisesRegex(ValueError, "max_retries=1"):
            AgentWorkflow(FakeRetriever(), FakeReranker(), FakeGrader([]), FakeGenerator(), max_retries=2)

    def test_service_failure_is_error_not_refusal(self):
        workflow = self.build([("sufficient", [])])

        def fail(*args, **kwargs):
            raise ReliabilityError("RATE_LIMITED", "模型服务当前限流。", retryable=True)

        workflow.grader.grade = fail
        response = workflow.run("question")

        self.assertEqual(response.result_type, "error")
        self.assertEqual(response.error_code, "RATE_LIMITED")
        self.assertTrue(response.retryable)
        self.assertNotEqual(response.state.final_action, "refuse")
        self.assertTrue(response.request_id)

    def test_model_call_budget_exhaustion_stops_before_generator(self):
        workflow = self.build([("insufficient", ["detail"]), ("sufficient", [])])
        workflow.rewriter = FakeRewriter()
        workflow.max_model_calls = 2

        response = workflow.run("question")

        self.assertEqual(response.result_type, "error")
        self.assertEqual(response.error_code, "CALL_BUDGET_EXHAUSTED")
        self.assertEqual(self.generator.calls, [])

    def test_retry_scores_only_new_merged_candidates_and_request_caches_are_isolated(self):
        retriever = OverlapRetriever()
        reranker = ScoringReranker()
        workflow = AgentWorkflow(
            retriever,
            reranker,
            FakeGrader([
                ("insufficient", ["detail"]),
                ("sufficient", []),
                ("insufficient", ["detail"]),
                ("sufficient", []),
            ]),
            FakeGenerator(),
            index_version_id="index-v1",
        )

        first = workflow.run("question")
        second = workflow.run("question")

        self.assertEqual(first.result_type, "answer")
        self.assertEqual(second.result_type, "answer")
        self.assertEqual(
            [
                (call[0], [item["chunk_id"] for item in call[1]])
                for call in reranker.score_calls
            ],
            [
                ("question", [0, 1, 2]),
                ("detail", [1, 2, 3]),
                ("question", [3]),
                ("question", [0, 1, 2]),
                ("detail", [1, 2, 3]),
                ("question", [3]),
            ],
        )

    def test_cache_key_includes_query_text_and_index_version(self):
        reranker = ScoringReranker()
        workflow = AgentWorkflow(
            FakeRetriever(),
            reranker,
            FakeGrader([]),
            FakeGenerator(),
            index_version_id="index-v1",
        )
        cache = {}
        original = result(1, "original text")

        workflow._rerank_with_cache("q1", [original], top_n=1, score_cache=cache)
        workflow._rerank_with_cache("q1", [original], top_n=1, score_cache=cache)
        workflow._rerank_with_cache("q2", [original], top_n=1, score_cache=cache)
        workflow._rerank_with_cache(
            "q1", [result(1, "changed text")], top_n=1, score_cache=cache
        )
        workflow.index_version_id = "index-v2"
        workflow._rerank_with_cache("q1", [original], top_n=1, score_cache=cache)

        self.assertEqual([len(call[1]) for call in reranker.score_calls], [1, 1, 1, 1])

    def test_cached_and_full_rescoring_produce_same_stable_order(self):
        scores = {
            ("question", "evidence 0"): 0.9,
            ("question", "evidence 1"): 0.7,
            ("question", "evidence 2"): 0.7,
            ("question", "evidence 3"): 0.3,
        }
        candidates = [result(index) for index in range(4)]
        baseline_reranker = ScoringReranker(scores)
        expected = baseline_reranker.rerank("question", candidates, top_n=4)
        cached_reranker = ScoringReranker(scores)
        workflow = AgentWorkflow(
            FakeRetriever(),
            cached_reranker,
            FakeGrader([]),
            FakeGenerator(),
            index_version_id="index-v1",
        )
        cache = {}
        workflow._rerank_with_cache(
            "question", candidates[:3], top_n=3, score_cache=cache
        )
        actual = workflow._rerank_with_cache(
            "question", candidates, top_n=4, score_cache=cache
        )

        self.assertEqual(
            [item["chunk_id"] for item in actual],
            [item["chunk_id"] for item in expected],
        )
        self.assertEqual([len(call[1]) for call in cached_reranker.score_calls], [3, 1])

    def test_multi_scope_target_selection_keeps_two_distinct_articles_per_document(self):
        workflow = AgentWorkflow(
            FakeRetriever(), FakeReranker(), FakeGrader([]), FakeGenerator()
        )
        candidates = []
        for spec_index, (spec_id, edition_id) in enumerate(
            (("cn.a", "2025"), ("cn.b", "2022"), ("cn.c", "2013"))
        ):
            for local_index, article in enumerate(("1.0.1", "2.0.1", "9.9.9")):
                candidates.append(
                    {
                        "text": f"{spec_id}-{article}",
                        "source": f"{spec_id}.pdf",
                        "spec_id": spec_id,
                        "edition_id": edition_id,
                        "chunk_id": spec_index * 10 + local_index,
                        "article_id": article,
                        "focused_best_rank": local_index + 1,
                        "focused_rank_sum": local_index + 1,
                        "document_query_ranks": {
                            "target-a": 1 if local_index == 0 else local_index + 2,
                            "target-b": 1 if local_index == 1 else local_index + 2,
                        },
                    }
                )

        selected = workflow._select_scope_target_coverage(
            candidates,
            ["target-a", "target-b"],
            ("cn.a@2025", "cn.b@2022", "cn.c@2013"),
            top_n=6,
            score_cache={},
            preferred=[],
        )

        self.assertEqual(len(selected), 6)
        self.assertEqual(
            {(item["spec_id"], item["article_id"]) for item in selected},
            {
                ("cn.a", "1.0.1"),
                ("cn.a", "2.0.1"),
                ("cn.b", "1.0.1"),
                ("cn.b", "2.0.1"),
                ("cn.c", "1.0.1"),
                ("cn.c", "2.0.1"),
            },
        )

    def test_focused_intent_rejects_definitions_and_unrelated_flood_evidence(self):
        matcher = AgentWorkflow._matches_focused_intent

        self.assertFalse(
            matcher(
                {"text": "2.0.5 最高运行速度 maximum running speed 列车正常运营的最高速度。"},
                "线路最高运行速度",
            )
        )
        self.assertTrue(
            matcher(
                {"text": "4.2.4 设计最高运行速度应根据线路功能定位经比选确定。"},
                "线路最高运行速度",
            )
        )
        self.assertFalse(
            matcher(
                {"text": "车站出入口的防淹措施应满足当地防洪排涝要求。"},
                "车辆基地防洪防淹",
            )
        )
        self.assertTrue(
            matcher(
                {"text": "车辆基地布局应满足防洪、防淹要求。"},
                "车辆基地防洪防淹",
            )
        )

    def test_fresh_air_intent_requires_air_semantics_and_matching_scene(self):
        matcher = AgentWorkflow._matches_focused_intent

        self.assertFalse(
            matcher(
                {"text": "车站公共区冲洗用水量为2L/m²。"},
                "车站公共区 人员 新风量 新鲜空气量 乘客 工作人员 每小时",
            )
        )
        self.assertFalse(
            matcher(
                {"text": "地下车站设备管理用房的楼梯间应满足疏散要求。"},
                "设备管理用房 人员 新风量 新鲜空气量 乘客 工作人员 每小时",
            )
        )
        self.assertTrue(
            matcher(
                {"text": "区间隧道每个乘客的新鲜空气量不应少于12.6m³。"},
                "区间 人员 新风量 新鲜空气量 乘客 工作人员 每小时",
            )
        )
        self.assertTrue(
            matcher(
                {"text": "每个乘客每小时的新鲜空气量不应少于30m³。"},
                "车站公共区 人员 新风量 新鲜空气量 乘客 工作人员 每小时",
            )
        )
        self.assertTrue(
            matcher(
                {"text": "每个乘客每小时需供应\n的新鲜空气量不应少于30m³。"},
                "车站公共区 人员 新风量 新鲜空气量 乘客 工作人员 每小时",
            )
        )
        self.assertTrue(
            matcher(
                {"text": "设备与管理用房内每个工作人员的新风量不应少于30m³。"},
                "设备管理用房 人员 新风量 新鲜空气量 乘客 工作人员 每小时",
            )
        )
        self.assertFalse(
            matcher(
                {"text": "列车运行交路应根据各设计年限客流量确定。"},
                "GB50157-2013设计年限",
            )
        )
        self.assertTrue(
            matcher(
                {"text": "设计年限应分为初期、近期、远期。"},
                "GB50157-2013设计年限",
            )
        )

    def test_target_selection_does_not_fill_unused_slots_with_duplicate_intent(self):
        workflow = AgentWorkflow(
            FakeRetriever(), FakeReranker(), FakeGrader([]), FakeGenerator()
        )
        candidates = [
            {
                "text": text,
                "source": "spec.pdf",
                "spec_id": "cn.a",
                "edition_id": "2025",
                "chunk_id": index,
                "article_id": article,
                "document_query_ranks": {query: rank},
            }
            for index, (article, text, query, rank) in enumerate(
                (
                    ("3.0.21", "下穿水域两端设置防淹门。", "地下工程穿越水域时的防淹", 1),
                    ("3.0.19", "工程应进行防内涝和防洪水设计。", "防止自然灾害 防内涝 防洪 防淹", 1),
                    ("30.8.7", "河道附近另设防淹设施。", "地下工程穿越水域时的防淹", 2),
                )
            )
        ]

        selected = workflow._select_scope_target_coverage(
            candidates,
            ["地下工程穿越水域时的防淹", "防止自然灾害 防内涝 防洪 防淹"],
            ("cn.a@2025",),
            top_n=6,
            score_cache={},
            preferred=[],
        )

        self.assertEqual([item["article_id"] for item in selected], ["3.0.21", "3.0.19"])

    def test_target_selection_fills_remaining_limit_from_preferred_distinct_articles(self):
        workflow = AgentWorkflow(
            FakeRetriever(), FakeReranker(), FakeGrader([]), FakeGenerator()
        )
        query = "车站公共区 人员 新风量 新鲜空气量 乘客 工作人员 每小时"
        candidates = [
            {
                "text": text,
                "source": "spec.pdf",
                "spec_id": "cn.a",
                "edition_id": "2025",
                "chunk_id": index,
                "article_id": article,
                "document_query_ranks": ({query: rank} if rank else {}),
            }
            for index, (article, text, rank) in enumerate(
                (
                    ("1.0.1", "车站公共区每个乘客的新鲜空气量要求。", 1),
                    ("1.0.2", "采用通风时每个乘客的新鲜空气量要求。", 2),
                    ("1.0.3", "采用空调时每个乘客的新鲜空气量要求。", 3),
                )
            )
        ]

        selected = workflow._select_scope_target_coverage(
            candidates,
            [query],
            ("cn.a@2025",),
            top_n=3,
            score_cache={},
            preferred=candidates,
        )

        self.assertEqual(
            [item["article_id"] for item in selected],
            ["1.0.1", "1.0.2", "1.0.3"],
        )

    def test_target_selection_can_keep_two_distinct_clauses_for_one_target(self):
        workflow = AgentWorkflow(
            FakeRetriever(), FakeReranker(), FakeGrader([]), FakeGenerator()
        )
        query = "车站公共区 人员 新风量 新鲜空气量 乘客 工作人员 每小时"
        candidates = [
            {
                "text": text,
                "source": "spec.pdf",
                "spec_id": "cn.a",
                "edition_id": "2025",
                "chunk_id": index,
                "article_id": article,
                "document_query_ranks": {query: index + 1},
            }
            for index, (article, text) in enumerate(
                (
                    ("1.0.1", "采用通风时每个乘客的新鲜空气量要求。"),
                    ("1.0.2", "采用空调时每个乘客的新鲜空气量要求。"),
                )
            )
        ]

        selected = workflow._select_scope_target_coverage(
            candidates,
            [query],
            ("cn.a@2025",),
            top_n=2,
            score_cache={},
            preferred=[],
        )

        self.assertEqual([item["article_id"] for item in selected], ["1.0.1", "1.0.2"])

    def test_target_selection_does_not_impose_equal_document_quota(self):
        workflow = AgentWorkflow(
            FakeRetriever(), FakeReranker(), FakeGrader([]), FakeGenerator()
        )
        queries = ["区间人员新风量", "公共区人员新风量", "设备用房人员新风量"]
        candidates = [
            {
                "text": text,
                "source": f"{spec_id}.pdf",
                "spec_id": spec_id,
                "edition_id": "2025",
                "chunk_id": index,
                "article_id": article,
                "document_query_ranks": ranks,
            }
            for index, (spec_id, article, text, ranks) in enumerate(
                (
                    ("cn.a", "1.0.1", "一条覆盖全部场景", {query: 1 for query in queries}),
                    ("cn.b", "2.0.1", "区间要求", {queries[0]: 1}),
                    ("cn.b", "2.0.2", "公共区要求", {queries[1]: 1}),
                    ("cn.b", "2.0.3", "设备用房要求", {queries[2]: 1}),
                )
            )
        ]

        selected = workflow._select_scope_target_coverage(
            candidates,
            queries,
            ("cn.a@2025", "cn.b@2025"),
            top_n=4,
            score_cache={},
            preferred=[],
        )

        self.assertEqual(
            {item["article_id"] for item in selected},
            {"1.0.1", "2.0.1", "2.0.2", "2.0.3"},
        )

    def test_explicit_spec_target_is_not_copied_to_other_specifications(self):
        workflow = AgentWorkflow(
            FakeRetriever(), FakeReranker(), FakeGrader([]), FakeGenerator()
        )
        design_a = "GB 55033-2022 设计年限"
        design_b = "GB 50157-2013 设计年限"
        capacity_a = "GB 55033-2022 运能"
        candidates = [
            {
                "text": text,
                "source": f"{spec_id}.pdf",
                "spec_id": spec_id,
                "edition_id": edition,
                "standard_code": code,
                "chunk_id": index,
                "article_id": article,
                "document_query_ranks": ranks,
            }
            for index, (spec_id, edition, code, article, text, ranks) in enumerate(
                (
                    ("cn.a", "2022", "GB 55033-2022", "2.1.5", "设计年限应分为初期、近期、远期，并有运能要求", {design_a: 1, capacity_a: 1}),
                    ("cn.b", "2013", "GB 50157-2013", "1.0.8", "设计年限应分为初期、近期、远期", {design_b: 1}),
                    ("cn.b", "2013", "GB 50157-2013", "3.3.4", "列车运能计算", {capacity_a: 1}),
                )
            )
        ]

        selected = workflow._select_scope_target_coverage(
            candidates,
            [design_a, design_b, capacity_a],
            ("cn.a@2022", "cn.b@2013"),
            top_n=3,
            score_cache={},
            preferred=[],
        )

        self.assertEqual(
            {(item["spec_id"], item["article_id"]) for item in selected},
            {("cn.a", "2.1.5"), ("cn.b", "1.0.8")},
        )

    def test_scope_target_selection_prefers_normative_article_occurrence(self):
        workflow = AgentWorkflow(
            FakeRetriever(), FakeReranker(), FakeGrader([]), FakeGenerator()
        )
        target = "DB11/T 995-2025 疏散平台宽度、高差和间隙"
        candidates = [
            {
                "text": "条文说明：疏散平台宽度、高差和间隙应兼顾安全。",
                "source": "spec.pdf", "spec_id": "cn.a", "edition_id": "2025",
                "chunk_id": 2880, "article_id": "6.2.2", "pdf_page_start": 286,
                "document_query_ranks": {target: 1},
            },
            {
                "text": "疏散平台宽度600、800、1000mm，高度950mm，间隙50mm。",
                "source": "spec.pdf", "spec_id": "cn.a", "edition_id": "2025",
                "chunk_id": 405, "article_id": "6.2.2", "pdf_page_start": 40,
                "document_query_ranks": {target: 2},
            },
        ]

        selected = workflow._select_scope_target_coverage(
            candidates, [target], ("cn.a@2025",), top_n=2,
            score_cache={}, preferred=candidates,
        )

        self.assertEqual(selected[0]["chunk_id"], 405)

    def test_scope_target_selection_prefers_direct_rule_over_commentary_restatement(self):
        workflow = AgentWorkflow(
            FakeRetriever(), FakeReranker(), FakeGrader([]), FakeGenerator()
        )
        target = "DB11/T 995-2025 列车纵向冲击率上限"
        candidates = [
            {
                "text": "18.4.7 第3款 在保证列车舒适度，即纵向冲击率不大于0.75m/s³的前提下，停车精度应满足要求。",
                "source": "spec.pdf", "spec_id": "cn.db11", "edition_id": "2025",
                "chunk_id": 3431, "article_id": "18.4.7", "pdf_page_start": 359,
                "document_query_ranks": {target: 1},
            },
            {
                "text": "5.4.7 列车纵向冲击率不应大于0.75m/s³。",
                "source": "spec.pdf", "spec_id": "cn.db11", "edition_id": "2025",
                "chunk_id": 363, "article_id": "5.4.7", "pdf_page_start": 37,
                "document_query_ranks": {target: 2},
            },
        ]

        selected = workflow._select_scope_target_coverage(
            candidates, [target], ("cn.db11@2025",), top_n=1,
            score_cache={}, preferred=candidates,
        )

        self.assertEqual(selected[0]["article_id"], "5.4.7")

    def test_scope_target_selection_keeps_commentary_when_it_is_only_direct_match(self):
        workflow = AgentWorkflow(
            FakeRetriever(), FakeReranker(), FakeGrader([]), FakeGenerator()
        )
        target = "停车精度与纵向冲击率前提"
        candidates = [{
            "text": "18.4.7 第3款 在冲击率不大于0.75m/s³的前提下，停车精度为±0.3m。",
            "source": "spec.pdf", "spec_id": "cn.db11", "edition_id": "2025",
            "chunk_id": 3431, "article_id": "18.4.7", "pdf_page_start": 359,
            "document_query_ranks": {target: 1},
        }]

        selected = workflow._select_scope_target_coverage(
            candidates, [target], ("cn.db11@2025",), top_n=1,
            score_cache={}, preferred=candidates,
        )

        self.assertEqual(selected[0]["article_id"], "18.4.7")

    def test_scope_balance_keeps_best_evidence_from_each_compared_document(self):
        candidates = [
            {
                "text": text,
                "source": f"{spec_id}.pdf",
                "spec_id": spec_id,
                "edition_id": edition_id,
                "chunk_id": index,
                "article_id": article,
            }
            for index, (spec_id, edition_id, article, text) in enumerate(
                (
                    ("cn.a", "2025", "1.0.1", "车站出入口数量要求"),
                    ("cn.a", "2025", "9.9.9", "公共区疏散照明要求"),
                    ("cn.b", "2022", "2.0.1", "车站出入口协调要求"),
                    ("cn.c", "2013", "3.0.1", "车站出入口设置要求"),
                )
            )
        ]
        scores = {
            ("三份规范对车站出入口数量分别有什么规定？", "车站出入口数量要求"): 8,
            ("三份规范对车站出入口数量分别有什么规定？", "公共区疏散照明要求"): 10,
            ("三份规范对车站出入口数量分别有什么规定？", "车站出入口协调要求"): 7,
            ("三份规范对车站出入口数量分别有什么规定？", "车站出入口设置要求"): 6,
        }
        workflow = AgentWorkflow(
            FakeRetriever(), ScoringReranker(scores), FakeGrader([]), FakeGenerator()
        )

        selected = workflow._select_scope_balance(
            "三份规范对车站出入口数量分别有什么规定？",
            candidates,
            ("cn.a@2025", "cn.b@2022", "cn.c@2013"),
            top_n=3,
            score_cache={},
            preferred=candidates[:3],
        )

        self.assertEqual(
            {f"{item['spec_id']}@{item['edition_id']}" for item in selected},
            {"cn.a@2025", "cn.b@2022", "cn.c@2013"},
        )
        self.assertIn("1.0.1", {item["article_id"] for item in selected})

    def test_scope_balance_only_applies_to_explicit_comparisons(self):
        self.assertTrue(AgentWorkflow._requests_per_scope_answer("三份规范分别有什么规定？"))
        self.assertTrue(AgentWorkflow._requests_per_scope_answer("比较两份规范的要求"))
        self.assertFalse(AgentWorkflow._requests_per_scope_answer("城市轨道交通有什么要求？"))

    def test_scope_balance_keeps_direct_lifetime_clause_for_each_spec(self):
        candidates = [
            {
                "text": text, "source": f"{spec_id}.pdf", "spec_id": spec_id,
                "edition_id": edition, "chunk_id": index, "article_id": article,
                "pdf_page_start": page,
            }
            for index, (spec_id, edition, article, page, text) in enumerate((
                ("cn.a", "2025", "3.0.13", 29, "3.0.13 主体结构设计工作年限不低于100年，可更换构件不低于50年。"),
                ("cn.a", "2025", "12.4.7", 120, "主体结构侧墙按100%和50%的刚度包络设计。"),
                ("cn.b", "2022", "5.1.3", 22, "5.1.3 主体和重要结构设计工作年限不小于100年，其他结构50年。"),
                ("cn.c", "2013", "1.0.12", 21, "1.0.12 主体及影响运营安全的结构设计使用年限不低于100年。"),
            ))
        ]
        workflow = AgentWorkflow(
            FakeRetriever(), FakeReranker(), FakeGrader([]), FakeGenerator()
        )
        query = "比较三份规范对主体结构或重要结构设计年限的直接规定，并说明50年条款的适用边界。"

        selected = workflow._select_scope_balance(
            query, candidates, ("cn.a@2025", "cn.b@2022", "cn.c@2013"),
            top_n=6, score_cache={}, preferred=candidates,
        )

        self.assertEqual(
            {(item["spec_id"], item["article_id"]) for item in selected[:3]},
            {("cn.a", "3.0.13"), ("cn.b", "5.1.3"), ("cn.c", "1.0.12")},
        )
        self.assertLessEqual(len(selected), 6)

    def test_scope_balance_uses_remaining_slots_for_distinct_articles_per_spec(self):
        query = "比较三份规范对主体结构设计年限的直接规定，并说明50年边界。"
        candidates = [
            {
                "text": text, "source": f"{spec}.pdf", "spec_id": spec,
                "edition_id": edition, "chunk_id": index, "article_id": article,
            }
            for index, (spec, edition, article, text) in enumerate((
                ("cn.a", "2025", "12.1.2", "主体结构设计年限100年，其他结构50年。"),
                ("cn.a", "2025", "3.0.13", "主体结构及可更换构件的设计工作年限边界。"),
                ("cn.b", "2022", "5.1.3", "主体和重要结构100年，其他结构50年。"),
                ("cn.b", "2022", "2.1.5", "工程初期近期远期设计年限。"),
                ("cn.c", "2013", "11.1.6", "主体结构和可更换次要构件耐久性年限。"),
                ("cn.c", "2013", "1.0.12", "主体及严重影响运营安全结构不低于100年。"),
            ))
        ]
        workflow = AgentWorkflow(
            FakeRetriever(), FakeReranker(), FakeGrader([]), FakeGenerator()
        )

        selected = workflow._select_scope_balance(
            query, candidates, ("cn.a@2025", "cn.b@2022", "cn.c@2013"),
            top_n=6, score_cache={}, preferred=candidates,
        )

        selected_pairs = {(item["spec_id"], item["article_id"]) for item in selected}
        self.assertIn(("cn.a", "3.0.13"), selected_pairs)
        self.assertIn(("cn.c", "1.0.12"), selected_pairs)
        self.assertEqual(len(selected), 6)

    def test_scope_balance_uses_direct_provision_subject_not_boundary_tail(self):
        query = "比较三份规范对主体结构或重要结构设计年限的直接规定，并说明50年条款的适用边界。"

        self.assertEqual(
            AgentWorkflow._scope_balance_focus_query(query),
            "主体结构或重要结构设计年限",
        )

    def test_multi_scope_per_spec_request_uses_current_limit_above_top3(self):
        workflow = AgentWorkflow(
            FakeRetriever(), FakeReranker(), FakeGrader([]), FakeGenerator(),
            evidence_top_n=3,
        )

        limit = workflow._request_evidence_limit(
            "请分别说明三份规范各自第6.2.3条的核心要求。",
            ("cn.a@2025", "cn.b@2022", "cn.c@2013"),
        )

        self.assertEqual(limit, 6)

    def test_requirement_candidates_honor_explicit_specification_and_article(self):
        candidates = [
            {
                "standard_code": code,
                "spec_id": spec_id,
                "edition_id": edition,
                "article_id": article,
                "text": f"{code} {article}",
            }
            for code, spec_id, edition, article in (
                ("DB11/T 995-2025", "cn.db", "2025", "6.2.3"),
                ("GB 55033-2022", "cn.gb", "2022", "6.2.3"),
                ("GB 55033-2022", "cn.gb", "2022", "6.2.4"),
            )
        ]

        selected = AgentWorkflow._candidates_for_requirement(
            "GB 55033-2022第6.2.3条的主题和核心要求", candidates
        )

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["spec_id"], "cn.gb")
        self.assertEqual(selected[0]["article_id"], "6.2.3")

    def test_requirement_candidates_fall_back_when_no_explicit_scope_matches(self):
        candidates = [{"text": "general", "article_id": "1.0.1"}]

        self.assertIs(
            AgentWorkflow._candidates_for_requirement("一般要求", candidates),
            candidates,
        )

    def test_requirement_candidates_prefer_exact_missing_phrase_within_scope(self):
        candidates = [
            {
                "standard_code": "DB11/T 995-2025",
                "spec_id": "cn.db",
                "edition_id": "2025",
                "article_id": article,
                "text": text,
            }
            for article, text in (
                ("30.5.8", "车站公共区疏散照明要求。"),
                ("10.2.1", "本条明确了站点的出入口数量、结建率和连通率要求。"),
            )
        ]

        selected = AgentWorkflow._candidates_for_requirement(
            "DB11/T 995-2025 对车站出入口数量的要求", candidates
        )

        self.assertEqual([item["article_id"] for item in selected], ["10.2.1"])

    def test_unscoped_requirement_does_not_lexically_narrow_candidates(self):
        candidates = [
            {"text": "车辆前后端照明装置", "article_id": "5.6.9"},
            {"text": "信号系统与车库门接口", "article_id": "18.9.6"},
        ]

        selected = AgentWorkflow._candidates_for_requirement(
            "车辆前后端信号装置的要求", candidates
        )

        self.assertIs(selected, candidates)

    def test_focused_overlap_prefers_relevant_low_rank_candidate(self):
        relevant = {"text": "明确站点的出入口数量、结建率和连通率要求"}
        unrelated = {"text": "公共区疏散照明要求"}

        self.assertGreater(
            AgentWorkflow._focused_overlap_score(relevant, "车站出入口数量"),
            AgentWorkflow._focused_overlap_score(unrelated, "车站出入口数量"),
        )


if __name__ == "__main__":
    unittest.main()
