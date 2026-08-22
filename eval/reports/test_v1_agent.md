# Final Test v1 Agent Evaluation

- Cases: 20 (16 answerable, 4 unanswerable)
- Model: `deepseek-v4-flash`

## Retrieval / Evidence

- Initial HitRate@3: 0.8750
- Initial Recall@3: 0.7727
- Initial Recall@10: 0.8182
- Final HitRate@3: 0.8750
- Final Recall@3: 0.7727
- Multi-evidence complete@3: 1/3

## Agent Decision

- First sufficient: 13
- Retried: 7
- Retry sufficient: 1
- Retry still insufficient: 6
- Final answer/refuse: 14/6
- Correct unanswerable refusal: 4
- False accept/refusal: 0/2

## Per Case

| ID | Expected | First grade | Retry | Second grade | Action | Gold Top3 | Citation |
|---|---:|---|---:|---|---|---|---|
| FINAL-CAND-ORD-001 | True | sufficient | 0 | - | answer | True | True |
| FINAL-CAND-ORD-002 | True | sufficient | 0 | - | answer | True | True |
| FINAL-CAND-ORD-003 | True | sufficient | 0 | - | answer | True | True |
| FINAL-CAND-ORD-004 | True | sufficient | 0 | - | answer | True | True |
| FINAL-CAND-ORD-005 | True | insufficient | 1 | sufficient | answer | True | True |
| FINAL-CAND-ORD-006 | True | sufficient | 0 | - | answer | True | True |
| FINAL-CAND-HARD-001 | True | sufficient | 0 | - | answer | True | True |
| FINAL-CAND-HARD-002 | True | sufficient | 0 | - | answer | False | True |
| FINAL-CAND-HARD-003 | True | sufficient | 0 | - | answer | False | True |
| FINAL-CAND-HARD-004 | True | sufficient | 0 | - | answer | True | True |
| FINAL-CAND-MULTI-001 | True | sufficient | 0 | - | answer | True | True |
| FINAL-CAND-MULTI-002 | True | sufficient | 0 | - | answer | False | True |
| FINAL-CAND-MULTI-003 | True | insufficient | 1 | insufficient | refuse | False | - |
| FINAL-CAND-AGENT-001 | True | insufficient | 1 | insufficient | refuse | False | - |
| FINAL-CAND-AGENT-002 | True | sufficient | 0 | - | answer | True | True |
| FINAL-CAND-AGENT-003 | True | sufficient | 0 | - | answer | True | True |
| FINAL-CAND-UA-001 | False | insufficient | 1 | insufficient | refuse | None | - |
| FINAL-CAND-UA-002 | False | insufficient | 1 | insufficient | refuse | None | - |
| FINAL-CAND-UA-003 | False | insufficient | 1 | insufficient | refuse | None | - |
| FINAL-CAND-UA-004 | False | insufficient | 1 | insufficient | refuse | None | - |
