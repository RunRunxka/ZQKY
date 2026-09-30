# 整体架构图生成规格

生成方式：内置 imagegen；模式：全新生成（generate），无参考图片输入。日期：2026-09-30。

成图：[整体架构图 PNG](diagrams/rendered/00-overall-architecture-v1.png)。业务含义以 [架构说明](00-overall-architecture.md) 和数据库设计分册为准；下方保存实际使用的生成提示词，便于后续调整图像。

```text
Use case: infographic-diagram.
Create a NEW polished Chinese system architecture infographic for a teacher-facing project. This is a PROJECT DESIGN image, not a claim of implemented software. Landscape 4:3 canvas, very high resolution, crisp simplified Chinese, attractive blue/cyan engineering poster, white background, navy headings, rounded white cards on pale blue horizontal bands, small simple flat blue icons, carefully routed arrows. Use ample whitespace and very readable text, avoid microscopic text. Match the visual spirit of a clean five-layer enterprise architecture diagram. All Chinese labels must be accurate; no garbled words. Do not invent any extra modules or capabilities.

Exact title: “ZQKY（智启课源）整体架构图”
Exact subtitle: “独立知识点体系 · 小题失分学情分析 · AI 备课 · 针对性练习闭环”
Small title note: “目标设计 v1.0｜现有基础 + 待建设模块｜2026-09-30”
Legend: blue pill “现有基础”; amber pill “待建设”. For modules with existing and new parts use “现有基础 + 升级设计”. These statuses must be intelligible.

Organize into FIVE numbered horizontal bands, with a narrow left label column and wider main area. Text below is exact content to include, though you can rearrange it inside cards for good composition.

BAND 1 label “1. 用户与应用入口层”, small “教师端 Web · Next.js”.
Seven compact portal cards or a neat seven-part row:
“学习问答”, “教材资料库”, “知识点中心”, “题库”, “班级与测评”, “学情报告”, “教案与练习”.
Show knowledge center, classroom/assessment, analytics, AI lesson/practice as planned amber, existing chat/textbooks as existing blue, question bank as existing base plus upgrade. Do not place unverified URL routes.

BAND 2 label “2. 业务能力层”, small “唯一 FastAPI · 模块化单体”.
This band is the visual center and tallest band. A prominent central blue card:
“独立知识点体系”
“知识点 ID · 知识树 · 别名 · 内容修订”
“题目、原卷、教材、学情、教案统一引用”
badge “待建设”.
Around this card, six connected business capability cards arranged clearly, with clean connectors to the center:
a. “教材管理与 RAG” / “解析 · 混合检索 · 教材证据” / badge “现有基础”.
b. “题库管理与审核” / “导入 · 草稿校对 · 知识点分类” / badge “现有基础 + 升级设计”.
c. “原卷与成绩对齐” / “小题拆分 · 知识点确认 · 学生与题号匹配” / badge “待建设”.
d. “学情分析服务” / “按实际失分关联知识点 · 学生与班级报告” / badge “待建设”.
e. “AI 教案调整” / “学情与教材依据 · 调整理由 · 教师审核” / badge “待建设”.
f. “针对性练习” / “按知识点选题 · AI 补题审核 · 导出与回流” / badge “待建设”.
A narrow support strip beneath these cards: “公共支撑：现有模型管理｜建议审核｜版本与幂等｜任务与导出”.
Make the two following rule callouts prominent and verbatim:
“学情规则：相关小题只要有失分 → 关联知识点列为需巩固”
“业务边界：接收已给分成绩，不改卷、不拆评分点、不预测掌握概率”
The central knowledge point connects directly to questions; textbooks are optional evidence, NEVER depict textbook → knowledge → question as a mandatory ownership hierarchy. A question may link multiple knowledge points without duplicating question text. Do not show weighted knowledge mastery, scoring rubrics, prerequisite graphs, learning-path prediction, online automatic exams, or automatic marking.

BAND 3 label “3. 数据输入层”, small “教师提供 · 预览校对 · 确认导入”.
Five input cards:
“教材 / 教学资料” / “原文与教材依据”
“原始试卷 DOCX” / “完整题干 · 小题 · 公式配图”
“小题得分 XLSX / CSV” / “教师已给出的分数”
“学生名单 XLSX / CSV” / “稳定身份 · 学号与班级”
“题库题目 / AI 补题” / “确认后选用，建议先审核”
Make clear this is supplied data flowing UP into services, and persisted DOWN into storage; do NOT imply services generate original supplied score sheets or student rosters.

BAND 4 label “4. 数据与存储层”, small “分库职责明确 · 历史依据保留”.
Six storage cards:
“独立知识点 SQLite” / “知识点 · 修订 · 别名 · 教材关联” / “新增 5 表 · 待建设”
“独立题库 SQLite” / “题目 · 修订 · 导入审核 · 知识点关联” / “现有 9 表 + 新增 1 表”
“教学业务 SQLite” / “班级 · 原卷 · 成绩 · 学情 · 教案 · 练习” / “新增 33 表 · 待建设”
“教材目录 SQLite” / “原文修订 · 分块 · 索引代” / “复用现有”
“Qdrant” / “仅教材向量检索” / “复用现有”
“受管文件存储” / “原件 · 配图 · DOCX / PDF 导出”
Below storage, a very short note: “跨库引用由服务核验；正式修订不可变；修改生成新版本”.
Never store student scores or question-bank text in Qdrant.

BAND 5 label “5. 核心教学闭环”, small “数据驱动备课 · 教师审核执行”.
Six steps in left-to-right arrow sequence:
“原卷 + 小题成绩” → “失分关联学情” → “学生 / 班级报告” → “AI 教案调整” → “针对性练习” → “新成绩回流”.
A visible feedback arrow from the final step back to the SECOND step labeled “复用同一分析流程”.
Small rule note beneath: “缺考与空白不当零分；综合题只关联薄弱项，具体错因由教师确认”.
Bottom roadmap footer:
“实施顺序：数据对齐 → 学情报告 → 练习回流 → AI 备课”
Small final note:
“首版优先 DOCX；PDF 能力按实际实现提供。图中待建设内容不代表已经上线。”

Layout precision: no crossed lines over text, no illegible tiny dense paragraphs, no duplicate titles, no random English. Blue and cyan dominant, amber only for planned badges. The central knowledge system and loss-based learning analysis rule should stand out. Use the supplied text faithfully, resolve tight spacing by enlarging canvas and simplifying ornamentation rather than deleting key information.
```
