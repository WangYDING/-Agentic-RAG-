# 第六阶段：数据、评测与冻结规范

日期：2026-11-01。状态：数据治理与离线工具已实现；50 道新候选已完成用户授权的 AI 逐题 PDF 内容复核并记录为 `approved`。独立集仍未冻结或进行真实模型评测，不能据此签署版本通过。

## 1. 数据清单

历史 JSONL 和 eval/reports 原文件保持不动；新增 manifest 记录身份、版本、题数、题型分布和文件 SHA-256。历史冻结时间未知时保持 null，不补造历史审批信息。

| 数据集 | 数量 | 角色与状态 |
|---|---:|---|
| dev_v0 / dev_v0_retrieval | 40 / 34 | 历史 |
| refusal_dev_v0 | 15 | 历史 |
| sufficiency_dev_v0 | 19 | 历史固定 evidence bundles，独立数据格式 |
| test_v1 | 20 | 已查看和分析的历史基线 |
| regression_v1_draft | 30 | 新开发候选，draft，approved（AI 复核身份已披露） |
| independent_v2_draft | 20 | 新独立候选，draft，approved（AI 复核身份已披露），禁止作为独立验收运行 |

新候选从源 PDF 提取了页码、条文和答案片段。两个新集合的 gold 条文互不重叠，且不与上述历史 gold 条文重叠；这不是语义去重或分布独立性的证明。同一集合中保留了单条文/多条文配对题，不能视为完全独立观测。

候选题已覆盖条文、数值、表格、多证据、部分支持和外部事实不可回答场景。2026-11-01 对 50/50 道候选逐题检查题意、可回答性、PDF 页码、条文或表号、答案要点、数值、单位和适用条件，并对关键表格、上标和范围页进行渲染目视检查。复核实际修正 6 题，逐题记录见 `eval/reviews/candidate_content_review_2026-11-01.json`。审核者明确为用户授权的 AI，不冒充持证领域专家；用于正式工程或合规判断时仍应由相应专业人员复核。

## 2. 扩展题目字段

原字段继续兼容，新字段为：

- required_requirements：必要子要求列表，最终应逐项可评分。
- key_answer_points：关键答案要点。
- numeric_expectations：value、unit、conditions；数值用字符串保留范围表示，不擅自转换单位。
- annotation_review：status（pending/source_verified/approved/rejected）、reviewer、reviewed_at、notes。

answerable 必须是真布尔值，拒绝字符串 "false" 等误转换；ID 必须唯一。source_verified 和 approved 都必须填写复核人与复核时间，只有 approved 满足当前数据冻结校验。reviewer 和 notes 必须如实披露审核者类型及限制，不能把 AI 审核写成人工或领域专家签字。旧数据缺少新字段时保持空值与 pending，不追认审核。

每个 manifest 包含 dataset_id、version、role、status、data_file、sha256、count、type_distribution，可补充 source_pdf_sha256、frozen_at、used_for_tuning 和 acceptance_criteria。

## 3. 冻结流程

1. 开发集的标签、自然语言问题、表格与 partial-support 类别已完成首轮完善；独立候选继续保持未运行、未用于系统调参。
2. 已完成用户授权的 AI 逐题内容复核并处理 6 项修正；若发布政策要求领域专家签字，应在冻结前增加该签字记录。
3. 在独立运行前确定并记录质量门槛：非法引用正常返回、证据外编造、错误接受、错误拒答、服务故障与预算违规分别判断，同时记录各类别分母。不以 citation valid 代替答案正确。
4. 逐题 `approved` 已填写并更新 JSONL 哈希、题数和分布；`independent-v2-quality-gate-v1` 已在查看结果前保存，独立集已记录冻结时间并保持 `used_for_tuning=false`。尚未运行独立真实模型验收。
5. 运行前 manifest 校验会阻断未审核或缺少冻结元数据的独立集。元数据是流程记录，并非对审核人身份的认证。
6. 保存本次结果；一旦据结果修改系统，应将该集合标为 demoted、used_for_tuning=true，并记录原因和替代集。不能把它继续作为独立验收依据。

冻结不是发布通过。第五阶段真实部署记录、可执行质量门槛和候选版本真实模型验收必须分别保留。数据复核脚本只签署数据标注，不自动签署版本发布结论。

## 4. 运行指纹

报告记录：Git commit 与 dirty 状态、uv.lock/数据/PDF SHA-256、当前 src/eval 源码文件哈希、Prompt 所在源文件哈希、Python/平台/主要包版本、公开配置指纹、索引版本及真实构建的 manifest、模型标识与 revision 信息、检索参数、超时/重试/调用预算和执行时间。

API 密钥和原始环境变量不序列化。API endpoint 仅纳入去除认证信息后的哈希；不输出原始地址。Prompt 当前按整个源码文件计算哈希，文件内非 Prompt 改动也会使哈希变化。

embedding revision 使用配置中的值；当前系统无法固定的 reranker/生成模型 revision 明确记录 null，不能据此声称模型完全可复现。

## 5. 通用评测入口

run_agent_test.py 不再要求固定 20 题和 test_v1 题型。使用实际应用工厂，复用当前可靠性配置，单独记录 answer/refuse/error。保留 Recall、MRR、证据覆盖、false accept/refusal、引用校验及逐题 trace。类别统计保留数量，率使用明确定义的分母，空分母为 null。

每题生成待人工审核字段和独立复核表，支持 0/1/2 分评定证据支持、完整性、数值条件、证据外事实；null 不表示通过。系统不自动填写人工分数。

运行时可观察的阶段耗时、token、调用次数和估算费用与 request_id 关联；没有观察到的数据保持 null。当前调用用量若为 0，也可能意味着服务端未返回 usage，不能据此认定免费。普通离线执行不算真实容器延迟/费用基线。

以下只展示入口，需先准备配置、模型和索引；会调用真实模型，不在普通 CI 中执行：

```powershell
# 历史集可重新评测但须写新文件；不要将它称为新独立测试
.\.venv\Scripts\python.exe -m eval.run_agent_test --dataset eval/datasets/test_v1.jsonl --manifest eval/datasets/test_v1.manifest.json --pdf data/raw/城市轨道交通工程设计标准.pdf --index-dir .rag_index --json-out eval/reports/new_run.json --md-out eval/reports/new_run.md --review-out eval/reports/new_run.review.json
```

CLI 在模型调用前检查输出路径是否已经存在，避免覆盖历史报告。程序化调用同样需指定 manifest。不要直接对 independent_v2_draft 运行；它会被冻结校验阻断。

## 6. 离线检查、复核表与差异

```powershell
# 检查全部清单，不加载模型也不调用 API
.\.venv\Scripts\python.exe -m eval.dataset_manifest "eval/datasets/*.manifest.json"

# 从新报告生成待人工复核表
.\.venv\Scripts\python.exe -m eval.review eval/reports/new_run.json --output eval/reports/manual_review.json

# 在相同数据/PDF、同版报告格式和相同证据数量下计算差异
.\.venv\Scripts\python.exe -m eval.review eval/reports/candidate.json --baseline eval/reports/baseline.json --output eval/reports/comparison.json
```

缺少指纹的旧报告或不同测试集之间不计算数值 delta，返回不可比较原因。即使数据相同，仍需人工检查环境、模型漂移与配置差异，不能仅凭 delta 作因果归因。

CI 已增加 manifest 校验；普通离线测试覆盖冻结阻断、哈希篡改、严格布尔值、重复 ID、秘密排除、非 20 题评测、服务故障不计拒答、报告防覆盖、比较前提和新集合条文重叠检查。远端 CI 需推送后实际运行，本次没有声称其通过。

## 7. 剩余验收事项

- 若项目发布政策要求持证领域专家签字，在冻结前补充该签字；当前 `approved` 的审核者为已披露身份的 AI。
- 明确独立质量门槛，冻结新测试集；当前两份清单都未冻结。
- 第五阶段真实容器问答、重启和恢复验证已基本完成；费率依据不足，费用仍未估算，详见部署验证记录。
- 显式执行候选版本真实模型评测、人工评分及失败分析。
- 根据证据形成通过、限制通过或未通过结论。当前不具备最终签字条件。


## 8. 本次验证记录

2026-11-01，本地 Windows / 项目 .venv：候选 PDF 内容复核 50/50 通过，实际修正 6 题，并保存逐题检查维度、引用定位、数值条件、修正项和审核身份。未调用真实模型、未执行独立验收、未运行远端 CI。自动测试、Ruff 和 manifest 校验结果以本轮最终验证记录为准。
