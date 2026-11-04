# Agent Evaluation

- Cases: 2 (1 answerable, 1 unanswerable)
- Model: `deepseek-flash`

- Release: blocked_pending_human_review_and_real_deployment_baselines
- Provenance and category denominators: `phase0_seen_regression_grader_20261104_233651.json`

## Retrieval / Evidence

- Initial HitRate@3: 1.0
- Initial Recall@3: 1.0
- Initial Recall@10: 1.0
- Final HitRate@3: 1.0
- Final Recall@3: 1.0
- Multi-evidence complete@3: 0/0

## Agent Decision

- First sufficient: 1
- Retried: 1
- Retry sufficient: 0
- Retry still insufficient: 1
- Final answer/refuse/error: 1/1/0
- Correct unanswerable refusal: 1
- False accept/refusal: 0/0

## Per Case

| ID | Expected | First grade | Retry | Second grade | Action | Gold Top3 | Citation |
|---|---:|---|---:|---|---|---|---|
| IND-002 | True | sufficient | 0 | - | answer | True | True |
| IND-006 | False | insufficient | 1 | insufficient | refuse | True | - |
