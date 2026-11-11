# 评测工具治理与冻结流程 v1

日期：2026-11-10。基于上一轮66项测试的实现增量扩展。旧runner、历史报告、旧门槛和RAG业务源码保持不变。正在准备的新独立题集不在本轮读取或运行范围。

## 一、当前入口

| 文件 | 职责 |
|---|---|
| eval/usage_v1.py | 在SDK返回处识别usage是否存在、逐次调用缺测及费用估算 |
| eval/review_workflow_v1.py | 导出复核草稿、人工/AI复核导入、争议/裁决、可回放修订链 |
| eval/freeze_v1.py | 显式制品绑定、知识库字节校验、正式预检查及单次执行登记 |
| eval/decision_v1.py | 规则化pass/fail/inconclusive与独立签署制品 |
| eval/governance_cli_v1.py | 预检查、复核导入/导出、签署、复验命令 |
| eval/rehearsal_v1.py | 仅使用两道旧开发题和假组件的全流程演练 |
| eval/interface_probe_v1.py | 在指定RAG源码进程内做真实快照与范围澄清探测，不构造模型 |

所有新输出目录必须不存在；JSON文件用排他创建。不会覆盖原始回答、旧审核、历史报告或已存在的签署。机器格式延续rag-eval.*.v1，正式判断保存在额外decision.json，原始bundle/report不随复核修改。

## 二、usage与费用

适配器临时观察grader/generator/rewriter的client.chat.completions.create，原参数原样传递并返回原对象，finally恢复SDK对象；不修改CallBudget、不改变业务重试。只支持独占实例的串行评测，不可并发包装或与在线流量共享。

每次SDK尝试（含异常）记录input/output_tokens是否真正出现。字段不存在、None、负数、字符串或bool都不推断为0。provider返回的整数0是已观测零，与未知区分。只有尝试清单与observer调用次数完整对应、且每次字段均已观测，才输出全量token合计；否则全量值为null，另外列已观测合计、次数和比例。无请求用量样本不推断费用为0。

费用只有在双方token完整且显式提供费率、币种、来源、有效日期时估算；不同币种不相加。历史observer的累计0只能保留作原日志，不能证明provider有usage。当前仅支持现有同步chat.completions调用接口；其他客户端或隐藏SDK内部重试需单独观测，观测不足不会补零。

## 三、复核包与变更链

1. 从运行导出待填模板，身份、时间、理由为空时不能导入：

```powershell
python -m eval.governance_cli_v1 export-review-template <run-dir> --output <new-review-draft.json>
```

2. 审核者填写actor(identity/type/at)和各review.reviewer，二者须一致；时间须含时区。rubric_version使用原运行评分规则的SHA-256，模板已填写，不能填泛称v1。只保留实际修改的changes，每项提供原review哈希及修改理由。
3. 填逐事实、逐主张、数值条件、引用语义等标签；未核仍为null。human_approved=true只接受human身份，且要求相关字段完成；AI标签不能冒充人工签字。真实审核者及专业资格不会由工具自动认证。
4. 导入生成新版本，原包原始字节、规范化包、state、lineage和integrity哈希一并保存：

```powershell
python -m eval.governance_cli_v1 import-reviews <run-dir> <filled-packet.json> --output <new-revision-dir> [--parent <previous-revision-dir>]
python -m eval.governance_cli_v1 verify-review <revision-dir>
```

复核草稿不是已审核记录。旧case_id、fact_id、evidence_id、主张ID、布尔/分类字段、未知字段、过期review哈希、错误规则版本都会校验；支持事实需指向实际对应阶段的证据。审核者不能直接在review.adjudication里覆盖结论。

争议在packet.disputes中记录dispute_id/case_id/field/reason/review_sha256，field是存在的JSON指针，例如/fact_reviews/0/correct。裁决在packet.adjudications中记录dispute_id、uphold或replace、理由及裁决后的review哈希；replace必须同时提交显式review变更。只有human actor可裁决，未解决争议阻止通过。修订链按父state哈希逐层回放；修改日期不得早于父记录。

## 四、冻结清单

freeze由write_freeze以显式路径建立，包含purpose、frozen_at、approved_by、attempt_registry与九个bindings；不自行发现或搜索题集。

| Binding | 要求 |
|---|---|
| rag_source | RAG完整src、Prompt、锁文件、pyproject、Git提交/状态与源码哈希 |
| configuration | 白名单公开配置、实际模型ID/revision状态；正式模式要求provider endpoint身份哈希 |
| knowledge_base | catalog、active指针、snapshot manifest、各文档manifest、PDF、index.faiss、metadata原始字节哈希 |
| evaluation_source | 显式列出的评测模块及相关测试版本；排除独立题编写脚本和文件 |
| dataset | 原始题集文件哈希 |
| dataset_descriptor | 角色、frozen状态、题数、used_for_tuning、逐题事实/等价证据方案的审核及哈希 |
| rules | 完整评分规则文件哈希 |
| thresholds | 运行前声明的policy，含门槛、缺测/未复核/服务错误处理、硬失败和重跑政策 |
| environment | 解释器与依赖审计、锁文件哈希、完整locked sync成功的记录；不能把已有环境审计写成新安装成功 |

预检查校验缺项、字节变化、源码清单不完整、模型/配置/索引不一致、数据角色或审核状态不符、审核/门槛晚于冻结、Git脏状态和环境未完成等。正式模式要求independent数据、未用于调试、人工审核和干净源码；rehearsal只允许synthetic/development/historical，永不成为正式独立结论。

配置不读取.env或凭据；api_endpoint_sha256对移除用户名、密码和query后的endpoint身份求哈希。公开配置与workflow运行限制、model_ids、实际导入源码、知识库snapshot_id必须匹配。服务端revision确实不可取得时须明确unavailable且由预声明规则允许，不能虚构revision。

```powershell
python -m eval.governance_cli_v1 precheck <freeze.json> --output <new-precheck.json>
```

不合格预检查退出码为2。预检查和元数据绑定不表示真实模型或真实质量已验证。运行入口还会重复检查配置/源码/快照，执行前后复核冻结内容。正式API执行还需要独立的explicit independent_authorized=True；本轮没有设置，也没有暴露可直接启动正式验收的CLI命令。

单次运行政策通过声明的attempt_registry排他登记实现，同一登记目录按dataset哈希拒绝第二次执行，失败也不删除登记。登记目录须长期保留并由操作流程统一使用；它不是防恶意管理员篡改的全局防作弊系统。正式源码应放在独立干净checkout，运行/登记/报告置于其外，不能通过清理另一会话的目录来获得干净状态。

## 五、判断与签署

policy版本为rag-eval.policy.v1，必须声明on_missing_observation/on_unreviewed/on_service_error（只允许fail或inconclusive）、required_observations、thresholds、human审批、硬失败及单次运行政策。模拟policy只是工具夹具，不能用作正式门槛。

判断每次重算指标，不信任报告里手填的分数。任何硬失败或已知门槛未达到→fail；否则存在未复核/缺测/争议等→按预声明规则fail或inconclusive；全部条件满足才pass。fail优先于inconclusive，所有原因保留。零分母的null不默认为达标。位置覆盖、引用解析与语义正确继续分别计算。

签署要求human身份元数据及不早于运行/审核的时间；无法从JSON验证真实人类身份或领域资质，因此这是可审计签署记录，不是数字证书。独立审批仍需真实人工完成。不能对旧未绑定运行补一套事后门槛来签署通过。

```powershell
python -m eval.governance_cli_v1 sign <run-dir> --revision <revision-dir> --signer-json <actual-signer.json> --output <new-assessment-dir>
python -m eval.governance_cli_v1 verify-assessment <assessment-dir>
```

assessment保存decision.json、原因列表、重算评分、usage汇总、原run/审核state/freeze/policy哈希及lineage。原run和review均不回写。归档内部一致性复验与“当前部署仍匹配该快照”不同；签署前会重新核验live冻结输入，旧运行可通过archive-only模式查看原档案。

## 六、本轮演练与真实接入边界

```powershell
python -m eval.rehearsal_v1 --output <new-rehearsal-dir>
```

仅取旧dev_v0中的SEM-001/SEM-002，运行真实AgentWorkflow和手写假组件。演练的PDF/索引字节、门槛、审核身份和签署身份均明确为合成夹具，不是实际人工审核或领域专家签字。主演练用AI标签保留待人工状态，最终应为inconclusive；pass/fail分支由临时合成标签的测试覆盖，不能称为RAG质量通过。

最新候选检查采用专用进程，导入候选目录src，并把隔离评测包加入eval模块路径。只读取已知知识库目录与catalog，不读取新独立题。可加载本地FAISS文件验证快照，用旧题的空scope验证clarify，模型组件替换为“调用即报错”的对象，socket和OpenAI构造均禁止。该探测只证明接口与快照绑定，不证明真实检索、生成、usage或模型权重正确。

下一步真实接入验证的最小范围：

1. 完成独立环境的uv locked sync并记录成功，固定有效公开配置、endpoint、模型ID/revision、本地模型缓存和真实知识库快照。
2. 经明确授权后，按候选源码构造真实组件，通过适配器绑定检查；只用已见题各选一条回答/拒答/范围澄清，设置预算，不碰新独立题。
3. 核对真实候选/重排/生成上下文、调用次数与SDK逐次usage；缺usage和错误/重试仍用模拟客户端补测，可信币种费率未给出时费用保持null。
4. 完成真实人工复核后再固定正式数据、门槛及清洁发布快照，才考虑独立验收；本轮没有启动该步骤。


## 七、最终隔离与运行配置补充

历史回归清单已改为显式12项，避免通配扫描另一会话正在写入的新清单；新题文件不进入本轮工具验证。正式绑定还校验实际组件的provider超时/网络重试参数、embedding标识与revision，并要求SDK max_retries=0，不能仅信任配置文件标签。最终实施状态及真实验证记录见`EVALUATION_IMPLEMENTATION_STATUS_20261110.md`。
