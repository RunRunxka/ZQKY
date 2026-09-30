# 整体架构图 v1.1 修订规格

日期：2026-09-30。方式：内置 imagegen；模式：编辑（edit）。

编辑目标：[v1.0 原图](diagrams/rendered/00-overall-architecture-v1.png)。输出：[v1.1 修正版](diagrams/rendered/00-overall-architecture-v1.1.png)。原图保留用于追溯，当前展示以修正版为准。

修订原因：教案已有编辑、预览、规则填充、本机草稿和 Word/PDF 打印能力，不能将整个教案入口标为待建设。学情驱动 AI 调整、教学业务数据库和针对性练习闭环仍待建设。

```text
Edit the provided ZQKY architecture infographic. Preserve its entire five-band blue/white design, dimensions, clear Chinese typography, icons, connectors, independent knowledge system, exact score-loss rule, database counts, and teaching feedback loop. Make only the following factual corrections so existing lesson-plan capabilities are not incorrectly labeled unimplemented. Enlarge affected cards/bands moderately if needed for readable text.

1. In the small upper-right title note, change "目标设计 v1.0" to "目标设计 v1.1".
2. The LAST card in the top entry row currently "教案与练习" with amber 待建设. Change heading to "教案工作台", with BLUE badge "现有基础 + 升级设计" and a small additional line "针对性练习待建设". Existing lesson workspace is implemented.
3. In layer 2, the right-middle card currently "AI 教案调整", replace it with heading "教案工作台与 AI 升级". Use blue "现有基础 + 升级设计" status badge. It must contain TWO readable lines:
"现有前端：编辑 · 规则填充 · 草稿 · 导出"
"待建后端：学情驱动 AI 调整 · 教师审核"
Do not claim current rule-based filling is real AI, or current local lesson editing is already a backend service.
4. In left band-2 small description, use "新增业务统一 FastAPI · 模块化单体" rather than implying all existing editing is on the backend.
5. Below the storage row, retain the existing cross-database/version note and ADD a compact second line:
"现有教案草稿存浏览器本机；教学 SQLite 为待建设升级"
It must clearly distinguish current browser local draft storage from the planned teaching-business database, which remains 33 new tables.
6. Leave "针对性练习" and the loss-analysis-dependent "AI 教案调整" step in the bottom TARGET teaching loop as planned target capabilities; the whole poster remains a target architecture with existing plus planned status. Keep all other labels and arrows.
7. Change small final footer note to:
"现有教案支持 Word 下载 / PDF 打印；学情驱动 AI 与练习闭环待建设。"
Current PDF is browser print / save as PDF, not server PDF generation. Do not imply server PDF export is implemented.

Keep the exact learning rule: 相关小题只要有失分 → 关联知识点列为需巩固. Preserve no automatic grading/no scoring-point extraction/no mastery probability. No other new features. High-resolution crisp simplified-Chinese infographic.
```
