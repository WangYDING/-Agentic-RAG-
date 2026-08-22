import unittest

from eval.run_score_diagnostic import _threshold_metrics, summarize


class ScoreDiagnosticTest(unittest.TestCase):
    def test_threshold_metrics_separate_false_accept_and_false_refusal(self):
        result = _threshold_metrics([1, 1, 0, 0], [0.9, 0.4, 0.8, 0.2], 0.5)

        self.assertAlmostEqual(result["precision"], 0.5)
        self.assertAlmostEqual(result["recall"], 0.5)
        self.assertAlmostEqual(result["f1"], 0.5)
        self.assertAlmostEqual(result["false_accept_rate"], 0.5)
        self.assertAlmostEqual(result["false_refusal_rate"], 0.5)

    def test_summarize_reports_fixed_distribution_statistics(self):
        result = summarize([0.1, 0.2, 0.3, 0.4])

        self.assertEqual(result["count"], 4)
        self.assertAlmostEqual(result["min"], 0.1)
        self.assertAlmostEqual(result["p25"], 0.175)
        self.assertAlmostEqual(result["mean"], 0.25)
        self.assertAlmostEqual(result["median"], 0.25)
        self.assertAlmostEqual(result["p75"], 0.325)
        self.assertAlmostEqual(result["max"], 0.4)


if __name__ == "__main__":
    unittest.main()
