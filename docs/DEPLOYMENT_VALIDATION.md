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
| 补充检索代表问题的最终答案正确性 | 未通过：`MULTI-002` 错误拒答 |
| 请求编号、阶段耗时、调用数、token 记录 | 通过 |
| 费用估算 | 未执行：没有可信费率；未将缺失费用记为零 |
| 容器重启后复用同一索引 | 通过 |
| 保护现用索引的专用卷备份/恢复 | 通过 |
| 第六阶段 | 不在本次范围，未验证、未宣称通过 |

本次没有运行新的独立测试集，也没有改动或验收尚未推送的第六阶段内容。
