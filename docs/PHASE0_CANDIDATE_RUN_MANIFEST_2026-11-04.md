# 阶段 0 候选版本运行清单

> 准备日期：2026-11-04（Asia/Shanghai）  
> 目的：把远端已核实代码固定为可独立执行第 3 步发布前检查的候选版本。本次未运行冻结的 20 题，也未把历史 12/12 当作本候选的新验证结果。

## 版本身份

| 项目 | 固定值 |
|---|---|
| 候选目录 | `E:\Agentic-RAG-phase0-candidate` |
| 被测代码提交 | `7e5d82caf7aa9c76e83a9a3d03eae484eebdbb3a` |
| checkout 方式 | Git detached worktree，来源为本地核实后的提交对象 |
| 被测代码状态 | 建立后及准备完成后均由 `git status --short --branch` 确认为干净；模型、虚拟环境与索引为忽略的运行产物 |
| 证据归档提交 | 由 Git 历史和交付记录给出完整 SHA（提交无法在自身内容中稳定自引用）；该提交只增加本清单，不改变被测代码、依赖、数据、模型配置或索引逻辑 |
| 原工作区 | `E:\-Agentic-RAG--main`，保留且未清理其既有未提交修改 |

后续执行结果必须同时记录“被测代码提交”和“证据归档提交”。若候选代码发生任何修复，`7e5d82c` 立即失去候选身份，修复必须形成独立提交并重新生成本清单。

## 锁定环境

| 项目 | 固定值 / 结果 |
|---|---|
| 操作系统 | Microsoft Windows 10 IoT Enterprise LTSC，10.0.19044，x64 |
| CPU / 内存 | AMD Ryzen 9 7900X，12 核 / 24 逻辑处理器；31,814 MB 物理内存 |
| Python | CPython 3.12.16，候选虚拟环境 `E:\Agentic-RAG-phase0-candidate\.venv` |
| uv | 0.13.6 (`329bf9448`, x86_64-pc-windows-msvc) |
| 安装命令 | `uv sync --locked --extra dev --python 3.12.16` |
| 安装结果 | 成功；从既有 `uv.lock` 解析 109 packages，安装 89 packages；没有更新 lock |
| `uv.lock` 原始字节 SHA-256 | `312bdb4f4791a341caf270029a5bea549de327a32e9a90f609dbc4eb806816d5` |
| `uv.lock` 跨平台文本 SHA-256 | `4093b9a78526c47bf7d4b46457c2c7106cb0338ac31a2fac917a93f28b302a4e` |

可编辑安装会重写仓库中已跟踪的 `engineering_spec_rag.egg-info` 文件。准备过程中只把这些安装生成改动恢复到 `7e5d82c`，没有修改源码或依赖；虚拟环境保持可用。

## 数据与质量门槛

| 项目 | 固定值 / 校验结果 |
|---|---|
| PDF | `data/raw/城市轨道交通工程设计标准.pdf`；7,869,546 bytes |
| PDF SHA-256 | `e5ca2388ad68ed7b21b6092e66c12a73c74c17de8b532bef91c5b2ea57be78f7`；与数据集记录一致 |
| 独立集 | `independent_v2_draft`，版本 `0.3-pdf-content-reviewed`，20 题，状态 `frozen` |
| 独立集原始字节 SHA-256 | `2d8e9ddcf501235b19afbf1a9438474e24841d3355e959936ef9565b8ecd5fd3` |
| 独立集跨平台文本 SHA-256 | `2791c00f07eeddd9764198bc20ad8f7ee1c6ad5965a0fbc273cad5c26f624531`；与 manifest 一致 |
| 独立集 manifest 原始/文本 SHA-256 | `300b35587bc608e197c93219d300b3c14bedca2ab819f2028d0bdfa3a1154420` / `16bf3b50a2b66158ce72e6ef90b780d2780a29e9230863b914a188b680ae60ce` |
| 质量门槛 | `independent-v2-quality-gate-v1` |
| 门槛原始字节/文本 SHA-256 | `63ed78f956c64bbd6884100f73afb06e64cc4853b87a8e26519c83054c2b3899` / `49a63015c101810309b6d0527d95e4d39a36166516098795697a1fcf099a0fdb`；文本哈希与 manifest 一致 |
| 数据清单校验 | `uv run --locked python -m eval.dataset_manifest "eval/datasets/*.manifest.json"` 成功；7 份 manifest 全部通过 |
| 独立运行状态 | 本次未运行冻结 20 题，未生成或读取其系统答案 |

文本哈希使用候选版本 `eval.dataset_manifest.file_sha256()` 的 LF 归一化口径；原始字节哈希用于文件级审计，两者不得混用。

## 模型与检索条件

| 项目 | 固定值 / 限制 |
|---|---|
| Embedding | 配置标识 `BAAI/bge-small-zh-v1.5`；配置 revision 为 `null`（未固定） |
| Embedding 本次缓存解析 | Hugging Face `main` 当时解析为 `7999e1d3359715c523056ef9478215996d62a620`；应用 manifest 没有强制该值，未来重新下载仍可能漂移 |
| Reranker | 配置标识 `BAAI/bge-reranker-base`；配置 revision 不受独立字段约束（未固定） |
| Reranker 本次缓存解析 | Hugging Face `main` 当时解析为 `2cfc18c9415c912f9d8155881c133215df768a70`；应用准备标记只固定模型名，未来重新下载仍可能漂移 |
| 生成模型 | 实际真实预检使用 `deepseek-flash`；外部服务底层 revision 未知且无法由本仓库固定。`deepseek-chat` 仅为代码默认值，不是本轮实测模型 |
| Dense TopK / BM25 TopK | 两路均使用 `retrieval_top_k=10`；Hybrid 去重与 RRF 合并 |
| RRF | `rrf_k=60`（评测运行指纹中的固定检索常量） |
| 最终证据数 | `evidence_top_n=3` |
| 切分 | `chunk_size=300`，`overlap=50`，parser `pymupdf-structured-v1` |
| 模型准备 | `uv run --locked engineering-rag-model prepare` 成功；随后 `check` 返回 `status: ready` |

模型准备通过匿名 Hugging Face 请求完成；未使用或记录访问令牌。revision 未被配置和运行时 manifest 强制固定，是本候选的明确可复现性限制。

## 预算与重试

| 项目 | 固定值 |
|---|---:|
| 单次模型调用超时 | 30 秒 |
| 请求总时限 | 90 秒 |
| 模型调用上限 | 6 |
| 网络重试上限 | 1 |
| 补充检索重试上限 | 1（`AgentWorkflow` 强制） |
| 索引构建锁等待 | 30 秒 |
| 索引自动构建默认值 | `true`；第 3 步目标部署验证应显式使用已发布索引并按部署配置设为 `false` |

## 候选专属索引

旧索引没有复制。使用候选目录中的 PDF 绝对路径身份和候选代码重新构建，再用同一命令参数独立校验。

| 项目 | 固定值 / 结果 |
|---|---|
| 索引目录 | `E:\Agentic-RAG-phase0-candidate\.rag_index` |
| document ID | `e32b2a73134e8548ffbd374f14a52b27aaee9c2d7d2e482b802e756fb0c5fca2`（不同于旧 checkout 的路径身份） |
| version ID | `cbbc823c77c8acf3bcdddad7e124c20f0e1fe0329241f125cfb391c0d8f950ff` |
| chunks / embedding dim | 3701 / 512 |
| manifest schema | 3 |
| `manifest.json` SHA-256 | `197a9f5631bbe5139d9e7851f1519b921f56cddc5a3bab1ee05cc005bababf50` |
| `index.faiss` SHA-256 | `88364a67b43cee31880425c4baa545bf81c44be192e4c16204f12bdea2227d45` |
| `metadata.json` SHA-256 | `e88359483537b0d92b0870d7ae703eda66e6c8c11fad193e245343b0b0ab0081` |
| `active.json` SHA-256 | `c1c6925d4a8d1923975cff62d79e4f0357db7e49c8ee4b1bf3978513f4a0d1d6` |
| 构建结果 | `status: rebuild` |
| 校验结果 | `status: valid`，document ID、version ID、3701 chunks 均匹配 |

索引 version ID 与旧环境相同，是因为 PDF 内容、切分、embedding 标识/revision 和 parser 版本相同；document ID 因候选绝对路径改变而不同。这个结果不等于复制或复用旧索引。

## API 配置状态与秘密处理

- 初始准备时 API 未配置；真实预检执行时 `DEEPSEEK_API_KEY` 与 `DEEPSEEK_BASE_URL` 均已通过候选目录中被 Git 忽略的运行时配置提供，实际服务地址为 `https://api.deepseek.com`，实际模型标识为 `deepseek-flash`。
- 候选清单不包含密钥、令牌、代理地址或其他认证信息。
- 记录只保留“已配置”、公开服务地址和模型标识，不记录密钥值。
- 真实开发题验证结果另见 `docs/PHASE0_REAL_PRECHECK_2026-11-04.md`。

## 实际执行的准备命令

```powershell
git worktree add --detach E:\Agentic-RAG-phase0-candidate 7e5d82caf7aa9c76e83a9a3d03eae484eebdbb3a
uv sync --locked --extra dev --python 3.12.16
uv run --locked python -m eval.dataset_manifest "eval/datasets/*.manifest.json"
uv run --locked engineering-rag-model prepare
uv run --locked engineering-rag-model check
uv run --locked engineering-rag-index build --pdf "data/raw/城市轨道交通工程设计标准.pdf" --index-dir ".rag_index" --chunk-size 300 --overlap 50
uv run --locked engineering-rag-index check --pdf "data/raw/城市轨道交通工程设计标准.pdf" --index-dir ".rag_index" --chunk-size 300 --overlap 50
```

另执行只读的 Git 状态、文件哈希、平台信息和配置打印命令；配置输出只包含非秘密值及 API 配置布尔状态。

## 第 2 步完成判定

| 条件 | 状态 | 说明 |
|---|---|---|
| 候选代码来源明确、工作区干净 | 通过 | 被测代码为 `7e5d82c`；清单归档提交与被测代码分开记录 |
| 锁定环境安装成功 | 通过 | Python 3.12.16 + uv 0.13.6，`--locked` 安装成功 |
| PDF、冻结数据和质量门槛校验通过 | 通过 | 哈希与 manifest 一致；7 份数据清单通过 |
| 模型与匹配索引准备好 | 通过（有限制） | 本地模型 marker ready，候选路径索引 valid；模型 revision 未由运行配置强制固定 |
| 运行配置完整、无秘密进入记录 | 通过（有限制） | API 地址和密钥已在运行时提供；记录不含密钥。生成服务底层 revision 未知 |

结论更新（2026-11-04）：候选随后完成第 3 步离线、集成、安装入口和真实开发题预检，并执行一次冻结 20 题独立验收。执行无服务错误，但质量门槛未通过；详见 `docs/PHASE0_BASELINE_CONCLUSION_2026-11-04.md`。
