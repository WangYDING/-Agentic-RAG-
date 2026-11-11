# P1-V2-022 evidence-chain diagnosis

Date: 2026-11-09  
Status: frozen acceptance result preserved; no retrospective rescore

## Failure reproduction

The frozen independent-v2 run answered that both DB11/T 995-2025 and
GB 50157-2013 limit longitudinal jerk to `0.75 m/s³`.  Its final DB11
evidence cited 18.4.7 (commentary) and 5.5.3, while the frozen annotation
expected the direct provision 5.4.7.

## Original-PDF comparison

| Source | What the original page proves | Evidentiary role |
| --- | --- | --- |
| DB11/T 995-2025 5.4.7, PDF page 37 | “列车纵向冲击率不应大于 0.75 m/s³” | Direct normative basis for the requested upper limit |
| DB11/T 995-2025 18.4.7, PDF page 359 | Repeats `0.75 m/s³` as the comfort premise in the explanation of ATO stopping accuracy | Equivalent corroboration for the numeric fact, but not a replacement for the direct vehicle provision |
| DB11/T 995-2025 5.5.3, PDF page 38 | Requires smooth traction/braking transition and compliance with jerk requirements | Qualitative cross-reference only; it does not state the numeric limit |
| GB 50157-2013 4.1.15 | Directly states the corresponding `0.75 m/s³` limit | Direct normative basis |

## Decision

The answer's numeric conclusion was supported by an equivalent corroborating
passage that the original annotation did not list, but its DB11 citation chain
was incomplete because it omitted the direct provision 5.4.7.  The frozen
acceptance judgement remains unchanged.  This repair only changes candidate
evidence selection: when a direct provision and a commentary restatement both
match the same focused target, the direct provision is preferred.  Commentary
remains selectable when it is the only passage that directly answers the
question.
