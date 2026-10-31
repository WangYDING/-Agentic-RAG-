# 第五阶段部署验证记录

验证日期：2026-10-30（Asia/Shanghai）

## 当前机器结果

| 项目 | 结果 |
|---|---|
| Python / uv | 3.12.16 / 0.13.6 |
| 结构化日志与阶段耗时 | 离线替代组件通过 |
| 超时、限流、认证失败 | 故障注入通过；不调用真实 API |
| 索引备份、删除后恢复、重启式重新加载 | 临时 PDF + FAISS 集成测试通过 |
| Ruff | 通过 |
| 离线测试 | 88 passed |
| 集成测试 | 23 passed（含备份/恢复与重启式加载） |
| sdist / wheel | 构建成功 |
| wheel 离开源码目录 | 全新临时环境安装成功；包导入与 index/model/health CLI 帮助通过 |
| Docker 镜像实际构建/启动 | 未执行：本机没有 Docker 命令 |
| 真实问答与 token/费用 | 未执行：本机没有 API 配置 |
| 容器冷启动/热启动 | 未执行：依赖真实容器演练 |

未执行项不是验收通过项。目标环境完成真实演练后，应把镜像标签、主机规格、索引版本、请求编号、冷/热启动时间及 token 记录追加到本文件。

Windows 安装与 wheel 验证的远端记录：[GitHub Actions 41063600150](https://github.com/WangYDING/-Agentic-RAG-/actions/runs/41063600150) 已通过。后续提交增加 Linux 容器镜像构建检查；以该次检查最终归档结果为准。

## Windows 11 实机部署验证（已完成，含未通过项）

验证日期：2026-10-31（Asia/Shanghai）

### 主机与代码基线

| 项目 | 实测结果 |
|---|---|
| 主机 | `WANGYDING`，Windows NT 10.0.26200.0，AMD64 |
| CPU / 逻辑处理器 | 12th Gen Intel Core i5-12450H / 12 |
| 物理内存 | 15.7 GiB |
| C 盘空间 | 已用 112.6 GiB，剩余 87.4 GiB |
| WSL | 3.0.3.0，Linux 内核 6.18.54.1-1；安装后尚待重启生效 |
| Docker / Compose | Docker CLI 29.9.2；Docker Compose 5.6.1 |
| 目标分支 / 提交 | `phase-1-reproducible-baseline` / `ded67dc3d135cb5f818dd041a073d1808e57c4f9` |
| 仓库初始状态 | 新克隆，分支跟踪 `origin/phase-1-reproducible-baseline`，无已有工作被覆盖 |

### 2026-10-31 已执行操作与结果

1. 检查 Windows、WSL、Docker Desktop、Docker Compose 和 Git。Docker Desktop 4.97.0 已安装，CLI 与 Compose 可执行；Windows 仍存在组件重启标记，WSL 发行版枚举返回 `E_ACCESSDENIED`，Docker Engine API 尚不可用。
2. 使用 `git clone --branch phase-1-reproducible-baseline --single-branch` 克隆指定远端分支。
3. 确认 `Dockerfile`、`compose.yaml`、`data/raw/城市轨道交通工程设计标准.pdf`（7,869,546 bytes）、`docs/DEPLOYMENT.md` 和本验证记录存在。
4. 创建本地 `.env`，公开配置为 `https://api.deepseek.com` / `deepseek-chat`，API 密钥保持空白；已确认 `.env` 同时被 `.gitignore` 和 `.dockerignore` 排除。未配置费用费率，因此后续不得把缺失用量或费用记为零。

### 初始阻塞与当时未执行项

- Windows 自 WSL/Virtual Machine Platform 安装后尚未重启（检查时连续运行约 184 小时），Docker 引擎不能用于镜像构建。
- API 密钥尚未由机器所有者在本地 `.env` 中填写。
- 因以上阻塞，镜像构建、模型准备、索引构建与校验、真实问答、容器重启计时及专用副本备份恢复演练均尚未执行，均不计为通过。

### 重启后的 Docker Desktop 故障处理

1. Windows 重启已完成；检查时系统运行约 0.07 小时，组件重启标记已清除。本地 `.env` 的 API 密钥字段非空，且仍被 Git 忽略；未读取或记录密钥值。
2. Docker Desktop 启动后，Docker CLI 29.9.2 使用 `desktop-linux` context，但 Linux 引擎管道未创建。等待 3 分钟和后续 4/5 分钟均未就绪。
3. Docker Desktop 4.97.0 日志给出稳定复现的根因：写入 `%APPDATA%\Docker\settings-store.json` 时，原子重命名返回 `The system cannot move the file to a different disk drive`，后端随即崩溃。
4. 实测 `%APPDATA%\Docker` 位于 EFS 加密层级。已在获得明确授权后尝试关闭残留进程、取消该目录的新文件自动加密、递归解密配置树，并对原 189-byte 设置文件做 SHA-256 一致性备份后重建；错误仍复现。
5. 原 EFS 配置目录已保留为 `%APPDATA%\Docker.efs-backup-20261031`；另有工作区设置文件备份 `work/docker-settings-backup/settings-store.json.before-efs-fix`。未执行恢复出厂设置。
6. 尝试将 Docker 配置迁移到未加密目录并建立联接时，受限执行账户因没有机器所有者的 EFS 证书而收到 `Access denied`。该账户无法完成必须由登录用户执行的 EFS 操作。Docker 引擎实际构建/启动因此仍未通过。
7. 机器所有者随后在本机账户下完成 `%APPDATA%\Docker` 解密。复查结果为目录和 `settings-store.json` 均标记 `U`，且 Docker 子目录不再自动加密新文件；原 `settings-store.json` 跨加密边界重命名故障不再出现。
8. Docker 后端已实际进入 Linux/WSL 引擎启动流程，但在 `%LOCALAPPDATA%\Docker\run\sailor-ingest.sock` 的旧 0-byte Unix socket 重解析点上崩溃，错误为 `The file cannot be accessed by the system`。受限执行账户使用 PowerShell 删除及 `fsutil reparsepoint delete` 均返回 Windows error 1920；该临时文件需由机器所有者账户清理后再继续。此时 `desktop-linux` context 已配置，但 Linux Engine 尚未运行，不能记为通过。
9. 机器所有者清理 `%LOCALAPPDATA%\Docker\run` 与 `%LOCALAPPDATA%\docker-secrets-engine` 后，Docker 在干净目录中重新创建 socket，但仍立即在 `sailor-ingest.sock` 的 rename 上返回 error 1920。复查显示 `%LOCALAPPDATA%\Docker` 顶层仍为 EFS 加密目录，而 `run` 子目录为未加密；由此确认不是残留 socket，而是 Windows AF_UNIX socket 位于 EFS 加密父路径时不可访问。需由拥有 EFS 证书的机器所有者解密 Local Docker 顶层后继续。

### 实机部署完成结果

机器所有者随后完成 Local Docker 目录解密。Docker Desktop 仍不能可靠地从原用户配置目录启动，因此本次验证使用未加密的替代配置目录启动 Docker Desktop：`APPDATA=C:\DockerDesktopProfile\Roaming`、`LOCALAPPDATA=C:\DockerDesktopProfile\Local`。启动时沿用本机已有的回环代理环境，但本记录不保存代理地址或认证信息。该方式下 Docker Linux Engine 可用；最终 `docker version` 报告 Server 29.9.2、API 1.56、`linux/amd64`。

| 项目 | 最终实测结果 |
|---|---|
| Windows / WSL | Windows NT 10.0.26200.0；WSL 3.0.3.0；Linux 内核 6.18.54.1-1 |
| Docker Desktop / Engine / Compose | 4.97.0 / 29.9.2 / 5.6.1 |
| CPU / 内存 | Intel Core i5-12450H，12 逻辑处理器；15.7 GiB |
| 最终 C 盘剩余空间 | 37.3 GiB（40,073,457,664 bytes） |
| 分支 / 提交 | `phase-1-reproducible-baseline` / `ded67dc3d135cb5f818dd041a073d1808e57c4f9` |
| 镜像 | `agentic-rag-rag-web:latest`；`sha256:8c4ee33c8052839c64139d4b25bd563bd4e737b7af28ebd6a9818cd481c09160`；30,105,472,912 bytes |
| 嵌入 / 重排模型 | `BAAI/bge-small-zh-v1.5` / `BAAI/bge-reranker-base` |
| 生成 API / 模型 | `https://api.deepseek.com` / `deepseek-flash`；密钥仅保存在被 Git 忽略的本地 `.env` |
| 文档 ID | `ee1309eebe902d704ba549b3dd573c868491b461128c0068a6cb51328e2ebbfc` |
| 索引版本 / 分块数 | `cbbc823c77c8acf3bcdddad7e124c20f0e1fe0329241f125cfb391c0d8f950ff` / 3701 |
| Web | `http://localhost:8501`；容器最终状态 healthy |

#### 构建、模型、索引与启动

1. Docker Hub 域名的直接访问在本机网络中超时；首次无缓存构建在 24.18 秒后失败。确认本机已有回环代理后，将代理仅注入 Docker Desktop 进程，官方基础镜像 `python:3.12-slim` 拉取成功，digest 为 `sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159`，耗时 17.24 秒。
2. `docker compose build --no-cache` 成功，耗时 2,121.15 秒（35 分 21 秒）。其中依赖准备约 1,425.4 秒、镜像层导出约 453.5 秒、解包约 101.2 秒。镜像约 28.0 GiB；锁定依赖包含 CUDA 13 / PyTorch 组件，而本机为 CPU 验证环境，这是当前镜像体积和磁盘占用的重要限制。
3. `docker compose run --rm rag-web engineering-rag-model prepare` 成功，耗时 834.26 秒；随后 `engineering-rag-model check` 返回 `status: ready`。模型卷约 1.231 GB，ready 标记为 `/models/ready/cf549ecce3ea5b272b6903c9.json`。下载使用 Hugging Face 匿名访问，日志提示可能受较低限流影响。
4. 曾误执行不存在的 `engineering-rag-model status` 子命令，CLI 正确拒绝；有效子命令 `prepare` 和 `check` 的结果不受影响。
5. `docker compose run --rm rag-web engineering-rag-index build` 成功，耗时 265.53 秒；`engineering-rag-index check` 耗时 1.82 秒并返回 `status: valid`、3701 个分块。
6. `docker compose run --rm rag-web engineering-rag-health ready` 耗时 1.87 秒，configuration、models、index 三项均为 true。
7. `docker compose up -d` 后，从命令开始至容器 healthy 且本机 8501 端口可访问共 8.70 秒。

实际执行的主要命令如下（密钥仅由本机 `.env` 注入，未输出）：

```powershell
docker pull python:3.12-slim
docker compose build --no-cache
docker compose run --rm rag-web engineering-rag-model prepare
docker compose run --rm rag-web engineering-rag-model check
docker compose run --rm rag-web engineering-rag-index build
docker compose run --rm rag-web engineering-rag-index check
docker compose run --rm rag-web engineering-rag-health ready
docker compose up -d
docker compose ps
```

#### 开发集真实问答

仅从项目开发集选取代表性问题；未读取或运行新的独立测试集。三次请求均收到 HTTP 200。费用字段均为 `null`：本次没有配置或取得该实际模型的可信费率，因此不计算估算费用，不能解释为零费用。

| 场景 / 开发集编号 | 请求编号 | 结果 | 检索重试 | 总耗时（服务 / 主机） | 阶段耗时 ms | 模型调用 / 重试 | 输入 / 输出 / 总 token | 费用 |
|---|---|---|---:|---:|---|---:|---:|---|
| 普通回答 `SEM-001`：上下行划分 | `4392bc0c4dbb40eaac27032f8f21d984` | 返回答案，引用校验通过 | 0 | 12,600.165 ms / 43.64 s | retrieval 32.218；rerank 3,892.943；grader 5,901.057；generation 2,773.385 | 2 / 0 | 1,254 / 1,081 / 2,335 | 未计算：未配置可信费率 |
| 补充检索 `MULTI-002`：地下车站站台范围线路平曲线与纵坡 | `11882cadc07f4eb385badabd1a455f1c` | 已触发一次补充检索，之后拒答；开发集标注为可回答，故正确性未通过 | 1 | 16,166.237 ms / 39.85 s | retrieval 121.057；rerank 8,687.517；grader 5,821.543；rewrite 1,535.618 | 3 / 0 | 1,546 / 711 / 2,257 | 未计算：未配置可信费率 |
| 证据不足拒答 `UA-CAND-A01`：四档减振最低分贝 | `bb22152d9ed6409c9af2e930a236147f` | 一次补充检索后拒答，符合开发集不可回答标注 | 1 | 11,669.317 ms / 34.99 s | retrieval 138.146；rerank 5,242.247；grader 4,534.000；rewrite 1,754.484 | 3 / 0 | 1,450 / 673 / 2,123 | 未计算：未配置可信费率 |

补充检索链路的工程行为已真实触发，但 `MULTI-002` 未找到完整的平面曲线证据而拒答，因此不能把多证据问答正确性记为通过。服务阶段总耗时小于主机端观测耗时；差值包含容器命令/API 客户端初始化、模型加载或连接等阶段外开销。

#### 容器重启与索引持久化

执行 `docker compose restart rag-web` 后，至容器 healthy 且 8501 可访问耗时 8.42 秒。随后业务就绪检查通过，索引版本仍为 `cbbc823c77c8acf3bcdddad7e124c20f0e1fe0329241f125cfb391c0d8f950ff`；启动日志没有索引构建动作。因此重启无需重建索引，持久化验证通过。

#### 专用卷备份与恢复演练

1. 创建专用卷 `agentic-rag_rag-indexes-drill-20261031`，将现用 `agentic-rag_rag-indexes` 以只读方式挂载并复制到专用卷，耗时 0.75 秒。现用卷没有写挂载。
2. 演练副本检查通过，耗时 1.45 秒。随后在专用卷的 `/indexes/drill-backups` 中执行 `engineering-rag-index backup`，耗时 1.59 秒。
3. 使用备份目录执行 `engineering-rag-index restore`，耗时 1.62 秒；恢复后检查耗时 1.34 秒，文档 ID、索引版本和 3701 个分块均保持一致。
4. 演练卷共 21,337,543 bytes，备份含 3 个文件。验证后删除该专用卷以释放空间；现用索引卷和模型卷保留。
5. 第一次复制尝试中，PowerShell 变量在 Docker `--mount` 参数中被当作字面量，Docker 在容器启动前拒绝命令；第二次检查尝试也因挂载参数引号解析失败而在容器启动前退出。两次均未改动任何卷；改用明确卷名和绝对路径后成功。

主要演练命令（路径省略为本仓库 PDF 的绝对路径）：

```powershell
docker volume create agentic-rag_rag-indexes-drill-20261031
docker run --rm --user 0 --mount type=volume,src=agentic-rag_rag-indexes,dst=/source,readonly --mount type=volume,src=agentic-rag_rag-indexes-drill-20261031,dst=/target agentic-rag-rag-web:latest sh -c "cp -a /source/. /target/ && chown -R rag:rag /target"
docker run --rm --env-file .env --mount type=bind,src=<PDF绝对路径>,dst=/data/document.pdf,readonly --mount type=volume,src=agentic-rag_rag-indexes-drill-20261031,dst=/indexes agentic-rag-rag-web:latest engineering-rag-index backup --backup-dir /indexes/drill-backups
docker run --rm --env-file .env --mount type=bind,src=<PDF绝对路径>,dst=/data/document.pdf,readonly --mount type=volume,src=agentic-rag_rag-indexes-drill-20261031,dst=/indexes agentic-rag-rag-web:latest engineering-rag-index restore --backup-dir /indexes/drill-backups/ee1309eebe902d704ba549b3dd573c868491b461128c0068a6cb51328e2ebbfc/cbbc823c77c8acf3bcdddad7e124c20f0e1fe0329241f125cfb391c0d8f950ff
docker volume rm agentic-rag_rag-indexes-drill-20261031
```

#### 最终复查与验收结论

最终执行 `docker compose config --quiet`、模型检查、现用索引检查、业务就绪检查和 `docker compose ps`。结果分别为配置有效、模型 ready、索引 valid、三项就绪检查为 true、Web 容器 healthy；现用索引版本未变化。`git diff --check` 通过，Git 仅显示本验证文档有跟踪修改；`.env` 未被跟踪。

| 第五阶段验收项 | 结论 |
|---|---|
| Windows 11、WSL 2、Docker Linux Engine、Compose 可用 | 通过，但 Docker Desktop 需从未加密替代配置目录启动 |
| 指定远端分支、部署文件、原始 PDF 与工作区保护 | 通过 |
| 本地密钥配置且不进入日志、报告或 Git | 通过 |
| 镜像、模型、索引、就绪检查与 Web 启动 | 通过 |
| 普通回答与证据不足拒答 | 通过 |
| 补充检索链路被触发 | 通过 |
| 补充检索代表问题的最终答案正确性 | 原始部署验证时未通过：`MULTI-002` 错误拒答；后续定向修复与实机复验见文末 |
| 请求编号、阶段耗时、调用数、token 记录 | 通过 |
| 费用估算 | 未执行：没有可信费率；未将缺失费用记为零 |
| 容器重启后复用同一索引 | 通过 |
| 保护现用索引的专用卷备份/恢复 | 通过 |
| 第六阶段 | 不在本次范围，未验证、未宣称通过 |

本次没有运行新的独立测试集，也没有改动或验收尚未推送的第六阶段内容。

## 真实问答延迟与费用初步基线

补测日期：2026-10-31（Asia/Shanghai）。本节复用前述 3 条完整请求记录，并从开发集补充 9 条固定请求，总样本 12 条；没有读取或运行 `test_v1` 等独立测试集。重启恢复时间 8.42 秒是容器恢复指标，不计入任何问答延迟统计。

### 运行条件与统计口径

| 项目 | 条件 |
|---|---|
| 主机 | Windows NT 10.0.26200.0；Intel Core i5-12450H；12 逻辑处理器；15.7 GiB 内存 |
| Docker | Docker Desktop 4.97.0；Linux Engine 29.9.2；Compose 5.6.1；`linux/amd64` |
| 镜像 | `agentic-rag-rag-web:latest`；`sha256:8c4ee33c8052839c64139d4b25bd563bd4e737b7af28ebd6a9818cd481c09160` |
| 索引 | `cbbc823c77c8acf3bcdddad7e124c20f0e1fe0329241f125cfb391c0d8f950ff`；3701 chunks |
| 模型 | embedding `BAAI/bge-small-zh-v1.5`；reranker `BAAI/bge-reranker-base`；generation `deepseek-flash` |
| 工作流配置 | retrieval top-k 10；evidence top-n 3；每次模型调用超时 30 秒；网络重试上限 1；请求总时限 90 秒；模型调用上限 6 |
| 并发与顺序 | 单并发。新增 9 条在同一个临时容器、同一个 workflow 实例中按固定顺序执行；索引卷和模型卷只读挂载 |
| 新增请求窗口 | 2026-10-31 14:47:44 至 14:49:30（Asia/Shanghai；UTC 06:47:44 至 06:49:30） |
| 首次 / 预热口径 | workflow 初始化耗时 27,112.252 ms，单独记录；初始化后的第 1 条 `SEM-002` 为首次请求，其余 8 条为同进程预热请求。初始化时间不并入请求 `total_ms` |
| 延迟口径 | 主统计使用结构化日志 `request_completed.total_ms`；阶段耗时为同一日志中的累计 retrieval、rerank、grader、rewrite、generation。p50/p95 使用排序样本的线性插值 |
| 用量口径 | 输入、输出和调用次数覆盖 Grader、查询改写、生成以及可计费重试；本批模型网络重试均为 0 |
| 正确性口径 | answerable 题按开发集 gold answer 核对；unanswerable 题以 refuse 为正确；answerable 题 refuse 记为错误拒答 |

### 逐请求记录

`—` 表示该阶段未执行。费用均为估算而非账单实扣；带区间的旧记录因当时未采集缓存命中拆分，区间下界假设全部输入命中缓存、上界假设全部输入未命中缓存。

| 题目 ID / 请求编号 | 场景 | 结果与正确性 | retrieval / rerank ms | grader / rewrite / generation ms | 总耗时 ms | 调用 / 输入 / 输出 token | 缓存命中 / 未命中输入 token | 估算费用 USD |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `SEM-001` / `4392bc0c4dbb40eaac27032f8f21d984` | 普通回答 | answer，正确 | 32.218 / 3,892.943 | 5,901.057 / — / 2,773.385 | 12,600.165 | 2 / 1,254 / 1,081 | 未获取 / 未获取 | 0.00065236–0.00083670 |
| `MULTI-002` / `11882cadc07f4eb385badabd1a455f1c` | 多证据、补充检索 | refuse，错误拒答 | 121.057 / 8,687.517 | 5,821.543 / 1,535.618 / — | 16,166.237 | 3 / 1,546 / 711 | 未获取 / 未获取 | 0.00043124–0.00065850 |
| `UA-CAND-A01` / `bb22152d9ed6409c9af2e930a236147f` | 证据不足、补充检索 | refuse，正确 | 138.146 / 5,242.247 | 4,534.000 / 1,754.484 / — | 11,669.317 | 3 / 1,450 / 673 | 未获取 / 未获取 | 0.00040815–0.00062130 |
| `SEM-002` / `38b019f02c9c4d568e95f10affd5df3e` | 普通回答、首次请求 | answer，正确 | 129.531 / 4,242.693 | 2,324.021 / — / 2,635.492 | 9,332.217 | 2 / 1,940 / 436 | 256 / 1,684 | 0.00051497 |
| `ART-001` / `4960d27fa2d1452386ba204b980c106e` | 普通回答、预热 | answer，正确 | 67.189 / 3,041.411 | 2,201.350 / — / 2,302.027 | 7,612.261 | 2 / 1,422 / 457 | 256 / 1,166 | 0.00044987 |
| `NUM-002` / `585d1282a1a64c7e924cb01edb6c5b34` | 普通回答、预热 | answer，正确 | 43.777 / 2,163.905 | 1,992.417 / — / 1,925.967 | 6,126.322 | 2 / 1,254 / 450 | 256 / 998 | 0.00042047 |
| `TAB-001` / `f93647e8a5ae41c095231668b6ebd464` | 普通回答、预热 | answer，正确 | 87.675 / 2,770.245 | 1,871.204 / — / 2,061.784 | 6,791.208 | 2 / 1,884 / 421 | 256 / 1,628 | 0.00049757 |
| `MULTI-001` / `56da751a4330434c95f0f7a512495d6d` | 多证据、预热 | answer，正确 | 64.250 / 2,535.372 | 1,797.769 / — / 2,498.061 | 6,895.818 | 2 / 1,432 / 493 | 256 / 1,176 | 0.00047297 |
| `MULTI-003` / `eef1668578e04e26bdcfd5847bf35b31` | 多证据、补充检索、预热 | refuse，错误拒答 | 151.949 / 5,618.809 | 6,848.426 / 2,469.427 / — | 15,088.988 | 3 / 1,430 / 1,143 | 384 / 1,046 | 0.00084385 |
| `UA-001` / `a1645c378c0144ef8e2fb6c781d0b61e` | 证据不足、补充检索、预热 | refuse，正确 | 109.771 / 7,176.048 | 8,626.748 / 1,931.429 / — | 17,844.364 | 3 / 1,512 / 582 | 512 / 1,000 | 0.00050074 |
| `UA-CAND-A02` / `781fcbcbe4074cb5835d65e5e901b8ab` | 证据不足、补充检索、预热 | refuse，正确 | 185.970 / 15,213.664 | 6,251.344 / 1,805.855 / — | 23,457.318 | 3 / 1,816 / 796 | 640 / 1,176 | 0.00065592 |
| `UA-CAND-D01` / `b473e2b0f1ea4871b3d639167b521a8d` | 部分证据、补充检索、预热 | refuse，正确 | 180.844 / 6,214.563 | 4,621.737 / 1,755.823 / — | 12,773.498 | 3 / 1,639 / 710 | 512 / 1,127 | 0.00059659 |

### 延迟与结果汇总

| 样本范围 | 有效样本 | service error | 正确 / 错误拒答 | p50 ms | p95 ms | 最大 ms | 补充检索比例 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 全部 | 12 | 0 | 10 / 2 | 12,134.741 | 20,370.193 | 23,457.318 | 6/12，50.0% |
| 新增同进程预热请求 | 8 | 0 | 6 / 2 | 10,192.880 | 21,492.784 | 23,457.318 | 4/8，50.0% |
| 普通回答 | 5 | 0 | 5 / 0 | 7,612.261 | 11,946.575 | 12,600.165 | 0/5，0% |
| 多证据 | 3 | 0 | 1 / 2 | 15,088.988 | 16,058.512 | 16,166.237 | 2/3，66.7% |
| 证据不足或部分证据拒答 | 4 | 0 | 4 / 0 | 15,308.931 | 22,615.375 | 23,457.318 | 4/4，100% |

首次请求 `SEM-002` 的服务总耗时为 9,332.217 ms，主机侧计时为 9,333.459 ms；新增其余请求的主机侧计时与服务日志相差均小于 3 ms。旧 3 条使用独立容器调用，主机计时包含容器和模型初始化，不与同进程预热请求混算。全 12 条累计模型调用 30 次、输入 18,579 token、输出 7,953 token。没有 API/系统错误，但两条 answerable 多证据题错误拒答，正确率为 83.3%；这类错误样本完整保留在延迟和费用统计中。

### 服务商费率、缓存分档与费用

实际服务商为 DeepSeek，模型名 `deepseek-flash`，请求使用 OpenAI-compatible Chat Completions API。费率取自 [DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/)，于 2026-10-31 核对；官方变更记录说明 DeepSeek-V4.1-Flash 新价格自 2026-09-10 04:00 UTC 生效。币种为 USD，单位均为每 1,000,000 token。

| 时段 | 缓存命中输入 | 缓存未命中输入 | 输出 |
|---|---:|---:|---:|
| 非高峰 | $0.003 | $0.15 | $0.60 |
| 高峰 | $0.006 | $0.30 | $1.20 |

官方定义高峰为周一至周五 01:00–04:00 和 06:00–10:00 UTC（中国法定节假日除外），其他时间均为非高峰，周末全天为非高峰。本次新增请求发生在 2026-10-31（周六），因此使用非高峰费率。DeepSeek 默认启用上下文缓存，API `usage` 返回 `prompt_cache_hit_tokens` 和 `prompt_cache_miss_tokens`；参考 [DeepSeek Context Caching](https://api-docs.deepseek.com/guides/kv_cache/)。

新增请求按以下公式逐次计算，并汇总一次问答内所有 Grader、改写和生成调用：

```text
估算费用 USD =
缓存命中输入 token / 1,000,000 × 0.003
+ 缓存未命中输入 token / 1,000,000 × 0.15
+ 输出 token / 1,000,000 × 0.60
```

新增 9 条合计缓存命中输入 3,328 token、缓存未命中输入 11,001 token、输出 5,488 token，精细分档估算合计 $0.00495293，平均 $0.00055033/次。旧 3 条只有总输入/输出 token，费用区间合计 $0.00149175–$0.00211650。因此全 12 条总费用估算区间为 $0.00644468–$0.00706943，单次平均为 $0.00053706–$0.00058912。

已采集请求中费用最高的是错误拒答 `MULTI-003`，估算 $0.00084385；它执行 3 次模型调用并产生 1,143 个输出 token。费用和正确率分开统计，错误拒答没有从费用中剔除。本次无服务商账单或控制台权限，未做实扣对账，所有金额均标为估算。

当前应用的 `RAG_INPUT_COST_PER_MILLION` / `RAG_OUTPUT_COST_PER_MILLION` 只能表达两种统一费率，不能同时表示缓存命中、缓存未命中以及峰谷价格。生产日志目前也只累计总输入 token。新增基线通过一次性测量脚本读取服务商返回的缓存字段，没有修改应用代码；在正式费用监控补齐分档字段前，不应把应用日志中的简单费用字段视为精确账单。

### 暂定门槛与超限处理

这些门槛只适用于上述单并发、同硬件、同镜像、同索引和非高峰费率条件，是 12 条小样本形成的初步基线，不承诺稳定性能：

- 单并发预热后服务总耗时 p95 暂定不高于 25 秒；单请求超过 25 秒保留样本并标记慢请求，超过 30 秒进入性能故障调查。当前预热 p95 为 21.493 秒，通过该初步门槛。
- 非高峰平均估算费用暂定不高于 $0.0007/次，单请求费用预警线为 $0.001；高峰时价格翻倍，必须按高峰费率另算，不能沿用非高峰门槛。当前平均费用上界 $0.00058912，通过初步预算门槛。
- service error 的小样本目标为 0；出现任何 error 都保留并单独调查，不从延迟或费用样本中删除。当前为 0/12。
- answer/refuse 正确性与性能、费用分开验收，错误结果仍计时计费。暂定错误结果比例不高于 10%；当前为 2/12（16.7%），未通过，问题集中在多证据完整性与补充检索。
- 预算超限时先检查缓存命中拆分、峰谷时段、输出 token 和模型调用数；若连续 3 条超过单请求预警线则停止后续批量调用并复核配置。token 或缓存拆分缺失时标为“未获取”并给出区间，不按零处理。

## 两条错误拒答的定位、修复与定向实机复验

复验日期：2026-10-31（Asia/Shanghai）。本节只使用 `dev_v0` 中的两条错误拒答案例及 3 条开发集对照题，没有运行独立测试集。原始 12 条基线及其 2/12（16.7%）结果保留不改；下面是修复后的定向回归，不冒充一次新的完整 12 题重测。

### 根因分类

| 案例 | 初轮召回 | 补充检索与重排 | Grader | 结论 |
|---|---|---|---|---|
| `MULTI-002` | 召回 7.3.2 纵坡，但缺 7.2.1 平面曲线，属于召回缺失 | 聚焦缺失要求后召回 7.2.1 的 chunk 441；完整问句重排时该证据降至第 8。条款又跨 chunk 441/442，真正含“A 型车 1500m、B 型车 1000m”的 chunk 442 未进入最终 3 条证据，属于重排/切块丢证据 | 在证据不完整时判 insufficient，行为正确 | 召回缺失与同条款切块后的重排丢证据共同导致；不是 Grader 误判 |
| `MULTI-003` | 召回 4.2.6 停车列位，但缺 2.0.14 全自动运行定义，属于召回缺失 | 原重写仍重复整题，已支持的停车问题主导召回；只用缺失要求检索时 2.0.14 为聚焦重排第 1 | 在缺定义时判 insufficient，行为正确 | 补充查询不够聚焦；不是重排丢证据，也不是 Grader 误判 |

最小修复没有修改 Grader 提示词、充分性标准、最大重试次数或最终证据条数：

1. 有明确 `missing_requirements` 时，第二轮直接以缺失要求检索，不再把已支持问题拼回查询；仅在缺失要求为空时保留原 QueryRewriter 回退。
2. 第二轮用缺失要求单独重排，并保证聚焦证据进入原有 top-3。
3. 仅当聚焦首证据存在“同来源、同条款、相邻 chunk_id ±1”时扩展相邻块，最多保留两个聚焦片段；不同条款、不同文档不会扩入。此规则使 7.2.1 的 chunk 441/442 能共同进入 Grader，而没有放宽拒答条件。

### 测试与真实请求

容器内 `unittest` 共 11 项通过：工作流 9 项、检索器 2 项。新增回归覆盖缺失要求聚焦、聚焦证据保留、同条款相邻块扩展，以及不同条款/不同来源不得扩入。宿主机没有可用的 `uv`，因此测试在现有生产镜像中挂载修改后的 `src` 和 `tests` 执行；这是环境限制，不是测试失败。

最终定向真实回归使用修改源码、现有模型卷和现有索引版本 `cbbc823c77c8acf3bcdddad7e124c20f0e1fe0329241f125cfb391c0d8f950ff`。费用沿用上文 2026-10-31 核对的 DeepSeek 周末非高峰 USD 费率；本轮结构化日志未取得缓存命中/未命中拆分，故按“全部输入命中/全部输入未命中”给出估算区间，未把缺失用量记为零。

| 题目 / 请求编号 | 预期 / 实际 | retrieval / rerank ms | grader / generation ms | 总耗时 ms | 调用 / 输入 / 输出 token | 估算费用 USD |
|---|---|---:|---:|---:|---:|---:|
| `MULTI-002` / `6d1e47af15a8429e81cefcdefa8e74cf` | answer / answer，正确；一次补充检索 | 299.745 / 15,117.706 | 9,827.625 / 5,139.545 | 30,385.654 | 3 / 2,745 / 1,628 | $0.00098504–$0.00138855 |
| `MULTI-003` / `6fafecfabc09480391fb54ac362d16d7` | answer / answer，正确；一次补充检索 | 259.516 / 13,691.404 | 5,163.729 / 4,583.195 | 23,698.574 | 3 / 1,882 / 1,230 | $0.00074365–$0.00102030 |
| `UA-CAND-A01` / `1d113990a0ce497fa556f2b2cd5e3895` | refuse / refuse，正确 | 292.380 / 10,836.303 | 5,447.941 / — | 16,577.034 | 2 / 1,208 / 689 | $0.00041702–$0.00059460 |
| `UA-001` / `d3398866fe7a478bb30e82588a3686ab` | refuse / refuse，正确 | 258.376 / 15,647.583 | 3,726.083 / — | 19,632.593 | 2 / 1,369 / 366 | $0.00022371–$0.00042495 |
| `SEM-001` / `689910be8fca4b2f87201bb9cff5eda0` | answer / answer，正确 | 123.847 / 3,822.982 | 5,281.079 / 2,607.324 | 11,835.643 | 2 / 1,254 / 1,049 | $0.00063316–$0.00081750 |

定向回归为 5/5 符合预期：两条错误拒答均修复，两条应拒答对照仍拒答，普通回答未回退。曾有一版只保留聚焦重排第一名，`MULTI-002` 请求 `6f9414020c144d79841a70e0289e5094` 仍拒答（23,844.935 ms，证据虽标为 7.2.1，但实际为不含目标句的 chunk 441）；该失败促使加入严格的同条款相邻块规则，失败样本未删除或记为通过。

### 部署后复验

执行 `docker compose build rag-web` 增量重建成功，新镜像为 `agentic-rag-rag-web:latest`，ID `sha256:20c39f767906264c17048592411e5f7712c8132add1df76669c715fd526b4532`，大小 30,105,528,164 bytes。随后 `docker compose up -d --force-recreate rag-web`，从命令开始到 healthy 为 11.435 秒。业务就绪检查三项均为 true；索引仍为上述版本、3701 chunks，没有重建。

在不挂载宿主机源码的正式容器中再次执行 `MULTI-002`，请求 `72000f809f7a424e97ae95e3582afee4` 正确回答并引用 7.3.2、7.2.1；总耗时 22,580.804 ms，retrieval 274.479 ms，rerank 13,389.448 ms，grader 5,825.152 ms，generation 3,090.538 ms，3 次模型调用，输入 2,745、输出 1,105 token。缓存拆分未获取，估算费用为 $0.00067124–$0.00107475。

当前结论：两条已知错误拒答的根因、最小修复和部署后实机验证均完成；没有通过放宽 Grader 降低拒答率。若把两条修复后的结果替换原基线中的对应失败，已知错误结果为 0/12；但完整固定 12 题尚未在新镜像上整体重跑，因此“≤10%”只能记为定向证据已满足，不能记成新的完整 12 题统计结论。
