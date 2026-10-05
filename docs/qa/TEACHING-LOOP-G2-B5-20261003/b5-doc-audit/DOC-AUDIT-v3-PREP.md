# B5 文档预核 v3 · PREP（停止）

本次只读预核，不批准 B5 关闭。ROOT 派卡时 r2 完整浏览器 8 正在运行，原 153/14 尚未执行；我未运行产品、HTTP、数据库或服务，也未参与产品实现。唯一写入为本报告及对应 JSON，权威文档仍由 ROOT 独占。

当前候选 `CANDIDATE-B5-r2.json` SHA `7800205803341a8e737e8d8ee7c0659bd6c264f78f72ce5e4f312ad3f39c5bec`，938 source / 2196 executable QA / 33 frozen contracts / 2004 build，build `EuGU-xptkS4Dv7wiXoxD4`。r2 相对 r1 产品、构建、契约及原 2193 QA 完全相同，仅追加 v6 的 3 个浏览器 QA 文件。没有据 QA 修订要求重复不受影响的 check/API。

## 独立只读保全与成功收据绑定

| 实际核查 | 结果 |
| --- | --- |
| 候选 938 源 / 2196 QA / 33 契约 / 2004 构建 | 逐文件 SHA256 零漂移 |
| 候选已有 1030 证据 | 零漂移；原首败、日志、候选与收据未改 |
| 589 原 G2 实时件 + 2 审批归档件 | 589 零漂移；README/REPORT 归档原字节与开工 baseline approved SHA 一致 |
| 4136 历史证据 | 逐文件 SHA256 零漂移 |
| next-env | 当前 SHA 与开工 `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc` 一致 |
| 新完整 check | 原日志实际 118 files / 1224 passed，exit0，106554.366ms；938 before/after 与 r2 完全相同，2193 原 QA 全保留，日志 SHA 符合收据 |
| 完整 API | 1918 pass / 1 既有规模 skip，exit0；410 后端/测试/脚本/模板 before/after 与 r2 相同。938 整体仅后来 3 个 FE 文件变化，未冒称整个 938 同字节或重跑 API |
| 独立 18 / 42 | 18 exit0 的 938 before/after 与 r2 相同；42 exit0/0skip 的 410 后端 before/after 相同，不拼接旧首敗 |

作者实际恢复 1 例、完整 API 实际运行，与独立 retained sample 的 16 库完整性/FK/全行/两 blob/56 文件只读核对分开。后者不是独立启动完整备份/恢复流程；现有矩阵已如实分列。实际规模 skip 为原 `100叶×200人次` 默认关闭的 XLSX 读取基线，不是新规模通过。

## 具体修订建议

### DOC-PREP-R01 · P2

位置：docs/CURRENT_STATUS.md 的 current-task 顶部与下一动作、docs/NEXT_SESSION_START.md 当前顶部、B5-CLOSE-MATRIX.md 顶部。

本次审读快照中，当前顶部/下一动作仍称r1 938/2193/v6准备；候选r2已于11:38 UTC冻结938/2196/33/2004，仅3新增QA，ROOT下发本任务时完整8正在运行。

修订：仅更新当前段为r2、v6封存和实际运行状态，给候选/QA delta/执行label；不提前写8通过。时间戳18:38/18:47/19:02/19:26历史段不改。

### DOC-PREP-R02 · P2

位置：docs/qa/TEACHING-LOOP-G2-B5-20261003/README.md:3、docs/qa/TEACHING-LOOP-G2-B5-20261003/REPORT.md:3、docs/NEXT_SESSION_START.md:24。

README顶部仍FEv2/unit11/4/R04R05待窄修/browser未执行；REPORT顶部仍独立15执行中/待新构建；NEXT未标原时点的段落仍称prebuild-v1及15执行中。末段补记已有独立18、新1224check/build和browser首1/7。

修订：更新当前摘要；NEXT旧未日期段显式标为准备/18:32时点历史，或引用冻结旧稿保留原事实。REPORT按B5已实现、独立、工程、浏览器/视觉、资源及not_run分段，避免读者靠末段推翻顶部。

### DOC-PREP-R03 · P2

位置：docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/B5-R2-EXTRA-IDENTITY-POLICY-v1.json、docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/b5-runtime-r2-process-identity.json。

19:40额外r2 HTML/proxy身份复核已被automatic approval blocked by policy拒绝，not_run且无重试；当前权威REPORT尚未分列本次阻断。该不可变收据existingEvidence用短名r2-process-identity.json，实际文件是ctrl/b5-runtime-r2-process-identity.json。

修订：新文档明确额外HTTP身份not_run/原因/未绕过，引用实际文件路径及r1实际HTML+同build/r2CIM证据；不改旧policy收据、不把CIM说成新的HTTP成功、不把原计划完整8说成绕过重试。

### DOC-PREP-R04 · P3

位置：docs/modules/lesson-plan/README.md:28。

状态组件段称当前仍只支持单份本地草稿、不处理跨标签页冲突，后面B5后台模式已有多文档/CAS。此句已有本地字样，主要为作用域容易误读。

修订：如需编辑稳定文档，将主语明确为默认本地模式；不要因这一低风险措辞扩大产品或重测。当前API/ROUTES/PROJECT/模块AGENTS未发现新的明确高优先级契约错误。

当前 API/ROUTES/PROJECT_GUIDE/lesson AGENTS 的 v1 正文、FastAPI 唯一后端、五整字段/教师六字段、受控三协议 wire、生产 Rag、CAS/原 receipt、追加迁移与导出边界未发现新的明确高优先级契约错误。本预核没有重做产品实现审查，也不扩张“已有候选”到“全部可用”。

## 关闭前必须补齐

- 独立真实四库浏览器完整8与实际四视口/键盘/焦点/reduced-motion、Word文件内容/100ms打印/固定旧对象未改：RUNNING_OR_PENDING。ROOT任务派发的运行状态；我未运行浏览器或HTTP，首r1完整1/7不能拼绿。
- 原完整153 E2E及原14聊天新候选实际门禁、26原图独立审阅与CV边界：NOT_RUN_AT_TASK_START。不可引用G2/B4历史绿结果为B5重跑。
- 所有本次自有API/frontend/stream/worker/浏览器/连接退出、端口释放、TEMP登记保留、用户进程不动：PENDING。r1 API closed，r2 API18736 serving，frontend27964 serving；本次只读现成收据未核现场CIM或控制生命周期。
- 最终源QA/33/2004/589+2/4136/next-env保全与exact-doc独立审批：PENDING。本PREP只在当前快照实测零漂移；必须最终资源退出后再审精确文档候选。

真实供应商教学质量、Word/WPS 人工排版、实际 PDF 保存、正式 Qdrant6333、正式数据迁移及更大压力均须继续显式列为未执行；既有 RAG-REL、R-14 与 CV 台账保留。额外 r2 身份 HTTP 命令被 automatic approval 以 blocked by policy 拒绝，not_run且未换工具/命令/端口/Agent重试；同一前端 r1 实际 HTML + r2 同 build/当前 CIM 证据可引用，但不能称新 r2 HTTP 复核成功。

ROOT 更新当前摘要并完成所有必要技术门禁和自有资源退出后，应另冻结 exact-doc 候选交独立后验。本 PREP 只提供问题和当前散列观察，不是 B5 关闭审批。原有时间戳运行记录应保持当时事实，不回改历史制造当前全绿。

问题针对 JSON 的 inputSnapshotSHA256 所载审读快照；ROOT 并行后续文档修订应另以新快照复核，本报告不追改原审读事实。
