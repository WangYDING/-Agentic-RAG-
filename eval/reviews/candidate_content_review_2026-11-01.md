# 新开发集与独立候选集 PDF 内容复核

- 复核日期：2026-11-01
- 复核者：Codex (AI; user-authorized PDF content reviewer)
- 题目：50（通过 50，退回 0）
- 独立候选集：未运行、未冻结、未用于本轮调参
- 身份说明：这是用户授权的 AI 内容复核，不冒充持证领域专家签字。

## 本轮实际修正

- `REG-002`：补充第36页表5.3.1注1，记录A型车两组备选长度的适用条件。；将合并书写的A/B车型数值拆为可独立评分的数值项。
- `REG-010`：补充遗漏的慢车被快车越行次数上限“两次”。
- `REG-012`：补充遗漏的低断面范围下限“本线总行车量的1/3”。
- `REG-022`：补充遗漏的丧失动力1/4及以下、1/3、1/2三组比例及对应运行条件。
- `REG-026`：在保留规范原文表述的同时，将人均通风量单位规范为m³/(人·h)。
- `IND-004`：将表格单元值按车型、左右侧和疏散平台条件拆为可独立评分的数值项。

## 逐题结论

| ID | 题意 | 证据定位 | 答案要点 | 数值/单位/条件 | 修正 | 结论 |
|---|---|---|---|---|---:|---|
| REG-001 | pass | pass | pass | pass | 0 | approved |
| REG-002 | pass | pass | pass | pass | 2 | approved |
| REG-003 | pass | pass | pass | pass | 0 | approved |
| REG-004 | pass | pass | pass | pass | 0 | approved |
| REG-005 | pass | pass | pass | pass | 0 | approved |
| REG-006 | pass | pass | pass | pass | 0 | approved |
| REG-007 | pass | pass | pass | pass | 0 | approved |
| REG-008 | pass | pass | pass | pass | 0 | approved |
| REG-009 | pass | pass | pass | pass | 0 | approved |
| REG-010 | pass | pass | pass | pass | 1 | approved |
| REG-011 | pass | pass | pass | pass | 0 | approved |
| REG-012 | pass | pass | pass | pass | 1 | approved |
| REG-013 | pass | pass | pass | pass | 0 | approved |
| REG-014 | pass | pass | pass | pass | 0 | approved |
| REG-015 | pass | pass | pass | pass | 0 | approved |
| REG-016 | pass | pass | pass | pass | 0 | approved |
| REG-017 | pass | pass | pass | pass | 0 | approved |
| REG-018 | pass | pass | pass | pass | 0 | approved |
| REG-019 | pass | pass | pass | pass | 0 | approved |
| REG-020 | pass | pass | pass | pass | 0 | approved |
| REG-021 | pass | pass | pass | pass | 0 | approved |
| REG-022 | pass | pass | pass | pass | 1 | approved |
| REG-023 | pass | pass | pass | pass | 0 | approved |
| REG-024 | pass | pass | pass | pass | 0 | approved |
| REG-025 | pass | pass | pass | pass | 0 | approved |
| REG-026 | pass | pass | pass | pass | 1 | approved |
| REG-027 | pass | pass | pass | pass | 0 | approved |
| REG-NEG-001 | pass | pass | pass | pass | 0 | approved |
| REG-NEG-002 | pass | pass | pass | pass | 0 | approved |
| REG-NEG-003 | pass | pass | pass | pass | 0 | approved |
| IND-001 | pass | pass | pass | pass | 0 | approved |
| IND-002 | pass | pass | pass | pass | 0 | approved |
| IND-003 | pass | pass | pass | pass | 0 | approved |
| IND-004 | pass | pass | pass | pass | 1 | approved |
| IND-005 | pass | pass | pass | pass | 0 | approved |
| IND-006 | pass | pass | pass | pass | 0 | approved |
| IND-007 | pass | pass | pass | pass | 0 | approved |
| IND-008 | pass | pass | pass | pass | 0 | approved |
| IND-009 | pass | pass | pass | pass | 0 | approved |
| IND-010 | pass | pass | pass | pass | 0 | approved |
| IND-011 | pass | pass | pass | pass | 0 | approved |
| IND-012 | pass | pass | pass | pass | 0 | approved |
| IND-013 | pass | pass | pass | pass | 0 | approved |
| IND-014 | pass | pass | pass | pass | 0 | approved |
| IND-015 | pass | pass | pass | pass | 0 | approved |
| IND-016 | pass | pass | pass | pass | 0 | approved |
| IND-017 | pass | pass | pass | pass | 0 | approved |
| IND-NEG-001 | pass | pass | pass | pass | 0 | approved |
| IND-NEG-002 | pass | pass | pass | pass | 0 | approved |
| IND-NEG-003 | pass | pass | pass | pass | 0 | approved |

## 限制与下一门槛

- 同一集合内存在共享条文的配对题，报告已逐题标注，汇总比例不能把它们视为完全独立观测。
- 本轮只复核数据标注，没有运行 RAG 或查看独立集模型结果。
- 独立集仍需预先写入验收标准并冻结，之后才能运行真实模型验收。
- 若用于安全、合规或正式工程判断，仍应由具备相应资质的领域人员复核。
