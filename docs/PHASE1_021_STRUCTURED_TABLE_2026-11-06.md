# Phase 1: P1-IND-021 structured table evidence repair

Date: 2026-11-06

## Diagnosis

The old article text contained the table labels and values but discarded empty cells and OCR coordinates. It therefore could not uniquely prove which speed column owned each value. The official PDF page 14 was visually checked before creating the reviewed structure; the Grader prompt was not relaxed.

## Immutable inputs and outputs

- Official PDF SHA-256: `907ffd92c569f79f163121904cccce69bc20905f9563854960bd184ca76f6fef`
- Original OCR manifest SHA-256: `38a3d3b65ab0397dde7df72d7e72605db1f0d58ae3d118a7faaeb6e2d2f82d45`
- Reviewed table sidecar: `data/ocr_reviews/cn.gb55033@2022.tables.v1.json`
- Derived OCR manifest SHA-256: `886a50dd65601e22caef4405d8c84ef1464aeb5fa7b47f11896d9160e633f8ee`
- Parser version: `rapidocr-page-artifact-v2-reviewed-tables`
- Previous snapshot retained: `39c3e07c109c07cb1dc331db3055cf041a33498aafb9dde6c2eb022421dd3020`
- New active snapshot: `65b3ccfc96a372e54b1c7ecc5ba7f622788d71beafee4206a0298ed10a9fb859`
- New GB 55033 document index: `929adb6747a6f1696f6c00df2f8e501b106e55a0478bf084cfb5a36b72f619b9`

The DB11/T 995-2025 and GB 50157-2013 document version IDs are unchanged. The previous snapshot remains loadable and can be republished with the rollback command.

## Structure and tests

The reviewed table explicitly preserves the five columns and empty cells:

- `密闭性车体 | — | — | <0.35 | <0.29`
- `非密闭性车体 | ≤0.5 | ≤0.4 | ≤0.27 | —`

Tests require rectangular string cells, exact consistency between `cells`, `headers` and `rows`, and verify that the two requested values remain in the 140km/h and 160km/h columns. Shifted/non-rectangular structures are rejected.

## Real targeted regression

Result: `eval/reports/phase1_seen_grader_021_structured_table_20261106.json`.

- Candidate pool: structured table evidence ranked second.
- Final evidence: E2 is table 3.0.4 on PDF page 14 with explicit row/column mapping.
- Grader: sufficient on the first pass; no retry.
- Answer: 140km/h `<0.35`; 160km/h `<0.29`.
- Citation: E2, table 3.0.4.

The prior failed real run remains in `eval/reports/phase1_seen_grader_021_table_mapping_20261106.json`.
