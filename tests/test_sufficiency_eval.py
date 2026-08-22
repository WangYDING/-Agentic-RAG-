import unittest

from eval.run_sufficiency import compute_metrics


class SufficiencyEvalTest(unittest.TestCase):
    def test_metrics_treat_insufficient_as_false_accept_control(self):
        cases = [
            {"expected_decision": "sufficient", "predicted_decision": "sufficient"},
            {"expected_decision": "sufficient", "predicted_decision": "insufficient"},
            {"expected_decision": "insufficient", "predicted_decision": "sufficient"},
            {"expected_decision": "insufficient", "predicted_decision": "insufficient"},
        ]

        metrics = compute_metrics(cases)

        self.assertEqual(metrics["confusion_matrix"], {"tp": 1, "fp": 1, "tn": 1, "fn": 1})
        self.assertAlmostEqual(metrics["accuracy"], 0.5)
        self.assertAlmostEqual(metrics["precision"], 0.5)
        self.assertAlmostEqual(metrics["recall"], 0.5)
        self.assertAlmostEqual(metrics["f1"], 0.5)
        self.assertAlmostEqual(metrics["false_accept_rate"], 0.5)
        self.assertAlmostEqual(metrics["false_refusal_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
