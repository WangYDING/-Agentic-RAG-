# Phase 1 跨规范独立验收候选运行清单

冻结日期：2026-11-06（Asia/Shanghai）
状态：已冻结、尚未运行
被测代码：`72958eecbc1aa381e2cc5a2464200c4c865271bb`
候选标签：`phase1-independent-candidate-2026-11-06`（标签对象 `ca0d518…`）
数据归档提交：`eec93d20a1962526cbcfa15abe49e17803c9240c`

## 环境和输入

- Python `3.12.16`；uv `0.13.6`；Windows 10 IoT 企业版 LTSC `10.0.19044`。
- `uv.lock` SHA-256：`9a754f29cd24fa85de1db0c1398df9b21d9b5c32cd1e6be49678fd8e83f677e2`。
- 文档目录 SHA-256：`c8ea08f5ad497a0d8d87fe61e2b3daa9ea41ba73ddb8301e4a1ecb475b532d6c`。
- PDF SHA-256：DB11/T 995-2025 `e5ca2388…78f7`；GB 55033-2022 `907ffd92…6fef`；GB 50157-2013 `a1130f89…dab3`。
- OCR manifest SHA-256：GB 55033-2022 `38a3d3b6…2d45`；GB 50157-2013 `58dc0f29…29f`。
- 知识库快照：`39c3e07c109c07cb1dc331db3055cf041a33498aafb9dde6c2eb022421dd3020`；manifest SHA-256 `4c4a15f60428f4714505f0ae7e08c80a5fbe77b79c67b258ed279c98496bd7a6`。
- 三个文档索引版本：DB11 `02c44af1…e1d4`；GB 50157 `3d708f4c…b5b2`；GB 55033 `e13c5f84…b927`。

## 模型、Prompt 和预算

- embedding：`BAAI/bge-small-zh-v1.5`，revision 未固定；reranker：`BAAI/bge-reranker-base`，revision 未固定。
- 生成/Grader/改写模型：`deepseek-flash`；服务端底层 revision 无法固定，记录为未知。
- Prompt 所在文件 SHA-256：generator `4b64f595…fba0`；grader `17a22817…e1c3`；rewriter `9729fb0a…fea1`；工作流 `2d4d4520…a0cb`。
- 每文档每路 TopK `10`；普通最终证据 `3`；跨规范多目标最多 `8`。
- 单次模型调用超时 `30s`；请求总预算 `90s`；模型调用上限 `6`；网络重试 `1`；检索补充重试最多 `1`。
- 密钥和 API 地址只在运行时注入，不进入清单、结果或日志。

## 冻结数据和门槛

- 数据集：`eval/datasets/phase1_cross_spec_independent_v1.jsonl`，30 题，SHA-256 `f870154d…91de`。
- 来源审核：30/30 已对照原 PDF；审核者为 Codex（AI），不是持证领域专家；冻结前未运行或查看候选答案。
- 门槛：`eval/acceptance/phase1_cross_spec_quality_gate_v1.json`，SHA-256 `3403494c…acce`。
- 评测入口：`eval/run_phase1_independent_v1.py`，SHA-256 `1db0a53b…391a`；只增加记录，不修改候选运行逻辑。

## 运行约束

必须一次按原顺序运行全部 30 题，输出到全新文件，禁止覆盖。保存范围、快照、候选池、最终证据、请求编号、回答/拒答、引用、阶段耗时和 token。两道澄清题必须没有检索和模型调用。服务错误保留原样，不删题、不当作业务拒答。
