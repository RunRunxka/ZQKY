# 「更多能力」移除与可达性审计（UX-PERF-CLOSEOUT v1 / T3）

日期：2026-09-23。范围：`main` 上 `/chat` 输入区模式菜单。审计对象：`深度求解 deep_solve`、
`深度研究 deep_research`、`沉浸观看 immersive_watching`。本页只登记事实与证据；进度与验收状态见 STATUS。

## 1. 移除前的可达性清单（现场实测，非静态推断）

审计方法：全仓 `grep -rn` 覆盖 `apps/web/src`、`apps/api/app`、`tests/`、`scripts/`、`docs/`，
再按「谁写入 / 谁能触发 / 最终能否发送」三层判定。

| 值 | 写入者（改动前） | 调用链 | 改动前可达性 |
| --- | --- | --- | --- |
| `deep_solve` | `services/capability-catalog.ts`（目录项，`secondary: true`）；`features/chat/CapabilityMenu.tsx`（图标表） | 菜单「更多能力」飞出层的一行 → 点击 `onSelect('deep_solve')` | **不可达**：真实模式 `unavailable` 集合包含它，行被 `disabled`；`ChatWorkspace.submit()` 另有 `capabilityAvailableInReal` 守卫 |
| `deep_research` | 同上的目录项 + 图标表；`features/chat/CapabilityConfigCard.tsx`（研究配置表单）；`services/capability-catalog.ts`（`ResearchFormConfig`/校验/快照/摘要） | 飞出层行 + 配置卡 → 发送 | **不可达**（同上） |
| `immersive_watching` | 同上的目录项 + 图标表 | 飞出层行 | **不可达**（同上） |

结论：三者**在真实模式下本就不可选**，其唯一入口是「更多能力」二级飞出层；配置卡与阶段/产物链路在
`ChatWorkspace` 中没有任何渲染点（`CapabilityConfigCard` 只被单测引用）。因此它们是**不可达产品代码**，
按批次要求整体删除，而不是改动可用行为。

### 1.1 测试替身中的可达性（改动前的唯一“执行”来源）

`tests/fixtures/scripted-chat-service.ts`（仅测试目录使用的显式模拟服务）按能力值分支模拟
`deep_solve` / `deep_research` 的阶段与产物，`features/chat/model/artifact.test.ts` 用它们覆盖
「阶段序列 / 两段式追问 → 产物」通用管线。这些**不是产品执行路径**：生产 store 只注入
`createRealChatService`，`ChatWorkspace` 也不会写入这两个能力值。

### 1.2 后端

`apps/api/app/api/v1/capabilities.py` 维护的是通用状态接口（服务/学习问答对话为 `ready`，
教案填充、组卷、模板、教材资料库、题库、**教材检索（RAG）**、Agent、MCP、Skills 为 `planned`），
**不含这三个模式**；后端全仓对这三个字符串零引用（`grep -rn` 无命中）。因此本次移除**没有**后端
对应代码需要删除，也没有触碰通用 `/capabilities` 接口或其他模块共享的模型能力映射
（`model_config.py` 的 `capabilities` 是「模型是否支持 chat/stream」的另一套语义，与本菜单无关）。

## 2. 本次删除的内容

| 类别 | 位置 |
| --- | --- |
| 目录项 | `services/capability-catalog.ts`：三个 `CapabilityDef` 与 `secondary` 字段 |
| 飞出层与其状态 | `features/chat/CapabilityMenu.tsx`：`moreOpen`、`.chat-cap-more`、`.chat-cap-flyout`、`ChevronRight` 与三项图标 |
| 专属配置表单 | `features/chat/CapabilityConfigCard.tsx`（`ResearchFields`）；`capability-catalog.ts`（`ResearchFormConfig`、`RESEARCH_MODE_LABELS`、`RESEARCH_DEPTH_LABELS`、`createEmptyResearchConfig`、`deep_research` 校验/快照/摘要分支） |
| 专属演示生成器 | `features/chat/model/capability-demo.ts`：`makeResearchSubtopics`、`makeResearchCitations`、`researchReportToMarkdown`（仅供已删除分支使用；`ReportArtifactData` 类型保留，旧会话的 report 产物仍可渲染） |
| 测试替身分支 | `tests/fixtures/scripted-chat-service.ts` 的两个能力分支与 `RESEARCH_MODE_LABELS` 引用 |
| 样式 | `features/chat/styles/chat.css`：`.chat-cap-more*`、`.chat-cap-flyout*`（含手机媒体查询内的一处） |
| 已失效测试 | `capability-catalog.test.ts`（secondary/研究校验/研究快照）、`CapabilityMenu.test.tsx`（飞出层入口、研究配置卡）、`artifact.test.ts`（`deep_solve`、`deep_research` 两例） |

**未删除且必须保留**：`deep_question`（智能出题）、`visualize`（可视化）与其配置表单；
`ask_questions`（追问澄清）；追问卡、阶段、产物、工具等通用链路；`ReportArtifactView` 渲染
（旧会话数据兼容）。

### 2.1 覆盖替换（不因删测试丢管线覆盖）

原 `deep_research` 用例是唯一覆盖「能力轮 + 追问确认 → 同一轮续答 → 产出产物」的用例。
删除后在 `artifact.test.ts` 新增一例，改用保留的 `visualize` 能力走同一 S3 组合流
（`armAskUser()` + 能力轮），断言同轮续答文本与产物标题，保持该通用管线有回归。

## 3. 删除后的替换：RAG 模式

- 位置：原「更多能力」处，与「对话 / 追问澄清 / 智能出题 / 可视化」同一列表、同一行样式、
  同一 `aria-pressed` 选中语义；**无二级菜单、无选择弹窗**。
- 行为（总控裁定，写入 PROJECT_GUIDE）：**不可选（disabled）**，与其余非对话能力的可用性契约一致；
  原因以**行内徽标**「未接入 · 规划中」直接可见（不只在 `title` 里），并与后端
  `capabilities.py` 的 `feature="rag", status=planned` 一致。
- 纵深防御：`ChatWorkspace.submit()` 对 `rag` 保留专门的阻断文案
  （「尚未接入（规划中）：本轮未发送任何检索请求，输入已保留」），任何非菜单路径到达也不会把请求
  发到普通聊天冒充 RAG，也不会返回模拟检索结果。
- `get_rag_adapter()` 仍恒定不可用、capability 仍为 `planned`；本批**不宣称 RAG 已能回答**。

## 4. 历史数据兼容

- 旧会话消息里的 `extensions.capability`（`{ value, label, config? }`）是**轮次冻结快照**，
  类型与存储未改动，仍按原样读取、不迁移、不回填、不清库。
- **明确降级展示（r4 补齐）**：消息「来源与上下文」现在按轮次快照渲染 `extensions.capability`——
  已移除的模式显示「模式 · 深度求解」＋「该模式入口已停用（随「更多能力」一并移除），此处仅按历史轮次
  快照如实展示，历史记录保持可读。」；仍存在但真实模式不可用的显示「该模式当前未接入，仅按轮次快照
  如实展示，不代表现在可以发起。」（单测 `message-duration.test.tsx` 覆盖两种分支）。
- 全仓 `getCapability()` 的调用点只有实时选择（`CapabilityMenu` 的 `value` 与 `ChatWorkspace`
  的 `capabilityValue`）与上述展示路径的**目录存在性判断**（用 `find` 而非回退到「对话」），
  因此历史值既不会被错标成「对话」，也不会被静默丢弃。快照中的 `label`（例如「深度求解」）是当时
  写入的字符串，历史消息照常可读。
- `tests/e2e/chat-message-locate.spec.ts` 中一处 **report 产物数据的 `data.mode` 字段**
  （`'deep_research'`）属于产物 JSON 内容、不是能力路由，保留不动（避免改测试数据语义）。

## 5. 复核命令

```bash
# 三个模式在源码/测试/脚本/文档中的全部命中（应只剩说明性注释与“不得回流”断言）
grep -rn "deep_solve\|deep_research\|immersive_watching" apps tests scripts
# 后端零命中
grep -rn "deep_solve\|deep_research\|immersive_watching" apps/api --include=*.py
# RAG 模式的声明链
grep -rn "RAG 模式" apps/web/src
grep -rn "feature=\"rag\"" apps/api/app/api/v1/capabilities.py
```
