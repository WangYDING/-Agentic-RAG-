# Phase 1 seen-set regression record (2026-11-07)

## Identity

- Code under test: `39d5fdb` (`fix: grade asymmetric specification comparisons`)
- Knowledge-base snapshot: `65b3ccfc96a372e54b1c7ecc5ba7f622788d71beafee4206a0298ed10a9fb859`
- Previous snapshot retained for rollback: `39c3e07c109c07cb1dc331db3055cf041a33498aafb9dde6c2eb022421dd3020`
- Model configuration: the frozen Phase 1 `deepseek-flash` configuration recorded in each raw run
- Evaluation status: both datasets are **seen regression sets**, not independent acceptance evidence

## Implemented fixes

| Commit | Change |
| --- | --- |
| `b22400f` | Scope-bound syntax decomposition for parallel multi-part questions (011/013) |
| `5d1e7cf` | Reviewed structured derivation for GB 55033-2022 table 3.0.4 and a rollbackable snapshot (021) |
| `7f358f4` | Preserve Phase 0 single-document evidence coverage |
| `5b1c639` | Bounded cross-spec evidence coverage within the request evidence limit |
| `39d5fdb` | Avoid invented requirements in asymmetric cross-spec comparisons |

## Phase 0 seen 20-question regression

Raw result: `eval/reports/phase0_seen_20_full_stable_20261107.json`

- 16/16 answerable questions answered; 4/4 unanswerable questions refused.
- False accepts: 0. False refusals: 0. Service errors: 0.
- Final Recall@3: 100%; multi-evidence complete coverage: 3/3.
- This successful run predates the final Grader-only commit `39d5fdb`; a final confirmation run is still required when the model service is stable.

## Phase 1 seen 30-question runs

| Run | Answer / refuse / error | Answerable final evidence complete | Scope violations | Citation errors | Cross-spec p95 | Total tokens | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `phase1_seen_30_full_stable_20261107.json` | 22 / 6 / 2 | 23/25 | 0 | 0 | 90.563 s | 107,010 | Failed: evidence loss and service errors |
| `phase1_seen_30_full_stable_retry_20261107.json` | 22 / 8 / 0 | 25/25 | 0 | 0 | 70.093 s | 116,886 | Failed: false refusals on 013/017/018 |
| `phase1_seen_30_full_final_20261107.json` | 23 / 5 / 2 | 25/25 | 0 | 0 | 90.422 s | 112,392 | Unable to determine because of service errors |

For the final run, P1-IND-026 and P1-IND-027 correctly took the no-model `clarify_scope` path; the serialized outer result type is `refuse`. P1-IND-028 through P1-IND-030 correctly refused. P1-IND-013 and P1-IND-014 ended with `MODEL_TIMEOUT` and were retained as failures. The remaining 23 answerable questions answered, including 017, 018, 020 and the repaired structured-table case 021.

The final run proves that all gold clauses for all 25 answerable questions reached final evidence and that scope and citation constraints held. It does **not** prove stable answer quality because two answerable samples did not complete. The repeated 013 behavior (answer, false refusal, or timeout across real runs) is a service/cost stability problem, not an unresolved clause-recall failure. The 014 timeout in the final run shows that the instability is not isolated to one question.

## Decision

Phase 1 is not ready for a new independent acceptance run. The current status is **unable to determine because of runtime/model-service instability**. Do not replace the preserved independent result (`23/30` overall and `16/25` answerable) with these seen-set regressions.

Before freezing a new independent set:

1. establish a stable runtime window or make an explicit, separately reviewed latency/call-budget change;
2. rerun the complete Phase 1 seen 30 questions once, without deleting or retrying individual failed samples;
3. rerun the complete Phase 0 seen 20 questions against the exact final code commit;
4. audit final evidence and generated answers, then record quality, p95 latency, tokens and model calls.

Only after both complete regressions are stable should a new cross-spec dataset and its thresholds be authored, reviewed and frozen before any candidate answers are requested.
