# Offline evaluation tool validation

Offline fixture/tool validation only; not real RAG evaluation or independent acceptance.

Run: `tooling-v1-synthetic-20261109`. Conclusion: `not_applicable`.

Semantic metrics use explicit review labels; null is unobserved/unreviewed.

| Metric | Confirmed numerator | Applicable denominator | Full rate | Observed rate | Missing |
|---|---:|---:|---:|---:|---:|
| initial_candidates.recall@1 | 1.5 | 5 | None | 0.5 | 2 |
| initial_candidates.hitrate@1 | 2 | 5 | None | 0.6666666666666666 | 2 |
| initial_candidates.recall_micro@1 | 2 | 6 | None | 0.5 | 2 |
| initial_candidates.recall@3 | 2.5 | 5 | None | 0.8333333333333334 | 2 |
| initial_candidates.hitrate@3 | 3 | 5 | None | 1.0 | 2 |
| initial_candidates.recall_micro@3 | 3 | 6 | None | 0.75 | 2 |
| initial_candidates.recall@5 | 2.5 | 5 | None | 0.8333333333333334 | 2 |
| initial_candidates.hitrate@5 | 3 | 5 | None | 1.0 | 2 |
| initial_candidates.recall_micro@5 | 3 | 6 | None | 0.75 | 2 |
| initial_candidates.recall@10 | 2.5 | 5 | None | 0.8333333333333334 | 2 |
| initial_candidates.hitrate@10 | 3 | 5 | None | 1.0 | 2 |
| initial_candidates.recall_micro@10 | 3 | 6 | None | 0.75 | 2 |
| initial_candidates.mrr@10 | 3.0 | 5 | None | 1.0 | 2 |
| initial_reranked.recall@1 | 1.5 | 5 | None | 0.5 | 2 |
| initial_reranked.hitrate@1 | 2 | 5 | None | 0.6666666666666666 | 2 |
| initial_reranked.recall_micro@1 | 2 | 6 | None | 0.5 | 2 |
| initial_reranked.recall@3 | 2.5 | 5 | None | 0.8333333333333334 | 2 |
| initial_reranked.hitrate@3 | 3 | 5 | None | 1.0 | 2 |
| initial_reranked.recall_micro@3 | 3 | 6 | None | 0.75 | 2 |
| initial_reranked.recall@5 | 2.5 | 5 | None | 0.8333333333333334 | 2 |
| initial_reranked.hitrate@5 | 3 | 5 | None | 1.0 | 2 |
| initial_reranked.recall_micro@5 | 3 | 6 | None | 0.75 | 2 |
| initial_reranked.recall@10 | 2.5 | 5 | None | 0.8333333333333334 | 2 |
| initial_reranked.hitrate@10 | 3 | 5 | None | 1.0 | 2 |
| initial_reranked.recall_micro@10 | 3 | 6 | None | 0.75 | 2 |
| initial_reranked.mrr@10 | 3.0 | 5 | None | 1.0 | 2 |
| final_fact_complete | 0 | 5 | None | None | 5 |
| complete_correct_answer | 0 | 5 | None | 0.0 | 1 |
| generator_fact_complete | 3 | 4 | None | 1.0 | 1 |
| evidence_support | 0 | 4 | None | None | 4 |
| citation_legal | 1 | 4 | 0.25 | 0.25 | 0 |
| task_success | 2 | 7 | None | 0.3333333333333333 | 1 |
| false_accept | 0 | 1 | 0.0 | 0.0 | 0 |
| false_refuse | 0 | 5 | 0.0 | 0.0 | 0 |
| clarify_action_correct | 1 | 1 | 1.0 | 1.0 | 0 |
| service_error | 1 | 7 | 0.14285714285714285 | 0.14285714285714285 | 0 |
| final_position_complete_diagnostic | 3 | 5 | None | 1.0 | 2 |
| generator_position_complete_diagnostic | 3 | 4 | 0.75 | 0.75 | 0 |

## Review progress

```json
{
  "human_reviewed_case_ids": [],
  "ai_reviewed_case_ids": [
    "SYN-ANSWER",
    "SYN-REFUSE",
    "SYN-CLARIFY",
    "SYN-ERROR",
    "SYN-EQUIVALENT",
    "SYN-COMPOSITE"
  ],
  "pending_quality_case_ids": [
    "SYN-ANSWER"
  ],
  "human_confirmed_task_success_lower_bound": 0.0,
  "human_approval_complete": false
}
```

## Behavior confusion matrix

```json
{
  "answer": {
    "answer": 4,
    "refuse": 0,
    "clarify": 0,
    "error": 1
  },
  "refuse": {
    "answer": 0,
    "refuse": 1,
    "clarify": 0,
    "error": 0
  },
  "clarify": {
    "answer": 0,
    "refuse": 0,
    "clarify": 1,
    "error": 0
  }
}
```

## Performance and observed coverage

```json
{
  "all": {
    "case_ids": [
      "SYN-ANSWER",
      "SYN-REFUSE",
      "SYN-CLARIFY",
      "SYN-ERROR",
      "SYN-EQUIVALENT",
      "SYN-COMPOSITE",
      "SYN-MISSING-OBS"
    ],
    "actual_actions": {
      "answer": 4,
      "refuse": 1,
      "clarify": 1,
      "error": 1
    },
    "latency_ms": {
      "observed_count": 6,
      "total_count": 7,
      "observed_fraction": 0.8571428571428571,
      "observed_sum": 1046,
      "p50": 12,
      "p95": 1000
    },
    "model_calls": {
      "observed_count": 5,
      "total_count": 7,
      "observed_fraction": 0.7142857142857143,
      "observed_sum": 3,
      "p50": 1,
      "p95": 1
    },
    "input_tokens": {
      "observed_count": 1,
      "total_count": 7,
      "observed_fraction": 0.14285714285714285,
      "observed_sum": 20,
      "p50": 20,
      "p95": 20
    },
    "output_tokens": {
      "observed_count": 1,
      "total_count": 7,
      "observed_fraction": 0.14285714285714285,
      "observed_sum": 8,
      "p50": 8,
      "p95": 8
    }
  },
  "expected:answer": {
    "case_ids": [
      "SYN-ANSWER",
      "SYN-ERROR",
      "SYN-EQUIVALENT",
      "SYN-COMPOSITE",
      "SYN-MISSING-OBS"
    ],
    "actual_actions": {
      "answer": 4,
      "error": 1
    },
    "latency_ms": {
      "observed_count": 4,
      "total_count": 5,
      "observed_fraction": 0.8,
      "observed_sum": 1041,
      "p50": 14,
      "p95": 1000
    },
    "model_calls": {
      "observed_count": 3,
      "total_count": 5,
      "observed_fraction": 0.6,
      "observed_sum": 3,
      "p50": 1,
      "p95": 1
    },
    "input_tokens": {
      "observed_count": 1,
      "total_count": 5,
      "observed_fraction": 0.2,
      "observed_sum": 20,
      "p50": 20,
      "p95": 20
    },
    "output_tokens": {
      "observed_count": 1,
      "total_count": 5,
      "observed_fraction": 0.2,
      "observed_sum": 8,
      "p50": 8,
      "p95": 8
    }
  },
  "expected:clarify": {
    "case_ids": [
      "SYN-CLARIFY"
    ],
    "actual_actions": {
      "clarify": 1
    },
    "latency_ms": {
      "observed_count": 1,
      "total_count": 1,
      "observed_fraction": 1.0,
      "observed_sum": 2,
      "p50": 2,
      "p95": 2
    },
    "model_calls": {
      "observed_count": 1,
      "total_count": 1,
      "observed_fraction": 1.0,
      "observed_sum": 0,
      "p50": 0,
      "p95": 0
    },
    "input_tokens": {
      "observed_count": 0,
      "total_count": 1,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    },
    "output_tokens": {
      "observed_count": 0,
      "total_count": 1,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    }
  },
  "expected:refuse": {
    "case_ids": [
      "SYN-REFUSE"
    ],
    "actual_actions": {
      "refuse": 1
    },
    "latency_ms": {
      "observed_count": 1,
      "total_count": 1,
      "observed_fraction": 1.0,
      "observed_sum": 3,
      "p50": 3,
      "p95": 3
    },
    "model_calls": {
      "observed_count": 1,
      "total_count": 1,
      "observed_fraction": 1.0,
      "observed_sum": 0,
      "p50": 0,
      "p95": 0
    },
    "input_tokens": {
      "observed_count": 0,
      "total_count": 1,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    },
    "output_tokens": {
      "observed_count": 0,
      "total_count": 1,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    }
  },
  "outcome:answer": {
    "case_ids": [
      "SYN-ANSWER",
      "SYN-EQUIVALENT",
      "SYN-COMPOSITE",
      "SYN-MISSING-OBS"
    ],
    "actual_actions": {
      "answer": 4
    },
    "latency_ms": {
      "observed_count": 3,
      "total_count": 4,
      "observed_fraction": 0.75,
      "observed_sum": 41,
      "p50": 14,
      "p95": 15
    },
    "model_calls": {
      "observed_count": 3,
      "total_count": 4,
      "observed_fraction": 0.75,
      "observed_sum": 3,
      "p50": 1,
      "p95": 1
    },
    "input_tokens": {
      "observed_count": 1,
      "total_count": 4,
      "observed_fraction": 0.25,
      "observed_sum": 20,
      "p50": 20,
      "p95": 20
    },
    "output_tokens": {
      "observed_count": 1,
      "total_count": 4,
      "observed_fraction": 0.25,
      "observed_sum": 8,
      "p50": 8,
      "p95": 8
    }
  },
  "outcome:clarify": {
    "case_ids": [
      "SYN-CLARIFY"
    ],
    "actual_actions": {
      "clarify": 1
    },
    "latency_ms": {
      "observed_count": 1,
      "total_count": 1,
      "observed_fraction": 1.0,
      "observed_sum": 2,
      "p50": 2,
      "p95": 2
    },
    "model_calls": {
      "observed_count": 1,
      "total_count": 1,
      "observed_fraction": 1.0,
      "observed_sum": 0,
      "p50": 0,
      "p95": 0
    },
    "input_tokens": {
      "observed_count": 0,
      "total_count": 1,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    },
    "output_tokens": {
      "observed_count": 0,
      "total_count": 1,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    }
  },
  "outcome:error": {
    "case_ids": [
      "SYN-ERROR"
    ],
    "actual_actions": {
      "error": 1
    },
    "latency_ms": {
      "observed_count": 1,
      "total_count": 1,
      "observed_fraction": 1.0,
      "observed_sum": 1000,
      "p50": 1000,
      "p95": 1000
    },
    "model_calls": {
      "observed_count": 0,
      "total_count": 1,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    },
    "input_tokens": {
      "observed_count": 0,
      "total_count": 1,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    },
    "output_tokens": {
      "observed_count": 0,
      "total_count": 1,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    }
  },
  "outcome:refuse": {
    "case_ids": [
      "SYN-REFUSE"
    ],
    "actual_actions": {
      "refuse": 1
    },
    "latency_ms": {
      "observed_count": 1,
      "total_count": 1,
      "observed_fraction": 1.0,
      "observed_sum": 3,
      "p50": 3,
      "p95": 3
    },
    "model_calls": {
      "observed_count": 1,
      "total_count": 1,
      "observed_fraction": 1.0,
      "observed_sum": 0,
      "p50": 0,
      "p95": 0
    },
    "input_tokens": {
      "observed_count": 0,
      "total_count": 1,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    },
    "output_tokens": {
      "observed_count": 0,
      "total_count": 1,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    }
  },
  "type:unspecified": {
    "case_ids": [
      "SYN-ANSWER",
      "SYN-REFUSE",
      "SYN-CLARIFY",
      "SYN-ERROR",
      "SYN-EQUIVALENT",
      "SYN-COMPOSITE",
      "SYN-MISSING-OBS"
    ],
    "actual_actions": {
      "answer": 4,
      "refuse": 1,
      "clarify": 1,
      "error": 1
    },
    "latency_ms": {
      "observed_count": 6,
      "total_count": 7,
      "observed_fraction": 0.8571428571428571,
      "observed_sum": 1046,
      "p50": 12,
      "p95": 1000
    },
    "model_calls": {
      "observed_count": 5,
      "total_count": 7,
      "observed_fraction": 0.7142857142857143,
      "observed_sum": 3,
      "p50": 1,
      "p95": 1
    },
    "input_tokens": {
      "observed_count": 1,
      "total_count": 7,
      "observed_fraction": 0.14285714285714285,
      "observed_sum": 20,
      "p50": 20,
      "p95": 20
    },
    "output_tokens": {
      "observed_count": 1,
      "total_count": 7,
      "observed_fraction": 0.14285714285714285,
      "observed_sum": 8,
      "p50": 8,
      "p95": 8
    }
  }
}
```

Semantic scores may include disclosed AI reviews; no acceptance without human approval and frozen thresholds.

## Scoring modes

```json
{
  "initial_candidates.recall@1": "automatic_location_or_behavior",
  "initial_candidates.hitrate@1": "automatic_location_or_behavior",
  "initial_candidates.recall_micro@1": "automatic_location_or_behavior",
  "initial_candidates.recall@3": "automatic_location_or_behavior",
  "initial_candidates.hitrate@3": "automatic_location_or_behavior",
  "initial_candidates.recall_micro@3": "automatic_location_or_behavior",
  "initial_candidates.recall@5": "automatic_location_or_behavior",
  "initial_candidates.hitrate@5": "automatic_location_or_behavior",
  "initial_candidates.recall_micro@5": "automatic_location_or_behavior",
  "initial_candidates.recall@10": "automatic_location_or_behavior",
  "initial_candidates.hitrate@10": "automatic_location_or_behavior",
  "initial_candidates.recall_micro@10": "automatic_location_or_behavior",
  "initial_candidates.mrr@10": "automatic_location_or_behavior",
  "initial_reranked.recall@1": "automatic_location_or_behavior",
  "initial_reranked.hitrate@1": "automatic_location_or_behavior",
  "initial_reranked.recall_micro@1": "automatic_location_or_behavior",
  "initial_reranked.recall@3": "automatic_location_or_behavior",
  "initial_reranked.hitrate@3": "automatic_location_or_behavior",
  "initial_reranked.recall_micro@3": "automatic_location_or_behavior",
  "initial_reranked.recall@5": "automatic_location_or_behavior",
  "initial_reranked.hitrate@5": "automatic_location_or_behavior",
  "initial_reranked.recall_micro@5": "automatic_location_or_behavior",
  "initial_reranked.recall@10": "automatic_location_or_behavior",
  "initial_reranked.hitrate@10": "automatic_location_or_behavior",
  "initial_reranked.recall_micro@10": "automatic_location_or_behavior",
  "initial_reranked.mrr@10": "automatic_location_or_behavior",
  "final_fact_complete": "review_required_provisional",
  "complete_correct_answer": "review_required_provisional",
  "generator_fact_complete": "review_required_provisional",
  "evidence_support": "review_required_provisional",
  "citation_legal": "automatic_location_or_behavior",
  "task_success": "review_required_provisional",
  "false_accept": "automatic_location_or_behavior",
  "false_refuse": "automatic_location_or_behavior",
  "clarify_action_correct": "automatic_location_or_behavior",
  "service_error": "automatic_location_or_behavior",
  "final_position_complete_diagnostic": "automatic_location_or_behavior",
  "generator_position_complete_diagnostic": "automatic_location_or_behavior"
}
```

## Grouped metrics

Grouped metrics by expected action and question type are in report.json.
