# 评测系统本轮实施状态

日期：2026-11-09。仅开发/回归离线验证，无真实模型/API调用，无新独立题集或独立验收。

## 已实现并验证

- 纯评测 WorkflowAdapter：只传问题和经过白名单检查的 QueryScope；保留方法签名、缓存能力、调用参数，不增大top_k/top_n；串行观察后恢复对象。
- 记录初始/重试检索、实际重排调用、最终判定证据、每次Generator实际证据入参及哈希、最后生成上下文、行为/错误/范围/请求日志。原始数据与无法规范化的缺测分开保留。
- Recall@1/3/5/10（宏/微分名）、HitRate、MRR、最终事实覆盖、完整正确答案、支持度、行为错误率、引用合法率、端到端成功、完整混淆矩阵、分组性能nearest-rank分位数与用量观测比例。
- 事实/主张/数值条件/引用语义等显式复核字段；null不算通过；AI身份与人工审批分离；报告含已观察子集、缺测、确认下界及人工确认下界。
- 代码/测试/Prompt/锁文件/规则/题集/配置的指纹；文档/索引manifest可选绑定；输入前后不变、制品原始字节SHA-256、对象关联与报告重算校验；拒绝覆盖已有运行。
- 七场景合成回放全链路；SEM-001/SEM-002两道旧dev题，经真实AgentWorkflow配合手写假组件运行。旧gold未宣称已审核，fixture文档版本明确标为假版本。
- 最终定向pytest：**66 passed in 9.96s**。含历史runner 4项、新接口与链路、历史schema/metrics/governance。新增文件ruff通过，Git暂存差异检查通过。

### 离线产物

- `eval/reports/tooling-v1-synthetic-20261109/report.md`：7场景；合成服务错误率1/7；完整正确答案率null；人工审批未完成。
- `eval/reports/tooling-v1-seen-20261109/report.md`：2道已见题；工具输出2个answer，但完整正确答案率null，没有质量验收结论。
- 两个目录均含cases、公开rag-inputs、observations、reviews、run、report、bundle、归档输入和artifacts.json；两个目录的严格verify均通过。
- 验证命令见 `EVALUATION_INTERFACE_V1.md`。报告不是历史RAG分数的替代，也不能据此宣称真实质量或性能。

## 已实现未验证

- 适配器在真实模型/真实多规范知识库上的完整部署观测；本轮只验证真实workflow与注入假组件。
- 文档/索引/公开配置/模型标识的可选绑定接口已实现；真实部署快照、服务端revision及完整索引文件内容尚未绑定或核验。索引manifest哈希不等于所有索引内容已验证。
- 人工事实/主张复核后的真实质量汇总：聚合算法已用夹具验证，实际人工审核尚未进行。

## 尚未实现或完成

- 本目录新环境的完整uv locked sync：在线同步被网络访问权限拒绝，离线同步缺少缓存；未更新uv.lock或pyproject。现有环境 `E:/Agentic-RAG-phase0-candidate/.venv/Scripts/python.exe` 只读用于测试，jieba0.42.1匹配锁文件；已安装锁内包无版本不匹配。这不等于本目录独立环境已完整建立，也不代替平台/extras解析。
- provider usage是否真正存在的可靠观测：旧observer对缺usage也输出0；适配器保留原日志但token聚合保守置null。尚无真实费用/币种基线。
- 完整争议裁决与人工审批操作流程、正式冻结门禁、预声明失败重跑策略和正式pass/fail签署。
- 新独立测试集及门槛按要求未制作；当前开发入口明确拒绝 independent 数据。

## Git核实和提交情况

评测目录是自身含.git的独立克隆，origin指向本地候选目录。实际分支 `codex/evaluation-contract-v1`；HEAD仍为 `dad052705e11068e8da1b24090742222de666c38`。

12个实现/接口/测试文件已定向暂存。尝试提交失败，原因是仓库没有user.name/user.email，Git报 Author identity unknown；没有代填作者或修改全局配置。此状态文档、两个运行目录及旧题转换输入作为新增文件保留，tmp为调试/环境同步中间文件。没有改动src、uv.lock、pyproject或既有报告。

另一会话候选HEAD核实为5c9eb711bd3ce738550658412aa06141b5f513ee；相比dad0527只有README、文档及历史报告新增，适配器相关运行源码相同。该候选目录未被本会话修改。

## 距正式评测

需先完成可复现运行环境、真实系统与文档索引绑定、人工审核事实与证据方案、独立题集和门槛/重试政策冻结，以及正式验收入口。当前可以继续做旧题回归与评测工具开发，尚不能启动或宣称正式独立验收。
