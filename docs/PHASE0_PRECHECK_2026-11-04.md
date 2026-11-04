# PHASE0_PRECHECK：候选发布前检查

> 执行日期：2026-11-04（Asia/Shanghai）  
> 候选目录：`E:\Agentic-RAG-phase0-candidate`  
> 被测代码：`7e5d82caf7aa9c76e83a9a3d03eae484eebdbb3a`  
> 准备清单归档提交：`90c799436a2de12ebd7709006a86424297286e93`  
> 范围：第 3 步中不需要真实 API 的前五项检查。冻结的 `independent_v2_draft` 20 题未运行、未读取系统答案。

## 总结

| 顺序 | 检查 | 状态 | 实际结果 |
|---|---|---|---|
| 1 | 候选身份 | 已通过 | 归档提交的父提交是 `7e5d82c`；两者只差文档，运行逻辑、依赖锁和入口无差异 |
| 2 | Ruff、离线测试 | 已通过 | Ruff 通过；110 passed、24 deselected、3 warnings |
| 3 | PDF/FAISS 集成测试 | 已通过 | 23 passed、111 deselected；0 skipped；真实 PDF 存在并参与测试 |
| 4 | 数据清单校验 | 已通过 | 7 份 manifest 通过；独立集为 frozen 20 题；质量门槛绑定有效 |
| 5 | 构建与安装入口 | 已通过（含一次环境失败后原条件重试） | sdist/wheel 构建成功；仓库外安装成功；5 个正式命令帮助均退出 0；无 API 问答入口安全失败 |
| 6 | 真实开发题与部署行为 | 因条件缺失未执行 | API 地址/密钥未配置；当前主机没有 Docker 命令。未验证真实问答、请求追踪、容器镜像或重启复用 |

结论：候选运行逻辑未变，前五项最终通过。可以在补齐目标运行环境和运行时 API 配置后继续第 6 项；在第 6 项通过前，不能进入冻结 20 题验收。

## 1. 候选身份

执行并核对：

```powershell
git status --short
git rev-parse HEAD
git rev-parse HEAD^
git diff --name-status 7e5d82caf7aa9c76e83a9a3d03eae484eebdbb3a..HEAD
git diff --exit-code 7e5d82caf7aa9c76e83a9a3d03eae484eebdbb3a HEAD -- src app.py agent_demo.py pyproject.toml uv.lock
```

结果：

- 检查开始时归档 HEAD 为 `90c799436a2de12ebd7709006a86424297286e93`，其父提交为被测代码 `7e5d82caf7aa9c76e83a9a3d03eae484eebdbb3a`。
- 两者唯一差异为新增 `docs/PHASE0_CANDIDATE_RUN_MANIFEST_2026-11-04.md`。
- `src`、`app.py`、`agent_demo.py`、`pyproject.toml`、`uv.lock` 无差异。
- 各检查完成后再次核对，运行逻辑仍无差异。构建命令生成的 `egg-info` 工作树变化已恢复到归档提交；没有形成源码修复。

判定：**已通过**。

## 2. Ruff 与离线测试

### Ruff

命令：

```powershell
uv run --locked ruff check .
```

结果：`All checks passed!`

### 离线测试

命令：

```powershell
uv run --locked python -m pytest -m "not integration and not model" -o addopts=""
```

结果：

- 收集 134 项；选择 110 项，24 项 deselected。
- `110 passed, 24 deselected, 3 warnings in 5.98s`。
- 3 条 warning 均来自已锁定的 `jieba` 包在 Python 3.12 下报告正则字符串非法转义的 `SyntaxWarning`；没有测试失败。
- 测试未调用真实模型 API。

判定：**已通过**。本次数量与既有工程日志的 110 passed 一致；以本次实际输出为准。

## 3. PDF/FAISS 集成测试

命令：

```powershell
uv run --locked python -m pytest -m integration -o addopts=""
```

结果：

- 收集 134 项；选择 23 项，111 项 deselected。
- `23 passed, 111 deselected in 26.04s`。
- `tests/test_index_manager.py` 与 `tests/test_real_pdf_article_provenance.py` 全部通过。
- 0 skipped。候选目录中的真实 PDF 存在，因此没有“必要资源缺失”跳过项。
- 未调用真实模型 API。

判定：**已通过**。

## 4. 数据清单、冻结集与质量门槛

命令：

```powershell
uv run --locked python -m eval.dataset_manifest "eval/datasets/*.manifest.json"
```

结果：

| 数据集 | 版本 | 数量 | 状态 |
|---|---|---:|---|
| `dev_v0` | `legacy-1` | 40 | historical |
| `dev_v0_retrieval` | `legacy-1` | 34 | historical |
| `independent_v2_draft` | `0.3-pdf-content-reviewed` | 20 | frozen |
| `refusal_dev_v0` | `legacy-1` | 15 | historical |
| `regression_v1_draft` | `0.3-pdf-content-reviewed` | 30 | draft |
| `sufficiency_dev_v0` | `legacy-1` | 19 | historical |
| `test_v1` | `legacy-1` | 20 | historical |

校验同时确认独立集 SHA、PDF SHA 与 `independent-v2-quality-gate-v1` 的门槛 SHA 绑定有效。`eval/reports/` 中没有 `independent_v2` 结果文件。本次没有运行冻结集。

判定：**已通过**。

## 5. 构建、外部安装与正式入口

### 构建产物

命令：

```powershell
uv build
```

结果：

| 产物 | 大小 | SHA-256 |
|---|---:|---|
| `dist/engineering_spec_rag-0.1.0.tar.gz` | 85,697 bytes | `f34b1c08c8d088f70df8d97e35c5d9a58970423ebf2489c621dc2905cbd0a409` |
| `dist/engineering_spec_rag-0.1.0-py3-none-any.whl` | 61,158 bytes | `f9b806ba4f8effee056c93ceebf4f5eb587bd308e90a46f03ba8ce6c42363fc2` |

sdist 和 wheel 均构建成功。

### 仓库外安装

验证目录：`E:\Agentic-RAG-phase0-wheel-verify-20261104`，Python 3.12.16。

第一次安装**实际失败**：uv 默认使用 C 盘缓存，解压 `pyarrow==26.0.1` 时返回 `os error 112`（磁盘空间不足）。当时 C 盘/临时目录只剩约 84,074,496 bytes；E 盘约有 115.6 GB 可用。该失败发生在依赖缓存解压阶段，不是 wheel 导入或候选代码失败。

没有更新依赖、修改 wheel 或修改候选代码。只设置：

```powershell
$env:UV_CACHE_DIR='E:\Agentic-RAG-phase0-uv-cache'
```

随后对**同一个 wheel**、同一个外部虚拟环境重试，安装成功：`Installed 82 packages`。外部 wheel 安装按 wheel 元数据重新解析依赖，而不是复用仓库 `.venv`；候选本身的开发/测试环境仍严格来自 `uv.lock`。

### 正式入口

离开源码目录，在外部验证目录执行：

- `engineering-rag --help` → exit 0
- `engineering-rag-web --help` → exit 0（显示 Streamlit run 帮助）
- `engineering-rag-index --help` → exit 0
- `engineering-rag-model --help` → exit 0
- `engineering-rag-health --help` → exit 0

无 API 配置时执行安装后的问答入口：

```powershell
engineering-rag --pdf "E:\Agentic-RAG-phase0-candidate\data\raw\城市轨道交通工程设计标准.pdf" `
  --index-dir "E:\Agentic-RAG-phase0-candidate\.rag_index" `
  --question "测试无 API 配置错误"
```

结果：exit 2，并只返回：

```text
配置错误：缺少配置：DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL。请通过显式参数、环境变量或 .env 提供。
```

没有输出堆栈、密钥、代理地址或候选答案。

判定：**最终通过**。保留首次缓存盘空间失败作为环境故障记录；它不从报告中删除。

## 6. 真实开发题与部署行为

状态：**因 API 或部署条件缺失而未执行**。

当前条件：

- `DEEPSEEK_API_KEY`：未配置。
- `DEEPSEEK_BASE_URL`：未配置。
- Docker 命令：当前主机不可用。
- 候选索引：已存在并通过 `engineering-rag-index check`；version ID 为 `cbbc823c77c8acf3bcdddad7e124c20f0e1fe0329241f125cfb391c0d8f950ff`。

因此以下项目尚无本候选的新证据：

- 普通可回答开发题的答案和引用定位。
- 不可回答开发题的明确拒答。
- 已知多证据题是否实际触发补检、补齐证据并完整回答。
- 镜像身份、容器内源码提交绑定。
- 请求编号、阶段耗时、token 和真实结果。
- 服务重启后复用同一候选索引且不重建。

这些项目不能沿用历史 12/12 代替。只有在准备交付的运行方式中补齐 API 和部署条件、全部验证通过后，才能进入冻结 20 题验收。

## 失败与限制清单

### 实际失败及原因

1. 外部 wheel 第一次安装失败：C 盘 uv 缓存解压 `pyarrow` 时磁盘空间不足。未删除失败记录；改用 E 盘缓存后原 wheel 安装成功。

### 非阻断警告

1. 离线测试出现 3 条 `jieba` 正则转义 `SyntaxWarning`，测试仍全部通过。
2. 外部 wheel 安装依据包元数据解析当时可用依赖；它用于安装入口验证，不替代 `uv.lock` 锁定环境。

### 条件缺失未执行

1. 真实开发题：缺运行时 API 地址与密钥。
2. 容器构建、镜像身份和重启行为：当前主机没有 Docker 命令。
3. 冻结独立 20 题：按验收顺序主动保留，未运行。

## 下一步门槛

先在目标交付环境完成第 6 项，并把被测代码 `7e5d82c`、证据归档提交、镜像摘要、索引 version、请求编号、耗时、token、答案与证据一起归档。若真实验证失败或修改运行逻辑，必须更新候选身份并补跑受影响的第 1–5 项；不得直接进入冻结 20 题。
