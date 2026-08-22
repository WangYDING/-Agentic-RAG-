# Retrieval Evaluation Report

- Dataset: `eval/datasets/dev_v0_retrieval.jsonl`
- Mode: `rrf`
- Cases: `34`

## Overall

| metric | value |
|---|---:|
| recall@1 | 0.6716 |
| recall@3 | 0.8627 |
| recall@5 | 0.9314 |
| recall@10 | 0.9608 |
| mrr@10 | 0.8336 |
| hitrate@1 | 0.7353 |
| hitrate@3 | 0.9412 |
| hitrate@5 | 0.9706 |
| hitrate@10 | 1.0000 |

## By Question Type

### article_number

| metric | value |
|---|---:|
| recall@1 | 1.0000 |
| recall@3 | 1.0000 |
| recall@5 | 1.0000 |
| recall@10 | 1.0000 |
| mrr@10 | 1.0000 |
| hitrate@1 | 1.0000 |
| hitrate@3 | 1.0000 |
| hitrate@5 | 1.0000 |
| hitrate@10 | 1.0000 |

### confusing_article

| metric | value |
|---|---:|
| recall@1 | 1.0000 |
| recall@3 | 1.0000 |
| recall@5 | 1.0000 |
| recall@10 | 1.0000 |
| mrr@10 | 1.0000 |
| hitrate@1 | 1.0000 |
| hitrate@3 | 1.0000 |
| hitrate@5 | 1.0000 |
| hitrate@10 | 1.0000 |

### false_premise

| metric | value |
|---|---:|
| recall@1 | 0.3333 |
| recall@3 | 0.3333 |
| recall@5 | 0.6667 |
| recall@10 | 0.6667 |
| mrr@10 | 1.0000 |
| hitrate@1 | 1.0000 |
| hitrate@3 | 1.0000 |
| hitrate@5 | 1.0000 |
| hitrate@10 | 1.0000 |

### hard_answerable

| metric | value |
|---|---:|
| recall@1 | 0.6667 |
| recall@3 | 0.6667 |
| recall@5 | 0.6667 |
| recall@10 | 1.0000 |
| mrr@10 | 0.7143 |
| hitrate@1 | 0.6667 |
| hitrate@3 | 0.6667 |
| hitrate@5 | 0.6667 |
| hitrate@10 | 1.0000 |

### multi_evidence

| metric | value |
|---|---:|
| recall@1 | 0.3333 |
| recall@3 | 0.5000 |
| recall@5 | 0.6667 |
| recall@10 | 0.6667 |
| mrr@10 | 0.7778 |
| hitrate@1 | 0.6667 |
| hitrate@3 | 1.0000 |
| hitrate@5 | 1.0000 |
| hitrate@10 | 1.0000 |

### multi_evidence_hard

| metric | value |
|---|---:|
| recall@1 | 0.5000 |
| recall@3 | 0.5000 |
| recall@5 | 1.0000 |
| recall@10 | 1.0000 |
| mrr@10 | 1.0000 |
| hitrate@1 | 1.0000 |
| hitrate@3 | 1.0000 |
| hitrate@5 | 1.0000 |
| hitrate@10 | 1.0000 |

### numeric

| metric | value |
|---|---:|
| recall@1 | 1.0000 |
| recall@3 | 1.0000 |
| recall@5 | 1.0000 |
| recall@10 | 1.0000 |
| mrr@10 | 1.0000 |
| hitrate@1 | 1.0000 |
| hitrate@3 | 1.0000 |
| hitrate@5 | 1.0000 |
| hitrate@10 | 1.0000 |

### numeric_hard

| metric | value |
|---|---:|
| recall@1 | 1.0000 |
| recall@3 | 1.0000 |
| recall@5 | 1.0000 |
| recall@10 | 1.0000 |
| mrr@10 | 1.0000 |
| hitrate@1 | 1.0000 |
| hitrate@3 | 1.0000 |
| hitrate@5 | 1.0000 |
| hitrate@10 | 1.0000 |

### semantic_article

| metric | value |
|---|---:|
| recall@1 | 0.7500 |
| recall@3 | 1.0000 |
| recall@5 | 1.0000 |
| recall@10 | 1.0000 |
| mrr@10 | 0.8750 |
| hitrate@1 | 0.7500 |
| hitrate@3 | 1.0000 |
| hitrate@5 | 1.0000 |
| hitrate@10 | 1.0000 |

### semantic_hard

| metric | value |
|---|---:|
| recall@1 | 1.0000 |
| recall@3 | 1.0000 |
| recall@5 | 1.0000 |
| recall@10 | 1.0000 |
| mrr@10 | 1.0000 |
| hitrate@1 | 1.0000 |
| hitrate@3 | 1.0000 |
| hitrate@5 | 1.0000 |
| hitrate@10 | 1.0000 |

### table_hard

| metric | value |
|---|---:|
| recall@1 | 0.5000 |
| recall@3 | 1.0000 |
| recall@5 | 1.0000 |
| recall@10 | 1.0000 |
| mrr@10 | 0.7500 |
| hitrate@1 | 0.5000 |
| hitrate@3 | 1.0000 |
| hitrate@5 | 1.0000 |
| hitrate@10 | 1.0000 |

### table_lookup

| metric | value |
|---|---:|
| recall@1 | 0.0000 |
| recall@3 | 0.7500 |
| recall@5 | 1.0000 |
| recall@10 | 1.0000 |
| mrr@10 | 0.3833 |
| hitrate@1 | 0.0000 |
| hitrate@3 | 0.7500 |
| hitrate@5 | 1.0000 |
| hitrate@10 | 1.0000 |

### terminology

| metric | value |
|---|---:|
| recall@1 | 0.6667 |
| recall@3 | 1.0000 |
| recall@5 | 1.0000 |
| recall@10 | 1.0000 |
| mrr@10 | 0.7778 |
| hitrate@1 | 0.6667 |
| hitrate@3 | 1.0000 |
| hitrate@5 | 1.0000 |
| hitrate@10 | 1.0000 |

## Per Case

- `SEM-001` (semantic_article): first_hit_rank=1
- `SEM-002` (semantic_article): first_hit_rank=1
- `SEM-003` (semantic_article): first_hit_rank=1
- `SEM-004` (semantic_article): first_hit_rank=2
- `ART-001` (article_number): first_hit_rank=1
- `ART-002` (article_number): first_hit_rank=1
- `NUM-001` (numeric): first_hit_rank=1
- `NUM-002` (numeric): first_hit_rank=1
- `TAB-001` (table_lookup): first_hit_rank=5
- `TAB-002` (table_lookup): first_hit_rank=3
- `TERM-001` (terminology): first_hit_rank=1
- `TERM-002` (terminology): first_hit_rank=3
- `TERM-003` (terminology): first_hit_rank=1
- `NUM-003` (numeric): first_hit_rank=1
- `NUM-004` (numeric): first_hit_rank=1
- `TAB-003` (table_lookup): first_hit_rank=2
- `TAB-004` (table_lookup): first_hit_rank=2
- `MULTI-001` (multi_evidence): first_hit_rank=3
- `MULTI-002` (multi_evidence): first_hit_rank=1
- `MULTI-003` (multi_evidence): first_hit_rank=1
- `SHARD-001` (semantic_hard): first_hit_rank=1
- `SHARD-002` (semantic_hard): first_hit_rank=1
- `SHARD-003` (semantic_hard): first_hit_rank=1
- `CONF-001` (confusing_article): first_hit_rank=1
- `CONF-002` (confusing_article): first_hit_rank=1
- `NHARD-001` (numeric_hard): first_hit_rank=1
- `NHARD-002` (numeric_hard): first_hit_rank=1
- `THARD-001` (table_hard): first_hit_rank=2
- `THARD-002` (table_hard): first_hit_rank=1
- `MHARD-001` (multi_evidence_hard): first_hit_rank=1
- `UA-003` (false_premise): first_hit_rank=1
- `HARD-001` (hard_answerable): first_hit_rank=7
- `HARD-002` (hard_answerable): first_hit_rank=1
- `HARD-003` (hard_answerable): first_hit_rank=1