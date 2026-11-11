# 评测标注 v2 增量协议

本协议只改变测试题标注与复核，不改变公开 RAG 输入 `rag-eval.rag-input.v1` 或业务策略。`rag-eval.test-case.v1` 继续受理；有新评分语义的题显式使用 `rag-eval.test-case.v2`。旧版题不隐式补字段。复核对象仍为 `rag-eval.review.v1`，v2 题要求对应的增量复核字段。

## 字段与评分

- 回答题 `numeric_constraints_v2[]`：每条有 `constraint_id`、字符串 `value`、`unit`、`comparison`、非空条件字符串列表 `conditions`、一个或多个 `fact_ids`，以及 `link_semantics`（`all_facts` / `any_fact`）。`numeric_constraint_reviews_v2[]` 按 ID 逐约束记录 `correct`，每个约束都参与完整正确答案判定；缺测为 `null`，不能默认为通过。原 `necessary_facts[].numeric` 仍按 v1 评分，迁移时避免重复计分。
- 拒答题 `refusal_annotation_v2`：`supported_facts`、必填非空 `missing_facts` 与 `allowed_explanation`。复核 `refusal_review_v2.missing_facts_not_asserted` 和 `explanation_within_allowed` 连同原 `behavior_review.appropriate` 决定任务成功。规范前提可说明，不能凭它断定缺失的项目事实。
- 澄清题 `clarification_annotation_v2`：`required_fields` 和未来条件 `branches[]`（`branch_id`、`when`、`evidence_groups`）。复核 `clarification_review_v2.required_fields_requested` 与 `no_premature_branch_answer` 决定本轮任务成功。分支证据仅供诊断和后续补充条件时使用，不进入本轮 Recall、事实完整度或生成要求。

所有新字段都不进入 `make_rag_input`。复核模板由 `pending_review(case)` 生成；`validate_review` 校验约束 ID 覆盖。原始资料中的多条件和同值多对象必须逐题确认 `fact_ids`、`all_facts` / `any_fact` 后迁移；这改变评分，旧人工签核不能自动沿用。

## 迁移

复制原题为新版本，保留旧文件和哈希；设置 `schema_version=rag-eval.test-case.v2`；逐条核定关联、条件和行为分支；重新审核实质变化的题并生成新的签核与哈希。v1 题无需转换。正式冻结与独立运行仍由既有门禁决定。
