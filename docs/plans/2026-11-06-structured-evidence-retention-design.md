# Structured Evidence Retention Design

## Goal

Prevent already-recalled, necessary evidence from being displaced during retry selection without treating candidate matching as proof that an article is applicable or sufficient.

## Boundary

This change affects candidate evidence selection only. The Grader still decides sufficiency and applicability, and the answer may cite only evidence present in the final context. The Phase 1 independent 30-case result remains the historical acceptance result; subsequent runs are seen regression only.

## Requirement sources

The workflow derives structured requirements from two sources:

- The user question defines authoritative answer requirements.
- Grader missing-requirement text supplies retry hints only.

A Grader hint may reserve evidence only when it can be mapped back to a requirement already present in the user question. A Grader-only requirement may trigger conservative retry retrieval but cannot consume a retained-evidence slot.

Each parsed requirement records the specification ID, edition ID, explicit or inferred article ID, subrequirement, source, parse status, and reason.

## Article groups

Candidates are grouped by `spec_id + edition_id + article_id`. Multiple chunks belonging to one article are assessed together. A group is eligible for deterministic retention only when:

1. specification and edition are explicit;
2. exactly one candidate article group directly covers the question-derived subrequirement;
3. the required article chunks are complete and untruncated;
4. no competing article group offers an equally reasonable interpretation; and
5. the match is supported by direct source text, not broad lexical overlap or reranker rank alone.

An inferred article ID is a selection decision, not a correctness conclusion.

## Selection

Eligible article groups are retained first within the current request's `evidence_limit`. Remaining slots are filled using the existing reranked order. If a complete group cannot fit, the workflow must not retain a partial group; it follows the conservative retry path and records the reason.

`supported_evidence_ids` may be positive supporting context but cannot by itself remove or retain evidence.

After selection, the workflow verifies that every retained article group is complete in the final context and that every chunk remains inside the request's bound specification/version scope.

## Trace

The request trace records:

- parsed question requirements and Grader hints;
- candidate article groups and relevant source excerpts;
- the portion of each subrequirement covered;
- competing groups and why they were excluded;
- retained groups and consumed slots;
- fallback reasons such as ambiguous, broad match, truncated, incomplete, over limit, or out of scope;
- final completeness and scope verification.

## Validation

Tests cover the six selection-loss false refusals and P1-IND-016, plus ambiguous groups, broad matches, truncated groups, missing versions, Grader-only requirements, current evidence limits above three, complete multi-chunk retention, and final scope/version checks. Phase 0 and Phase 1 regression comparisons remain per-case and report evidence, decision, and answer changes rather than aggregate results alone.
