# Phase 1: P1-IND-011 / P1-IND-013 query decomposition repair

Date: 2026-11-06

## Scope

This change repairs candidate-recall loss caused by treating a multi-part question as one undifferentiated retrieval query. It does not change the frozen Phase 1 independent score; the 30 cases are now a seen regression set.

## Rules

- A shared predicate is bound only where the original syntax supports it. For P1-IND-011, `design life` is bound to both named specifications, while the predecessor-only `capacity` requirement is bound only to GB 55033-2022.
- Scene words in P1-IND-013 are retrieval targets inside the already-bound scope. They do not assign a scene to a specification in advance.
- Ambiguous parallel syntax keeps the original query and records `parallel_target_not_uniquely_parsed`.
- Retry selection uses the current request evidence limit, direct predicate matching, explicit specification binding and existing Dense/BM25 ranks. It does not rerank an unbounded expanded pool.

## Tests

The regression tests cover shared predicates, a predecessor-only extra requirement, multiple scenes without a predetermined specification identity, ambiguous fallback, direct predicate matching, uneven evidence needs by document, and the evidence-limit bound.

Focused Ruff and 67 query/retrieval/evidence workflow tests passed before the table-ingestion work began. The combined focused suite later passed 77 tests.

## Real targeted evidence

Fixed input snapshot: `39c3e07c109c07cb1dc331db3055cf041a33498aafb9dde6c2eb022421dd3020`.

- P1-IND-011: `eval/reports/phase1_seen_recall_011_direct_predicate_20261106.json` answered with GB 55033-2022 article 2.1.5 and GB 50157-2013 article 1.0.8. The capacity requirement remained bound to GB 55033-2022.
- P1-IND-013 candidate diagnosis: the decomposed retrieval pool contains DB11/T 995-2025 article 14.2.11, GB 55033-2022 articles 6.4.9/6.4.10, and GB 50157-2013 articles 13.2.4/13.2.17/13.2.33.
- P1-IND-013 latest targeted answer evidence: `eval/reports/phase1_seen_recall_011_013_scoped_decomposition_20261106.json`. It answered without a service error and included the newly recalled 13.2.4, but did not retain every annotated clause in the final answer. Therefore this record proves the candidate-recall repair, not complete answer-quality closure.
- The timeout produced while the expanded pool was reranked remains archived in `eval/reports/phase1_seen_recall_013_preference_20261106.json`.

## Remaining verification

The new knowledge-base snapshot and the complete Phase 0 20-case and Phase 1 30-case seen regressions must audit final evidence and answers case by case. Targeted success does not replace those runs.
