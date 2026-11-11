# Phase 1 final candidate manifest (2026-11-07)

## Frozen identity

- Runtime-logic commit: `39d5fdbae133ccc226f128ffa7cb27934486db6f`
- Candidate source tree and prior evidence commit: `4f8ddad1ab3512459e5bd80fa900dc2c5820ab1b`
- Branch: `codex/phase1-multi-spec-precision`
- Knowledge-base snapshot: `65b3ccfc96a372e54b1c7ecc5ba7f622788d71beafee4206a0298ed10a9fb859`
- Snapshot manifest SHA-256: `aefe786f01fb7b22759381daad2bc6450517a2883a08122475431051af903b56`
- Catalog SHA-256: `5cdfdfab146786b449f28c636d9b3b8104260bc4d4a220d0b626cdf4f7a369b2`
- `uv.lock` SHA-256: `9a754f29cd24fa85de1db0c1398df9b21d9b5c32cd1e6be49678fd8e83f677e2`
- Python: 3.12.16; uv: 0.13.6

The candidate tree contains evidence-only commits after the runtime-logic commit. Those commits do not change the application runtime. The final evidence-archive commit created after this manifest must be reported separately from the runtime-logic commit.

## Models and retrieval

- Embedding: `BAAI/bge-small-zh-v1.5`; revision unknown.
- Reranker: `BAAI/bge-reranker-base`; revision unknown.
- Generation: `deepseek-flash`; provider-side revision unknown.
- Retrieval TopK: 10 per configured route.
- Normal final evidence limit: 3; bounded cross-spec multi-requirement requests may use the existing limit of up to 8.
- Model-call limit: 6; network retry limit: 1.

Secrets are injected at runtime and are not recorded.

## Timeout diagnosis and frozen budget

The previous 30-question run used a 30-second per-call timeout and a 90-second total timeout. P1-IND-013 and P1-IND-014 each used only three model calls including one retry, below the six-call limit. Their failed generation stages lasted about 60.5 and 61.1 seconds because a 30-second call timed out and was retried. Earlier runs completed the same questions within the call-count budget, demonstrating provider latency variation.

A controlled probe changed only the runtime budgets to:

- per model/API call: **60 seconds**;
- total request: **180 seconds**;
- network retries: **1**;
- model calls: **6**.

Under that budget, P1-IND-013 answered in 49.875 seconds using 2 calls and 8,441 tokens; P1-IND-014 answered in 39.172 seconds using 2 calls and 7,536 tokens, with no retry. Raw evidence: `eval/reports/phase1_timeout_probe_013_014_budget60_180_20261107.json`.

This is a runtime-budget change, not a retrieval, prompt, Grader, or answer-policy change. It increases the permitted worst-case wait by 90 seconds per request and may allow a slow call to consume more output tokens. Actual latency, calls and tokens must be reported for both full regressions and the independent acceptance run.

## Frozen known-set inputs

- Phase 0 seen 20 SHA-256: `2d8e9ddcf501235b19afbf1a9438474e24841d3355e959936ef9565b8ecd5fd3`
- Phase 1 seen 30 SHA-256: `f870154d3cc4e6dabd700e4c2b031f81ffb6604073ea1926f926e231255391de`

All subsequent Phase 0 and Phase 1 full known-set runs must use the identity and budgets above. Errors and timeouts remain in-place. No per-question retry may replace a complete-run result.
