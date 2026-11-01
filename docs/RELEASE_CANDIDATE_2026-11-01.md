# 第六阶段候选版本收口记录（2026-11-01）

## 可复现身份

- 集成基线：远端 `phase-1-reproducible-baseline` 的 `e0d0b6dfb6c25ba76eea36bacea99769e8fb850f`；本记录及第六阶段数据治理改动由后续提交叠加，最终提交以 Git 历史为准。
- 依赖锁：`uv.lock` SHA-256 `4093b9a78526c47bf7d4b46457c2c7106cb0338ac31a2fac917a93f28b302a4e`。
- Python / uv：Python 3.12.16；uv 0.13.6。
- PDF：`e5ca2388ad68ed7b21b6092e66c12a73c74c17de8b532bef91c5b2ea57be78f7`。
- 开发候选集：30 题，SHA-256 `200425c134f33e7ed82eebc71c74bb39bcaa11c8b46304498b1817bbb32cd84b`。
- 独立候选集：20 题，SHA-256 `2d8e9ddcf501235b19afbf1a9438474e24841d3355e959936ef9565b8ecd5fd3`；已冻结，未运行。
- 质量门槛：`independent-v2-quality-gate-v1`，SHA-256 `49a63015c101810309b6d0527d95e4d39a36166516098795697a1fcf099a0fdb`。
- Prompt 源文件：Generator `9502e4f3…52b38`；Grader `2f353fdf…725da`；Rewriter `d9c0ff24…5de16`（完整值可由版本内文件重算）。

默认配置为 embedding `BAAI/bge-small-zh-v1.5`（revision 未固定）、reranker `BAAI/bge-reranker-base`（revision 未固定）、generation `deepseek-chat`（外部模型 revision 未固定），retrieval top-k 10、evidence top-n 3、单次调用 30 秒、网络重试 1、总时限 90 秒、模型调用上限 6。2026-10-31 实机部署记录通过环境变量使用 `deepseek-flash`，索引版本为 `cbbc823c77c8acf3bcdddad7e124c20f0e1fe0329241f125cfb391c0d8f950ff`、3701 chunks；该索引不是当前无 Docker 工作区的本地索引，不能混称为本次重新构建。

## 锁定环境检查

2026-11-01 使用 `uv sync --frozen --extra dev`：

- Ruff：通过。
- 离线测试：首次为 106 passed、1 failed；失败原因是新增门槛文件校验后，旧测试夹具未绑定门槛 SHA，属于测试夹具遗漏。修正夹具后重跑为 107 passed、24 deselected。
- integration：23 passed，另有 5 个 subtests，通过。
- 7 个数据 manifest：均通过；独立集状态为 frozen。
- sdist 与 wheel：构建成功。

当前主机没有 `.env`、Docker 命令和 `.rag_index`，因此没有冒充完成真实模型、容器或索引复测；真实开发回归沿用有请求编号、模型、索引和配置记录的 2026-10-31 实机结果。独立集没有运行。

## 已知限制

- 外部生成模型与 reranker revision 不能完全固定。
- 可信公开费率仍缺失，费用不能作为最终发布门槛。
- 正确性修复后的固定 12 题为 12/12，但 p95 延迟升至 26.299 秒；重排分数复用已有离线等价性覆盖，尚待相同实机条件下重新测量固定 12 题。
- 候选题的逐题内容复核由用户授权的 AI 完成，并非领域专家签署；审核身份与限制已保留。
