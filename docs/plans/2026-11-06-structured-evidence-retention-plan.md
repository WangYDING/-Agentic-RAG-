# Structured Evidence Retention Implementation Plan

## Task 1: Add structured requirement and article-group primitives

- Add failing unit tests for question-derived requirements, Grader-only hints, explicit articles, uniquely inferred articles, ambiguity, broad matches, and incomplete groups.
- Implement immutable requirement, group, and selection-decision data structures in a focused module.
- Implement deterministic parsing and grouping with explicit failure reasons.
- Run the focused unit tests.

## Task 2: Add bounded deterministic retention

- Add failing tests for multi-chunk article retention, request evidence limits up to eight, no partial group insertion, competing groups, and remaining-slot allocation.
- Implement retention as a pure selector over the current candidate pool and reranked order.
- Ensure `supported_evidence_ids` cannot independently discard existing evidence.
- Run focused workflow tests.

## Task 3: Integrate retry hints and traceability

- Add failing workflow tests proving Grader-only requirements trigger retry but do not reserve slots.
- Integrate question requirements, Grader hints, and selection decisions into the retry workflow.
- Record parse, candidate, selection, fallback, completeness, and scope-verification trace entries.
- Verify final retained groups are complete and within the request scope.

## Task 4: Targeted and regression verification

- Run offline tests and lint.
- Run targeted seen cases for the six evidence-selection failures and P1-IND-016.
- Compare Phase 0 cases individually: candidates, final evidence, decision, and answer.
- Run the Phase 1 30-case seen regression and compare quality, scope violations, p95 latency, token use, and model calls with the preserved independent result.
- Do not classify these runs as a new independent acceptance.

## Deferred defects

- P1-IND-021: Grader false refusal with complete evidence.
- P1-IND-013: candidate recall gap and final evidence omission.

These are diagnosed and fixed separately after the evidence-selection rule is stable.
