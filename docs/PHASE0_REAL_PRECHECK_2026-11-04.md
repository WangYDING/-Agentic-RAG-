# PHASE0_REAL_PRECHECK：真实开发题质量预检

> 执行日期：2026-11-04（Asia/Shanghai）  
> 被测代码：`7e5d82caf7aa9c76e83a9a3d03eae484eebdbb3a`  
> 执行目录：`E:\Agentic-RAG-phase0-candidate`  
> 索引版本：`cbbc823c77c8acf3bcdddad7e124c20f0e1fe0329241f125cfb391c0d8f950ff`  
> 实际生成模型：`deepseek-flash`（外部服务底层 revision 未知）  
> API：运行时配置已提供；报告不保存密钥。

## 结论

本地质量预检通过：已有普通可回答题成功记录；本轮固定不可回答题正确拒答；已知多证据题实际触发一次补检，补齐缺失证据后完整回答。消防题此前只证明补检—拒答链路能够运行，由于没有完成 gold 审核，不计入质量通过样本。

容器构建和服务重启按调整后的范围暂缓，不阻塞本地质量验收。冻结 20 题在本报告生成时仍未运行。

## 运行指纹

| 项目 | 值 |
|---|---|
| 被测代码 | `7e5d82caf7aa9c76e83a9a3d03eae484eebdbb3a` |
| 证据分支 | `codex/phase0-candidate-evidence` |
| Python / uv | CPython 3.12.16 / uv 0.13.6 |
| PDF SHA-256 | `e5ca2388ad68ed7b21b6092e66c12a73c74c17de8b532bef91c5b2ea57be78f7` |
| document ID | `e32b2a73134e8548ffbd374f14a52b27aaee9c2d7d2e482b802e756fb0c5fca2` |
| index version | `cbbc823c77c8acf3bcdddad7e124c20f0e1fe0329241f125cfb391c0d8f950ff` |
| Embedding | `BAAI/bge-small-zh-v1.5`；本次解析 `7999e1d3359715c523056ef9478215996d62a620` |
| Reranker | `BAAI/bge-reranker-base`；本次解析 `2cfc18c9415c912f9d8155881c133215df768a70` |
| Generation | `deepseek-flash`；服务地址 `https://api.deepseek.com`；底层 revision 未知 |
| 检索 / 证据 | Dense TopK 10、BM25 TopK 10、最终证据 3、补充检索最多 1 次 |
| 预算 | 单次 30 秒、总时限 90 秒、模型调用上限 6、网络重试 1 |

## 逐题审核

| 场景 | 题目 | 预期 | 实际 | 审核结论 |
|---|---|---|---|---|
| 普通可回答 | 方向划分题 | 正确回答并引用原文 | 用户已确认成功回答、覆盖开发集要求并引用对应条文 | 通过；此前真实运行的精确请求编号和 token 未在本次工具输出中取得，保留为记录限制 |
| 链路观察 | 消防题 | 本轮未指定 gold | 触发补检后拒答 | 只证明链路运行；未审核拒答正确性，不计为“正确拒答”或“多证据修复”通过 |
| 不可回答 | `UA-CAND-A01`：四档减振最低分贝 | 规范没有统一最低分贝值，应拒答 | 补检一次后拒答，列出四项缺失分贝要求，没有生成任何具体分贝值 | 通过 |
| 已知多证据 | `MULTI-002`：站台范围平曲线与纵坡 | 补齐第 7.2.1、7.3.2 条并完整回答 | 补检一次；第二次 grade 为 sufficient；引用 p.45 第 7.2.1 条与 p.48 第 7.3.2 条；答案完整 | 通过 |

## `UA-CAND-A01` 运行记录

- 问题：一般减振、中等减振、高等减振和特殊减振分别必须达到多少分贝的最低减振效果？
- Gold：unanswerable；规范只划分等级并要求按项目评价选方案，没有四档统一最低分贝值。
- 结果：`refuse`。
- 请求编号：`8f5cf212593647c39f261594bfb26eee`。
- 补充检索：1 次。
- Trace：`retrieve → grade insufficient → retry → retrieve → grade insufficient → refuse`。
- 缺失项：一般、中等、高等、特殊减振各自的最低分贝值。
- 阶段耗时：retrieval 47 ms；rerank 2,313 ms；grader 4,593 ms。
- 总耗时：6,953 ms。
- 模型调用 / 网络重试：2 / 0。
- token：input 1,232；output 421；total 1,653。
- 费用：未配置可信费率，`estimated_cost=null`。
- 审核：拒答与标注一致；没有证据外事实或虚构数值。**通过。**

## `MULTI-002` 运行记录

- 问题：地下车站站台范围内的线路，在平面曲线和纵向坡度设置上分别有什么要求？
- Gold：第 7.2.1 条（直线优先；曲线时 A 型车 ≥1500m、B 型车 ≥1000m）和第 7.3.2 条（一个坡道；宜 2‰；困难地段 ≤3‰；有效排水时可平坡）。
- 结果：`answer`。
- 请求编号：`0063271b5b474cc29677fde9e483b077`。
- 补充检索：1 次，实际覆盖该路径。
- Trace：`retrieve → grade insufficient → retry → retrieve → grade sufficient → generate → citation_validate true`。
- 最终证据：
  - p.48，第 7.3.2 条（纵坡）。
  - p.45，第 7.2.1 条两个相邻证据块（平曲线条件与 A/B 型车数值）。
- 阶段耗时：retrieval 46 ms；rerank 3,329 ms；grader 8,828 ms；generation 4,812 ms。
- 总耗时：17,015 ms。
- 模型调用 / 网络重试：3 / 0。
- token：input 2,781；output 1,658；total 4,439。
- 费用：未配置可信费率，`estimated_cost=null`。
- 答案审核：
  - 核心结论有证据：是。
  - 必要要求完整：是。
  - 数值、单位和条件正确：1500m、1000m、2‰、≤3‰、有效排水时平坡均正确。
  - 证据外事实：未发现。
  - 引用合法：`citation_validate=true`，能定位第 7.2.1、7.3.2 条。
- 审核：**通过，多证据修复在固定候选上得到真实覆盖。**

## 已知限制与暂缓项

- 每道题均由独立 CLI 进程启动，日志包含较多模型初始化和 Hugging Face HEAD/GET 信息；日志展示优化不属于阶段 0 验收范围。
- embedding/reranker 配置未强制 revision；报告记录了本次实际解析值，但未来重新下载仍可能漂移。
- 生成服务底层 revision 未知。
- 容器、镜像身份和服务重启复用索引未验证，按调整后的范围暂缓。
- 方向划分题和消防题的精确请求日志未在本轮工具上下文中取得；不伪造请求编号或 token。

## 进入冻结集前的最后确认

在启动冻结 20 题前，应再次确认：候选运行逻辑仍等于 `7e5d82c`；工作区干净；冻结集结果目录为空；运行模型仍为 `deepseek-flash`；索引 version 仍为 `cbbc823c…50ff`；质量门槛 SHA 未变化。确认后方可开始唯一一次独立验收运行。
