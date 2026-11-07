# Phase 1 independent v2 freeze record

This record was completed before requesting any candidate-system answer for the new dataset.

- Dataset: 27 new questions, SHA-256 `6532a7f0a67aaa793ee165378db1f5c6e105b8740adf1a18e5010f0b658541f7`.
- Distribution: 24 answerable (18 single-spec, 6 cross-spec), 1 scope clarification and 2 evidence-insufficient controls.
- Runtime logic: `94adda3bb3e926a3180be1ef91e51cd67403049e`.
- Snapshot: `65b3ccfc96a372e54b1c7ecc5ba7f622788d71beafee4206a0298ed10a9fb859`.
- Runtime budget: 60 seconds per call, 180 seconds total, 1 network retry, 6 model calls.
- Source review: 27/27 approved by Codex AI under user authorization; this is not a licensed domain-expert sign-off.
- The questions, gold answer points, references, page numbers, numbers, units and conditions were reviewed before the first run. Candidate-system answers were not run or viewed during authoring, source review or threshold setting.
- The quality gate is stored in `eval/datasets/phase1_cross_spec_independent_v2.quality_gate.json`. Service errors remain errors and make the run unable to determine. After the first run, this dataset becomes seen regression data regardless of the result.

This freeze does not declare Phase 1 complete. Completion requires a single raw run, per-question answer audit and a gate decision using the identities above.
