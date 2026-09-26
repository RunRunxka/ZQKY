# 智启课源

> [!CAUTION]
> 本项目是进行中的复刻工程，**整体尚未完成**。主聊天与模型已有真实 FastAPI 接口；教案为本地规则；阅读、知识库、写作等模块保留批准的**显式模拟**（界面均有标注）。当前批次、验证边界与下一动作**只看 [STATUS](docs/STATUS.md)**，本 README 只做入口，不保存进度。

以 **智启课源品牌**完成参考产品的全部产品前端、AI 交互和原有动画：全站视觉以当前学习问答 `/chat` 为基准，保留蓝色主题与既有业务。参考产品按固定提交只读对齐（`F:\DeepTutor` v1.6.5 / `42fab3cf429a1fbf36b257ab8d116a3814964202`，不升级、不写入）。正式前端在 `apps/web`，真实业务后端在 `apps/api`。

## ✨ 核心能力

- **学习问答**：三协议真实 SSE 流式、推理/正文与公式渲染（长推理流已做性能收口：活跃流轻量呈现 + 增量合并，50k 字推理帧间隔 p95 166.7→5.6 ms）、来源消息定位、本地会话与轮次快照；模式菜单含真实本地「RAG 模式」与教材追问：教材原文、章节、行号及同轮澄清
- **教案工作台**：本地规则填充、编辑与草稿恢复、Word/PDF 导出（原 Word 模板不改）
- **学习空间**：会话历史、题库、角色目录、CLI 应用（本地登记）
- **知识库与笔记**：登记→解析→索引显式模拟（进度/取消/重试/恢复）；笔记与聊天「保存到笔记」同仓储
- **书籍与课程**：14 类 block、章节大纲、练习、资源引用与进度
- **沉浸阅读**：材料/集合、批注/书签/阅读进度；伴生助手为显式模拟事件流
- **协作写作 / Whisper**：自动保存、版本与撤销；双席位房间（AI 回复显式模拟）
- **模型与供应商**：连接/模型目录/发现/推理控制，凭证仅保存于后端
- **公共壳**：220/56px 侧栏（导航内可滚动「学习记录」区域）、折叠偏好、手机模态抽屉、统一 404 与主题、品牌 favicon

## 🛠️ 技术栈

- **框架**：Next.js 16（App Router）+ React 19 + TypeScript 5.7
- **样式**：Tailwind CSS 3.4 + 单一变量层（蓝色主题；字体 token：`--font-ui` 正文 / `--font-display` 标题 / `--font-ui-serif` 导航与学习问答 / `--font-document` 教案文档 / `--font-mono` 代码）
- **状态**：Zustand 5
- **内容渲染**：react-markdown、KaTeX、Mermaid、Chart.js
- **文档导出**：docxtemplater / PizZip（Word）
- **后端**：FastAPI（Python ≥ 3.12，uv 管理），SSE 三协议适配
- **测试**：Vitest（jsdom）+ Playwright + pytest
- **工程**：npm workspaces（根锁文件）

## 🚀 快速开始

### 环境要求

- Node.js 26（当前验证环境；jsdom 单测需 `NODE_OPTIONS=--no-experimental-webstorage`）
- Python ≥ 3.12 与 [uv](https://docs.astral.sh/uv/)（仅运行真实后端时需要）

### 安装依赖

```powershell
Set-Location 'H:\备份xuexi\智启课源'
npm.cmd ci
```

### 本地开发

```powershell
npm.cmd run dev
```

前端 `http://127.0.0.1:5173`，首页 `/chat`，教案 `/lesson-plans`。保持原浏览器来源：`localhost`、`127.0.0.1` 与不同端口的数据互不相同。已有依赖时无需重复 `ci`；不要停止归属不明的服务。

### 启动真实后端（可选）

```powershell
npm.cmd run setup:api   # 首次：uv sync 创建后端环境
npm.cmd run dev:api     # http://127.0.0.1:8000
```

在「设置」中配置连接和模型；API Key 保存到后端 `apps/api/.env`，重启后恢复。主聊天仅走真实服务（生产模拟入口与文案已清理）；旧模拟数据库留存但不读写，测试替身只存在于测试目录。

### 使用本地教材 RAG

启动 Ollama 和上述现有后端、前端后，在 `/chat` 模式菜单选「RAG 模式」或「追问澄清」，输入题目即可。
这两个入口使用本地教材引擎，无需在普通聊天模型菜单配置云模型。学科范围为数学、物理、化学、生物。
未选择学科时只在这四科册内检索（本机快照 6,745 个正文块），其他学科的教材册不在产品检索空间内；
索引本身仍保留全库，历史评测口径不变。

当前默认展示**教材原文讲解与定位**：每条引用回到原文字符区间，并显示书册、章节和行号。
证据不足会请求补充；追问卡可提交补充、跳过或取消。刷新或断线后点「继续本轮」，在后端仍存活且轮次未过期时恢复；
后端重启或 10 分钟过期后明确要求重新发送，不伪装续接。最多 3 次定位。
自由生成的解题推导未开放；机器筛选不等于人工教学质量验收。

本机资产在 `.local-data/rag`（忽略 Git），教材原文件仍只读访问 `F:\人教版教材\markdown`。
模型需与资产中 `models.yaml` 的固定 digest 一致：`qwen2.5:7b`、`bge-m3:latest`。
`GET /api/v1/rag/status` 检查依赖、资产与模型身份；不可用时不转云端。
迁移到另一台电脑需一并安装 Python 锁定依赖、同一版本模型与教材目录，并重新生成资产清单；只复制 Git 代码不足以运行。
运行记录仅写调用元数据到 `.local-data/rag-state/api_usage.jsonl`，不落盘题文/生成缓存；用户会话保存在浏览器。

真实浏览器验收脚本（需 web :5174 与 api :8001 已启动，使用隔离上下文与固定预算，不读写用户草稿）：

```powershell
node scripts/test-rag-delivery.mjs    # 数学正向题 + 语料外拒答：追问、刷新续接、提交/跳过/取消、三视口
node scripts/test-rag-subjects.mjs    # 四科真实结果 + 注入题 + 跨会话越权 + 过期轮次
```

两者只取消自己创建的轮次，证据写入 `_work/rag-delivery/<runId>/`（含 report.json 与截图）；任一 FAIL 都会保留真实结果、不自动重试或换题。

### 构建生产版本

```powershell
npm.cmd run build
```

### 预览构建结果

```powershell
npm.cmd run start
```

## 📌 常用命令

| 命令 | 作用 | 典型场景 |
| --- | --- | --- |
| `npm.cmd run dev` | 启动前端开发服务器（5173） | 日常开发 |
| `npm.cmd run dev:api` | 启动 FastAPI 后端（8000） | 真实问答/模型联调 |
| `npm.cmd run setup:api` | 安装后端依赖（uv sync） | 首次或后端依赖变更 |
| `npm.cmd run build` | 构建前端生产包 | 发布前验证；e2e 前置 |
| `npm.cmd run start` | 预览生产构建（5173） | 上线前检查 |
| `npm.cmd run typecheck` | TypeScript 类型检查 | 提交前质量把关 |
| `npm.cmd run lint` | ESLint（0 警告） | 提交前质量把关 |
| `npm.cmd run test:unit` | Vitest 单测（jsdom） | 逻辑回归 |
| `npm.cmd run test:api` | 后端 pytest | 后端回归 |
| `npm.cmd run test:e2e` | Playwright 浏览器回归（隔离 5174，跑上一次构建） | 页面/交互回归 |
| `npm.cmd run test:chat` | 聊天集成回归（本地流式替身后端 + 构建） | 问答链路回归 |
| `npm.cmd run template:build` | 由 `assets/templates/source` 派生教案模板与字段 schema | 模板变更 |
| `npm.cmd run template:verify` | 校验派生模板与原件一致性 | 模板变更后核验 |
| `npm.cmd run format:check` | Prettier 格式检查 | 格式统一 |
| `npm.cmd run check` | typecheck + lint + unit + build 串跑 | 收尾全量检查 |

单测在 Node 26 下必须设置 `NODE_OPTIONS=--no-experimental-webstorage`（否则 jsdom localStorage 会大量假失败）；浏览器回归使用隔离上下文与 5174。`test:e2e` 跑的是**上一次构建**，改码后先 `build`。

## 🧩 功能模块

### 1) 学习问答（基准页）

`/chat` 是全站默认主页与视觉基准：真实 FastAPI 三协议 SSE、推理与正文分栏、公式、来源消息定位、会话与草稿本地持久化；学习记录并入左侧导航，模式菜单为单层（对话/追问澄清/智能出题/可视化/RAG 模式——后者未接入、不可选）。生产模拟服务与入口已清理，复杂能力（工具、附件解析、RAG 检索）未接入前明确不可用。

### 2) 教案工作台

`/lesson-plans`：本地规则填充、编辑、草稿恢复与 Word/PDF 导出。原始 Word 与派生模板校验信息保留在 `assets/templates/source/`；原 Word 模板不改。

### 3) 学习空间与资料

`/space` 是学习空间 hub：会话历史、题库、角色目录、CLI 应用（本地登记），另有笔记本 `/notebooks` 与聊天共仓储；MCP/Skills 只在设置中管理。

### 4) 知识库、书籍与课程

知识库为显式模拟的登记→解析→索引流程（进度/取消/重试/恢复），真实文件解析与向量检索未接入；书籍/课程提供 block 渲染、章节大纲、练习、笔记、资源与进度（导航中「书籍」已并入「教材资料库」，路由与数据不变）。各模块未完成状态以 [STATUS](docs/STATUS.md) 台账为准。

### 5) 沉浸阅读与协作写作

阅读支持材料/集合、批注/书签/阅读进度与显式模拟伴生助手；写作支持自动保存、版本/撤销与双席位 Whisper 房间（AI 回复为显式模拟）。

### 6) 模型与设置

`/settings` 统一管理外观、模型与连接、MCP、Skills 与扩展；供应商配置、发现与推理控制按后端契约实现，凭证不进入前端与 Git。

## ⚙️ 配置与边界

| 项 | 约定 |
| --- | --- |
| 参考产品 | `F:\DeepTutor` 固定提交 `42fab3cf…` 只读；不升级、不写入 |
| 视觉基准 | 当前学习问答 `/chat`；蓝色主题 `--blue`；公共变量层在 `globals.css` |
| 数据隔离 | 浏览器数据按来源与端口隔离；自动化使用隔离上下文与 5174，不读写真实草稿 |
| 凭证 | API Key 仅存后端 `apps/api/.env`；`.env.example` 无敏感值；Git 不备份浏览器数据库或运行时凭证 |
| 提交 | 检查 → 小批改动 → 验证 → 明确范围提交；不自动推送/部署，不改全局 Git 身份 |

## 📚 文档入口

| 文档 | 唯一职责 |
| --- | --- |
| [开发规则](AGENTS.md) | 工作范围、数据保护和工程规则 |
| [项目说明](docs/PROJECT_GUIDE.md) | 当前目标、学习问答视觉基准、技术结构、数据流、允许差异、Git 恢复方法 |
| [当前进度](docs/STATUS.md) | 唯一进度与交接入口，代码审查、完整计划、验证边界、下一动作 |
| [新会话启动文本](docs/replica/NEXT_SESSION_START.md) | 接手步骤，不复制进度与计划、不扩大当次授权 |
| [协作任务模板](docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md) | 可复用任务卡与结果卡，不保存当前进度 |
| [阅读代码审查](docs/reviews/READING_REVIEW_2026-09-08.md) | 历史首败、修复和局部验收证据 |
| [页面矩阵](docs/replica/PAGE_MATRIX.md) · [AI 交互矩阵](docs/replica/AI_INTERACTIONS.md) · [动画矩阵](docs/replica/MOTION_MATRIX.md) | 逐项验收，不另抄阶段统计 |
| [路由索引](docs/ROUTES.md) · [后端 API](docs/API.md) | 运行时入口和真实接口 |
| [本批证据](docs/qa/UX-PERF-CLOSEOUT-20260923/README.md) | 长推理流性能前后数据、模式菜单与字体取证、可达性审计 |

旧 HANDOFF、TASKS、计划和 review 已归档到 `docs/archive/`（映射与 SHA256 见 [归档清单](docs/archive/MANIFEST.json)）；原始 `项目规划/` 与 Word 原件保留。旧提示词和旧“已完成”结论不是当前指令。

## 📁 项目结构

```text
├── apps/
│   ├── web/                 # 正式前端（Next.js App Router）
│   │   └── src/
│   │       ├── app/         # 薄路由与布局
│   │       ├── components/  # 公共壳与通用控件
│   │       ├── features/    # 业务模块（chat / lesson-plan / reading / …）
│   │       ├── services/    # API 与本地仓储
│   │       └── contracts/   # 跨模块契约
│   └── api/                 # 真实业务后端（FastAPI）
├── assets/templates/source/ # 教案模板副本与校验信息
├── docs/                    # 规范、进度、矩阵、归档与证据
├── infra/                   # 部署规划（当前仅说明）
├── scripts/                 # 启动、模板与检查工具
├── tests/                   # e2e / integration / review / fixtures
├── 项目规划/                 # 原始规划与参考原件（非执行入口）
├── 教师备课教案模板.docx      # 原始 Word 模板（不改）
└── package.json             # 根 npm 工作区与命令入口
```

## 🤝 贡献

- 开工前先读 [AGENTS.md](AGENTS.md)、[PROJECT_GUIDE](docs/PROJECT_GUIDE.md) 与 [STATUS](docs/STATUS.md)；任务只以 STATUS 当前任务和用户最新指令为准，不据旧待办扩大范围。
- 提交前运行 `npm.cmd run check`（typecheck + lint + unit + build）；浏览器相关改动另跑 `npm.cmd run test:e2e`（先 `build`）。
- 最新提交以 `git log -5 --oneline` 为准；历史标签只是快照，不是发布版。不发布网站、不推送远程、不发送外部消息，除非获得明确授权。

## 📄 许可证

本仓库为私有项目（`package.json` 中 `private: true`），未附开源许可证文件。引用的字体与第三方资源的来源和许可见 [资源说明](docs/licenses/deeptutor-chat/README.md)。

## 🙏 致谢

- 参考产品 **DeepTutor** 及其作者：产品结构、视觉参考与交互对齐的依据（只读固定提交）。
- 字体资源 Geist / Lora（OFL，见 `apps/web/public/fonts/chat/`）与 Thinking-orbs（MIT，vendored）。
