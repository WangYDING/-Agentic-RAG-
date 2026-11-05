# 阶段 1 切片 2：三规范知识库构建、发布与恢复记录

记录日期：2026-11-05。范围仅为摄取、身份、索引和知识库快照；用户查询范围选择、跨库检索编排和答案引用展示留到切片 3。

## 完成结论

三份官方 PDF 均已有可核验摄取文本。系统已构建并原子发布一个包含三份规范的知识库快照；单文档索引和整组快照均不可变，活动指针只在整组校验成功后切换。重启加载、候选损坏、构建中断、单文档替换、回滚、发布指针失败和并发发布均有自动测试。

## 正式活动快照

- 快照 ID：`39c3e07c109c07cb1dc331db3055cf041a33498aafb9dde6c2eb022421dd3020`
- 快照 manifest SHA-256：`4c4a15f60428f4714505f0ae7e08c80a5fbe77b79c67b258ed279c98496bd7a6`
- embedding：`BAAI/bge-small-zh-v1.5`，revision 未固定（记录为 `null`），维度 512。
- 切分：300 字符，overlap 50。
- 本地产物目录：`.rag_knowledge_base/`，约 22.9 MB；属于运行产物，不进入 Git。

| 规范身份 | 文档索引版本 | 片段数 | 摄取来源 | manifest SHA-256 |
| --- | --- | ---: | --- | --- |
| `cn.beijing.db11t995@2025` | `02c44af10491c4049b8fb5855aee31183c23edc052814590fc1cd8ff8bd2e1d4` | 3701 | 原生 PDF，`pymupdf-structured-v2-superscript` | `a9b1551fdc65615d5f66a0439bc6da80d8deaee1dc3f9f23d103f6e0f1fed617` |
| `cn.gb50157@2013` | `3d708f4c6be3f986e46b614b48ec3443775213802c2533518060e94ec682b5b2` | 2110 | 已核验逐页 OCR，`rapidocr-page-artifact-v1-clause-spacing` | `3af24834bfc5882dde665f122aaffee51441b25c8d45fd4bde40cae7aefaf8e5` |
| `cn.gb55033@2022` | `e13c5f84abcf574c58d94854a6f2b3f2574e5c56c657e31689fb77e61fe1b927` | 284 | 已核验逐页 OCR，`rapidocr-page-artifact-v1-clause-spacing` | `0038887c4430cee883176b489d53fe0b98d24aa02c2788f6f7f8ac2d0cabcb28` |

首次实际构建暴露出 OCR 条文号可能紧接中文正文（如 `1.0.2本规范`）。旧解析不会丢正文，但会丢条文号元数据。新增反例测试后，匹配规则只放宽到“条文号后为空白或中文”，避免把普通数字串猜成条文；两份 OCR 索引随后重建并产生上述新版本。此前快照 `a2852c703f7436aa8d8c37d6be625aa80ce84c73f24a6876c620a6be453fc3e5` 仍可加载，作为本次实际回滚验证点。

## 验证结果

- Ruff 通过。
- 无生成模型测试：169 passed，1 deselected。
- 知识库新增故障测试：6/6 通过。
- 现有 integration：30 passed，139 deselected；包含阶段 0 单 PDF 索引路径。
- 使用新进程执行 `engineering-rag-kb check`，加载的快照 ID 与发布结果一致。
- 对三份规范分别用其正文特征查询 BM25，均命中自身第 `1.0.2` 条；PDF 页码分别为 27、20、5，返回记录均含正确 `spec_id` 和 `edition_id`。
- 旧快照可显式加载；新快照没有覆盖其文档索引。
- sdist 和 wheel 构建成功；wheel 在源码目录外的新 Python 3.12 环境安装后，`engineering-rag-kb --help` 可启动并显示 build/check/rollback 三个正式子命令。

实际准备命令：

```powershell
uv run --locked engineering-rag-kb build --catalog data/spec_catalog.v1.json --root .rag_knowledge_base --embedding-model BAAI/bge-small-zh-v1.5
uv run --locked engineering-rag-kb check --root .rag_knowledge_base
uv run --locked ruff check .
uv run --locked python -m pytest -m "not model" -o addopts=""
```

## 已知边界

- embedding 模型名称已固定，但本次没有可用的上游 revision 标识；底层 revision 如实记录为未知。索引文件自身及 manifest 已用 SHA-256 固定。
- OCR 表格保留逐行文本和坐标，尚未形成结构化单元格模型。
- 本切片证明三份文档可分别加载和检索，不实现用户选择“全部/指定规范/指定版本”，也不实现跨文档 Dense/BM25 合并；这些属于切片 3。
- 运行目录中的历史 OCR 试验产物未作为正式输入；正式输入仅为目录记录的 `data/derived/ocr/verified/...` 及其哈希。
