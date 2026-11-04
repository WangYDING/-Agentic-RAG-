# Agent Evaluation

- Cases: 20 (16 answerable, 4 unanswerable)
- Model: `deepseek-flash`

- Release: blocked_pending_human_review_and_real_deployment_baselines
- Provenance and category denominators: `phase0_independent_20261104_162214.json`

## Retrieval / Evidence

- Initial HitRate@3: 1.0
- Initial Recall@3: 0.8947368421052632
- Initial Recall@10: 1.0
- Final HitRate@3: 1.0
- Final Recall@3: 0.8947368421052632
- Multi-evidence complete@3: 1/3

## Agent Decision

- First sufficient: 13
- Retried: 7
- Retry sufficient: 0
- Retry still insufficient: 7
- Final answer/refuse/error: 13/7/0
- Correct unanswerable refusal: 4
- False accept/refusal: 0/3

## Per Case

| ID | Expected | First grade | Retry | Second grade | Action | Gold Top3 | Citation |
|---|---:|---|---:|---|---|---|---|
| IND-001 | True | insufficient | 1 | insufficient | refuse | False | - |
| IND-002 | True | insufficient | 1 | insufficient | refuse | True | - |
| IND-003 | True | insufficient | 1 | insufficient | refuse | False | - |
| IND-004 | True | sufficient | 0 | - | answer | True | True |
| IND-005 | True | sufficient | 0 | - | answer | True | True |
| IND-006 | False | insufficient | 1 | insufficient | refuse | True | - |
| IND-007 | True | sufficient | 0 | - | answer | True | True |
| IND-008 | True | sufficient | 0 | - | answer | True | True |
| IND-009 | True | sufficient | 0 | - | answer | True | True |
| IND-010 | True | sufficient | 0 | - | answer | True | True |
| IND-011 | True | sufficient | 0 | - | answer | True | True |
| IND-012 | True | sufficient | 0 | - | answer | True | True |
| IND-013 | True | sufficient | 0 | - | answer | True | True |
| IND-014 | True | sufficient | 0 | - | answer | True | True |
| IND-015 | True | sufficient | 0 | - | answer | True | True |
| IND-016 | True | sufficient | 0 | - | answer | True | True |
| IND-017 | True | sufficient | 0 | - | answer | True | True |
| IND-NEG-001 | False | insufficient | 1 | insufficient | refuse | None | - |
| IND-NEG-002 | False | insufficient | 1 | insufficient | refuse | None | - |
| IND-NEG-003 | False | insufficient | 1 | insufficient | refuse | None | - |
