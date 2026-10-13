# 文档索引

> 2026-10-13：R 系列重建与 R10 收口后的文档集。重构前的设计/QA/复刻矩阵等文档已清理
> （经 git 历史或 tag `archive-full-v1-20261011` 取读）。

## 当前有效文档

| 文档 | 职责 |
| --- | --- |
| [../AGENTS.md](../AGENTS.md) | 仓库指南（结构 / 命令 / 红线 / 环境坑 / 协作） |
| [../README.md](../README.md) | 项目简介与快速开始 |
| [CURRENT_STATUS.md](CURRENT_STATUS.md) | **唯一进度、问题台账、当前任务、下一动作、交接状态**（门禁数字以顶部「当前状态」为准） |
| [PROJECT_GUIDE.md](PROJECT_GUIDE.md) | 唯一目标、架构硬性（LangChain+LangGraph）、稳定决定 |
| [MULTI_AGENT_COLLABORATION_PROPOSAL.md](MULTI_AGENT_COLLABORATION_PROPOSAL.md) | 多智能体协作规范：角色、任务卡/结果卡模板、本项目门槛、可复制提示词 |
| [API.md](API.md) / [ROUTES.md](ROUTES.md) | 现行接口契约（含 R10 删除语义表）/ 路由与模块索引 |
| [qa/README.md](qa/README.md) | 重建后 QA 证据索引（R6/R7/R8 探针与截图） |
| [../test/README.md](../test/README.md) | 闭环测试套件与走查顺序 |
| [licenses/deeptutor-chat/README.md](licenses/deeptutor-chat/README.md) | 第三方（参考产品）许可，保留适用 |

## 已清理（可经 git 历史恢复）

`docs/archive/`、`docs/design/teaching-loop-v1/`、`docs/modules/`、`docs/replica/`、
`docs/NEXT_SESSION_START.md`、根 `qa/`、`项目规划/` 以及 `docs/qa/` 中除 R6/R7/R8 外的全部旧批次证据
——均属重构前材料，2026-10-13 清理。（`docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md` 同日重写为现行
协作规范，不再属于已清理范围。）
