# AGENTS.md — 智启课源

> 面向编码智能体的仓库指南。读完本文件再动手。
> **2026-10-11 推倒重做 → 2026-10-12 R0–R9 重建完成 → 2026-10-13 R10 收口**：在最小骨架上
> 按 R 系列批重建了完整教学闭环（八个板块 + 统一问答 + Agent 工具化），并在 R10 处理完用户
> 真机实测四问题（学习问答发送链路、壳包含块、数据清空、闭环测试套件、**删除语义重做**——
> 舍弃归档只留删除 + 拆开交叉引用）。**2026-10-23 R12** 把教案工作台重做为 magic-resume
> 形态的三栏编辑器，正文预览按 Word 模板四表逐行还原，导出目录页码与预览同源。历史完整产品
> （全量期）仍归档于 git tag `archive-full-v1-20261011`——**取回参考的唯一入口**，不要把旧文件
> 直接捞回工作区。

## 1. 项目概述

智启课源是**对话优先的闭环教学 AI 工作台**：`/chat` 统一学习问答承载全部教学 AI 能力；
八个业务板块（教材资料库 / 知识点 / 题库 / 班级管理 / 试卷管理 / 学情分析 / 教案工作台 / 练习）
既是独立页面，也是学习问答里的 Agent 工具（一句话或带文件触发）。

- **架构硬性（用户裁定）**：所有 LLM 调用统一经 **LangChain**（`services/agent/model.py` 模型工厂 +
  `services/llm/` 运行层），多步 AI 流程由 **LangGraph** 编排；业务代码禁止直连供应商 SDK
  （门禁 `tests/test_no_raw_sdk_imports.py`）。
- **红线延续**：AI 输出只进候选、教师确认才落库（写操作走中断确认卡）；学生个人信息不进模型；
  凭证只存后端 `.env`（`apps/api/.env`）经 SecretStore 注入，不进进程环境/日志/前端。
- **装配约定**：业务域按 `app.services.<domain>.assembly:assemble(app, settings)` 逐批装配
  （`main.py _DOMAIN_ASSEMBLIES`，列表顺序即依赖顺序）；缺依赖的域路由 503/501，不假成功。

## 2. 技术栈

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 前端 | Next.js 16（App Router）+ React 19 + TypeScript 5.7 | 正式前端 `apps/web` |
| 样式 | Tailwind CSS 3.4 + 单一 CSS 变量层 | `apps/web/src/styles/globals.css`；字体走 token |
| 状态 | Zustand 5 | 对话单 store（`features/chat/model/store.ts`）|
| 内容渲染 | react-markdown、KaTeX、Mermaid、Chart.js | 消息正文与产物预览 |
| 交互动效 | framer-motion 14 + @radix-ui/react-tooltip | 教案工作台（Reorder 拖拽 / 手风琴 / 悬浮提示）；仅该页客户端加载 |
| 后端 | FastAPI（Python ≥ 3.12，uv 管理） | `apps/api`，SSE 三协议适配 + 八域装配 |
| Agent | langgraph 1.2 + langchain 1.4（core 1.6） | `app/services/agent/`；checkpointer 落 SQLite；模块 LLM 走 `app/services/llm/` |
| 测试 | Vitest（jsdom）+ Playwright + pytest | 单测 / e2e / 后端（后端 1946 例，2026-10-23） |

## 3. 仓库结构

```text
apps/
├── web/                      # Next.js 前端
│   └── src/
│       ├── app/              # 路由：/chat(home)、/lesson-plans、/textbooks、/knowledge-points、
│       │                     #       /question-bank、/practices、/learning-analysis、
│       │                     #       /assessments{,/roster,/papers}、/settings
│       ├── components/       # 公共壳（layout/，含 ModuleWorkspaceShell 业务根登记）与控件（ui/、motion/）
│       ├── features/         # chat / lesson-plan / textbook / knowledge-points / question-bank /
│       │                     # assessments / learning-analysis / practices / model-settings / settings
│       ├── services/         # API 客户端（各域 *-api.ts）、SSE 客户端、导航登记（唯一来源）
│       └── styles/           # globals.css / motion.css
└── api/                      # FastAPI 后端
    ├── app/api/v1/           # health/capabilities/chat/agent/model_* + 八域路由 + workflow_jobs/export_artifacts
    ├── app/services/         # agent（编排+工具）/ llm（LangChain 运行层）/ 八域服务 + 各域 assembly.py
    ├── app/providers/llm/    # 三协议供应商适配（38 供应商注册表）
    ├── app/repositories/     # 四库仓储（textbook_catalog/knowledge/question_bank/teaching）+ vector_store/jobs
    ├── app/core/             # config / secrets / sqlite / migrations（四库追加式）/ data_lock
    ├── app/resources/        # 教案模板（lesson_templates/）
    └── tests/                # pytest（1946 例；入口见 §4 环境坑）
tests/                        # e2e（Playwright，系统 msedge 通道，自起 5174）与 fixtures
docs/                         # 权威文档（CURRENT_STATUS / PROJECT_GUIDE / API / ROUTES /
                              #          MULTI_AGENT_COLLABORATION_PROPOSAL）
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
npm.cmd run test:e2e      # Playwright e2e（自起 5174；系统 msedge 通道）
npm.cmd run check         # typecheck + lint + unit + build 串跑
```

**已知环境坑（务必遵守）**：
- 后端一律 `uv run python -m <module>`（pytest/uvicorn 均然）——`.venv\Scripts\*.exe`
  入口的 launcher 可能内嵌旧路径（F:\ZQKY 曾是 H:\备份xuexi\智启课源 的 junction），
  直接走 exe 会 ModuleNotFoundError。
- 前端单测必须 `NODE_OPTIONS=--no-experimental-webstorage`（Node 26 jsdom 假失败）。
- Playwright 用**系统 msedge 通道**（`playwright.config.ts` 已默认；自写脚本用
  `chromium.launch({ channel: 'msedge' })`），本机没有自带 chromium 二进制。
- `npm.cmd run check` 是串行链：单测挂则 build 不跑；`ScoreImportPanel` 有已知负载型 flake，
  单跑/复跑即绿（先复跑再下结论）。
- **不要在 dev server 运行时执行 `npm.cmd run build`**：`next build` 会改写 `apps/web/.next`，
  而 Turbopack 开发服务器仍持有旧模块工厂，浏览器会报
  `(0, ...someExport) is not a function`（典型：设置 → 模型与连接 →「自动获取信息」）。
  处理顺序：停 dev → 删 `apps/web/.next` → 重新 `npm.cmd run dev` → 浏览器
  **Ctrl+Shift+R 硬刷新**。同理，HMR 出现莫名其妙的 `is not a function` 时先清 `.next` 再重启。

## 5. 代码组织规范

- **路由薄、业务厚**：`app/` 只负责路由、布局、页面状态；业务进 `features/<module>`。
- **类型分层**：跨模块类型进 `contracts/`；模块专有类型留在模块内。
- **能力注入**：页面经显式 props/Context/服务接口获得能力；不在模块顶层读
  `window`/`document`/localStorage；浏览器专用能力置于客户端生命周期内。
- **单一后端**：不要借 Next.js Route Handlers 起第二套业务后端。
- **依赖纪律**：用根 workspace 与锁文件；常规开发不顺手升级框架或换包管理器。
- **样式纪律**：全站共用 `globals.css` 变量层与字体 token；页面不散写具体字体名。
- **LLM 纪律**：新模块 LLM 调用一律经 `resolve_agent_chat_model` + `services/llm/`（提示词登记
  `PromptSpec` 带版本；结构化输出用 `run_structured`；流式用 `chat_model.astream`）；
  禁止 `openai`/`anthropic` SDK 直连（有门禁测试）。
- **装配纪律**：新业务域写 `app/services/<domain>/assembly.py`（`assemble(app, settings)`），
  在 `main.py _DOMAIN_ASSEMBLIES` 按依赖顺序登记；不要改他人域的装配。
- **前端壳纪律**：新业务页在 `ModuleWorkspaceShell.independentRoots` 登记（无斜杠首段）+
  `navigation.ts` 登记后由壳统一提供侧栏与滚动，页面裸渲染（不自包 WorkspaceShell）。
- **动效与浮层纪律**：拖拽 / 手风琴 / 入场动画用 **framer-motion**（尊重 `useReducedMotion`），
  悬浮提示用 **@radix-ui/react-tooltip**；不引入第二套主题或第二套动效库。
- **教案工作台纪律**：样式作用域 `.lesson-workbench`；三栏 + 悬浮 dock + 面板折叠；预览与导出
  共用 `features/lesson-plan/services/pagination.ts` 的分页与字号口径，导出请求携带
  `sectionPages`（模块 → 正文页码），不得让预览与 docx 目录各算一套。

## 6. 测试与验收要求

- 提交前跑 `npm.cmd run check`；路由、布局改动另跑 e2e（先 `build`）。
- 门禁基线（2026-10-23）：后端 **1946**、前端 **87 文件 771 例**、e2e **17**；数字与命令证据写进
  `docs/CURRENT_STATUS.md`。
- 只跑与变更相关且有意义的场景；**未执行的检查明确写「未执行」及原因，不写「应当通过」**。
- 区分真实服务、本地规则与规划状态；**构建成功不等于业务或视觉验收通过**。
- 自动化用隔离上下文与测试端口，不读写真实草稿/凭证；浏览器自动化用系统 `msedge` 通道
  （本机无自带 chromium），e2e 自起 5174，不碰用户 5173 会话。

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
| [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md) | 唯一进度、问题台账、当前任务、下一动作、交接状态（顶部「当前状态」为门禁数字权威） |
| [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md) | 唯一目标、视觉基准、稳定决定 |
| [docs/API.md](docs/API.md) / [docs/ROUTES.md](docs/ROUTES.md) | 现行接口契约（含删除语义表）/ 路由索引 |
| [docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md](docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md) | 多智能体协作规范：角色、任务卡/结果卡模板、本项目门槛、可复制提示词 |
| [docs/README.md](docs/README.md) / [docs/qa/README.md](docs/qa/README.md) | 文档索引 / 重建后 QA 证据 |
| [test/README.md](test/README.md) | 闭环测试套件与走查顺序 |

重构前的设计与 QA 文档已清理（2026-10-13；协作规范已重写为现行文档）；历史实现与文档的唯一入口是
git tag `archive-full-v1-20261011`。

## 10. 多智能体协作要点

规范、任务卡/结果卡模板与可复制提示词见
[docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md](docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md)。要点：

- 总控负责拆分、依赖、文件归属、集成与最终交付；共享工作区同一文件同一时段仅一个写入者。
- 每个任务需有 ID、版本、负责人、可写范围、验收条件与结果格式；共享契约先定单一负责人。
- 默认由总控独占权威进度文档、验收矩阵、依赖锁文件与最终 Git 操作。
- 保留用户与其他智能体的改动：不切换共享分支、不批量暂存、不清理未知数据、不撤销他人工作。
- 真机验收遵守「自建数据自建自删」：脚本用独立命名空间建链，结束后核对用户数据回到基线。

## 11. 模块级 AGENTS.md

改下列模块前，先读对应文件：

- [apps/web/src/features/chat/AGENTS.md](apps/web/src/features/chat/AGENTS.md) — 对话与 Agent 交互
- [apps/api/AGENTS.md](apps/api/AGENTS.md) — FastAPI 后端（随重建更新）
