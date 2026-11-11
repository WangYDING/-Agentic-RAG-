# Agent Evaluation

- Cases: 4 (3 answerable, 1 unanswerable)
- Model: `deepseek-flash`

- Release: blocked_pending_human_review_and_real_deployment_baselines
- Provenance and category denominators: `phase0_seen_regression_evidence_selection_20261104_234817.json`

## Retrieval / Evidence

- Initial HitRate@3: 1.0
- Initial Recall@3: 0.5
- Initial Recall@10: 0.8333333333333334
- Final HitRate@3: 1.0
- Final Recall@3: 0.8333333333333334
- Multi-evidence complete@3: 2/3

## Agent Decision

- First sufficient: 0
- Retried: 4
- Retry sufficient: 2
- Retry still insufficient: 2
- Final answer/refuse/error: 2/2/0
- Correct unanswerable refusal: 1
- False accept/refusal: 0/1

## Per Case

| ID | Expected | First grade | Retry | Second grade | Action | Gold Top3 | Citation |
|---|---:|---|---:|---|---|---|---|
| IND-001 | True | insufficient | 1 | insufficient | refuse | False | - |
| IND-003 | True | insufficient | 1 | sufficient | answer | True | True |
| MULTI-002 | True | insufficient | 1 | sufficient | answer | True | True |
| IND-006 | False | insufficient | 1 | insufficient | refuse | True | - |
