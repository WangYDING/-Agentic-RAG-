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

## 第六阶段数据治理与通用评测

新入口、manifest 字段、冻结规则和人工量表见 `docs/EVALUATION_PROTOCOL.md`。当前新增 30 道开发候选和 20 道独立候选，已于 2026-11-01 完成用户授权的 AI 逐题 PDF 内容复核并标为 `approved`；审核身份和非领域专家限制已写入逐题记录。质量门槛已在看结果前固定，独立集已经冻结但仍未运行，禁止据此宣称独立测试通过。历史数据和报告未重写。

离线数据检查：

```powershell
.\.venv\Scripts\python.exe -m eval.dataset_manifest "eval/datasets/*.manifest.json"

# 重新执行来源核验（只读；加 --write 才会更新候选与核验报告）
.\.venv\Scripts\python.exe -m eval.curate_candidates

# 重现最终 PDF 内容复核（只读；加 --write 才会写回 approved 与复核记录）
.\.venv\Scripts\python.exe -m eval.finalize_candidate_review
```

`run_agent_test` 现在必须传 `--manifest` 和 `--review-out`；旧命令需补齐参数，并选择新的报告路径。该入口调用真实应用，不会在普通 CI 中运行。发布验收仍等待预设验收门槛、独立集冻结和真实模型评测。
