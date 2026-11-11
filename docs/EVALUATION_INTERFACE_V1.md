# RAG 评测接口与离线工具 v1

日期：2026-11-09。状态：开发/回归工具，未冻结正式验收规则或门槛。不得将本轮离线验证解释为真实 RAG 达标。

## 1. 实际目录与版本

评测目录：`E:/-Agentic-RAG--main/evaluation-worktree`。这是具有自身 `.git` 的独立克隆目录，origin 指向本地候选目录，并非主仓库 worktree 列表中的共享工作树。实际分支 `codex/evaluation-contract-v1`，本轮开始 HEAD 为 `dad052705e11068e8da1b24090742222de666c38`。分支是通过 Git 读取证实的，不是以先前失败的新分支命令推断。

主目录仍为历史保全区；候选目录当前 HEAD 已推进到 `5c9eb71`。相对 dad0527 仅新增文档/历史报告，适配器相关运行源码未变。未向候选目录写入文件、安装依赖或操作 Git。

## 2. 入口与文件

| 文件 | 用途 |
|---|---|
| `eval/contract_v1.py` | 六类带版本机器格式及跨对象校验 |
| `eval/adapter_v1.py` | 注入已构造 workflow，观察调用和实际输出 |
| `eval/scoring_v1.py` | 指标、事实/主张复核汇总、混淆矩阵、性能 |
| `eval/fingerprints_v1.py` | 原始字节 SHA-256、源码/锁文件/环境审计 |
| `eval/pipeline_v1.py` | 读取→公开输入→观测→复核→评分→JSON/Markdown→复验 |
| `eval/offline_workflow_v1.py` | 两道已见开发题配合手写假组件运行真实 AgentWorkflow |
| `eval/examples/synthetic_contract_v1.json` | 七个合成场景，非独立测试集 |
| `tests/test_eval_pipeline_v1.py` | 不准联网/构造 OpenAI 客户端的链路测试 |

历史 schema、runner、metrics、review、manifest、provenance 的入口与语义保持原样。新版并行使用 `rag-eval.*.v1`，不改写历史成绩或把历史 0/1/2 人工量表混算。

## 3. RAG 对接边界

`WorkflowAdapter(workflow, identities=...)` 接收 `make_rag_input(case)`，只调用 `workflow.run(question, scope=QueryScope(...))`。题号/格式版本用于评测关联，不传给 workflow；参考答案、必要事实、预期行为和证据标签均不传入。

公开范围仅允许 `spec_ids`、`edition_ids` 两个键；严格调用项目的 QueryScope 解析器。其他键（包括评测元数据）在调用前拒绝。空范围保持 unspecified，由原业务决定是否澄清。

适配器只临时包装 retriever/reranker/generator，原参数原样传递，不增加 top_k/top_n，不额外检索/重排/生成，保留 inspect.signature 及 score cache 能力，finally 恢复对象和 logger。只支持**独占 workflow 的串行评测**，不可与在线请求共享实例或并发包装。

旧 source 到文档 ID/版本的映射只能来自显式系统身份表，不能读取 gold 推断。无法定位时，规范化阶段列表为 null，原始结果保存在 extensions。离线旧题演示中的 `synthetic-edition-not-verified` 是假组件版本，不是原 PDF 的真实规范版本。

## 4. 必须字段与缺测

必须存在：case_id、actual_action、answer_text、error、四个阶段列表、generator_invoked、citations、retrieval_rounds、actual_scope、measurements。缺测保持 null；已观测空列表为 []。

- 行为：answer/refuse/clarify/error；业务 clarify_scope 显式映射 clarify，不按 result_type=refuse 误计。
- 阶段：initial_candidates 为首次 retrieve 返回；reranked_results 为首次 rerank/select_top 返回。retrieval_rounds 按每次 retrieve 分段，保留该段最后一次实际排序返回，不能冒充业务最终证据。所有中间排序事件在 raw_events 中保留。
- final_decision_evidence 为 state.evidences；generator_context 为最后一次 generate_answer 的实际证据入参。每次生成调用均记录原始入参、输入哈希、输出和是否完成，不从最终证据倒推上下文。
- 没调用 Generator 时 context=null。已调用但不能归一化时仍为 null，raw_events 保留。无法观察调用接口时 generator_invoked=null，不能默认 false；其题号在报告单列，不能隐藏条件分母。
- actual_scope 保留业务绑定的 business_ids；无法观测时为 null。
- error 必须有 code；系统异常明确记为 error，不转为业务拒答。
- 引用分别记录解析与范围校验，null 不当合法。合法性不代表语义支持。
- latency_ms 从调用系统到收到输出，含重试；初始化不混入查询。model_calls 取 observer。旧 observer 对缺失 usage 也累加0，因此 input/output_tokens 保守记 null，原始 token 字段另存，尚不能提供可信的全量 provider usage。

## 5. 评分与复核

规则全文见 `EVALUATION_METRICS_CONTRACT_V1.md`，本轮重新保留原初稿全部定义。K=1/3/5/10，候选/重排/各轮分别命名。

| 项目 | 评分依据 |
|---|---|
| Recall/HitRate/MRR、位置完整诊断 | 稳定文档/版本/PDF页范围/条文或表格位置；方案内 AND，方案间 OR；不按随机 chunk/evidence ID 相等评分 |
| 错误接受、错误拒答、澄清行为、服务错误 | 预期与实际行为，完整3×4混淆矩阵 |
| 引用合法率 | 非空引用、可解析、来源完整且范围合法 |
| 最终事实覆盖 | 逐事实 final_evidence_supported，独立于生成上下文 |
| 完整正确答案 | 必要事实覆盖/正确、数值单位条件、完整主张清单、无矛盾/外推、引用合法且支持主张 |
| 证据支持度 | 已回答的回答题、完整主张清单、supported主张占比；空主张不获满分 |
| 端到端成功 | 回答满足完整正确；拒答/澄清还需恰当性复核 |
| 性能 | nearest-rank p50/p95、调用/token已观测汇总及覆盖率，按题型、预期和实际行为分组 |

每项含 case_values、分子、分母、rate、适用题号、observed_rate/denominator、缺测题号和确认下界。存在缺测时全量 rate=null；宏平均分子为逐题得分之和；微平均另命名并标明 case/fact-group 单位。JSON含按题型/预期行为的分组指标。

复核每个必要事实保存 context_supported、final_evidence_supported、answer_covered、correct、numeric_conditions_correct、证据ID和理由；每个主张保存 supported/unsupported/contradicted/null。answer_review 记录主张清单完整、无矛盾、无实质性外推、引用语义支持。未复核均为 null，不以缺少主张清单自动认定通过。

身份/日期/规则版本留存；AI标签明确披露，human_approved=true 仅允许 human。语义指标是暂定标签分数，最终人工审批单列；human_confirmed_task_success_lower_bound 不计AI签署。新运行使用排他创建，原始输出/旧复核文件不被覆盖；adjudication 保留扩展位，完整争议裁决工作流尚未完成。

## 6. 指纹、归档和校验

run 保存系统/评测两份 Git 分支、HEAD、dirty/status、源码文件清单及哈希；评测代码含 tests，Prompt按源文件哈希。另存输入题集、规则、extra_inputs、配置白名单哈希、模型ID/未知revision、文档哈希和索引manifest哈希。

输入在运行前归档并记录哈希；运行前后校验输入与源码；文档/索引hash覆盖调用前后。输出目录包含 cases/rag-inputs/observations/reviews/run/report/bundle JSON、Markdown和 artifacts.json。最终复验检查文件哈希、对象关联、逐项重算评分、归档题集与cases一致。

`verify` 默认同时核验当前源码/输入/文档；后续代码提交或修改可使严格核验失败，表示当前状态与原运行不同。`--archive-only` 仅验证归档内部一致性，**不代表当前系统仍匹配，也不是数字签名或独立审计认证**。与历史换行归一化 SHA-256 区分，新制品哈希使用原始字节。

当前冻结ready固定为 false；正式独立集在入口直接拒绝，尚未实现通过门槛评定或正式pass/fail签署。

## 7. 环境和复现

使用解释器：`E:/Agentic-RAG-phase0-candidate/.venv/Scripts/python.exe`。只读取其已安装包，不在该目录同步/安装。该环境的 jieba=0.42.1，与锁文件相同；已安装锁内包版本审计无不匹配。

本目录执行 `uv sync --locked --extra dev --python <上述解释器> --cache-dir tmp/uv-cache` 创建本地 .venv 时，下载被系统网络权限拒绝；再用 --offline 缺缓存。锁文件/pyproject 未更新。**不能声称本地新环境完整准备成功**；已安装版本审计也不替代平台标记/extras的完整sync验证。

在评测目录用上述解释器运行：

```powershell
python -m pytest tests/test_eval_pipeline_v1.py tests/test_eval_contract_v1.py tests/test_eval_runner.py tests/test_eval_governance.py tests/test_eval_schema.py tests/test_eval_metrics.py -p no:cacheprovider --basetemp=tmp/validation-new-run -o addopts='' -q
python -m eval.pipeline_v1 replay eval/examples/synthetic_contract_v1.json --output eval/reports/tooling-v1-synthetic-20261109 --use-fixture-reviews
python -m eval.offline_workflow_v1 --output eval/reports/tooling-v1-seen-20261109
python -m eval.pipeline_v1 verify eval/reports/tooling-v1-synthetic-20261109
```

输出路径必须未存在；每次使用新名称，禁止删旧结果重跑。

## 8. 距正式评测的剩余项

1. 独立环境的完整锁定同步（网络条件允许后）；真实模型/API本轮未调用。
2. 当前候选的真实知识库身份、文档/索引和公开配置/模型revision绑定；真实多规范部署的观察字段及 provider usage 仍需接通验证。
3. 必要事实、等价证据与组合方案的人工审核，数值单位条件和完整主张复核；争议裁决/复核导入的正式审批流程。
4. 尚未准备的新独立题集、独立门槛、失败重跑政策，以及不可变系统/评测快照与正式pass/fail签署入口。

本轮只证明评测工具在模拟/旧题离线场景工作，不证明RAG真实质量、性能或泛化能力。


## 2026-11-10 增量实现

usage、复核修订链、冻结门禁、单次运行登记和签署流程已增量实现。当前操作说明见 `EVALUATION_GOVERNANCE_V1.md`；本文件上述“尚未实现”条目属于2026-11-09基线状态，不能代替最新实施记录。
