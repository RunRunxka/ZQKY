# 文档归档与现行说明修正

日期：2026-10-01。用户要求归档旧文档，以 9 月 29 日之后的任务为核心，并清理修正过期说明。本次以 **2026-09-29（含）** 为分界，只整理文档；起点 `main@d70f812777539374743e2ac0becad828fa167552`。

## 实际整理

- 移动 31 个旧 QA 目录、旧 `docs/reviews` 和原 `项目规划`，共 33 个目录、679 个文件，进入 `docs/archive/pre-20260929/`。
- 整理前保存 23 份现行文档原文，包括大篇幅 CURRENT_STATUS/PROJECT_GUIDE、旧三矩阵、09-29 RAG PLAN 和旧启动词。原始文件共 702 份，逐项路径、字节数、sha256 见 [MANIFEST](../../archive/pre-20260929/MANIFEST.json)。
- 保留 09-29 RAG-QUALITY、B0–B3 交付和 B2/B3 后续审查；增加 [现行索引](../../README.md)、[当前接手步骤](../../NEXT_SESSION_START.md)、[近期 QA 索引](../README.md) 与 [归档索引](../../archive/README.md)。
- 修正根 README/AGENTS、CURRENT_STATUS、PROJECT_GUIDE、API/ROUTES、协作模板、相关模块指南与设计入口。题库/知识点/施测/成绩按已交付实现说明；保留教案现有本地功能，明确学情报告、AI 教案升级和练习回流仍待建设。
- 移除旧全页面复刻和默认 B0 的现行任务指令；旧三矩阵改为历史入口，已完成 B1/B2/B3 提示词加历史标记；详细伪代码、DDL 设计与旧证据原文保留。
- 将 B3 审查 2 项 P1、8 项 P2 纳入当前台账。本次未修产品，也未启动 B4；提交本身不代表审查问题已修复。

## 保全和例外

历史报告、冻结件及原始参考材料不改写。近期 RAG 冻结件引用的旧 `RAG-REBUILD-v1/FROZEN-CANDIDATE.json` 在原路径留相同字节的兼容副本。当前说明的后续修改会与旧候选的文档散列不同，不重算旧候选来掩盖差异。

既有许可、有效工程/安全规则、原 Word 模板及用户已有未跟踪设计附件、测试产物保留。本次未改产品源码、依赖锁文件或正式数据，不启动服务、不提交、不推送。

## 检查证据

执行结果见 [verification.json](verification.json)，复核程序见 [verify_documents.py](verify_documents.py)。检查包含归档逐文件散列与字节数、原位兼容副本、现行 Markdown 文件链接、近期冻结证据未修改及差异范围。

实跑结果：**702/702 原文件散列与字节数一致；57 份现行文档的 228 个本地文件链接无缺失；7 个近期证据目录零修改；153 个 B3 产品文件零散列漂移；`git diff --check` 退出码 0**。历史冻结文档与本次现行说明之间的差异是已披露的后续修订。

未执行：npm/pytest/Playwright、真实模型/Word/Qdrant、正式数据库迁移；本次是纯文档整理，不把既有测试结果冒充本次重跑结果。

归档执行记录为 [archive_documents.py](archive_documents.py) 与 [refresh_current_docs.py](refresh_current_docs.py)。它们记录本次一次性整理步骤，不应在现行工作区重复执行。
