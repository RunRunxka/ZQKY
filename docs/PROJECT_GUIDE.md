# 项目指南

> 唯一目标与稳定决定。历史完整产品的目标与红线归档于 git tag `archive-full-v1-20261011`
> （`git show archive-full-v1-20261011:docs/PROJECT_GUIDE.md`）。

## 1. 目标

**对话优先的闭环教学 AI 工作台**：一个统一的对话界面承载全部教学 AI 能力，八个业务板块
（教材资料库 / 知识点 / 题库 / 班级管理 / 试卷管理 / 学情分析 / 教案工作台 / 练习）既是独立页面，
也是学习问答里的 **Agent 工具**——一句话或带文件即可触发；对话与业务之间没有模式切换。

- **架构硬性（用户裁定）**：所有 LLM 调用统一经 **LangChain**（`resolve_agent_chat_model` +
  `services/llm/` 运行层：提示词版本指纹 + `with_structured_output`/`astream`）；多步 AI 流程
  由 **LangGraph** 编排（主 Agent 图 + 各域 job 执行器）。业务代码禁止直连供应商 SDK
  （门禁 `tests/test_no_raw_sdk_imports.py`）。
- **统一问答**：`/chat` 是唯一默认主页；追问澄清即普通对话；教材检索是工具不是通道；
  对话框含附件、上下文容量环（受支持模型窗口）、思考强度（仅显示当前模型受支持档位）。
- **模型配置独立于业务**：连接 / 档案 / 目录 / 授权（含 OAuth 受管认证；受管认证暂不可用于
  Agent/模块调用，可回退 `/chat/stream` 直连）。
- **装配约定**：业务域按 `app.services.<domain>.assembly:assemble(app, settings)` 逐批装配
  （`main.py _DOMAIN_ASSEMBLIES`，顺序即依赖顺序）；缺依赖的域路由 503/501，不假成功。

## 2. 稳定决定（红线延续）

- **AI 只进候选**：AI 产出必须经教师确认后才落库；Agent 写操作走中断确认卡（`apply_lesson_proposal`、
  导入类工具产草稿）；教案「候选/草稿」彻底分离（采用才写入）。
- **学生个人信息不进模型**：姓名 / 学号 / 人员 ID 不进入任何模型上下文；学情矩阵与 AI 评价
  一律使用后端代称（`学生A/B…`）。
- **凭证边界**：API Key 只存后端 `.env` 经 SecretStore 显式注入；LangChain 官方包构造前断言
  `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` 未在进程环境出现。
- **单一业务后端**：FastAPI（`apps/api`）；前端不直连模型、不起第二套后端。
- **视觉基准**：`/chat` 为默认主页；品牌蓝与既有排版 token 不变；业务页由 `ModuleWorkspaceShell`
  统一提供壳与滚动（业务根登记制，页面裸渲染）。
- **数据保护**：不覆盖用户正在编辑的会话/草稿；读取失败不降级为空数据。**删除即删除**
  （2026-10-13 用户裁定「舍弃所有归档功能，只留删除」+「拆开交叉引用」）：归属/自身历史行随实体级联，
  下游产物随上游级联，可空引用置空；**成绩链只随施测（其所有者）显式删除**，班级/学生/试卷/练习的删除
  永不静默销毁学生成绩；不可拆的引用 409 逐项列出并给可执行下一步（清单见 [API.md](API.md) 删除语义）。
  归档端点保留为历史数据兼容，界面与客户端已无入口。

## 3. 八个板块与主要入口

| 板块 | 页面 | 后端域 | 关键口径 |
| --- | --- | --- | --- |
| 教材资料库 | `/textbooks` | textbooks | PDF/DOCX/md 导入→清洗（含 C4-5 页眉页脚/页码剔除）→切块→Ollama bge-m3→Qdrant；索引代/修订不可变 |
| 知识点 | `/knowledge-points` | knowledge | 教材目录成树（噪声段透明过滤）；节点 CRUD + 别名 + **学习目标**；AI 候选/教材提取只进候选 |
| 题库 | `/question-bank` | question_bank | 课后习题提取→草稿→确认；AI 整理/补题（needs_review）；知识点×难度过滤 |
| 班级管理 | `/assessments/roster` | teaching | 名单 xlsx 导入（含性别列）；删除学生双模式（无成绩=彻底删除 / 有成绩=移除并保留历史），班级人数即时下降；无归档入口 |
| 试卷管理 | `/assessments/papers` | teaching | DOCX/PDF 文本层导入→规则拆题→AI 知识点分类提案→占比环图；不显示试卷原文 |
| 学情分析 | `/learning-analysis` | teaching | 小题分四态导入（0/空/缺考/免考不补零）；五图（红色柱得分率/热力图/知识点排行/学生×知识点/分数段）+ AI 评价 + 报告导出 |
| 教案工作台 | `/lesson-plans` | lesson_plans | 三栏（模块/排版 · 编辑 · 第 3 页起 A4 预览）；普惠体四族字体；七模块+自定义；流式逐格生成；导出自动补封面+目录 |
| 练习 | `/practices` | teaching | 学情/描述驱动出题；微调；未审核不可导出；学生卷/教师卷 docx（OMML 公式）+ 成绩模板 |

## 4. 环境与命令

见根 [AGENTS.md](../AGENTS.md) §4（含 uv `python -m` 入口坑与单测环境变量）。
