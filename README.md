# 智启课源

当前复刻任务（2026-09-08）从 [连续实施到最终交付](docs/replica/NEXT_SESSION_START.md) 继续，最新 [代码与进度复核](docs/replica/REVIEW_S2_S3_2026-09-08.md) 有待修缺陷。完整前端尚未交付；先修R19–R25再连续完成S3–S8。下文D01–D09等旧开发路线为历史，启动命令、数据来源和既有功能说明仍可参考。

中文学习与备课工作台。支持教案本地编辑、规则填充、草稿和 Word/PDF 导出，以及 FastAPI 三协议学习问答、连接与问答模型管理。账号、数据库和云端历史未接入。最新修复、验证边界与前后截图见 [问答与模型管理验收](docs/CHAT_MODEL_REVIEW.md)。

正式工程已经从独立Vite模块迁入Next.js；`教案模板部分`为冻结归档，后续开发请在 `apps/web` 中进行。

## 开始开发

```powershell
Set-Location 'H:\备份xuexi\智启课源'
npm.cmd ci
npm.cmd run dev
```

可选本机后端（D02 起，健康检查与能力状态；不接数据库）：首次运行 `npm.cmd run setup:api` 安装 uv 锁定的 Python 依赖，然后 `npm.cmd run dev:api` 启动 `127.0.0.1:8000`。前端经同源代理访问 `/api/v1/*`，后端不启动时教案与全部页面照常可用。

模型设置：后端启动后访问 [设置页](http://127.0.0.1:5173/settings)，配置 OpenAI Chat Completions / Responses / Anthropic Messages 连接，从服务发现或手动添加模型，保存生成参数、设置默认问答模型，分别进行普通与流式测试。凭证只保存在当前后端进程，重启后重新填写；配置文件不含凭证。

学习问答（D04 起）：配置并测试模型后，访问 [学习问答](http://127.0.0.1:5173/chat) 即可进行流式对话。会话历史保存在当前浏览器（IndexedDB），发送中可停止，失败可重试且不丢已输入内容。RAG、附件解析与工具调用仍为规划中。注意：后端重启后默认模型的凭证需要到设置页重新填写，凭证缺失时问答页会明确提示且不会发送请求。

打开 [学习问答](http://127.0.0.1:5173/chat)。根地址自动跳转到该页面；教案工作台从导航或 [直达链接](http://127.0.0.1:5173/lesson-plans) 进入。本机草稿与旧版使用同一地址、键名和JSON版本；请一直使用 `127.0.0.1`，`localhost`或其他端口属于不同浏览器来源。

已安装依赖时直接运行 `npm.cmd run dev`。先前任务启动的服务如果仍在运行，无需再启动；端口冲突时检查进程归属。

生产本地预览：`npm.cmd run build` 后运行 `npm.cmd run start`。两种服务都只监听本机，均使用5173，不能同时启动。

## 交给下一位开发者

按顺序读取：[AGENTS.md](AGENTS.md) → [当前决策](docs/DECISIONS.md) → [任务清单](docs/TASKS.md) → [交接记录](docs/HANDOFF.md) → 修改范围内的目录级AGENTS.md。

最新开发路线见 **[完整开发计划与 AI 执行任务包](docs/IMPLEMENTATION_PLAN.md)**。按 D01–D09 单项执行：先统一“规划中”入口，再接真实模型学习问答，随后完成沿用教案风格的 A3/A4 本地组卷、右侧实时预览和 DOCX/PDF 导出。本期不接数据库；教材库、题库、RAG、MCP 与 Skills 预留接口和状态。

上述是待实施计划，当前可用功能仍以本文件开头和 ROUTES 为准。本次只更新规划文档，没有实现新页面或模型服务。旧“项目规划”中的全站复刻与数据库优先任务包仅作历史参考。

可以直接发送：

> 请先读取根AGENTS.md、docs/DECISIONS.md、docs/TASKS.md和docs/HANDOFF.md，再检查目标模块及其目录级规范。只完成我接下来指定的任务；报告实际验证和剩余限制，不在冻结归档中开发。

首次继续开发可直接使用完整计划第16节的提示词，从 D01 开始；已经完成的任务先核实，不重复搭建。

## 工程结构

| 目录 | 作用 |
| --- | --- |
| `apps/web/src/app` | 路由、布局、错误与规划状态页 |
| `apps/web/src/components` | 公共布局与控件 |
| `apps/web/src/features/lesson-plan` | 正式教案模块 |
| `apps/web/src/services`、`contracts` | 共用导航、HTTP适配器和类型 |
| `apps/api` | 后端目录与接口规划，本次不运行服务 |
| `assets/templates/source` | 模板源副本及SHA256清单 |
| `docs` | 架构、决策、路由、接口、任务与交接 |
| `scripts`、`tests` | 模板工具、示例与浏览器回归 |
| `infra` | 后续部署规划 |
| `项目规划`、`教案模板部分` | 原始规划与冻结旧版 |
| `_work`、`test-results` | 本机产物，不进入版本管理 |

## 统一命令

| 命令 | 用途 |
| --- | --- |
| `npm run dev` | 开发服务 |
| `npm run typecheck` | Next路由类型和TypeScript检查 |
| `npm run lint` | ESLint，警告也视为失败 |
| `npm run test:unit` | 规则、数据、状态和存储单元测试 |
| `npm run build` | 生产构建 |
| `npm run start` | 启动已构建应用 |
| `npm run test:e2e` | 启动5174隔离服务并做浏览器回归，需先构建 |
| `npm run setup:api` | 首次安装后端依赖（uv sync，Python 3.12） |
| `npm run dev:api` | 启动本机后端 127.0.0.1:8000 |
| `npm run test:api` | 运行后端 pytest |

技术版本：Next.js 16.3.4、React 19.2.8、Tailwind 3.4.17；后端 Python 3.12（uv 管理）、FastAPI 0.141.1；其余以根 `package-lock.json` 与 `apps/api/uv.lock` 为准。本次在Windows、Node.js 26.2.0验证。Node环境需满足Next.js依赖要求。
| `npm run template:build` | 从正式模板副本构建派生模板/schema |
| `npm run template:verify` | 检查根原件及源副本SHA256 |
| `npm run check` | 类型、Lint、单测和构建串行检查 |

浏览器测试在Windows默认使用本机Edge；其他系统默认使用Playwright Chromium，首次可运行 `npx playwright install chromium`。可设置 `PLAYWRIGHT_CHANNEL` 切换已安装浏览器。工具从项目依赖加载，不引用个人Codex缓存。

本地草稿只有当前一份，清理浏览器数据会丢失；可导出JSON备份。PDF在打印对话框选择“另存为PDF”，不是服务端一键下载。Word/WPS最终人工版式验收仍待完成。详见[教案模块说明](docs/modules/lesson-plan/README.md)。
