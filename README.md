# 智启课源（ZQKY）

**对话优先的闭环教学 AI 工作台**：一个统一的学习问答界面（`/chat`）承载全部教学 AI 能力，
八个业务板块既是独立页面，也是问答里的 Agent 工具（一句话或带文件触发）。

- **架构硬性**：全部 LLM 调用经 **LangChain**，多步 AI 流程由 **LangGraph** 编排；
  业务代码禁止直连供应商 SDK（有门禁测试）。
- **红线**：AI 输出只进候选、教师确认才落库；学生姓名/学号不进模型；凭证只存后端
  `apps/api/.env` 经 SecretStore 注入。
- 唯一进度、台账与下一动作只看 [CURRENT_STATUS](docs/CURRENT_STATUS.md)；稳定决定见
  [PROJECT_GUIDE](docs/PROJECT_GUIDE.md)；仓库指南见 [AGENTS.md](AGENTS.md)。

## 功能入口

| 入口 | 能力 |
| --- | --- |
| `/chat` | 学习问答：流式对话、附件上传、上下文容量环、思考强度（受支持档位）、Agent 工具与确认卡；默认主页与视觉基准 |
| `/lesson-plans` | 教案工作台：三栏（模块/排版 · 编辑 · 第 3 页起 A4 预览）、七模块+自定义、流式生成、导出 docx（自动补封面与目录） |
| `/textbooks` | 教材资料库：导入→清洗→切块→嵌入→索引；索引代与修订不可变 |
| `/knowledge-points` | 知识点：教材目录成树、节点增改、学习目标、别名、AI 候选与教材提取 |
| `/question-bank` | 题库：课后习题提取、AI 整理/补题、知识点×难度分类与筛选 |
| `/practices` | 练习：学情/描述驱动出题 → 微调 → 确认门槛 → 学生卷/教师卷导出预览 |
| `/learning-analysis` | 学情分析：小题分导入（四态不补零）、五图、AI 评价、报告导出 |
| `/assessments/roster` `/assessments/papers` | 班级管理（名单 xlsx 导入；删除学生双模式、人数即时下降）/ 试卷管理（导入拆题、AI 知识点分类占比）；删除即删除，无归档入口 |
| `/settings` | 外观 / 模型与连接 / 关于 |

## 本地运行

Node.js 26（当前验证环境）、Python ≥3.12、uv；本机需 Ollama（`bge-m3` 嵌入）与 Qdrant
（`docker compose -f infra/qdrant/docker-compose.yml up -d`）。

```powershell
npm.cmd ci
npm.cmd run setup:api    # 首次：uv sync
npm.cmd run dev:api      # 127.0.0.1:8000
npm.cmd run dev          # 127.0.0.1:5173（首页 /chat）
```

模型在「设置 → 模型与连接」配置；API Key 仅由后端存于 `apps/api/.env`。

## 常用检查

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
npm.cmd run check        # typecheck + lint + unit + build
npm.cmd run test:api     # 后端 pytest（须 uv run python -m pytest，见 AGENTS.md 环境坑）
npm.cmd run test:e2e     # 先 build；隔离 5174
```

自动化使用临时数据根与隔离浏览器，不读写正式凭证/草稿；未执行的检查注明原因。

## 闭环测试套件

[test/](test/README.md)：教材 md / 名单 xlsx（40 人）/ 试卷 docx（16 计分叶）/ 小题分 xlsx
（四态）四件套 + 走查手册，由 `scripts/build-closed-loop-fixtures.py` 生成，并有常驻回归
（`apps/api/tests/test_closed_loop_fixtures.py`）保证与导入规则同步。

## 文档

- [当前状态与交接](docs/CURRENT_STATUS.md)：唯一进度、台账、当前任务、下一动作（门禁数字以顶部「当前状态」为准）。
- [项目指南](docs/PROJECT_GUIDE.md)：目标、架构硬性与稳定决定（含「删除即删除」口径）。
- [API](docs/API.md) / [路由](docs/ROUTES.md)：现行接口（含删除语义表）与页面索引。
- [多智能体协作规范](docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md)：角色、任务卡/结果卡模板与可复制提示词。
- [文档索引](docs/README.md)；[QA 证据](docs/qa/README.md)；[第三方许可](docs/licenses/deeptutor-chat/README.md)。
- 历史完整实现（重构前）唯一入口：git tag `archive-full-v1-20261011`。
