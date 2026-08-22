# Evaluation Baseline

This folder contains offline retrieval evaluation utilities.

Dataset format is JSONL. Each line:

```json
{"id":"q001","question":"车站出入口最小间距是多少？","question_type":"table_lookup","answerable":true,"gold_answer":"体育馆为50m。","gold_evidence":[{"document":"城市轨道交通工程设计标准.pdf","page":61,"article":"10.3.5","table":"表10.3.5"}]}
```

Run dense retrieval:

```powershell
.\.venv\Scripts\python.exe -m eval.run_retrieval --dataset eval/datasets/dev.jsonl --pdf data/raw/城市轨道交通工程设计标准.pdf --mode dense --json-out eval/reports/dense.json --md-out eval/reports/dense.md
```

Run dense + current reranker:

```powershell
.\.venv\Scripts\python.exe -m eval.run_retrieval --dataset eval/datasets/dev.jsonl --pdf data/raw/城市轨道交通工程设计标准.pdf --mode dense_rerank --json-out eval/reports/dense_rerank.json --md-out eval/reports/dense_rerank.md
```

Run the BM25 baseline:

```powershell
.\.venv\Scripts\python.exe -m eval.run_retrieval --dataset eval/datasets/dev_v0_retrieval.jsonl --pdf data/raw/城市轨道交通工程设计标准.pdf --mode bm25 --json-out eval/reports/dev_v0_bm25.json --md-out eval/reports/dev_v0_bm25.md
```

Run fixed equal-weight Dense Top10 + BM25 Top10 RRF:

```powershell
.\.venv\Scripts\python.exe -m eval.run_retrieval --dataset eval/datasets/dev_v0_retrieval.jsonl --pdf data/raw/城市轨道交通工程设计标准.pdf --mode rrf --json-out eval/reports/dev_v0_rrf.json --md-out eval/reports/dev_v0_rrf.md
```

Run the full Dense10 + BM25-10 union through the current reranker:

```powershell
.\.venv\Scripts\python.exe -m eval.run_retrieval --dataset eval/datasets/dev_v0_retrieval.jsonl --pdf data/raw/城市轨道交通工程设计标准.pdf --mode hybrid_rerank --json-out eval/reports/dev_v0_hybrid_rerank.json --md-out eval/reports/dev_v0_hybrid_rerank.md
```
