# Phase 1 independent v2 acceptance (2026-11-07)

## Decision

**未通过。** The fixed candidate completed all 27 questions without a service error, and scope, citation, refusal safety and most answer behavior passed. Final evidence coverage and complete-answer count missed their frozen thresholds. Phase 1 is not tagged or released as complete.

This dataset became a seen regression set immediately after this first run. Its result must not be replaced by a repaired rerun.

## Frozen identity

- Runtime-logic commit: `94adda3bb3e926a3180be1ef91e51cd67403049e`
- Data/gate freeze commit: `214150ef98d6f07f5bb038d88b9a21ff213da8b1`
- Dataset SHA-256: `6532a7f0a67aaa793ee165378db1f5c6e105b8740adf1a18e5010f0b658541f7`
- Knowledge-base snapshot: `65b3ccfc96a372e54b1c7ecc5ba7f622788d71beafee4206a0298ed10a9fb859`
- Generation model: `deepseek-flash`; provider revision unknown
- Per-call / total timeout: 60 / 180 seconds; network retries 1; model calls 6

## Frozen gate results

| Metric | Result | Gate | Status |
| --- | ---: | ---: | --- |
| Service errors | 0 | 0 | pass |
| Scope/version violations | 0 | 0 | pass |
| Illegal citations | 0 | 0 | pass |
| False accepts | 0/2 | 0/2 | pass |
| False refusals | 1/24 | ≤2/24 | pass |
| Correct final behavior | 26/27 | ≥26/27 | pass |
| Complete supported answers | 21/24 | ≥22/24 | **fail** |
| Candidate required-article coverage | 23/24 | ≥23/24 | pass |
| Final required-article coverage | 21/24 | ≥22/24 | **fail** |
| Generated-answer citation legality | 23/23 | 100% | pass |
| Critical numeric/unit/condition errors | 0 | 0 | pass |
| Unsupported material claims | 0 | 0 | pass |
| Clarification without retrieval/model | 1/1 | 1/1 | pass |

## Failures

- `P1-V2-009`: GB 50157-2013 clause 4.1.18 was not recalled; the answerable noise-limit question was refused.
- `P1-V2-015`: clause 5.5.8 was present, but generation omitted the flexible waterproof layer and drainage requirements for elevated bridge decks.
- `P1-V2-019`: all three structural-life clauses were candidates; final selection lost DB11 clause 3.0.13 and GB 50157 clause 1.0.12, so the answer incorrectly said those documents lacked direct rules.
- `P1-V2-022`: the numeric answer was correct and supported by another DB11 clause, but the pre-reviewed vehicle clause 5.4.7 was not retained. This fails the frozen article-chain metric, not factual answer correctness.

## Cost

- Total latency: 389.673 seconds; mean 14.432 seconds; p95 37.266 seconds; maximum 44.781 seconds.
- Total tokens: 97,757; mean 3,621; p95 7,573; model calls 53.
- Single-spec/control group: 19 questions, mean 10.567 seconds, p95 22.516 seconds, mean 3,246 tokens, p95 5,751 tokens, 39 calls.
- Cross-spec group: 7 questions, mean 26.984 seconds, p95 44.781 seconds, mean 5,154 tokens, p95 8,205 tokens, 14 calls.

## Release consequence

Do not create a Phase 1 completion tag and do not mark the project README as released. The raw result and answer review are archived unchanged. Any fixes based on these failures make this dataset a regression set; a later independent acceptance must use another new, reviewed and frozen dataset with thresholds set before the first candidate run.
