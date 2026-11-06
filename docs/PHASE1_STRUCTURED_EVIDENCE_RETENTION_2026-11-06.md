# Phase 1 structured evidence retention regression

Date: 2026-11-06. This is a seen regression, not an independent acceptance. The preserved Phase 1 independent result remains 23/30 correct final behavior and 16/25 complete answers.

## Fixed input

- Knowledge-base snapshot: `39c3e07c109c07cb1dc331db3055cf041a33498aafb9dde6c2eb022421dd3020`
- Generation model identifier: `deepseek-flash`
- Dataset: `phase1_cross_spec_independent_v1` (already seen)
- No OCR or index rebuild was performed.

## Change

- Question-derived requirements are authoritative; Grader-only requirements are retry hints and cannot reserve evidence slots.
- Candidates are grouped by specification, edition and article. A uniquely and directly matching complete article group is retained as a selection rule only.
- Multi-chunk articles are retained together. Retention uses the request's evidence limit, including limits above three for cross-specification per-scope questions.
- `supported_evidence_ids` no longer independently controls which existing evidence is discarded.
- Grader commentary is removed from retry queries while its useful retrieval terms are preserved.
- The final context is checked for complete retained groups and scope/version boundaries before the second Grader call.
- Trace output records parsed sources, retained groups, fallback reasons and final-context verification.

## Verification

- Offline tests: 186 passed, 31 deselected.
- Ruff: passed.
- Focused structured-retention/workflow tests: 41 passed.
- Scope/version violations in the targeted real runs: 0.

| Case | Latest behavior | Required final evidence | Result |
| --- | --- | --- | --- |
| P1-IND-011 | Refused | GB 55033 2.1.5 present; GB 50157 1.0.8 absent | Not fixed in this real run: retry candidate recall missed 1.0.8. Replay of the preserved independent candidate pool confirms the selector retains 2.1.5 and 1.0.8 when both are present. |
| P1-IND-012 | Answered | DB11 8.2.2; GB 50157 7.2.2; GB 55033 2.1.2 | Final evidence complete. |
| P1-IND-016 | Answered | GB 50157 9.2.6; GB 55033 2.1.16; cautious DB11 absence | Final evidence complete; the unrelated DB11 evidence is not treated as proof of absence. |
| P1-IND-017 | Answered | DB11 6.2.2; GB 55033 3.0.10 | Final evidence complete. |
| P1-IND-018 | Answered | DB11 10.2.1 (three chunks); GB 55033 2.1.30 | Complete multi-chunk article group retained within request limit 4. |
| P1-IND-020 | Answered | DB11 17.5.6; GB 55033 6.2.3 | Final evidence complete. |
| P1-IND-025 | Answered | Three distinct specifications' 6.2.3 articles | All three identities remain separate; four required chunks fit within request limit 6. |

The latest successful targeted runs used 12.75–50.81 seconds and 3,050–10,601 tokens per request. These figures are observations from a small seen subset, not a new performance acceptance result.

## Evidence files

- Initial seven-case runs: `eval/reports/structured_retention_p1-ind-*_20261106.json`
- Diagnostic traces: `eval/reports/structured_retention_failures_trace_20261106.json`
- Corrected evidence-limit runs for P1-IND-018 and P1-IND-025: `eval/reports/structured_retention_limit_retry_20261106.json`
- Sanitized retry run for P1-IND-011: `eval/reports/structured_retention_p1-ind-011_sanitized_20261106.json`

## Remaining boundary

P1-IND-011 is now a candidate-recall failure in the latest real run, not a final-selection loss: `GB 50157-2013` article 1.0.8 did not enter the retry candidate pool. The selector correctly follows the conservative path rather than inferring an article from broad wording. This must be handled as retrieval behavior, without weakening the uniqueness rule.

P1-IND-021 (Grader false refusal with complete evidence) and P1-IND-013 (candidate recall gap) remain explicitly deferred. No result here replaces the need for a newly frozen independent set after all fixes stabilize.
