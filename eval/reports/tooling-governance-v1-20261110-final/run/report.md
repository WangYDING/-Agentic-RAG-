# Offline evaluation tool validation

Offline fixture/tool validation only; not real RAG evaluation or independent acceptance.

Run: `run`. Conclusion: `not_applicable`.

Semantic metrics use explicit review labels; null is unobserved/unreviewed.

| Metric | Confirmed numerator | Applicable denominator | Full rate | Observed rate | Missing |
|---|---:|---:|---:|---:|---:|
| initial_candidates.recall@1 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| initial_candidates.hitrate@1 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_candidates.recall_micro@1 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_candidates.recall@3 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| initial_candidates.hitrate@3 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_candidates.recall_micro@3 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_candidates.recall@5 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| initial_candidates.hitrate@5 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_candidates.recall_micro@5 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_candidates.recall@10 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| initial_candidates.hitrate@10 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_candidates.recall_micro@10 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_candidates.mrr@10 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| initial_reranked.recall@1 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| initial_reranked.hitrate@1 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_reranked.recall_micro@1 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_reranked.recall@3 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| initial_reranked.hitrate@3 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_reranked.recall_micro@3 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_reranked.recall@5 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| initial_reranked.hitrate@5 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_reranked.recall_micro@5 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_reranked.recall@10 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| initial_reranked.hitrate@10 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_reranked.recall_micro@10 | 2 | 2 | 1.0 | 1.0 | 0 |
| initial_reranked.mrr@10 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:candidates.recall@1 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:candidates.hitrate@1 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:candidates.recall_micro@1 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:candidates.recall@3 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:candidates.hitrate@3 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:candidates.recall_micro@3 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:candidates.recall@5 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:candidates.hitrate@5 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:candidates.recall_micro@5 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:candidates.recall@10 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:candidates.hitrate@10 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:candidates.recall_micro@10 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:candidates.mrr@10 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:reranked.recall@1 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:reranked.hitrate@1 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:reranked.recall_micro@1 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:reranked.recall@3 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:reranked.hitrate@3 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:reranked.recall_micro@3 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:reranked.recall@5 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:reranked.hitrate@5 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:reranked.recall_micro@5 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:reranked.recall@10 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:reranked.hitrate@10 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:reranked.recall_micro@10 | 2 | 2 | 1.0 | 1.0 | 0 |
| round:retrieve-1:reranked.mrr@10 | 2.0 | 2 | 1.0 | 1.0 | 0 |
| final_fact_complete | 0 | 2 | None | None | 2 |
| complete_correct_answer | 0 | 2 | None | None | 2 |
| generator_fact_complete | 0 | 2 | None | None | 2 |
| evidence_support | 0 | 2 | None | None | 2 |
| citation_legal | 2 | 2 | 1.0 | 1.0 | 0 |
| task_success | 0 | 2 | None | None | 2 |
| false_accept | 0 | 0 | None | None | 0 |
| false_refuse | 0 | 2 | 0.0 | 0.0 | 0 |
| clarify_action_correct | 0 | 0 | None | None | 0 |
| service_error | 0 | 2 | 0.0 | 0.0 | 0 |
| final_position_complete_diagnostic | 2 | 2 | 1.0 | 1.0 | 0 |
| generator_position_complete_diagnostic | 2 | 2 | 1.0 | 1.0 | 0 |

## Review progress

```json
{
  "human_reviewed_case_ids": [],
  "ai_reviewed_case_ids": [],
  "pending_quality_case_ids": [
    "SEM-001",
    "SEM-002"
  ],
  "human_confirmed_task_success_lower_bound": 0.0,
  "human_approval_complete": false
}
```

## Behavior confusion matrix

```json
{
  "answer": {
    "answer": 2,
    "refuse": 0,
    "clarify": 0,
    "error": 0
  },
  "refuse": {
    "answer": 0,
    "refuse": 0,
    "clarify": 0,
    "error": 0
  },
  "clarify": {
    "answer": 0,
    "refuse": 0,
    "clarify": 0,
    "error": 0
  }
}
```

## Performance and observed coverage

```json
{
  "all": {
    "case_ids": [
      "SEM-001",
      "SEM-002"
    ],
    "actual_actions": {
      "answer": 2
    },
    "latency_ms": {
      "observed_count": 2,
      "total_count": 2,
      "observed_fraction": 1.0,
      "observed_sum": 0.0,
      "p50": 0.0,
      "p95": 0.0
    },
    "model_calls": {
      "observed_count": 2,
      "total_count": 2,
      "observed_fraction": 1.0,
      "observed_sum": 0,
      "p50": 0,
      "p95": 0
    },
    "input_tokens": {
      "observed_count": 0,
      "total_count": 2,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    },
    "output_tokens": {
      "observed_count": 0,
      "total_count": 2,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    }
  },
  "expected:answer": {
    "case_ids": [
      "SEM-001",
      "SEM-002"
    ],
    "actual_actions": {
      "answer": 2
    },
    "latency_ms": {
      "observed_count": 2,
      "total_count": 2,
      "observed_fraction": 1.0,
      "observed_sum": 0.0,
      "p50": 0.0,
      "p95": 0.0
    },
    "model_calls": {
      "observed_count": 2,
      "total_count": 2,
      "observed_fraction": 1.0,
      "observed_sum": 0,
      "p50": 0,
      "p95": 0
    },
    "input_tokens": {
      "observed_count": 0,
      "total_count": 2,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    },
    "output_tokens": {
      "observed_count": 0,
      "total_count": 2,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    }
  },
  "outcome:answer": {
    "case_ids": [
      "SEM-001",
      "SEM-002"
    ],
    "actual_actions": {
      "answer": 2
    },
    "latency_ms": {
      "observed_count": 2,
      "total_count": 2,
      "observed_fraction": 1.0,
      "observed_sum": 0.0,
      "p50": 0.0,
      "p95": 0.0
    },
    "model_calls": {
      "observed_count": 2,
      "total_count": 2,
      "observed_fraction": 1.0,
      "observed_sum": 0,
      "p50": 0,
      "p95": 0
    },
    "input_tokens": {
      "observed_count": 0,
      "total_count": 2,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    },
    "output_tokens": {
      "observed_count": 0,
      "total_count": 2,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    }
  },
  "type:semantic_article": {
    "case_ids": [
      "SEM-001",
      "SEM-002"
    ],
    "actual_actions": {
      "answer": 2
    },
    "latency_ms": {
      "observed_count": 2,
      "total_count": 2,
      "observed_fraction": 1.0,
      "observed_sum": 0.0,
      "p50": 0.0,
      "p95": 0.0
    },
    "model_calls": {
      "observed_count": 2,
      "total_count": 2,
      "observed_fraction": 1.0,
      "observed_sum": 0,
      "p50": 0,
      "p95": 0
    },
    "input_tokens": {
      "observed_count": 0,
      "total_count": 2,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
    },
    "output_tokens": {
      "observed_count": 0,
      "total_count": 2,
      "observed_fraction": 0.0,
      "observed_sum": null,
      "p50": null,
      "p95": null
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
  "round:retrieve-1:candidates.recall@1": "automatic_location_or_behavior",
  "round:retrieve-1:candidates.hitrate@1": "automatic_location_or_behavior",
  "round:retrieve-1:candidates.recall_micro@1": "automatic_location_or_behavior",
  "round:retrieve-1:candidates.recall@3": "automatic_location_or_behavior",
  "round:retrieve-1:candidates.hitrate@3": "automatic_location_or_behavior",
  "round:retrieve-1:candidates.recall_micro@3": "automatic_location_or_behavior",
  "round:retrieve-1:candidates.recall@5": "automatic_location_or_behavior",
  "round:retrieve-1:candidates.hitrate@5": "automatic_location_or_behavior",
  "round:retrieve-1:candidates.recall_micro@5": "automatic_location_or_behavior",
  "round:retrieve-1:candidates.recall@10": "automatic_location_or_behavior",
  "round:retrieve-1:candidates.hitrate@10": "automatic_location_or_behavior",
  "round:retrieve-1:candidates.recall_micro@10": "automatic_location_or_behavior",
  "round:retrieve-1:candidates.mrr@10": "automatic_location_or_behavior",
  "round:retrieve-1:reranked.recall@1": "automatic_location_or_behavior",
  "round:retrieve-1:reranked.hitrate@1": "automatic_location_or_behavior",
  "round:retrieve-1:reranked.recall_micro@1": "automatic_location_or_behavior",
  "round:retrieve-1:reranked.recall@3": "automatic_location_or_behavior",
  "round:retrieve-1:reranked.hitrate@3": "automatic_location_or_behavior",
  "round:retrieve-1:reranked.recall_micro@3": "automatic_location_or_behavior",
  "round:retrieve-1:reranked.recall@5": "automatic_location_or_behavior",
  "round:retrieve-1:reranked.hitrate@5": "automatic_location_or_behavior",
  "round:retrieve-1:reranked.recall_micro@5": "automatic_location_or_behavior",
  "round:retrieve-1:reranked.recall@10": "automatic_location_or_behavior",
  "round:retrieve-1:reranked.hitrate@10": "automatic_location_or_behavior",
  "round:retrieve-1:reranked.recall_micro@10": "automatic_location_or_behavior",
  "round:retrieve-1:reranked.mrr@10": "automatic_location_or_behavior",
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
