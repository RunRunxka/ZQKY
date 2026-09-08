# 智启课源

以 **智启课源品牌**复刻 `F:\DeepTutor` **v1.6.5 / 42fab3cf429a1fbf36b257ab8d116a3814964202** 的全部产品前端页面、AI 交互和原有动画。正式工程在 `apps/web`，参考仓库只读。

**当前未达到最终交付标准。** S5-D 建立了文本阅读切片，但本次独立审查发现数据丢失及交互缺陷；先修复，再补齐参考交互。S5-E～I、S6～S8 仍未完成。批次测试通过不等于完整复刻验收通过。

## 文档入口

| 文档 | 唯一职责 |
| --- | --- |
| [开发规则](AGENTS.md) | 工作范围、数据保护和工程规则 |
| [项目说明](docs/PROJECT_GUIDE.md) | 当前目标、技术结构、数据流、允许差异、Git 恢复方法 |
| [当前进度](docs/STATUS.md) | 唯一进度与交接入口，当前缺陷、验证边界、下一动作 |
| [下一会话执行提示词](docs/replica/NEXT_SESSION_START.md) | 从当前断点连续实施到最终验收 |
| [阅读代码审查](docs/reviews/READING_REVIEW_2026-09-08.md) | 本次源码依据、复现与修复验收要求 |
| [页面矩阵](docs/replica/PAGE_MATRIX.md) · [AI 交互矩阵](docs/replica/AI_INTERACTIONS.md) · [动画矩阵](docs/replica/MOTION_MATRIX.md) | 逐项验收，不另抄阶段统计 |
| [路由索引](docs/ROUTES.md) · [后端 API](docs/API.md) | 运行时入口和真实接口 |

旧 HANDOFF、TASKS、规划和 review 已合并到 `docs/archive/`，原文件映射与 SHA256 见 [归档清单](docs/archive/MANIFEST.json)。其中旧提示词、旧“已完成”结论不是当前指令。原始 `项目规划/` 和 Word/模板原件保留。

## 本地启动

```powershell
Set-Location 'H:\备份xuexi\智启课源'
npm.cmd ci
npm.cmd run dev
```

前端 `http://127.0.0.1:5173`，首页 `/chat`，教案 `/lesson-plans`。保持原浏览器来源；`localhost`、`127.0.0.1` 与不同端口的数据互不相同。已有依赖时无需重复 `ci`；不要停止归属不明的服务。

真实问答需另开终端运行 `npm.cmd run setup:api`（首次）及 `npm.cmd run dev:api`，后端监听 `127.0.0.1:8000`。在设置中配置连接和模型；当前凭证仅在后端进程内，重启后需重填。模拟模式不调用供应商或 MCP。生产预览用 `npm.cmd run build` 后运行 `npm.cmd run start`。

## 检查与版本

根命令：`npm.cmd run typecheck`、`npm.cmd run lint`、`npm.cmd run test:unit`、`npm.cmd run build`、`npm.cmd run test:e2e`。typecheck/build 顺序执行；浏览器检查使用隔离上下文与 5174，每批输出目录唯一。本机 Node 26 测试兼容命令和独立审查用例见 [审查报告](docs/reviews/READING_REVIEW_2026-09-08.md)。

本地 Git 基线 `b8cf71f`，标签 `checkpoint/pre-reading-review-20260908`；它是审查前快照，**不是合格发布版**。分支 `codex/replica-review-20260908`。以后按“检查 → 小批改动 → 验证 → 明确范围提交”推进，不自动推送。Git 管代码和文档，不备份浏览器数据库或运行时凭证。
