# B6-R01：来源总列表加载与报告选择的并发恢复

2026-10-04 14:19 CST。ROOT 判定实际 browser-r6 为需修复核实的可操作并发缺陷候选，不以修改 QA 等待顺序隐去失败。G3 已关闭的历史收据保持；本次新增产品候选另行冻结与门禁。

| 项 | 范围 |
| --- | --- |
| ID / 版本 | B6-R01 / v1 |
| 实现负责人 | g3_impl |
| 可写产品 | `apps/web/src/features/lesson-plan/components/SourcePanel.tsx`；新增模块 `b6-source-loading.test.tsx` |
| 自有证据 | `b6-integration/**`；全部旧首败与源快照保持 |
| 独立验收 | g3_v00 在 `b6-exports/review-source/**`；ROOT 集成与最终冻结 |
| 修前证据 | browser-r6：新后台教案创建成功、报告与两个知识点显示，模型及教材 taxonomy 未填充，加载状态持续；标准模型 GET 200 |
| 原因候选 | `load()` 与报告/切片/问题共用 source epoch；可用的报告选择使 metadata owner 失效，finally 也不释放 loading |
| 必要正确行为 | metadata 迟到时，用户报告选择已完成仍能取得模型/年级/版本且 loading 结束；旧 metadata 不自动覆盖新选择；刷新最新 owner 生效；discard / document / store / session 变化继续撤销旧响应 |
| 技术门禁 | 作者定向与独立正确行为；新完整 check / build / 原字节 next-env；受影响 G3 来源守卫；新真实浏览器 B6 全链与延迟反例；原完整153；无后台/DDL/导出器/共享契约变更时精确复用原 API/恢复/导出证据 |

不允许扩大为新模块、重设计或新后端。ROOT 独占文档、构建与服务。任何失败保留完整记录；只按新单轮统计最终结果，不拼旧通过部分。
