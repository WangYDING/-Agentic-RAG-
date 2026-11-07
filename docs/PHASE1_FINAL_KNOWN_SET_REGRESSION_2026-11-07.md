# Phase 1 final known-set regression (2026-11-07)

## Frozen candidate

- Runtime-logic commit: `94adda3bb3e926a3180be1ef91e51cd67403049e`
- Knowledge-base snapshot: `65b3ccfc96a372e54b1c7ecc5ba7f622788d71beafee4206a0298ed10a9fb859`
- Generation model: `deepseek-flash`; provider revision unknown
- Embedding: `BAAI/bge-small-zh-v1.5`; revision unknown
- Reranker: `BAAI/bge-reranker-base`; revision unknown
- Per-call / total timeout: 60 / 180 seconds
- Network retries / model-call limit: 1 / 6

The timeout increase is recorded in `docs/PHASE1_FINAL_CANDIDATE_MANIFEST_2026-11-07.md`. No retrieval TopK, evidence limit, model identifier, prompt, snapshot or answer policy was changed to hide a failed full run.

## Phase 0 seen 20

Raw result: `eval/reports/phase1_final_fixed_phase0_seen20_20261107.json`.

- 16/16 answerable questions answered; 4/4 unanswerable questions correctly refused.
- False accepts, false refusals and service errors: 0.
- Final Recall@3: 100%; multi-evidence complete coverage: 3/3.
- Citations valid: 16/16 generated answers.
- Total wall time: 242.843 seconds; mean 12.142 seconds; p95 19.781 seconds; maximum 23.218 seconds.
- Total tokens: 65,815; mean 3,291; model calls: 42.

## Phase 1 seen 30

Raw result: `eval/reports/phase1_final_fixed_seen30_20261107.json`.

- 25/25 answerable questions answered.
- P1-IND-026 and 027 correctly requested scope clarification without retrieval or model calls.
- P1-IND-028 through 030 correctly refused for missing project/measurement facts.
- Candidate and final necessary-article coverage: 25/25.
- Scope/version violations, citation errors and service errors: 0.
- Total wall time: 464.530 seconds; mean 15.484 seconds; p95 50.312 seconds; maximum 50.718 seconds.
- Total tokens: 127,803; mean 4,260; p95 9,676; model calls: 57.
- Previously timed-out P1-IND-013 completed in 50.312 seconds with 2 calls, no retry and 11,372 tokens. P1-IND-014 completed in 36.172 seconds with 2 calls, no retry and 9,423 tokens.

## Answer audit

All generated answers were checked against the frozen question requirements, final evidence, numbers, units and conditions. The repaired cases behaved as follows:

- P1-IND-012 did not treat the OCR-joined `45` text as a reliable table cell and did not assert it as a value.
- P1-IND-017 used the normative DB11/T 995-2025 clause at PDF page 40, not the later commentary occurrence, and reported 600/800/1000mm, 950mm and 50/150/300mm correctly.
- P1-IND-018 used the normative clause at PDF page 59 and preserved the four station levels plus the 70%, 50% and 90% controls.
- P1-IND-020 correctly answered the question actually asked: both 2h lower bounds and their distinct applicable objects, including the directly relevant uninterrupted/no-transient condition. The dataset's `required_requirements` also mentions grounding and lightning although the question asks only for backup-supply time. Those unasked items were not treated as mandatory, consistent with the rule that the question defines required answer points.
- P1-IND-021 preserved the reviewed table row/column mapping and answered `140 km/h → <0.35`, `160 km/h → <0.29`.

Reviewer: Codex (AI), user-authorized project answer reviewer; not a licensed engineering-domain sign-off.

## Decision

Both known sets pass on the same fixed runtime logic, knowledge-base snapshot, model configuration and timeout budget. They remain seen regression evidence and do not establish independent Phase 1 quality. The next action is to author and review a genuinely new cross-spec dataset, freeze its thresholds and hashes before requesting any candidate-system answers, and then run it once.
