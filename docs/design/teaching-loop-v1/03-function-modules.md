# 03 细化功能模块图

[返回总说明](README.md)。模块按业务职责划分，独立功能不必各建一个顶层页面。规划模块不提前创建生产空实现。

## 1. 模块分解图

[打开细化功能模块图 SVG](diagrams/rendered/03-function-modules-01.svg)。

```mermaid
flowchart LR
  ROOT[智启课源教学闭环] --> K[知识点中心]
  K --> K1[学科与知识树]
  K --> K2[名称 别名 修订 归档]
  K --> K3[知识点下的关联题目]
  K --> K4[可选教材依据关联]
  ROOT --> QB[现有独立题库升级]
  QB --> QB1[原件导入与草稿校对]
  QB --> QB2[知识点标注与筛选]
  QB --> QB3[题目内容 答案 附件 修订]
  QB --> QB4[AI 整理与补题建议审核]
  ROOT --> C[教学组织]
  C --> C1[班级与学年]
  C --> C2[学生名单导入与消歧]
  C --> C3[入班 离班 历史名单]
  ROOT --> A[测评工作台]
  A --> A1[原卷导入与保真预览]
  A --> A2[题干容器 小题 题号 满分校对]
  A --> A3[小题知识点建议与确认]
  A --> A4[施测班级与参加名单]
  A --> A5[成绩表映射 异常 修订]
  ROOT --> L[学情分析]
  L --> L1[按失分关联知识点]
  L --> L2[学生报告与小题证据]
  L --> L3[班级人数与失分分布]
  L --> L4[历史报告与教师说明]
  ROOT --> P[教案工作台升级]
  P --> P1[课题 课型 时长 目标约束]
  P --> P2[学情与教材证据选择]
  P --> P3[AI 调整建议及理由]
  P --> P4[教师逐项采用与修改]
  P --> P5[临时分组与结构化教案]
  ROOT --> E[针对性练习]
  E --> E1[按知识点选题与排除已用题]
  E --> E2[统一或临时分层练习]
  E --> E3[AI 缺题补充及题库审核]
  E --> E4[学生卷 教师卷 成绩模板]
  E --> E5[练习转测评与成绩回流]
  ROOT --> I[公共基础设施]
  I --> I1[模型冻结与任务恢复]
  I --> I2[幂等 版本冲突 错误信封]
  I --> I3[文件 原件 附件 导出]
  I --> I4[离线备份与引用检查]
```

## 2. 数据依赖图

```mermaid
flowchart LR
  K[已确认知识点] --> Q[题库关联与筛选]
  K --> IP[原卷小题标注]
  CL[班级与名单] --> A[施测]
  IP --> A
  A --> S[成绩导入与正式快照]
  S --> AN[失分关联报告]
  IP --> AN
  AN --> LP[教案建议]
  TB[教材 RAG 证据] --> LP
  Q --> LP
  LP --> EX[已审核练习]
  Q --> EX
  EX --> A2[新施测与回传模板]
  A2 --> S
```

学情分析本身不依赖题库或 RAG 在线：只要原卷、小题知识点和得分已确认，就能完成报告。题库提供可复用题资源；RAG 为备课提供教材依据，不替代成绩事实。

## 3. 代码模块职责建议

| 模块 | 前端建议归属 | 后端建议职责 | 数据拥有者 |
|---|---|---|---|
| 知识点中心 | `features/knowledge-points` | `services/knowledge_taxonomy` | knowledge 库 |
| 教学组织 | `features/classroom`，学生详情作为子功能 | `services/classroom` | teaching 库 |
| 测评工作台 | `features/assessment`，包含原卷/成绩导入子流程 | `services/assessment` | teaching 库 |
| 学情分析 | `features/learning-analytics`，学生画像作为报告视图 | `services/learning_analytics` | teaching 库 |
| 题库 | 复用 `features/question-bank` | 扩展现有 `services/question_bank` | question-bank 库 |
| 教案 | 复用 `features/lesson-plan` | `services/lesson_planning` | teaching 库，兼容旧草稿 |
| 练习 | `features/practice` | `services/practice_generation` | teaching 库 |
| 教材依据 | 复用现有知识库与教材范围选择 | 现有教材目录与 RAG 服务 | textbooks 库及 Qdrant |

路由保持薄层；列表、导入、校对、报告和建议审阅在同一业务模块组织。跨模块类型置于 contracts，仓储只负责本库读取和事务。统一错误信封沿用 `code/message/requestId/retryable/details`。

## 4. 建议入口与页面

| 页面 | 主要操作 | 对外能力状态 |
|---|---|---|
| `/knowledge-points` | 知识树、别名、关联题目、教材依据 | 未实现前 planned |
| `/classroom` | 班级与名单导入 | 未实现前 planned |
| `/assessments` | 测评列表、新建、复用原卷 | 未实现前 planned |
| `/assessments/[id]/paper` | 原卷与小题校对、知识点确认 | 未实现前 planned |
| `/assessments/[id]/scores` | 得分映射、异常与成绩修订 | 未实现前 planned |
| `/assessments/[id]/analytics` | 学生/班级失分关联报告 | 未实现前 planned |
| `/question-bank` | 保留已有入口，新增知识点分类筛选 | 已有能力以 CURRENT_STATUS 为准 |
| 现有教案工作台 | 新增学情依据和 AI 建议，不另起第二个教案系统 | V2 未实现前单独标 planned |
| `/practice` | 练习编辑、审核、导出和回流 | 未实现前 planned |

以上是路由设计，不是现行 API 或路由登记。实施时才同步 `docs/API.md` 与 `docs/ROUTES.md`。
