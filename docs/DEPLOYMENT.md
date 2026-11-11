# 单实例部署与恢复

本文面向本地或受控网络中的单实例 Streamlit 部署。公开多人使用前，还需要补充身份认证、请求限流、上传/路径限制和租户权限隔离。

## 已验证范围与资源

- 应用与测试基线：Windows、Python 3.12.16、uv 0.13.6。
- 容器基线：`python:3.12-slim`，按 `uv.lock` 安装，容器内使用普通用户 `rag`。
- 机器至少应为模型、Python/torch 依赖和索引预留足够磁盘。实际 CPU、内存、磁盘与冷/热启动基线必须在目标机器记录，本文不把未测量数值写成保证。

截至 2026-10-30，当前开发机没有 Docker 命令，也没有真实 API 配置。因此本机已完成 Dockerfile/Compose 静态审查、离线故障测试、索引备份恢复和安装产物验证；真实镜像启动、真实问答、容器重启耗时尚待有 Docker 和授权密钥的目标环境执行。

## 数据目录与密钥

| 容器路径 | 用途 | 挂载方式 |
|---|---|---|
| `/data/document.pdf` | 原始 PDF | 只读文件挂载 |
| `/indexes` | 已发布索引版本与活动指针 | 持久卷、可写 |
| `/models` | Hugging Face 模型缓存与准备标记 | 持久卷、可写 |

密钥只通过运行时环境变量注入，不进入镜像、Compose 文件或日志：

```powershell
$env:DEEPSEEK_API_KEY = "..."
$env:DEEPSEEK_BASE_URL = "https://..."
$env:DEEPSEEK_MODEL = "deepseek-chat"
```

## 构建与首次启动

```powershell
docker compose build

# 只执行一次，或模型标识变化后重新执行
docker compose run --rm rag-web engineering-rag-model prepare

# 显式构建并校验索引；服务启动不会隐式重建
docker compose run --rm rag-web engineering-rag-index build
docker compose run --rm rag-web engineering-rag-index check

# 业务就绪检查不会调用外部模型 API
docker compose run --rm rag-web engineering-rag-health ready

docker compose up -d
docker compose ps
```

访问 `http://localhost:8501`。镜像的 Docker `HEALTHCHECK` 使用 Streamlit 的本地健康地址，只表示进程存活；`engineering-rag-health ready` 才表示配置、模型和当前索引都已准备好。

## 日志与指标

```powershell
docker compose logs -f rag-web
```

每次问答结束会输出 `event=request_completed` 的单行 JSON。使用 `request_id` 查找一次请求，可以看到应用/索引/模型版本、retrieval/rerank/grader/rewrite/generation/total 耗时、answer/refuse/error、错误代码、两类重试、模型调用数及可获取的 token 用量。日志默认不包含密钥、完整问题、证据正文或模型原始响应。

如同时配置 `RAG_INPUT_COST_PER_MILLION` 和 `RAG_OUTPUT_COST_PER_MILLION`，日志会根据累计 token 写入 `estimated_cost`；该值明确是估算，不代替服务商账单。未配置费率时字段为 `null`，避免虚构价格。

进程内指标注册表分别累计 answer、refuse、error，保留最近 1000 个总耗时和阶段耗时样本并计算 p50/p95；还统计模型调用、网络重试、检索补充重试、token、索引加载、构建失败、恢复和版本切换。`request_id` 不作为指标标签。当前版本通过结构化日志采集这些数据，尚未提供 Prometheus HTTP 端点。

## 备份与恢复

备份操作只复制已经校验通过、且与当前 PDF/模型/切分参数严格匹配的活动版本：

```powershell
docker compose run --rm rag-web engineering-rag-index backup --backup-dir /indexes/backups
```

命令输出具体备份版本目录。将整个持久卷做外部快照，或把该目录复制到独立存储。恢复时必须指向具体版本目录：

```powershell
docker compose run --rm rag-web engineering-rag-index restore --backup-dir /indexes/backups/<document_id>/<version_id>
docker compose run --rm rag-web engineering-rag-index check
docker compose restart rag-web
docker compose run --rm rag-web engineering-rag-health ready
```

恢复会重新校验 manifest、SHA-256、FAISS 维度和数量，并拒绝当前 PDF、模型 revision 或切分参数不一致的备份。发布活动指针前保留原版本；失败不会把半成品设为活动索引。

## 回滚

1. 将应用镜像回滚到已验证标签，不使用浮动的 `latest` 作为生产恢复依据。
2. 先用该版本的 `engineering-rag-index check` 检查索引 schema；不兼容时恢复与应用版本配套的备份。
3. 执行业务就绪检查后再恢复流量。
4. 保留旧索引版本，确认新版本稳定后再另行制定清理策略。

## 部署演练清单

在目标机器记录以下实际结果，不用模拟值替代：

1. 无缓存构建镜像、准备模型、构建索引和首次就绪的时间与资源峰值。
2. 执行一次真实问答，按请求编号保存阶段耗时、token 和估算费用（如已配置费率）。
3. 重启容器后确认索引版本不变且未重新构建，记录热启动时间。
4. 用替代客户端制造超时，确认 UI 返回 `error`，日志包含同一请求编号和 `MODEL_TIMEOUT`。
5. 备份活动版本、移除测试副本、恢复并重新通过 `check` 与 `ready`。

当前开发机的可验证结果记录在 [DEPLOYMENT_VALIDATION.md](DEPLOYMENT_VALIDATION.md)。
