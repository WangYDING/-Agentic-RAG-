# RAG Project Archaeology and Architecture Audit

> 审计日期：2026-08-16  
> 审计目标：判断仓库当前真实能力，并给出面向秋招 Agent 应用开发 / 大模型应用开发岗位的演进路线。  
> 审计原则：以实际入口和调用链为准，不以 README、文件名或未接线的类推断能力。

## 1. Executive Summary

### 1.1 结论

当前项目应归类为 **C. Basic RAG（早期原型）**，不是 Agentic RAG。

实际主链路是：固定路径单 PDF -> PyMuPDF 全文抽取 -> 简单正则清洗 -> 300 字符 / 50 字符重叠的固定滑窗 -> `BAAI/bge-small-zh-v1.5` embedding -> 内存 `FAISS IndexFlatIP` dense retrieval -> `BAAI/bge-reranker-base` CrossEncoder 重排 -> DeepSeek Chat 生成 -> UI/CLI 在答案之外展示若干来源标签。

它已经超过最小 Naive RAG 的地方是：使用中文 embedding、两阶段检索、Streamlit UI、多轮历史和 Streamlit 主链路中的 LLM query rewrite。但这些能力尚未形成可验证、可部署、可迭代的工程系统：没有持久索引、增量更新、BM25/hybrid、检索阈值、可靠页码、答案级 citation、evaluation、benchmark、tracing、测试、API、容器化和 Agent 决策循环。

### 1.2 最重要的代码事实

- CLI 入口是 `main.py:11-83`；Web 入口是 `app.py:15-145`。两条链路有行为漂移。
- `src/vector_store.py:36-44` 虽然实现了 `save/load`，但任何入口都没有调用；实际索引仅存在于内存。
- `src/query_rewriter.py` 只在 `app.py:105-108` 使用；CLI 使用 `ChatMemory.build_context_query()` 的直接历史拼接。
- 所有问题都无条件执行 retrieval；不存在是否检索的路由、工具选择、质量检查或迭代检索。
- “引用”只是 UI/CLI 对最终 chunks 的并列展示。`Generator.generate_answer()` 只接收文本列表，不接收来源 metadata，无法产出可校验的 claim-to-source citation。
- `1.py` 是废弃旧实现：引用不存在的 `data/raw/毕业要求.pdf` 和未定义的 `clean_chunks()`，并硬编码 API key。它不属于当前可运行主链路，但构成凭据泄露风险。
- 仓库没有测试、评测集、评测脚本、日志、API、Docker、部署配置、`.env.example`、标准依赖清单或 package metadata。
- 本地 `.venv` 的解释器路径已失效；因此本次无法完成端到端动态运行。所有动态行为结论均标明其证据边界。

### 1.3 最高优先级建议

1. 先轮换已暴露凭据，清理旧入口并建立唯一应用服务层。
2. 建立可复现的 baseline 和小型人工标注 benchmark；没有评测前不要声称任何优化“提升准确率”。
3. 保留 BGE dense + CrossEncoder 的合理选择，补足页级/条文级 metadata、持久化索引、可验证 citations 和 retrieval failure handling。
4. 用 BM25 + dense + RRF/加权融合增强规范编号、术语和精确数值检索，再用 benchmark 验证。
5. 最后才加入受控 Agent 工作流：检索路由、rewrite、质量判定、有限次数 retry 和有依据终止；不要直接引入多 Agent 或 GraphRAG。

## 2. Current Architecture

### 2.1 仓库实物清单

| 类别 | 实际内容 | 结论 |
|---|---|---|
| 项目说明 | `README` | 仅 24 行项目描述，无安装、运行、架构、评测或设计取舍 |
| 依赖 | `requirements` | 非标准文件名；缺少代码直接依赖 `sentence-transformers`、`numpy` |
| 入口 | `main.py`, `app.py`, `1.py` | CLI、Streamlit、废弃旧脚本三套入口/实现 |
| 摄取 | `src/loader.py` | 仅 PDF；PyMuPDF 文本抽取和轻量正则清洗 |
| 切分 | `src/splitter.py` | 固定字符滑窗，附加启发式条文号 |
| Embedding | `src/embedder.py` | SentenceTransformer BGE small zh，归一化向量 |
| 向量库 | `src/vector_store.py` | FAISS `IndexFlatIP`，内存 metadata；未接线 save/load |
| 检索 | `src/retriever.py` | 单路 dense retrieval |
| 重排 | `src/reranker.py` | BGE CrossEncoder reranker |
| 改写 | `src/query_rewriter.py` | DeepSeek LLM rewrite，仅 Web 主链路使用 |
| 生成 | `src/generator.py` | DeepSeek Chat，prompt-only groundedness 约束 |
| 记忆 | `src/chat_memory.py` | 进程/会话内最近 3 轮 |
| 占位模块 | `src/pipeline.py`, `src/utils.py` | 空文件 |
| 数据 | `data/raw/城市轨道交通工程设计标准.pdf` | 唯一业务文档；未发现派生索引或 manifest |
| 笔记 | `过程问答`, `知识系统` | 学习/面试笔记，不属于运行系统 |

以下请求中指定的目录/文件在仓库中不存在：`pyproject.toml`、`requirements.txt`、`tests/`、`scripts/`、`configs/`、`examples/`、`docs/`（审计前）、`.env.example`、Docker/deployment 文件。仓库还存在 `.env` 与 `APIKEY` 两个凭据文件；是否被 Git 历史追踪为 **UNKNOWN**，因为当前工作区没有可用 Git repository metadata。

### 2.2 组件图

```text
                         ┌────────────────────────────┐
fixed PDF path ─────────>│ load_pdf_text + clean_text │
                         └──────────────┬─────────────┘
                                        v
                         split_text_with_ref(300, 50)
                                        |
                                        v
                         BGE-small-zh-v1.5 embeddings
                                        |
                                        v
                            in-memory FAISS FlatIP

User query ──> [Web: LLM rewrite | CLI: history concatenation]
                                        |
                                        v
                          dense search (Web K=5..20,
                             default 10; CLI K=10)
                                        |
                                        v
                       CrossEncoder rerank (default N=3)
                       [Web 可关闭；CLI 固定开启]
                                        |
                                        v
                    text-only context + recent chat history
                                        |
                                        v
                              DeepSeek generation
                                        |
                           answer + separately listed chunks
```

## 3. Actual Runtime Pipeline

### 3.1 文档进入、解析与切分

1. 文档入口：CLI 在 `main.py:12` 写死 PDF 路径；Web 在 `app.py:72-75` 接受服务器本地路径字符串，默认仍是同一 PDF。没有上传、目录扫描、对象存储或多文档管理。
2. Loader：`src.loader.load_pdf_text()`，实现见 `src/loader.py:7-23`。
3. 解析：`fitz.open()` / PyMuPDF，逐页调用 `page.get_text("text")`，然后把非空页文本拼成一个字符串。不是 layout-aware parser；没有 OCR、表格、图片、标题树处理。
4. 清洗：`src/loader.py:26-58` 删除形如 `- 12 -` 的页码，逐行 trim/压缩空格，并删除两个中文字符之间的空白。docstring 声称“去页眉页脚”，实际没有页眉页脚识别或频次删除；导入的 `Counter` 未使用。
5. Chunk：`src/splitter.py:37-69` 按 Python 字符位置固定滑窗切分，不感知 token、句子、段落、页或条文边界。
6. 参数：两个真实入口均为 `chunk_size=300`, `overlap=50`（`main.py:18-23`, `app.py:34-39`）。
7. Metadata：每个 chunk 保存 `text`, `source`, `chunk_id`, `article_id`, `display_ref`。`article_id` 由 chunk 内第一条满足行首模式 `((\d+\.)+\d+) + 空白` 的文本启发式提取。没有 page、document_id、版本、章节、标题路径、字符偏移、checksum、时间戳或 ACL。`VectorStore.search()` 兼容读取 `chapter_id/chapter_title`，但 splitter 从不生成它们，属于数据契约漂移。

重要后果：Loader 在切分前丢失页边界，因而后续无法恢复可靠页码；固定窗口可能从条文中间切断，`display_ref` 也可能指向 chunk 中较晚出现而非 chunk 主体所属的条文。

### 3.2 Embedding、索引与更新

8. Embedding model：`BAAI/bge-small-zh-v1.5`，见 `src/embedder.py:9-18`。
9. 生成位置：应用启动/Streamlit cache miss 时，先对全部 chunk 批量 `model.encode(..., normalize_embeddings=True)`；查询时对 query 单条 encode。没有显式 BGE query instruction。
10. Vector store：`faiss.IndexFlatIP`（`src/vector_store.py:6-14`）。由于文档和查询向量已归一化，inner product 等价于 cosine similarity。
11. 持久化：**主链路没有持久化**。`save/load` 方法存在（`src/vector_store.py:36-44`）但没有调用点。每次 CLI 启动都重建；Streamlit 依赖 `@st.cache_resource` 暂存于当前服务进程。
12. 数据更新/reindex：没有显式更新、删除、版本或增量索引流程。CLI 重启会全量重建；Web 的 cache key 主要是路径参数，同一路径内容被替换时是否失效没有由项目控制，因此存在 stale index 风险。可靠行为需要加入文件 hash/mtime manifest 后才能确认。

### 3.3 Query、retrieval 与 reranking

13. Query 处理：Web 无条件调用 DeepSeek `QueryRewriter.rewrite()`；CLI 使用 `ChatMemory.build_context_query()` 把最近问答和当前问题拼接。单轮 Web 问题也会多一次 LLM 调用。
14. Retrieval 算法：query embedding + FAISS exact inner-product dense search。
15. Top-k：Web 滑块范围 5-20、默认 10；CLI 固定 10。`Retriever` 自身默认 3，但真实入口均覆盖它。Rerank Web 默认保留 3（范围 1-5），CLI 固定 3。
16. Dense only：第一阶段召回是 dense only。
17. BM25/sparse：不存在。
18. Hybrid：不存在。
19. Metadata filtering：不存在。
20. Query rewrite：Web 存在并进入主链路；CLI 不存在 LLM rewrite，只做原始历史拼接。没有 rewrite fallback、输出校验或效果评测。
21. Reranker：存在且进入两条主链路；Web 可关闭。模型为 `BAAI/bge-reranker-base`。值得注意的是 Web dense retrieval 使用 `rewritten_query`，但 rerank 又使用原始 `query`（`app.py:111-115`）；对“那验收标准呢”一类指代问题，reranker 会失去 rewrite 补全的信息，可能推翻正确召回。

没有相似度阈值、rerank 阈值、空结果语义判定、去重、邻接 chunk 扩展、parent-child retrieval、MMR 或 retrieval quality check。只要文档有 chunk，系统通常总会把排名最高的内容交给 LLM，即使它与问题无关。

### 3.4 Context、prompt、答案与引用

22. Context 构造：入口只抽取最终结果中的 `text`；`Generator` 以 `参考片段1/2/3` 拼接，中间两个换行（`src/generator.py:16-19`）。没有 token budget、去重、来源 metadata、文档顺序恢复、上下文压缩或冲突处理。
23. Prompt 使用：把历史、原始当前问题和参考片段插入单个 user prompt，并要求基于片段、禁止编造、信息不足时明确说明。
24. 是否强制基于证据：只有 prompt 软约束；没有结构化输出 schema、引用校验、entailment/faithfulness 检查或拒答门槛。因此不能称为“强制”。
25. Citation/source：UI/CLI 会在答案之外列出最终 chunks 的 `source/display_ref`，Web 还显示文本和分数。这是 retrieved-source display，不是答案内可验证 citation。由于生成器未收到 metadata，模型无法可靠输出来源编号对应关系。
26. 无资料处理：如果 PDF 完全提取不到文本，CLI 退出；Web 意图显示错误，但 `build_knowledge_base()` 的失败分支返回 4 个值（`app.py:41-42`），调用方解包 5 个值（`app.py:85`），实际会先抛 `ValueError`。对“文档有文本但问题无关”的情况，没有 retrieval failure handling，只依赖 prompt 的“给定片段未提供完整信息”。
27. Hallucination control：仅低温度 `0.2` 和 prompt 约束。没有输入证据门控、citation completeness、答案后验验证、事实一致性检查或 uncertainty policy。

### 3.5 Evaluation、observability、cache、interfaces 和 Agent

28. Evaluation：不存在。
29. Retrieval evaluation：不存在标注 query-qrel、Recall@K、MRR、nDCG、HitRate 或对比实验。
30. Generation evaluation：不存在 faithfulness、answer correctness、citation precision/recall、拒答准确率或人工 rubric。
31. Tracing/logging：不存在结构化日志、request ID、阶段耗时、token/cost、召回分布、异常追踪或 tracing。只有 CLI `print` 和 Streamlit 展示。
32. Cache：只有 Streamlit `@st.cache_resource` 缓存模型和以 PDF 路径参数构建的知识库；没有 embedding cache、query/result cache、LLM response cache，也没有显式失效策略。
33. API：不存在 HTTP API。Streamlit 是 Web UI，不等同于稳定服务 API。CLI 存在。
34. Agent：不存在真正 Agent。没有 tool schema/function calling、planner/router、state machine、action/observation loop 或自主终止条件。
35. 决策权：无。所有问题沿固定 DAG 执行。
36. 是否决定 retrieval：否，所有问题无条件 retrieval。
37. 多轮/迭代 retrieval：有最近 3 轮对话记忆，但每次请求只有一次 retrieval，不会基于结果质量继续检索。
38. 是否普通 RAG 包装成 Agent：仓库运行界面没有直接把它命名为 Agent，但若在简历中称为 Agent/Agentic RAG，会与代码事实不符。当前只是带 query rewrite 的固定 RAG pipeline。

## 4. RAG Capability Matrix

| 能力 | 状态 | 主链路证据 | 审计判断 |
|---|---|---|---|
| PDF ingestion | PARTIAL | `loader.py`, 两个入口 | 单文件路径，无上传/批处理/版本 |
| PDF parsing | YES | `fitz.get_text("text")` | 纯文本抽取，无 layout/OCR/table |
| 清洗 | PARTIAL | `clean_text()` | 基础正则；页眉页脚声称与实现不符 |
| Chunking | YES | `split_text_with_ref()` | 300/50 字符滑窗，结构意识弱 |
| Metadata | PARTIAL | splitter record | 仅 source/chunk/article heuristic |
| Dense embedding | YES | `Embedder` | BGE small zh，normalized |
| Vector retrieval | YES | `IndexFlatIP` | exact dense cosine |
| Persistent index | NO IN RUNTIME | `save/load` 未调用 | 每次重建/进程 cache |
| Incremental indexing | NO | 无实现 | 无 add/update/delete/version workflow |
| Sparse/BM25 | NO | 无实现 | 对编号/术语/精确数值不友好 |
| Hybrid fusion | NO | 无实现 | 无 RRF/weighted fusion |
| Metadata filter | NO | 无实现 | 无文档/章节/版本/权限过滤 |
| Query rewrite | PARTIAL | 仅 `app.py` | CLI 漂移；无失败回退/评测 |
| Reranking | YES | 两入口 | CrossEncoder；Web 可关闭 |
| Context builder | PARTIAL | `generator.py:16-19` | 纯拼接，无预算/去重/邻接扩展 |
| Grounded prompt | PARTIAL | generator prompt | prompt-only，不是可验证约束 |
| Citation | PARTIAL/MISLEADING | 入口额外展示 chunks | 不是 claim-level citation；缺页码 |
| No-answer handling | WEAK | prompt + empty-doc check | 无相关性阈值；Web 空文档分支有 bug |
| Retrieval evaluation | NO | 无文件/调用 | 无法量化 rerank/rewrite 收益 |
| Generation evaluation | NO | 无文件/调用 | 无法量化 groundedness |
| Multi-document | NO | 单路径/单索引 | README “多文档”描述未实现 |

## 5. Agent Capability Matrix

| Agent 能力 | 状态 | 说明 |
|---|---|---|
| LLM 路由是否需要检索 | NO | 固定无条件检索 |
| Tool/function calling | NO | Retriever 只是普通函数，由应用硬编码调用 |
| 选择检索策略 | NO | 只有 dense 路径 |
| Query rewrite 决策 | NO | Web 无条件 rewrite |
| 结果质量判断 | NO | 无 threshold/critic/validator |
| Retry / iterative retrieval | NO | 单次召回 |
| 多查询分解 | NO | 无 decomposition |
| 状态与步骤预算 | NO | 无 agent state / max steps |
| 可解释 action trace | NO | 无 action/observation trace |
| 自主终止/拒答 | NO | 仅生成 prompt 提示 |
| 多轮对话 | PARTIAL | 最近 3 轮内存，不等于 Agent loop |
| Agent 框架 | NO | 当前也不需要为框架而引入框架 |

## 6. Dead / Drifted Components

### 6.1 未进入主链路或废弃实现

| 组件 | 事实 | 风险/结论 |
|---|---|---|
| `1.py` | 与模块化主链路平行的旧版 RAG；引用缺失 PDF、调用未定义 `clean_chunks()`、使用英文 MiniLM/L2 | 不可运行的 abandoned implementation，应删除或移入明确的 archive（更建议删除） |
| `src/pipeline.py` | 0 字节 | 占位 dead file |
| `src/utils.py` | 0 字节 | 占位 dead file |
| `VectorStore.save/load()` | 有实现，无调用点 | “支持持久化”不能算当前能力 |
| `chapter_id/chapter_title` | search 会读取，splitter 不生成 | 新旧 metadata 契约漂移 |
| `loader.Counter` | 导入但未使用 | 可能是未完成的页眉页脚清理思路 |
| `embedder.OpenAI/os/load_dotenv` | 导入/调用但 embedding 实际只用 SentenceTransformer | 冗余依赖与职责噪声 |
| `pickle` metadata | 仅未接线 save/load 使用 | 若未来加载不可信文件有反序列化风险 |

### 6.2 README 与实现不一致

- README 声称“支持多文档规范检索”：实际每次只接受一个 PDF 路径并构建一个临时索引。
- README 声称“引用来源追溯”：实际只显示文件名和不可靠的启发式条文/chunk 标签，无页码、版本和答案内引用绑定。
- README 声称针对“页眉页脚噪声”优化：`clean_text()` 没有实现页眉页脚检测或删除。
- 学习笔记称采用“结构与长度约束结合的混合切分策略”：运行代码只有固定字符滑窗，条文号只用于展示，不参与边界决定。
- 学习笔记中关于 Query Rewrite 的描述只对 Web 入口成立；CLI 仍直接拼接历史。

### 6.3 两条生产候选链路漂移

| 行为 | CLI `main.py` | Web `app.py` |
|---|---|---|
| query processing | 历史全文拼接 | DeepSeek rewrite |
| rerank | 固定启用 | 可关闭 |
| 参数 | 固定 recall 10 / rerank 3 | UI 可调 |
| cache | 无 | 进程内 Streamlit resource cache |
| 引用详情 | 文件 + ref | 文件 + ref + scores + chunk text |

这种漂移使得测试、复现和面试描述都没有唯一“系统行为”。应把 pipeline 收敛到一个 application service，CLI/Web/API 仅做适配。

### 6.4 Mock/fallback/测试假链路

- 未发现 mock/fake 实现。
- 未发现掩盖异常的 fallback；相反，大多数模型、API、文件和 rewrite 失败会直接中断请求。
- 未发现测试，因此不存在“测试覆盖假链路”的直接证据；实际问题是主链路完全无测试。

## 7. Engineering Issues

### P0：必须解决

1. **凭据泄露**：`1.py:7-10` 硬编码看似真实的 API key；仓库还有 `.env`、`APIKEY`。立即在提供商侧轮换/吊销，不只是删除字符串；新增 `.gitignore` 和无秘密值的 `.env.example`。Git 历史是否曾包含秘密为 UNKNOWN，需要可用 `.git` 历史或远端仓库证据。
2. **不可复现环境**：现有 `.venv` 指向不存在的 Python；`requirements` 缺直接依赖且无版本锁定。新环境无法可靠安装/运行。
3. **没有任何自动化测试或 evaluation**：无法证明系统正确、rerank/rewrite 有收益，也无法防止改造回归。
4. **引用不可靠**：页边界在 loader 阶段丢失，article id 是滑窗内启发式匹配；当前展示可能让用户误以为是精确规范溯源。
5. **无关问题仍强制生成**：没有 retrieval threshold/质量判定，最高分 chunk 不等于相关证据；工程规范场景中会产生高风险“有依据感”幻觉。
6. **Web 错误分支本身崩溃**：空文档时返回 4 项却解包 5 项，扫描 PDF 提示无法按设计展示。

### P1：强烈建议解决

1. 建立唯一 pipeline/service，消除 CLI/Web 行为漂移并删除旧 `1.py`、空模块。
2. 把摄取与查询解耦，增加 index manifest、文档 checksum、持久化和确定性的 rebuild/update/delete。
3. 保留页级 Document 对象，增加 `document_id/source/page/chapter/article/chunk_id/version/checksum` metadata。
4. 将固定字符切分升级为“页/标题/条文边界优先 + 长度上限 + overlap”的可配置 chunker，并用 benchmark 选择参数。
5. 增加 BM25，使用 RRF 起步做 dense+sparse hybrid；规范编号、术语和精确数值是明确业务理由。
6. 统一 query rewrite 语义；rerank 应使用可消解指代的检索 query，或把原问题与 rewrite 同时纳入，并通过消融实验决定。
7. 增加相关性阈值、无答案策略、空结果/模型失败降级和明确错误类型。
8. 构建 citation-aware context，要求结构化答案引用 evidence IDs，并做 citation existence/coverage 校验。
9. 增加 FastAPI、配置管理、结构化日志、request trace、阶段 latency/token/cost 和健康检查。
10. 补全 README：业务边界、架构、运行方式、数据/模型、评测结果、技术决策与已知限制。

### P2：锦上添花

1. embedding batch/cache、异步 LLM client、并发限制、超时重试、模型 warm-up。
2. parent-child retrieval、相邻条文扩展、MMR/去重，但必须由错误分析驱动。
3. reranker/embedding 模型可替换接口与离线对比脚本。
4. Docker、CI、指标面板、负载测试和部署 runbook。
5. 文档上传/管理 UI、索引状态和可解释检索调试页。
6. Agentic workflow 在 baseline 和 evaluation 稳定后加入。

## 8. Evaluation Gaps

当前所有“提升检索质量/准确性”的描述都没有实验数据支撑。至少需要：

### 8.1 数据集

- 从真实规范中建立 80-150 条问题作为第一版，包含事实、精确数值、条文号、跨 chunk、多轮指代、无答案和越权/闲聊问题。
- 每题标注 gold answer、relevant document/page/article/chunk（允许多证据）、answerable 标志和问题类型。
- 划分固定 dev/test；索引参数只在 dev 调整，最终一次性报告 test。
- 记录标注规范与 reviewer disagreement。若数据量不足，可先 30-50 条做 smoke benchmark，但不能包装成充分结论。

### 8.2 Retrieval metrics

- Recall@5/10、MRR@10、nDCG@10、HitRate@K。
- 分类型报告：条文号/术语/语义改写/数值/多轮。
- 消融：dense baseline、dense+rerank、BM25、hybrid、hybrid+rerank、rewrite on/off、chunk strategy A/B。
- 同时记录索引时间、query p50/p95 latency、内存和模型体积。

### 8.3 Generation metrics

- Answer correctness、faithfulness/groundedness、citation precision、citation recall/completeness、拒答 precision/recall。
- LLM-as-judge 只能作为辅助；保留规则校验和人工抽样，固定 judge prompt/model/version。
- 对每次失败归因到 parse/chunk/retrieve/rerank/context/generate/citation，而不是只给一个总分。

### 8.4 当前 UNKNOWN

- 真实 PDF 页数、可抽取字符量、扫描页比例、表格/双栏情况：本地 Python 环境不可用，未动态解析。需要恢复环境后运行 ingestion profile。
- BGE 模型和 reranker 是否已缓存、当前机器能否加载：需要有效 Python 与模型缓存/网络证据。
- DeepSeek endpoint 当前可用性、模型实际响应与成本：本次不调用外部付费服务，也不读取秘密值。
- 当前问答质量、latency 和资源占用：没有可运行环境、benchmark 或历史 trace。

## 9. Recruitment Readiness Assessment

| 维度 | 分数 / 10 | 扣分原因 |
|---|---:|---|
| 技术深度 | 3.5 | 有 BGE + FAISS + CrossEncoder + rewrite，但关键逻辑大多是直连组件；无检索实验、阈值、失败分析或业务约束建模 |
| RAG 完整度 | 4.0 | 主链路完整且有 rerank；缺 ingestion lifecycle、hybrid、可靠 metadata/citation、failure handling 和 evaluation |
| Agent 能力 | 0.5 | 只有 LLM query rewrite 和多轮历史；没有工具选择、决策循环、质量检查或 retry |
| 工程能力 | 2.0 | 有模块拆分和 UI；但环境不可复现、三入口漂移、无服务层/API/config/CI/deployment，错误处理薄弱 |
| 可观测性 | 0.5 | 只有 print/UI 分数，无结构化 logging/tracing/metrics |
| 可评测性 | 0.0 | 无数据集、指标、脚本、基线或实验记录 |
| 可扩展性 | 3.0 | 类边界提供初步替换点；但单文档、内存索引、全量启动、metadata contract 漂移限制扩展 |
| 面试可讲性 | 4.0 | 能讲基础两阶段 RAG；无法用数字回答“为什么这样选、提升多少、失败在哪里” |
| 项目真实性 | 3.5 | 有真实工程规范 PDF 和实际 UI；但场景只有单文件 demo，README 多文档/页眉页脚/引用表述超出实现 |
| 简历竞争力 | 3.0 | 可作为学习项目，不足以作为 Agent 应用岗核心项目；尤其缺评测与 Agent 决策证据 |

综合判断：当前可以诚实表述为“工程规范 PDF 两阶段 RAG 原型”，不应表述为“生产级知识库”“多文档系统”或“Agentic RAG”。

## 10. Target Architecture

### 10.1 推荐业务定位

目标不是泛化的“上传 PDF 聊天”，而是：**面向城市轨道交通工程规范的可追溯问答与条文核验助手**。核心用户任务是定位规范条文、核对定量要求、比较相关条款并返回可核验页码/条文引用。这个定位自然解释 hybrid retrieval、metadata、citation、拒答和 evaluation 的必要性。

### 10.2 目标链路

```text
Offline / ingestion
PDF -> page-aware parse -> normalization -> section/article-aware chunking
    -> metadata + document manifest
    -> dense embeddings -----> vector index
    -> tokenization ----------> BM25 index

Online / query
request -> policy/router (retrieve or direct reject/answer)
        -> conditional query rewrite / decomposition
        -> dense retrieval + BM25 retrieval
        -> RRF fusion -> dedup/filter -> CrossEncoder rerank
        -> relevance/evidence quality gate
             ├─ sufficient -> context builder -> grounded generation
             ├─ weak -> bounded rewrite/retry (max 1-2)
             └─ insufficient -> evidence-based refusal
        -> citation validation -> response
        -> trace + metrics + evaluation record
```

### 10.3 模块与真实问题的对应关系

| 新增/增强模块 | 解决的真实问题 | 为什么现在值得做 |
|---|---|---|
| Page-aware parser | 当前无法给可靠页码，表格/页结构丢失 | citation 是规范问答的信任基础 |
| Structure-aware chunker | 固定滑窗切断条文，条文号归属不可靠 | 提升检索粒度与引用可读性 |
| Document manifest/index manager | 每次启动全量 embedding，更新不可控 | 可复现、可增量、可部署 |
| BM25 | 编号、专业术语、精确措辞是 sparse 强项 | 与工程规范查询高度匹配 |
| Hybrid fusion | dense/sparse 各自有盲区 | RRF 简单、可解释、易做消融 |
| Reranker | 对融合候选精排 | 保留当前合理设计，但必须评测 |
| Context builder | 去重、相邻条文、token budget、evidence IDs | 降低噪声并支持引用 |
| Citation validator | 防止模型引用不存在证据 | 将“展示来源”升级为可验证溯源 |
| Evaluation harness | 当前所有优化没有证据 | 是项目技术深度和面试说服力核心 |
| Retrieval quality gate | 无关问题也强行回答 | 为拒答与 retry 提供明确条件 |
| Bounded Agent workflow | 对复杂/指代/低质量检索做有限决策 | 有真实决策权，避免名义 Agent |

### 10.4 Agent 是否适合加入

适合，但只能作为受控 workflow，而不是自由规划的聊天 Agent。第一版决策权应限定为：

1. 判断请求是否属于规范知识库范围、是否需要 retrieval。
2. 仅在指代不明或首轮证据不足时 rewrite。
3. 调用统一 retrieval tool，读取结构化结果与分数。
4. 依据可解释规则 + 小模型/LLM grader 判断证据是否充分。
5. 最多重试 1-2 次，可改变 query 或过滤条件；达到预算后拒答。
6. 有充分证据才生成，随后校验 citation ID。

不建议当前加入 GraphRAG、知识图谱、多 Agent。仓库只有单份规范，尚无实体关系查询证据，也没有 baseline 指标证明普通 hybrid RAG 已到瓶颈。

## 11. Gap Analysis

| 当前 | 目标 | 差距 | 优先级 |
|---|---|---|---|
| 单 PDF 路径启动时摄取 | 独立、可重复、可增量 ingestion | manifest/index lifecycle | P0/P1 |
| 全文字符串 | page/section/article Document | 可靠结构与 provenance | P0 |
| 300/50 字符滑窗 | 结构优先 + 长度约束 | chunk quality | P1 |
| source/chunk/article heuristic | page/version/checksum/section metadata | citation/filtering | P0/P1 |
| dense only | dense + BM25 + fusion + rerank | recall robustness | P1 |
| top-N 永远生成 | quality gate + calibrated refusal | failure safety | P0 |
| 文本拼接 | budgeted evidence context | noise/control | P1 |
| 来源列表 | claim/evidence citation | verifiability | P0/P1 |
| 无评测 | fixed benchmark + CI regression | measurable quality | P0 |
| 固定 pipeline | bounded agent decisions | genuine Agent capability | Phase 4 |
| print/UI | logs/traces/metrics | observability | P1 |
| Streamlit/CLI 各自编排 | shared service + API adapters | consistency/testability | P1 |

## 12. Refactoring Roadmap

> 文件名是推荐目标布局，不代表当前已存在。每个阶段都应保持可运行，指标退化时停止继续堆功能。

### Phase 0：项目清理

**修改目标**：消除安全风险和多入口漂移，建立可复现 baseline，但不改变检索算法。

- 涉及文件：`README`、`requirements`（迁移为 `pyproject.toml` 或标准 `requirements.txt`）、`.env`、`APIKEY`、`1.py`、`main.py`、`app.py`、`src/pipeline.py`、`src/utils.py`。
- 新增模块：`.env.example`、`.gitignore`、`src/config.py`、`src/application/rag_service.py`、`tests/` 基础结构。
- 删除模块：删除 `1.py`、空 `pipeline.py/utils.py`；秘密文件移出版本控制。删除前先轮换 key。
- 技术方案：入口只调用同一个 `RAGService`; 使用 typed settings；固定 Python/依赖版本；加入 lint/type/test 命令。
- 验收标准：干净环境一条命令安装；CLI/Web 对同一输入产生相同检索结果；仓库 secret scan 为 0；空 PDF/错误路径返回明确错误。
- 测试方式：配置单测、import smoke test、CLI/Web service contract test、secret scanner、静态检查。

### Phase 1：Baseline RAG

**修改目标**：做成可复现、可引用、可拒答的可靠 baseline。

- 涉及文件：重构 `loader.py`、`splitter.py`、`vector_store.py`、`retriever.py`、`generator.py`、入口。
- 新增模块：`src/domain/document.py`、`src/ingestion/parser.py`、`src/ingestion/chunker.py`、`src/indexing/index_manager.py`、`src/rag/context_builder.py`、`src/rag/citations.py`、`scripts/build_index.py`。
- 删除模块：删除兼容但无来源的 `chapter_id/chapter_title` 读取逻辑，或正式纳入统一 schema；不保留两套 metadata contract。
- 技术方案：逐页解析；保留 page_no 和 offset；条文/标题边界优先，超长条文再按长度切；文件 hash manifest；FAISS + metadata 原子持久化；证据 ID；最小相关性门槛与拒答。
- 验收标准：索引重启可加载而非重算；同文件不重复索引；修改文件可检测并重建；每条答案 citation 可解析到真实 PDF 页和 chunk；无关问题能够拒答。
- 测试方式：parser/chunker golden tests、metadata round-trip、index save/load、citation validator、no-answer integration tests。

### Phase 2：Retrieval Enhancement

**修改目标**：针对规范编号、术语、数值和语义表达同时提高 recall/precision。

- 涉及文件：`retriever.py`、`reranker.py`、`query_rewriter.py`、`context_builder.py`、配置。
- 新增模块：`src/retrieval/bm25.py`、`dense.py`、`fusion.py`、`filters.py`、`quality.py`。
- 删除模块：删除入口中的检索编排和散落 top-k 参数；统一由 retrieval pipeline 管理。
- 技术方案：中文适配 tokenizer 的 BM25；dense 与 BM25 各取候选；先用 RRF 融合；去重后 CrossEncoder；按 dev set 校准 top-k、top-n 和阈值；rewrite 仅处理上下文依赖 query。
- 验收标准：相对 Phase 1，固定 dev/test 上 Recall@10、MRR/nDCG 有明确提升，且 p95 latency/内存仍在事先设定预算内；至少报告一次失败/无提升的实验。
- 测试方式：离线 retrieval benchmark、组件单测、fusion deterministic test、reranker batch test、rewrite regression cases、性能基准。

### Phase 3：Evaluation System

**修改目标**：让每个技术决策有数据支撑，并能持续回归。

- 涉及文件：所有 RAG 组件的稳定接口和 response schema。
- 新增模块：`eval/datasets/*.jsonl`、`eval/run_retrieval.py`、`eval/run_generation.py`、`eval/metrics.py`、`eval/report.py`、`docs/evaluation.md`。
- 删除模块：删除 README 中无实验支撑的效果声称；用带版本的报告替代。
- 技术方案：人工 gold evidence + answer；retrieval 与 generation 分层评测；规则指标 + 人工抽样 + 固定 judge；保存 run config、git revision、模型版本和结果。
- 验收标准：一条命令复现 baseline 与 candidate 对比；报告 Recall@K/MRR/nDCG、faithfulness、citation、refusal、latency/cost；CI 跑小型 smoke set。
- 测试方式：metric unit tests、dataset schema validation、determinism test、known-good/known-bad examples、人工复核抽样。

### Phase 4：Agentic RAG

**修改目标**：只为可观察到的 retrieval failure 增加有限决策能力。

- 涉及文件：`query_rewriter.py`、retrieval service、generator、API response/trace。
- 新增模块：`src/agent/state.py`、`router.py`、`tools.py`、`workflow.py`、`policies.py`。
- 删除模块：删除 Web 中无条件 rewrite；删除任何与统一 workflow 重复的入口逻辑。
- 技术方案：显式状态机即可，暂不必使用 LangGraph；节点为 route -> rewrite(optional) -> retrieve -> grade -> retry(max 1-2) -> generate/refuse -> validate citations。Retriever 作为结构化 tool；每步有 timeout、budget 和 trace。
- 验收标准：Agent 能跳过不需要知识库的请求，能对低质量首轮检索做一次有效 retry，达到预算后稳定拒答；与 non-agent baseline 相比在多轮/模糊问题子集显著改善且成本可接受。
- 测试方式：状态转移单测、mock tool contract、max-step/loop prevention、失败注入、agent-vs-baseline benchmark、trace assertions。

### Phase 5：Engineering / Deployment

**修改目标**：形成可演示、可部署、可排障的完整应用。

- 涉及文件：Streamlit 作为 UI adapter，所有配置和 application service。
- 新增模块：`src/api/` FastAPI、Dockerfile、compose（如确有外部服务）、CI workflow、health/readiness、structured logging、metrics、deployment docs。
- 删除模块：删除 UI 对模型和索引对象的直接构建；UI 只调用 API/service。
- 技术方案：ingestion job 与 query API 分离；request ID；结构化错误；超时/retry/rate limit；模型/索引 warm-up；Docker 非 root；秘密通过环境注入。
- 验收标准：容器一键启动；健康检查通过；并发目标下 p95 达标；日志可串起一次 query 的 rewrite/retrieval/rerank/generation；重启索引不丢失。
- 测试方式：API contract/e2e、Docker smoke、并发压测、故障注入、部署回滚演练、依赖/镜像安全扫描。

## 13. Recommended Final Project Positioning

### 13.1 推荐项目名

**面向城市轨道交通工程规范的可追溯 Agentic RAG 问答与条文核验系统**

只有完成 Phase 4 且有 Agent-vs-baseline 数据后才使用 “Agentic”。Phase 1-3 阶段应命名为“可追溯 Hybrid RAG 规范问答系统”。

### 13.2 最终简历叙事应回答的四个问题

1. **业务为什么难**：规范长、条文编号和精确数值多、跨页/跨条关联、错误引用成本高。
2. **为什么这样设计**：dense 解决语义表达，BM25 解决编号/术语，reranker 提高候选精度，metadata/citation 保证可核验，quality gate 控制拒答。
3. **你自己实现了什么**：page-aware ingestion、结构化 chunk、index lifecycle、hybrid fusion、context/citation contract、evaluation harness、受控 agent state machine，而不只是调用框架 chain。
4. **结果如何证明**：固定测试集上的 Recall@K/MRR/nDCG、faithfulness/citation/refusal、p95 latency/cost，以及消融和失败案例。

### 13.3 不建议的表述

- 不要在没有 benchmark 时写“显著提升准确率”。
- 不要把 Streamlit 称为生产 API。
- 不要把 query rewrite 或固定 pipeline 称为 Agent。
- 不要把候选 chunk 列表称为精确 citation。
- 不要声称多文档、页眉页脚优化、持久化或增量更新，除非对应主链路和测试已经落地。

### 13.4 理想最终交付物

- 可复现的源码、配置、容器和演示 UI/API。
- 公开可说明来源或脱敏自建的 evaluation dataset。
- 自动生成的 retrieval/generation/latency 对比报告。
- 一张展示 ingestion、hybrid retrieval、quality gate、agent retry 和 citation validation 的架构图。
- 3-5 个成功案例和同等数量的失败案例/改进记录。
- README 中明确限制、技术决策、实验结果和复现步骤。

最终竞争力不来自堆叠更多框架，而来自：**能定义工程规范检索的真实失败模式，能用数据证明改进，能让答案可追溯，并让 Agent 的每一次决策都有边界、有观测、有收益。**
