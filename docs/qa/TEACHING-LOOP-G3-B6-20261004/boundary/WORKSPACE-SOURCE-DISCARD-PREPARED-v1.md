# G3-BOUNDARY 追加完整工作台第 8 例准备记录 v1

- 时间：2026-10-04T13:05:21.872785+08:00。
- 状态：PREPARED_STOP_PENDING_ROOT_RUN。独立准备，未执行，不据此判产品通过或缺陷。
- 新文件：`workspace-source-discard-boundary.test.tsx`；SHA-256 `8b68be843345166c267f08c7e9f2a11ddd8b50cba3d46364129e4141433301fd`。旧 3 文件 / 7 例逐字节保持原 SHA。
- 受测组件是实际 `LessonPlanWorkspace`，包括实际 `ServerControls`、`SourcePanel`、`EditorOverlays`、`EditorContext`、`useServerPersistence`、`LeaveProtection` 与公共壳导航；未仿写 context 同步 effect。
- 匿名 API 服务替身只受控返回固定 BASE/A 业务读取与记录 saveLesson 包；jsdom dialog/File.text/ResizeObserver、next/router 属能力适配。无真实浏览器、FastAPI、正式数据或 HTTP。

行为顺序：完整固定 BASE 和关联来源 → 新报告 A 与 KP 已返回并明确选择（仍未到 600ms）→ 经实际 JSON 导入校验写完整 11 字段 A 稿 → 点击公共“学习问答” → 实际离开对话框明确放弃 → 断言完整可见 BASE 正文、来源报告 BASE、固定 v1 sourceLabel / revisionId / analysisRunId、A KP 不再显示、恢复键为空、保存次数 0 → 3600ms 多周期仍不回写 → 仅新增标题 B 编辑 → saveLesson 只 1 次、原 CAS 1、完整 11 字段（包含原过程 ID）除标题外逐项为 BASE、context BASE、返回缓存固定 v2。

旧自定义 Controls 无 ServerControls，适合原迟到写回反例，不能代表完整工作台的 context 同步职责。第 8 例覆盖该实际集成边界；前 7 例及原首败保持不变。ROOT 应冻结含新文件的候选后执行全 8 例并保留首跑日志/PID/来源 QA 前后核对。本记录不是 G3 CLOSED。
