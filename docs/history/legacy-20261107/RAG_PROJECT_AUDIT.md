# RAG 项目工程化与架构审计

> 更新日期：2026-10-30（Asia/Shanghai）  
> 审计对象：当前工作目录中的代码、配置、测试及评测报告。  
> 原则：以实际入口和调用链为准；区分静态实现、历史实验结果与本次动态验证。  
> 本文替代 2026-08-16 版本的当前状态判断。旧版结论的适用范围及修订原因见文末。

## 1. 当前结论

当前项目属于 **具有测试与评测基础的可追溯 Hybrid Agentic RAG 工程原型**。它已具备结构化摄取、持久索引、混合检索、证据充分性判定、有限重试、拒答及引用校验，不能继续归类为仅有内存 Dense 检索的 Basic RAG。

作为技术展示项目，现有实现能够说明问题定义、架构取舍与失败分析；作为需要稳定交付和多人使用的服务，仍缺少环境复现、故障处理、索引并发保护、运行观测和部署验证。

| 维度 | 已实现 | 主要边界 |
|---|---|---|
| 模块与入口 | 解析、检索、重排、生成与工作流拆分；Web 和 Agent CLI 复用编排 | 应用组件依赖 eval 目录；基础 CLI 与 Agent 入口功能不同 |
| 摄取与来源 | page/article/table-aware 解析与结构化 metadata | 不代表支持扫描件 OCR、任意复杂版面或多规范版本管理 |
| 持久化 | FAISS、metadata、manifest、源 PDF SHA-256、schema v2 | 无原子切换与构建锁；未校验索引产物哈希 |
| 检索 | Dense + BM25 候选合并去重，CrossEncoder 重排 | 多证据完整召回仍是瓶颈 |
| 受控 Agent | 充分性判定、缺失信息驱动重试、最多一次重试、拒答、trace | 不是自由规划、多 Agent 或任意工具调用系统 |
| 引用 | Evidence ID、来源及 provenance 校验 | 不验证事实蕴含；校验失败不阻断答案返回 |
| 测试与评测 | tests、分层数据集、评测脚本、逐题报告 | 本次环境未能通过全量测试；没有已验证的自动回归流水线 |
| 交付与运维 | pyproject.toml、配置示例、启动说明、Streamlit UI | 当前目录未发现 CI、容器部署、服务 API 或完整运行监控配置 |

## 2. 实际入口与调用链

### 2.1 Web 与完整 Agent CLI

`app.py` → `agent_demo.build_agent_workflow()` → `AgentWorkflow.run()`。

初始化：PDF → `IndexManager.build_or_load()` → 结构化 chunks 与 FAISS → Dense/BM25 retrievers → CrossEncoder、Grader、Generator、QueryRewriter。

问答：Dense Top10 + BM25 Top10 候选合并去重 → CrossEncoder Top3 → Evidence Sufficiency Grader。

- 首轮 sufficient：生成答案，记录引用校验结果并返回。
- 首轮 insufficient：依据 missing_requirements 改写，补充检索，与首轮候选合并去重后重新重排和判定。
- 第二轮仍 insufficient：拒答，不调用 Generator 生成事实答案。
- `max_retries` 被限制为 1，没有无限循环。

Web 使用 `st.cache_resource` 缓存工作流。界面保留历史消息，但完整 Agent 当前以单个 query 运行，生成时传入空历史；聊天展示不等于已实现上下文多轮问答。

### 2.2 基础 CLI

`main.py` 通过 `RAGService` 使用 Dense retrieval、可选重排、生成与引用校验，支持历史上下文构造。它保留基础演示用途，不具备完整 Agent 的充分性判定与有限重试流程。README 已说明该差异，后续仍应防止两个入口的配置和错误处理漂移。

### 2.3 关键实现依据

| 文件 | 职责 |
|---|---|
| `src/loader.py`、`src/splitter.py` | 页、条文、表格解析与切分 |
| `src/document_schema.py` | Document/Page/Table/Chunk 数据结构及 provenance |
| `src/index_manager.py`、`src/vector_store.py` | manifest、源文件变更检测、索引保存加载、维度和数量检查 |
| `eval/bm25.py`、`eval/run_agent_test.py` | 当前被应用复用的 BM25 和 HybridRetriever |
| `src/evidence.py` | Evidence 上下文、来源展示、引用编号与 provenance 校验 |
| `src/evidence_sufficiency.py` | LLM 充分性判定及 JSON 字段校验 |
| `src/agent_workflow.py` | retrieve-grade-retry-answer/refuse 状态流 |
| `src/rag_service.py` | 基础 RAG 服务编排 |
| `tests/`、`eval/` | 自动测试、检索与 Agent 评测、结果报告 |

## 3. 已有工程化价值

1. **可追溯的数据契约**：证据携带来源、页码、条文或表格信息，生成上下文使用 Evidence ID，超过只在 UI 并列展示原文片段的阶段。
2. **可复用的持久索引**：根据 PDF checksum、chunk 参数、embedding model 和 schema 判断是否复用索引；加载时检查向量维度、向量数量和 metadata 数量。
3. **可终止的质量决策**：相关性重排与充分性判定分离，证据不足时有有限重试和明确拒答。
4. **有实验支撑的架构选择**：保留 Dense、BM25、RRF、Hybrid rerank 对比，以及充分性、拒答和 held-out Agent 报告。
5. **有测试的编排边界**：工作流和服务可注入替代组件，测试覆盖状态转移、重试上限、拒答不生成和引用等行为。

## 4. 工程化缺口与优先级

### P1：环境复现与自动检查

`pyproject.toml` 已声明依赖，但版本范围较宽，当前目录未发现依赖锁文件或 CI 工作流。本机默认 Python 环境存在缺包及科学计算库二进制兼容问题；这不证明按安装说明建立的干净环境必然失败。

建议：锁定经过验证的依赖组合；在干净虚拟环境完成安装和测试；增加无需真实模型 API 的自动检查。验收应记录 Python 版本、依赖版本和实际测试结果，不能仅引用 README 中历史通过数。

### P1：应用包边界

`agent_demo.py` 从 `eval.bm25` 和 `eval.run_agent_test` 导入正式检索组件，而 setuptools 的包发现仅包含 `src*`。源码目录运行依赖 eval 存在，标准安装后的完整应用交付尚未得到验证。

建议：将 BM25、HybridRetriever 及其运行依赖移入应用包，让评测反向复用正式组件；明确 CLI/Web 的安装入口。验收是在源码目录之外安装构建产物后，仍可导入和构建应用组件。

### P1：引用校验成为输出约束

`AgentWorkflow._answer()` 校验引用后仍无条件设置 final_action=answer；Web 先显示答案，再提示校验错误。`RAGService.answer()` 同样返回校验结果而不阻断。

另外，`validate_citations()` 检查已出现的 Evidence ID 及证据来源字段，未强制要求答案出现引用，也不检查每条事实是否被证据支持。因此 citation valid 不等于事实正确、证据完整或逐项引用覆盖。

建议：明确无引用、未知引用、来源缺失的处理策略；在展示前执行输出门槛，失败时有限修复或返回明确失败状态。测试覆盖合法引用、缺失引用和非法引用。

### P1：外部调用和结构化输出故障处理

业务层最多一次检索重试，不等于模型 API 调用的故障治理。Generator、Grader 等未显式配置项目级超时和重试预算；SDK 默认行为不能替代明确的业务策略。非法 JSON 或字段错误可抛出异常，`app.py` 的问答调用没有统一异常边界。

Grader 已验证字段类型、decision 枚举和证据 ID，但尚未完整约束 sufficient 与 missing_requirements 等字段之间的一致性。

建议：统一配置调用超时、有限故障重试及错误分类；处理空响应和非法输出；区分业务拒答与服务故障。用替代客户端验证超时、限流、无效 JSON 和不一致判定，不需要真实 API 故障。

### P2：索引写入安全与生命周期

当前按顺序直接写入 `index.faiss`、`metadata.json` 和 `manifest.json`，没有构建锁或原子版本切换。中断或并发构建可能留下不一致产物。损坏 JSON、损坏索引的恢复策略不完整。

现有 SHA-256 针对源 PDF；维度与数量检查无法检测相同数量 metadata 的内容篡改或错配。目录主要由文件名派生，同名文档及不同配置可能竞争同一索引位置。解析器逻辑变化还需要主动维护 schema 失效规则。

建议：先构建临时版本，验证完成后切换；增加写入互斥、产物校验和损坏恢复策略。验收覆盖中断、损坏、同名文档及并发构建场景。

### P2：日志、耗时与成本

现有 trace 记录流程步骤和决策，尚不能替代持久结构化日志与指标。缺少统一请求编号、各阶段耗时、token/cost、错误类别和请求整体预算记录。

建议：记录必要运行元数据，避免默认记录敏感问题全文；统计检索、重排和模型调用耗时及失败率。有并发使用目标后，再设定并验证吞吐与 p95 延迟要求。

### P2：部署与使用边界

当前交付方式是本地 CLI/Streamlit，尚未验证容器、健康检查、就绪检查、独立摄取任务与服务部署。Web 可输入服务器本地 PDF/索引路径，若扩展到不可信用户，应先约束路径、资源和权限范围。

建议：先提供可复现启动和容器 smoke 验证；明确是否需要多人接入，再决定独立 API、认证、限流及权限隔离。无需为展示项目预先引入微服务或多 Agent。

## 5. 评测结果与解释边界

以下来自仓库既有 README 和 `eval/reports/`，**本次没有重新运行模型评测**。

| 指标 | 既有记录 |
|---|---:|
| Dense Recall@10（dev） | 0.8873 |
| RRF Recall@10（dev） | 0.9608 |
| Hybrid + reranker MRR@10（dev） | 0.8922 |
| Hybrid + reranker Recall@10（dev） | 0.9510 |
| Held-out answerable / unanswerable | 16 / 4 |
| Held-out 正确拒答 unanswerable | 4 / 4 |
| Held-out false refusal | 2 / 16 |
| Held-out multi-evidence complete@3 | 1 / 3 |
| Held-out generated answers 引用校验通过 | 14 / 14 |

来源：`README`、`eval/reports/test_v1_agent.md` 及相应 JSON 报告。

需要保留的解释限制：

- development set 用于开发与选择，不能作为独立泛化证明。
- README 记载 test_v1 在冻结后运行且未用于调参；本次未独立验证冻结过程。
- Hybrid 的 MRR 与 Dense50 对齐，不代表所有指标全面超过 Dense50。
- 引用校验通过只说明现有规则未发现编号或 provenance 问题，不能表述为答案事实准确率 100%。
- `MULTI-002` 暴露部分支持被判为 sufficient 的问题；false accept=0 的回答/拒答分类指标不排除答案不完整。
- 小规模、单规范数据尚不足以证明多文档、版本冲突、复杂表格和真实用户请求下的可靠性。

## 6. 本次动态验证

执行日期：2026-10-30。使用当前系统默认 `python`，未建立干净环境、安装依赖、下载模型或调用外部模型 API。

### 全量测试

命令：`python -m pytest`。

结果：收集阶段出现 **9 个错误**，未完成全量执行。涉及缺少 `jieba`、`openai`、`fitz`，以及 NumPy 2.2.6 与本机 SciPy 等已安装二进制包不兼容。

这属于本次环境验证受阻，不能直接归因于项目逻辑错误，也不能确认 README 中的历史结果 `57 passed, 5 subtests passed` 已在本机复现。

### 选定测试

命令：

```powershell
python -m pytest tests/test_agent_workflow.py tests/test_rag_service.py tests/test_evidence_citation.py tests/test_rrf.py tests/test_eval_schema.py tests/test_eval_metrics.py tests/test_agent_demo.py
```

结果：**31 passed, 1 failed**。失败项为 `test_demo_builds_existing_agent_workflow`，在替换 Embedder 前导入真实模型模块时触发上述 NumPy/SciPy 兼容错误；没有执行真实模型推理。

### 其他验证边界

- 当前目录没有可用 Git repository metadata，无法核对提交历史、远端配置或冻结版本。
- 当前目录未发现 CI 和容器配置，不代表远端一定不存在相关能力。
- 未执行端到端问答、性能压测、安装产物验证或部署验证。
- 本次仅更新审计文档，没有修复上述代码或环境问题。

## 7. 推荐实施顺序与验收

| 顺序 | 工作 | 完成标志 |
|---|---|---|
| 1 | 锁定环境、建立干净安装和自动测试 | 新环境按说明可安装；测试结果可追溯 |
| 2 | 正式检索组件移入应用包 | 应用不再导入评测 runner；安装产物可独立使用 |
| 3 | 引用输出门槛、异常边界、grader 一致性 | 非法引用和服务故障不会作为正常答案返回 |
| 4 | 索引原子切换、锁与恢复 | 中断、损坏、并发场景可预测且不加载错配索引 |
| 5 | 请求日志、耗时、预算和部署说明 | 能定位失败阶段；干净环境可启动并完成 smoke 验证 |
| 6 | 扩充多证据评测与多文档场景 | 使用新的开发数据与独立测试数据，避免反复调优现有 held-out 集 |

现阶段应优先补齐可安装、可失败恢复、可观测与可交付能力，再根据评测证据决定是否增加检索策略或 Agent 功能。

## 8. 历史审计修订说明

2026-08-16 版本将当时项目归为 Basic RAG，并记录未接线的持久化、无评测、无测试、无 Agent 等问题。该版本描述的是旧阶段，不能继续用作当前能力清单。

本次依据现有代码修订以下结论：

- “只有内存索引” → 已有 IndexManager 和持久化加载链路，但仍缺并发及故障保护。
- “没有 metadata/citation” → 已有结构化 provenance 和引用校验，但未实现事实蕴含验证及输出阻断。
- “没有 hybrid、测试、benchmark、Agent” → 已有对应组件、数据、报告和有限状态工作流。
- “没有依赖清单和配置示例” → 已有 pyproject.toml 和 .env.example，环境复现仍需补强。
- 旧版关于废弃文件和凭据暴露的记录不作为当前事实重述；本次未检查秘密内容或 Git 历史，无法判断历史凭据是否曾泄露或完成轮换。

当前状态以本文及相应源码为准；后续审计应继续保留日期、证据来源和验证边界。
