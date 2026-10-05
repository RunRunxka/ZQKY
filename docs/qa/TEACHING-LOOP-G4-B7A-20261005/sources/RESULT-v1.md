# G4-S v1 作者结果（STOP，待独立验收）

2026-10-05，负责人 g4_s。唯一产品改动为 `apps/web/src/features/lesson-plan/components/SourcePanel.tsx`；唯一新增作者测试为 `apps/web/src/features/lesson-plan/g4-source-intent.test.tsx`。已停止产品及测试写入，由 ROOT 冻结、构建后释放独立正确行为与实际业务浏览器验收。

显式教材清除现在推进独立 `verifyIntent`，即使原证据和新证据均为 null 也撤销此前核验。每次新核验获得新意图，在读取教材和核验依据两个 await 后以及显示迟到错误前，同时检查意图、原 source owner、mode/document/store/live session，以及原 selection/value 签名。卸载与 discard 也推进意图。

教材清除只修改 evidence，没有推进通用 source epoch，未清题目／练习选择或修改模型、要求、时长、classReady。年级／版本、selection、文档／store／session 的现有 source 守卫仍有效；metadataEpoch、source epoch、pending-report owner 完整保留。documentId/start/end 编辑仍表示准备下一片段，不新增取消语义；已提交的固定片段仍可返回并被采用。

| 自检 | 本轮实际结果 | 证据与边界 |
| --- | --- | --- |
| 新作者来源行为 | 29/29 | 公开 SourcePanel DOM 操作；手写 API 与会话边界替身。包含 getSource/verify × null/非空 × 单清/双清、两阶段旧错误、新核验、原签名、年级/版本、doc/store/session/mode/discard、参数语义、待处理报告与题读取、卸载 |
| 原 B6 来源作者 | 5/5 | 原测试只读，新轮新输出；未拼接旧轮结果 |
| 原 G3 来源作者 | 5/5 | 原测试只读，新轮新输出 |
| 原独立 Source 8 oracle | 8/8 | 作者运行既有独立 oracle，不代替独立验收者签收 |
| 上述四文件完整单轮 | 47/47，exit0 | Node24/Vitest3.2.4；PID20636；8916.619ms；0 skip/todo，未配置 retry；9个监控文件 before/after 相同。`author-first-COMMAND.json`、`author-first-results.json`、`author-first.log` |
| 两个新增/改动文件 ESLint | exit0，零警告 | PID21020；11199.152ms；`lint-first-COMMAND.json`、`lint-first.log` |

没有本专属执行失败；旧 B5 精确基线、B6 审查清除首败、历史 Source 8 与配置均未修改。现行共享现场 main 与 UI/GSAP 成果由 ROOT 开工基线保全；本 Agent 未执行任何 Git 操作。

本轮未执行 typecheck／完整 check／build／E2E／实际业务浏览器／后端／真实模型／教师评价／Word-WPS。新产品类型、工程与浏览器门禁由 ROOT 集成后执行；这里的来源 API 响应仅为隔离组件替身，不宣称真实 RAG 核验。建议真实浏览器保持 `route.fetch()` 获得的实际 source 与 verify 响应，分别在清除点击后释放，核可见来源与实际生成请求不含旧 evidence；另验证清除后的新核验。不得重试被拒的额外 HTTP 身份探针。

命令/时间/完整 SHA/TEMP 见 [RESULT-v1.json](RESULT-v1.json)。两个子进程和日志句柄均已关闭，没有服务或浏览器归本 Agent 持有。两个新 TEMP 保留；未读取正式缓存、凭证、`.env` 或导入 `app.main`。

独立重跑可使用 `vitest.config.ts` 的明确四文件集合，将报告写入本批新的不可覆盖 label。V00 应增加自己的清除 oracle 与真实响应验收，不以这 47 例的作者数量代签。
