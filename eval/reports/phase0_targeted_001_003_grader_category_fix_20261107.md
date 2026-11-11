# Agent Evaluation

- Cases: 4 (3 answerable, 1 unanswerable)
- Model: `deepseek-flash`

- Release: blocked_pending_human_review_and_real_deployment_baselines
- Provenance and category denominators: `phase0_targeted_001_003_grader_category_fix_20261107.json`

## Retrieval / Evidence

- Initial HitRate@3: 1.0
- Initial Recall@3: 0.5
- Initial Recall@10: 0.8333333333333334
- Final HitRate@3: 1.0
- Final Recall@3: 1.0
- Multi-evidence complete@3: 3/3

## Agent Decision

- First sufficient: 0
- Retried: 4
- Retry sufficient: 3
- Retry still insufficient: 1
- Final answer/refuse/error: 3/1/0
- Correct unanswerable refusal: 1
- False accept/refusal: 0/0

## Per Case

| ID | Expected | First grade | Retry | Second grade | Action | Gold Top3 | Citation |
|---|---:|---|---:|---|---|---|---|
| IND-001 | True | insufficient | 1 | sufficient | answer | True | True |
| IND-003 | True | insufficient | 1 | sufficient | answer | True | True |
| MULTI-002 | True | insufficient | 1 | sufficient | answer | True | True |
| IND-006 | False | insufficient | 1 | insufficient | refuse | True | - |
