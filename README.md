# 智启课源（ZQKY）

面向教师的 AI 教学工作台，采用 **Next.js + FastAPI**。2026-09-29 起的建设核心是教材 RAG、独立知识点库、原卷与小题得分对齐、题库，以及后续学情分析、教案调整和练习回流。当前任务与实现偏差只看 [CURRENT_STATUS](docs/CURRENT_STATUS.md)，稳定规则见 [PROJECT_GUIDE](docs/PROJECT_GUIDE.md)。

## 功能入口

| 入口 | 能力与边界 |
| --- | --- |
| `/chat` | 真实多模型 SSE 与教材 RAG；默认主页与既有视觉基准 |
| `/knowledge-bases` | 真实教材上传/解析/目录/修订/索引；历史本地登记只读 |
| `/knowledge-points` | 独立知识点管理、别名、教材依据、导入校对和候选确认 |
| `/question-bank` | 独立题库、导入校对、知识点关联与 AI 补题候选；当前审查偏差看状态台账 |
| `/assessments` | 名单→原卷→施测→成绩→历史五步工作区；当前审查偏差看状态台账 |
| `/lesson-plans` | 已有本地规则填充、编辑/草稿恢复、Word 与打印/PDF 导出；学情驱动 AI 调整属后续建设 |
| `/books`、`/courses` | 保留既有内容和课程会话能力；书籍生成仍为显式本地模拟 |
| `/settings` | 模型与连接、Embedding/任教范围、外观及扩展管理 |

学情报告、针对练习与成绩回流闭环尚未实现。写作、阅读、学习空间、智能组卷、模板中心保留规划根页，完整运行时路径见 [ROUTES](docs/ROUTES.md)。

## 本地运行

Node.js 26（当前验证环境）、Python ≥3.12、uv。根 npm workspace 和 `apps/api/uv.lock` 是依赖依据。

```powershell
Set-Location 'H:\备份xuexi\智启课源'
npm.cmd ci
npm.cmd run setup:api
npm.cmd run dev:api     # 127.0.0.1:8000；另一个终端启动前端
npm.cmd run dev         # 127.0.0.1:5173
```

已有依赖时不需要重复安装。聊天和教学业务需要后端；API Key 在设置中配置，仅由后端存于 `apps/api/.env`。浏览器数据按来源/端口隔离，不用开发或测试来源覆盖用户正式草稿。

## 教材 RAG 与存储

生产 `/api/v1/rag/*` 使用 **RagV2Service**，按教师确认的任教范围和教材目录的当前索引代进行检索；不再把旧四科固定快照、6,745 块或旧 `models.yaml` 当作当前运行条件。

先启动本机 Ollama、Qdrant 和 FastAPI，在设置完成 Embedding 配置与任教范围，在教材资料库导入或重建索引，再在学习问答使用 RAG。首答提供紧凑知识点及可核验教材证据；详解冻结并使用当前选择的聊天模型，可为本地或云端。依赖未就绪时如实报错，不降级为云端检索或假成功。

业务采用四个独立 SQLite：教材、题库、知识点、教学业务；Qdrant 仅存教材向量；原件保存在内容寻址的受管 assets。索引代、原文修订与正式成绩版本有各自唯一权威，不混用 ID 和编辑 revision。数据目录不入 Git，备份/恢复与迁移按 [API](docs/API.md)、[稳定决定](docs/PROJECT_GUIDE.md) 和对应脚本执行。

教材 RAG 的可运行性、检索证据和人工教学质量分别验收，不能以构建或自动化通过宣布教学质量已通过。

## 常用检查

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
npm.cmd run check       # typecheck + lint + unit + build
npm.cmd run test:api
npm.cmd run test:e2e    # 先 build；隔离 5174，跑上一次构建
npm.cmd run test:chat
npm.cmd run template:verify
```

自动化使用临时后端数据根、隔离浏览器与测试服务，不读写正式凭证/草稿/6333 向量库。未执行的检查注明原因；文档整理不冒称执行业务回归。

## 文档

- [当前文档索引](docs/README.md)：阅读顺序与 9 月 29 日起主线。
- [当前状态与问题](docs/CURRENT_STATUS.md)：唯一下一动作和台账。
- [教学闭环设计](docs/design/teaching-loop-v1/README.md)、[详细实施计划](docs/design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md)：实体/ER/模块/关系表/伪代码与验收规格。
- [当前接手入口](docs/NEXT_SESSION_START.md)、[AGENTS](AGENTS.md)：执行范围、规范与数据保护。
- [API](docs/API.md)、[ROUTES](docs/ROUTES.md)：现行契约和运行时页面索引。
- [历史归档](docs/archive/README.md)：旧任务/复刻矩阵/原始规划/完整状态快照与散列映射。
- [第三方许可](docs/licenses/deeptutor-chat/README.md)：保留并继续适用。

DeepTutor 固定提交仅为历史界面参考，保留智启课源品牌、蓝色主题和已有兼容约束；不再以旧全页面复刻路线组织当前任务。
