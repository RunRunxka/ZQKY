# AGENTS.md — 智启课源

> 面向编码智能体的仓库指南。读完本文件再动手；改动某个模块时，先读该模块目录下的 `AGENTS.md`。
> 当前进度与下一动作只看 [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md)，目标与稳定决定只看
> [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md)；本文件不保存进度。

## 1. 项目概述

智启课源是一套面向教师备授课场景的 Web 应用：以**学习问答**（真实大模型 SSE）为核心，
配套**教案工作台**（本地规则填充 + Word/PDF 导出）、**教材资料库**、**书籍/课程**、
**教材 RAG 检索**（本地 Ollama 引擎）与**模型/连接管理**。前端复刻自 DeepTutor v1.6.5
（固定提交 `42fab3cf…`，只读对齐、不升级、不写入），用智启课源品牌与蓝色主题。

- **真实服务**：学习问答（三协议 SSE）、教材 RAG（本地引擎）、模型连接/目录/发现。
- **本地规则**：教案填充与导出、书籍生成（本地模拟执行器）、知识库登记（显式模拟）。
- **规划中（无实现，导航标「规划中」徽标）**：协同写作、沉浸阅读、学习空间、智能组卷、题库、模板中心。
- **已移除**：Whisper 密室、笔记本、Agent 任务（2026-09 清理；历史见 `docs/archive/History.md`）。

## 2. 技术栈

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 前端框架 | Next.js 16（App Router）+ React 19 + TypeScript 5.7 | 正式前端 `apps/web` |
| 样式 | Tailwind CSS 3.4 + 单一 CSS 变量层 | `apps/web/src/styles/globals.css`；字体走 token（`--font-ui` 等） |
| 状态 | Zustand 5 | 双 store + 统一 ChatService 事件（chat） |
| 内容渲染 | react-markdown、KaTeX、Mermaid、Chart.js | 公式/图表/流程图 |
| 文档导出 | docxtemplater + PizZip | 教案 Word 导出 |
| 后端 | FastAPI（Python ≥ 3.12，uv 管理） | 真实业务后端 `apps/api`，SSE 三协议适配 |
| 本地 RAG | Ollama（`qwen2.5:7b`、`bge-m3`） | 固定快照 `app.services.rag_engine` |
| 测试 | Vitest（jsdom）+ Playwright + pytest | 单测 / e2e / 后端 |
| 工程 | npm workspaces（根锁文件） | 依赖版本以 `package-lock.json` 为准 |

## 3. 仓库结构

```text
├── apps/
│   ├── web/                      # 正式前端（Next.js App Router）
│   │   └── src/
│   │       ├── app/              # 薄路由与布局（[planned] 为规划页捕获路由）
│   │       ├── components/       # 公共壳（layout/）与通用控件（ui/）
│   │       ├── features/         # 业务模块（chat / lesson-plan / knowledge / books / courses / model-settings / settings）
│   │       ├── services/         # API 客户端与本地仓储（不含 UI）
│   │       ├── contracts/        # 跨模块共享类型
│   │       └── styles/           # globals.css / motion.css 单一变量层
│   └── api/                      # 真实业务后端（FastAPI，唯一业务后端）
│       ├── app/api/v1/           # HTTP 路由（chat / rag / model_* / capabilities / health）
│       ├── app/providers/llm/    # 供应商适配（三协议）
│       ├── app/services/         # 业务服务（含 rag_engine 固定快照）
│       ├── app/schemas|contracts|repositories|core/
│       └── tests/                # pytest
├── assets/templates/source/      # 教案模板副本与校验信息（原 Word 不改）
├── docs/                         # 规范、进度、矩阵、API、归档与批次证据
│   ├── CURRENT_STATUS.md         # 唯一进度/问题/任务/下一动作入口
│   ├── PROJECT_GUIDE.md          # 唯一目标与稳定决定
│   ├── API.md / ROUTES.md        # 现行接口契约 / 路由索引
│   ├── archive/History.md        # 全部历史归档（只读快照）
│   ├── replica/                  # 三矩阵（页面 / AI 交互 / 动画）与接手说明
│   └── qa/                       # 各批次证据（历史记录，保持原样）
├── infra/                        # 部署规划（当前仅说明）
├── scripts/                      # 启动、模板构建/校验、RAG 验收工具
├── tests/                        # e2e（Playwright）/ integration / fixtures
├── 项目规划/                      # 原始规划与参考原件（非执行入口）
├── 教师备课教案模板.docx          # 原始 Word 模板（不改）
└── package.json                  # 根 npm 工作区与命令入口
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
npm.cmd run test:e2e      # Playwright 全量（隔离 5174）
npm.cmd run test:chat     # 聊天集成回归（本地流式替身后端 + 构建）
npm.cmd run check         # typecheck + lint + unit + build 串跑
npm.cmd run template:build / template:verify   # 教案模板派生 / 校验
```

> 单测在 Node 26 下必须 `NODE_OPTIONS=--no-experimental-webstorage`，否则 jsdom localStorage 大量假失败。

## 5. 代码组织规范

- **路由薄、业务厚**：`app/` 只负责路由、布局、页面状态；业务进 `features/<module>`；公共壳与控件进 `components/`。
- **类型分层**：跨模块类型进 `contracts/`；模块专有类型留在模块内。导航、主题、服务定义只维护一套。
- **能力注入**：页面经显式 props/Context/服务接口获得能力；不在模块顶层读 `window`/`document`/localStorage；
  浏览器专用能力置于客户端生命周期内；服务端不共享可变用户编辑状态。
- **单一后端**：不要借 Next.js Route Handlers 起第二套业务后端；真实业务都在 `apps/api`。
- **依赖纪律**：用根 workspace 与锁文件；常规开发不顺手升级框架或换包管理器。
- **样式纪律**：全站共用 `globals.css` 变量层与字体 token；页面不散写具体字体名；模块专属样式以页面修饰类起头，
  不污染共享层。`components/layout/space.css` 是知识库/书籍/课程等内容页的共享基础样式（`space-*` 类）。

## 6. 测试与验收要求

- 提交前跑 `npm.cmd run check`；路由、布局、保存或导出改动另跑 `npm.cmd run test:e2e`（先 `build`）。
- 只跑与变更相关且有意义的场景；**未执行的检查明确写「未执行」及原因，不写「应当通过」**。
- 区分真实服务、本地规则、显式模拟与规划状态；**构建成功不等于业务或视觉验收通过**。
- 自动化用隔离浏览器上下文、固定测试数据与测试端口（5174），**不读写真实草稿/凭证**。
- 已知跨批间歇用例（如 books-commit-safety 双标签写锁竞争 R-14）按 `docs/CURRENT_STATUS.md` 台账管理，
  不以单次全绿宣称候选恒绿。

## 7. 数据、凭证与安全边界

- **凭证**：API Key 只存后端 `apps/api/.env`；`.env.example` 只含空值或无敏感示例；密钥不进前端、源码、日志、截图、测试样本。
- **原 Word 模板不改**：派生模板用 `assets/templates/source`，记录校验值并测导出。
- **参考产品只读**：`F:\DeepTutor` 固定提交不升级、不写入；教材原文件 `F:\人教版教材\markdown` 只读。
- **数据保护**：不覆盖用户正在编辑的浏览器会话；读取失败/结构损坏不当空库覆盖；写入失败保留编辑可重试。
- **不外发**：不发布网站、不推送远程、不发外部消息，除非用户明确授权。

## 8. Git 约定

- 检查 → 小批改动 → 验证 → 明确范围提交；**不自动推送/部署，不改全局 Git 身份**。
- 当前分支 `main`（个人分支）；默认集成分支为 `feat/glass-theme`。撤销明确提交优先 `git revert`，
  不用 `reset --hard`/`clean -fd`。保存检查点不代表已验收。

## 9. 文档地图

| 文档 | 职责 |
| --- | --- |
| [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md) | 唯一进度、问题台账、当前任务、下一动作 |
| [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md) | 唯一目标、视觉基准、稳定决定 |
| [docs/API.md](docs/API.md) / [docs/ROUTES.md](docs/ROUTES.md) | 现行接口契约 / 路由索引 |
| [docs/replica/](docs/replica/) | 页面 / AI 交互 / 动画三矩阵 |
| [docs/archive/History.md](docs/archive/History.md) | 全部历史归档（只读，非当前指令） |
| [docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md](docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md) | 可复用任务卡/结果卡 |

## 10. 多智能体协作要点

- 总控负责拆分、依赖、文件归属、集成与最终交付；共享工作区同一文件同一时段仅一个写入者。
- 每个任务需有 ID、版本、负责人、可写范围、验收条件与结果格式；共享契约先定单一负责人。
- 默认由总控独占权威进度文档、验收矩阵、依赖锁文件与最终 Git 操作。
- 实现者自检并标记待验收；独立验收者对稳定候选核查并给证据；总控确认已验收。
- 保留用户与其他智能体的改动：不切换共享分支、不批量暂存、不清理未知数据、不撤销他人工作。

## 11. 模块级 AGENTS.md

改下列模块前，先读对应文件了解实现细节与局部规范（**规划中的模块不写**）：

- [apps/web/src/features/chat/AGENTS.md](apps/web/src/features/chat/AGENTS.md) — 学习问答
- [apps/web/src/features/lesson-plan/AGENTS.md](apps/web/src/features/lesson-plan/AGENTS.md) — 教案工作台
- [apps/web/src/features/knowledge/AGENTS.md](apps/web/src/features/knowledge/AGENTS.md) — 教材资料库
- [apps/web/src/features/books/AGENTS.md](apps/web/src/features/books/AGENTS.md) — 书籍
- [apps/web/src/features/courses/AGENTS.md](apps/web/src/features/courses/AGENTS.md) — 课程
- [apps/web/src/features/model-settings/AGENTS.md](apps/web/src/features/model-settings/AGENTS.md) — 模型与连接
- [apps/web/src/features/settings/AGENTS.md](apps/web/src/features/settings/AGENTS.md) — 设置
- [apps/api/AGENTS.md](apps/api/AGENTS.md) — FastAPI 后端
