# AGENTS.md — 智启课源（最小骨架版）

> 面向编码智能体的仓库指南。读完本文件再动手。
> **本仓库于 2026-10-11 推倒重做**：只保留对话 + 教学 Agent 编排 + 模型配置的最小骨架；
> 历史完整产品（教学闭环全量：教案/学情/题库/知识点/教材/名单/原卷/施测/成绩/练习）
> 已归档为 git tag `archive-full-v1-20261011`，可随业务重建按需取回参考。

## 1. 项目概述

智启课源的当前形态是一个**对话优先的教学 AI 工作台底座**：一个干净的对话界面
（会话、流式消息、附件上传、Agent 中断确认卡）+ 模型配置（连接/档案/目录/授权）。
业务能力（教学闭环）将随重建在 Agent 工具表中逐项回归——**先对话，再长业务**。

- **当前真实能力**：对话（三协议 SSE 直连模型）、教学 Agent 编排（LangGraph 内嵌，
  工具表为空骨架）、模型配置（含 OAuth 受管认证）、受管资产（上传落 blob）。
- **当前不含**：任何业务页面与业务后端域（原教案/学情/题库/知识点/教材/名单/原卷/
  施测/成绩/练习全部移除，数据已清空）。
- **红线延续**：AI 输出只进候选、教师确认才落库；学生个人信息不进模型；
  凭证只存后端 `.env`（`apps/api/.env`）经 SecretStore 注入，不进进程环境/日志/前端。

## 2. 技术栈

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 前端 | Next.js 16（App Router）+ React 19 + TypeScript 5.7 | 正式前端 `apps/web` |
| 样式 | Tailwind CSS 3.4 + 单一 CSS 变量层 | `apps/web/src/styles/globals.css`；字体走 token |
| 状态 | Zustand 5 | 对话单 store（`features/chat/model/store.ts`）|
| 内容渲染 | react-markdown、KaTeX、Mermaid、Chart.js | 消息正文与产物预览 |
| 后端 | FastAPI（Python ≥ 3.12，uv 管理） | `apps/api`，SSE 三协议适配 |
| Agent | langgraph + langchain + langchain-openai/anthropic | `app/services/agent/`；checkpointer 落 SQLite |
| 测试 | Vitest（jsdom）+ Playwright + pytest | 单测 / e2e / 后端 |

## 3. 仓库结构

```text
apps/
├── web/                      # Next.js 前端
│   └── src/
│       ├── app/              # 路由：/chat（home）、/settings
│       ├── components/       # 公共壳（layout/）与通用控件（ui/、motion/）
│       ├── features/
│       │   ├── chat/         # 对话（store/消息/composer/追问卡/产物面板）
│       │   ├── model-settings/   # 模型连接与档案设置面板
│       │   └── settings/     # 设置页（外观/模型/关于）
│       ├── services/         # API 客户端与本地仓储
│       └── styles/           # globals.css / motion.css
└── api/                      # FastAPI 后端
    ├── app/api/v1/           # health / capabilities / chat / agent / model_* 路由
    ├── app/services/         # agent（编排）/ model_*（运行时）/ assets / jobs（引擎骨架）
    ├── app/providers/llm/    # 三协议供应商适配（38 供应商注册表）
    ├── app/repositories/     # model_config_repository / assets / jobs
    ├── app/core/             # config / secrets / sqlite / migrations 机制
    └── tests/                # pytest（220 用例）
tests/                        # e2e（Playwright）
docs/                         # 骨架文档（旧全量文档随归档 tag 保留）
```

## 4. 开发命令（Windows / 根目录）

```powershell
npm.cmd run dev           # 前端开发服务器 http://127.0.0.1:5173（首页 /chat）
npm.cmd run setup:api     # 首次：uv sync 创建后端环境
npm.cmd run dev:api       # 真实后端 http://127.0.0.1:8000
npm.cmd run build         # 生产构建（e2e 跑的是上一次构建，改码后先 build）
npm.cmd run typecheck     # TypeScript 类型检查
npm.cmd run lint          # ESLint（0 警告门槛）
npm.cmd run test:unit     # Vitest 单测（需 NODE_OPTIONS=--no-experimental-webstorage）
npm.cmd run test:api      # 后端 pytest
npm.cmd run check         # typecheck + lint + unit + build 串跑
```

**已知环境坑（务必遵守）**：
- 后端一律 `uv run python -m <module>`（pytest/uvicorn 均然）——`.venv\Scripts\*.exe`
  入口的 launcher 可能内嵌旧路径（F:\ZQKY 曾是 H:\备份xuexi\智启课源 的 junction），
  直接走 exe 会 ModuleNotFoundError。
- 前端单测必须 `NODE_OPTIONS=--no-experimental-webstorage`（Node 26 jsdom 假失败）。

## 5. 代码组织规范

- **路由薄、业务厚**：`app/` 只负责路由、布局、页面状态；业务进 `features/<module>`。
- **类型分层**：跨模块类型进 `contracts/`；模块专有类型留在模块内。
- **能力注入**：页面经显式 props/Context/服务接口获得能力；不在模块顶层读
  `window`/`document`/localStorage；浏览器专用能力置于客户端生命周期内。
- **单一后端**：不要借 Next.js Route Handlers 起第二套业务后端。
- **依赖纪律**：用根 workspace 与锁文件；常规开发不顺手升级框架或换包管理器。
- **样式纪律**：全站共用 `globals.css` 变量层与字体 token；页面不散写具体字体名。

## 6. 测试与验收要求

- 提交前跑 `npm.cmd run check`；路由、布局改动另跑 e2e（先 `build`）。
- 只跑与变更相关且有意义的场景；**未执行的检查明确写「未执行」及原因，不写「应当通过」**。
- 区分真实服务、本地规则与规划状态；**构建成功不等于业务或视觉验收通过**。
- 自动化用隔离上下文与测试端口，不读写真实草稿/凭证。

## 7. 数据、凭证与安全边界

- **凭证**：API Key 只存后端 `apps/api/.env`；`.env.example` 只含空值；
  密钥不进前端、源码、日志、截图、测试样本。
- **Agent 模型接入**：LangChain 官方包**必须显式传 key**（本地免 Key 用占位符），
  构造前断言 `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` 未在进程环境出现。
- **参考产品只读**：`F:\DeepTutor` 固定提交不升级、不写入；教材原文件只读。
- **数据保护**：不覆盖用户正在编辑的浏览器会话；读取失败/结构损坏不当空库覆盖。
- **不外发**：不发布网站、不推送远程、不发外部消息，除非用户明确授权。

## 8. Git 约定

- 检查 → 小批改动 → 验证 → 明确范围提交；**不自动推送/部署，不改全局 Git 身份**。
- 开工读取现场分支/HEAD，不自动切换共享分支。
- 撤销明确提交优先 `git revert`，不用 `reset --hard`/`clean -fd`。
- **归档 tag `archive-full-v1-20261011` 是历史完整产品唯一入口**：需要旧实现参考时
  `git show archive-full-v1-20261011:<path>`，不要把旧文件直接捞回工作区。

## 9. 文档地图

| 文档 | 职责 |
| --- | --- |
| [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md) | 唯一进度、问题台账、当前任务、下一动作 |
| [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md) | 唯一目标、视觉基准、稳定决定 |
| [docs/API.md](docs/API.md) / [docs/ROUTES.md](docs/ROUTES.md) | 现行接口契约 / 路由索引 |
| [docs/archive/History.md](docs/archive/History.md) | 旧合并历史（只读，非当前指令） |

## 10. 多智能体协作要点

- 总控负责拆分、依赖、文件归属、集成与最终交付；共享工作区同一文件同一时段仅一个写入者。
- 每个任务需有 ID、版本、负责人、可写范围、验收条件与结果格式；共享契约先定单一负责人。
- 默认由总控独占权威进度文档、验收矩阵、依赖锁文件与最终 Git 操作。
- 保留用户与其他智能体的改动：不切换共享分支、不批量暂存、不清理未知数据、不撤销他人工作。

## 11. 模块级 AGENTS.md

改下列模块前，先读对应文件：

- [apps/web/src/features/chat/AGENTS.md](apps/web/src/features/chat/AGENTS.md) — 对话与 Agent 交互
- [apps/api/AGENTS.md](apps/api/AGENTS.md) — FastAPI 后端（随重建更新）
