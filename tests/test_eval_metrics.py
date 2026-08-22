import unittest

from eval.metrics import compute_grouped_metrics, compute_retrieval_metrics


class EvalMetricsTest(unittest.TestCase):
    def test_recall_hitrate_and_mrr(self):
        cases = [
            {"question_type": "article", "hits": [True, False, False], "gold_hit_ids_by_rank": [[0], [], []], "gold_count": 1},
            {"question_type": "article", "hits": [False, False, True], "gold_hit_ids_by_rank": [[], [], [0]], "gold_count": 1},
            {"question_type": "table", "hits": [False, False, False], "gold_hit_ids_by_rank": [[], [], []], "gold_count": 1},
        ]

        metrics = compute_retrieval_metrics(cases)

        self.assertAlmostEqual(metrics["recall@1"], 1 / 3)
        self.assertAlmostEqual(metrics["hitrate@1"], 1 / 3)
        self.assertAlmostEqual(metrics["recall@3"], 2 / 3)
        self.assertAlmostEqual(metrics["hitrate@3"], 2 / 3)
        self.assertAlmostEqual(metrics["mrr@10"], (1 + 1 / 3 + 0) / 3)

    def test_recall_counts_unique_gold_evidence_coverage(self):
        cases = [
            {
                "question_type": "multi",
                "hits": [True, True, True],
                "gold_hit_ids_by_rank": [[0], [0], [1]],
                "gold_count": 2,
            }
        ]

        metrics = compute_retrieval_metrics(cases)

        self.assertAlmostEqual(metrics["hitrate@1"], 1.0)
        self.assertAlmostEqual(metrics["recall@1"], 0.5)
        self.assertAlmostEqual(metrics["recall@3"], 1.0)

    def test_unanswerable_without_gold_is_excluded_from_metrics(self):
        cases = [
            {
                "question_type": "unanswerable",
                "answerable": False,
                "metric_eligible": False,
                "hits": [True],
                "gold_hit_ids_by_rank": [[0]],
                "gold_count": 0,
            },
            {
                "question_type": "article",
                "answerable": True,
                "metric_eligible": True,
                "hits": [False, True],
                "gold_hit_ids_by_rank": [[], [0]],
                "gold_count": 1,
            },
        ]

        metrics = compute_retrieval_metrics(cases)

        self.assertEqual(metrics["count"], 1)
        self.assertAlmostEqual(metrics["recall@1"], 0.0)
        self.assertAlmostEqual(metrics["recall@3"], 1.0)

    def test_grouped_metrics(self):
        groups = compute_grouped_metrics([
            {"question_type": "article", "hits": [False, True], "gold_hit_ids_by_rank": [[], [0]], "gold_count": 1},
            {"question_type": "table", "hits": [True], "gold_hit_ids_by_rank": [[0]], "gold_count": 1},
        ])

        self.assertAlmostEqual(groups["article"]["recall@1"], 0.0)
        self.assertAlmostEqual(groups["article"]["recall@3"], 1.0)
        self.assertAlmostEqual(groups["table"]["recall@1"], 1.0)


if __name__ == "__main__":
    unittest.main()
