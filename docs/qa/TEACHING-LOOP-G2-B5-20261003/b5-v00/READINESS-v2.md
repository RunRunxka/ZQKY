# B5-V00 v2 增量准备封存

父任务明确新增历史复制正确行为验收，因此 v2 只增加 `browser/history-copy.spec.ts`、`browser/external-v2.config.ts`、本卡、静态证据与 v2 清单；v1 17 个文件全部原字节保持，原清单 SHA `b094eb8c51a5217758e468bd88e36c75f2cc30733dd6ca8f32fab1af74be99fc` 不变。

新增真实 browser 场景以两份手写 11 字段（rule 固定 v1 / manual 固定 v2）为独立 oracle。打开真实历史 URL → 只读 → 打开当前准备复制 → 确认真实 Next URL 已移除 revisionId → 明确复制按钮仍持有历史对象 → 全 11 字段与过程完整相等 → dirty/基线 v2 不动 → undo 回到 manual → redo 历史正文 → 保存新 manual v3 → undo/保存新 v4；原固定 v1/v2/v3 逐一完整读取不变。复制之前完成真实导航与 HTTP GET，之后暂停浏览器 autosave 计时以检查明确操作，没有替换业务 fetch。

静态展开数量共 **59**：API **42**、unit **10**、browser **7**。自身 TS 语法和 AST 静态检查仍为零诊断，v1 Python 语法结果复用未改源码的同一证据。框架收集和产品执行仍 **not_run：等待 CTRL 明确稳定 CANDIDATE-B5-rN**。没有调整测试超时、重试或预算。

运行方式沿用 READINESS-v1，真实 browser 的 config 改为 `docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/browser/external-v2.config.ts`。API 与 unit 路径保持，新 label 不得复用。执行后任何 QA 自身修正先保全首次原件并向 CTRL 报告、另开 QA revision；产品缺陷交 CTRL 修。

2026-10-03：V00 v2 自身 QA 源码停写，等待候选冻结。静态证据 `preparation/prepare-v2.json` 和 `QA-MANIFEST-v2.json` 供 CTRL 冻结绑定。
