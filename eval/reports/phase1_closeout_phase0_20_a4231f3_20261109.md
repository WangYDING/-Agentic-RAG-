# Agent Evaluation

- Cases: 20 (16 answerable, 4 unanswerable)
- Model: `deepseek-flash`

- Release: blocked_pending_human_review_and_real_deployment_baselines
- Provenance and category denominators: `phase1_closeout_phase0_20_a4231f3_20261109.json`

## Retrieval / Evidence

- Initial HitRate@3: 1.0
- Initial Recall@3: 0.8947368421052632
- Initial Recall@10: 1.0
- Final HitRate@3: 1.0
- Final Recall@3: 1.0
- Multi-evidence complete@3: 3/3

## Agent Decision

- First sufficient: 14
- Retried: 6
- Retry sufficient: 2
- Retry still insufficient: 4
- Final answer/refuse/error: 15/4/1
- Correct unanswerable refusal: 4
- False accept/refusal: 0/0

## Per Case

| ID | Expected | First grade | Retry | Second grade | Action | Gold Top3 | Citation |
|---|---:|---|---:|---|---|---|---|
| IND-001 | True | insufficient | 1 | sufficient | answer | True | True |
| IND-002 | True | sufficient | 0 | - | answer | True | True |
| IND-003 | True | insufficient | 1 | sufficient | error | True | False |
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
