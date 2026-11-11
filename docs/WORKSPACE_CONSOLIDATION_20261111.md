# 工作区整合记录（2026-11-11）

## 目标

唯一日常工作目录：`E:/-Agentic-RAG--main`。以业务分支提交 `5c9eb711bd3ce738550658412aa06141b5f513ee` 为整合基础。保持既有历史，不强推、不删除旧分支或工作区。

## 已完成的保全

备份位于 `tmp/workspace-consolidation-20261111/`：

- root-history.bundle、evaluation-history.bundle：两个仓库的全部引用历史。
- evaluation-working.patch、evaluation-index.patch：评测工作树与暂存区差异。
- evaluation-files/：325 个评测新增或修改文件，逐文件 SHA256 校验一致；清单见 evaluation-checksums.json。
- candidate-files/：27 个业务候选目录中的未跟踪评测报告。
- root-metrics-contract.md：主目录独有的未跟踪指标文档副本。

未读取独立题目正文，未执行新题评测。tmp、虚拟环境、索引、缓存未作为源码收集；原目录均保留。

## 整合与提交顺序

1. 在主目录从 5c9eb71 创建整合分支。旧分支的 11d0c60、216081e、4b18ef0 已有对应改动进入业务历史，不整批重复合并。53c10d9 的审计文档、main.py 空输入处理和生成的 egg-info 分别核对；不覆盖更新的业务实现，不提交生成的包元数据。
2. `chore: define repository layout and ignore local artifacts`：忽略根 tmp/、嵌套 evaluation-worktree/、ruff 缓存；记录单目录工作约定。历史报告保留原路径，以免破坏指纹和证据链。
3. `feat(eval): add versioned evaluation contracts and offline pipeline`：接口、指标定义、adapter、contract、fingerprints、pipeline、scoring、offline workflow、校验入口、示例和对应测试。
4. `feat(eval): add usage tracking and release governance`：usage、人工复核、争议裁决、freeze、decision、治理 CLI、rehearsal、接口探测、治理文档与测试；包含历史题清单隔离修正。
5. `test(eval): preserve evaluation tooling rehearsal evidence`：评测工具演练证据和实施记录。明确 synthetic/seen 与正式验收的区别，不改写原始报告或历史指纹。
6. `data(eval): preserve independent dataset authoring and review history`：题集编写脚本、候选版本、人工审核差异和覆盖表。保留 pending 等状态，不因为目录整合提升审核等级；不运行独立题。
7. `docs: document active baseline and evaluation readiness`：统一入口说明、当前业务基线、评测工具状态、独立题交接状态和实际验证限制。

每个提交使用明确文件清单，禁止从外层直接 git add .。检查重复指标文档是否字节一致，有差异则保留比较结果再决定。

## 验证与 GitHub

- 使用现有锁定环境，先跑评测工具明确选定的旧题/模拟测试，再跑允许的业务回归；不调用真实模型/API，不自动发现独立题集。
- 检查 src 与业务基线的差异、锁文件、敏感文件、生成产物和嵌套仓库，核对未提交文件清单。
- 验证后推送整合分支，通过 PR 更新 main。保留现有功能提交的历史；整理本轮新增提交，不重写已公开分支。
- 当前 GitHub 默认 main=68e443d，业务分支=5c9eb71；本轮未推送。

## 本轮整合状态

2026-11-11：Git 元数据恢复可写；已从 5c9eb71 创建 `codex/workspace-consolidation-20261111`，远程推送 dry-run 成功。两个 bundle 均通过 verify；325 个评测文件的备份、原工作树及迁入副本 SHA256 一致。27 个候选报告保留原路径，旧目录和历史分支均保留。

指标文档根草稿与评测版本并非字节一致：评测版本追加第 6 节，前文一致。采用评测扩展版，根草稿原字节另存 `EVALUATION_METRICS_CONTRACT_V1_ROOT_DRAFT_20261111.md`，原备份不动。第 6 节“冻结尚未实现”为 11 月 9 日历史状态；11 月 10 日治理实现以 `EVALUATION_IMPLEMENTATION_STATUS_20261110.md` 为准，不代表正式冻结或独立验收已完成。

53c10d9 的两个独有审计/目标文档恢复至 docs；较旧路线及项目审计副本保存在 `docs/history/legacy-20261107/`，不覆盖业务基线中更新的结论。main.py 补回空输入处理。生成的 egg-info 不迁入；既有跟踪文件保留。

评测历史证据保持原字节及指纹，pending 审核等级不变。新独立题文件仅复制、哈希校验，不解析正文、不运行；工具测试显式选取模拟和已见测试。

## 验证记录

- 工具源码与测试的 ruff 检查通过；src、uv.lock、pyproject.toml 与 5c9eb71 无差异。
- 新增 .gitattributes，评测文件保持原始字节，325 个已提交 blob 与原件逐一一致，防止 Windows 换行转换损坏历史指纹。
- 首轮定向测试为 97 passed、1 failed、4 errors：测试同时发生 Git 提交变化，冻结保护按设计报 source commit changed。该轮无效，最终需在提交号固定后重新运行。
- 最终验证及远程上传结果见后续记录；历史报告不回写。


## 最终本地验证（2026-11-11）

- 固定提交 c523b44：评测工具显式选定测试 **102 passed in 76.31s**；业务回归 **222 passed、31 deselected**。使用既有候选解释器，未安装或更新依赖，非全新 locked 环境验证。
- 工具测试曾暴露一项依赖工作区恰好为脏目录的负例；现明确生成 synthetic dirty-source 元数据，不改变业务或治理逻辑。原测试仍在旧目录及备份中。
- 最终324个迁入评测文件原字节一致，1个测试夹具为上述明确修正；27份候选报告原字节一致。无删除文件。敏感凭据模式扫描0命中；无新增嵌套仓库、tmp、虚拟环境或.env；旧的生成包元数据未更新。
- ruff通过；忽略保留的CRLF和历史Markdown行尾双空格后diff检查通过。src、uv.lock、pyproject.toml与5c9eb71完全一致。历史证据和指纹不回写。
- 未调用真实模型/API，未执行新独立题，未改变审核等级或正式验收结论；最终远程交付以GitHub分支及PR为准。
