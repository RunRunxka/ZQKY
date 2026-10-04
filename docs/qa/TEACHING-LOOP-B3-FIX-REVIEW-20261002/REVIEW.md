# B3 修复候选 r7：独立代码审查与 B4 前置

审查日期：2026-10-02。用户请求“review 实现代码，给出下阶段提示词”。本次审查未修改产品，未实施修复或启动 B4，未提交/推送/部署。现行用户规则、根/模块 AGENTS、CURRENT_STATUS 和 PROJECT_GUIDE 为边界；交付报告作为被核查的历史证据。

## 结论与候选身份

实际 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`；审查对象包含本次尚未提交的 B3 修复实现。开工 r7 **168/168 磁盘 SHA-256 一致**；用户 `next-env.d.ts` 的 SHA 为 `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`。基线见 [BASELINE](BASELINE.json)，收尾见 [FINAL-VERIFICATION](FINAL-VERIFICATION.json)。

原 B3-R01–R10 对应修复和相关窄回归通过。当前候选仍有 **8 项 P2 待修**；其中租约项覆盖成功发布和失败收敛两条路径。这些发现没有全部归因为本批新引入，也不追改旧验收结论。下一阶段建议按 **G1 修复并独立验收 → B4 学情与练习闭环**推进，固定成绩与题目输入通过 G1 后再作为 B4 基线。

## 具体发现

### B3F-R01 · P2 · 未保存的成绩校对仍能确认旧矩阵

位置：[ScoreImportReview.tsx:153](../../../apps/web/src/features/assessments/ScoreImportReview.tsx:153)、[确认按钮:557](../../../apps/web/src/features/assessments/ScoreImportReview.tsx:557)、[弹窗提交:632](../../../apps/web/src/features/assessments/ScoreImportReview.tsx:632)。

教师进入“预览承认”后仍能编辑小题分数。将某格从 2 改成 1，界面显示 1 和“有未保存的校对”，确认按钮与弹窗提交仍可操作；POST 只携带旧 `expectedImportRevision/previewVersion`，没有保存校对。独立组件探针记录旧包发出并显示受控成功回执；按真实后端只确认持久化矩阵的契约，未保存的新输入不会进入正式版本，形成教师看到的数据与提交版本不一致。该前端反例没有冒称真实浏览器全链已执行。

应在进入承认、打开弹窗及真正提交三个入口核对 dirty/saving/版本；继续编辑要撤销对应预览承认。未知响应重放仍保持原冻结请求，不能因新增守卫破坏已经提交的幂等确认。

证据：[独立前端报告](frontend/REPORT.md)、[三个正确行为反例](frontend/score-edit-boundaries.test.tsx)。

### B3F-R02 · P2 · 迟到映射保存覆盖后续输入

位置：[ScorePanel.tsx:279](../../../apps/web/src/features/assessments/ScorePanel.tsx:279)；可继续编辑的输入见 [第547行](../../../apps/web/src/features/assessments/ScorePanel.tsx:547)。

教师保存 `totalColumn=F`，请求尚未完成时输入仍启用，可改成 G。保存响应到达后代码无条件清 dirty 并 `setMappingDraft(mappingFromView(next))`，G 被替换回 F，还显示“已保存映射”。对象 epoch 只能防切换，不能识别同一对象上的后续编辑。

保存应冻结本地编辑序号：成功只 ACK 发出的版本；若用户已继续编辑，保留新输入及 dirty，仅更新服务端版本。或在该请求期间锁定整组映射编辑并明确显示状态。验收需覆盖迟到 200、409、422、刷新及 StrictMode。

### B3F-R03 · P2 · 返回施测时无法看到刚补入的名单

位置：[AssessmentsPanel.tsx:94](../../../apps/web/src/features/assessments/AssessmentsPanel.tsx:94)、[RosterPanel.tsx:363](../../../apps/web/src/features/assessments/RosterPanel.tsx:363)。

工作区保留访问过的面板挂载。先到“施测”加载甲，再回“名单”添加或导入乙，名单页能看到甲/乙；返回同班“施测”仍只有甲，乙无法勾选。学生资源 key 只有 classId，名单更新仅刷新名单面板的局部资源，没有贯穿工作区的名单变化版本或施测刷新入口。

让新增、导入确认、转班等名单变更通知施测学生资源。刷新名单保留仍有效的勾选、出勤与班级依据编辑；移出的学生明确处理，不用强制卸载面板丢弃全部草稿。

### B3F-R04 · P2 · 超长 XLSX 分数被静默截断后封存

位置：[tabular.py:244](../../../apps/api/app/services/tabular.py:244)、[通用字符串截断:51](../../../apps/api/app/services/tabular.py:51)。

成绩双视图读取复用会截为 20,000 字符的 `_cell_to_text`。真实 XLSX 字符串 `1.` + 19,998 个 `0` + `1` 长 20,001：直接精度校验应拒绝，读表后最后的 `1` 丢失，被解析为合法 1 分。实际 HTTP 上传 201、预览无阻断、确认 200，正式矩阵写入 `recorded/100`，总分 600 单位。

成绩原值及公式缓存不能使用展示截断作为数值输入；超过受支持长度应带物理行列定位拒绝，零正式成绩写入。需要检查身份、出勤、总分、公式缓存同一路径，而不是仅补一条数字正则。

证据：[真 HTTP 收据](scores/probe-results.json)、[后端报告](scores/RESULT.md)、[正确行为红断言](scores/review-assertions-log.txt)。

### B3F-R05 · P2 · 任务终态写入没有在写锁内统一核实实际租约时间

位置：[JobStore.complete:520](../../../apps/api/app/repositories/jobs/repository.py:520)、[_require_current_lease:656](../../../apps/api/app/repositories/jobs/repository.py:656)、[fail_if_current_lease:580](../../../apps/api/app/repositories/jobs/repository.py:580)。

成功发布只核 token/attempt/running，不核 `lease_expires_at`，已到期执行者仍能发布业务数据并进入 succeeded。独立逻辑时钟探针 TTL=3、完成时刻=4，业务 sentinel 仍写入；另覆盖引擎最后一次检查后到提交前跨过 expiry。

失败收敛虽新增到期核验，却在 `BEGIN IMMEDIATE` 获取写锁前采时。探针实际持有 SQLite 写锁，让收敛等待跨过到期点，释放后仍以旧时间写 failed。两条路径都必须在拿到写锁、读当前行之后采时，并同时核 token/attempt/state/expiry/cancel；失权零业务及终态写入，取消优先，发布失败事务回滚保持。

### B3F-R06 · P2 · 前一轮收尾期间的公共 retry 吞掉新轮调度

位置：[registry.py:91](../../../apps/api/app/services/jobs/registry.py:91)、[引擎收尾:184](../../../apps/api/app/services/jobs/engine.py:184)。

任务已写失败终态，旧 asyncio task 还在等待心跳收尾，`is_tracking` 仍为真。此时公开 retry 成功把 DB 改为 queued，注册表因旧 tracking 直接返回已调度。旧 task 收尾退出后，没有新执行者：实际 HTTP 200 queued@1，最终仍 queued@1、tracking=false、执行次数只有第一轮。

独立探针用事件屏障延长现有收尾窗口，没有伪造服务结果。调度需区分旧轮收尾与新轮已安排；可登记一次待调度或串接上一轮结束再执行，仍保证并发重复 retry 恰好一轮、无双执行者。旧轮收尾后再次 POST 可补调度 queued；问题是第一次 HTTP200 已接受的重试没有自动兑现，不能要求教师再次点击才能兑现这次回执。

### B3F-R07 · P2 · 共同材料不同的题仍按旧指纹跳过

位置：[QuestionBankService 确认查重:1923](../../../apps/api/app/services/question_bank/service.py:1923)。

两题 plain 字段相同，共同材料分别为 `1 mol/L` 和 `2 mol/L`；富内容 `derived-v1` 指纹不同，确认却继续用旧 `content_fingerprint` 查重。第二题默认被静默 skipped，`failures=[]`；明确 `edit_as_new` 仍得到 `DUPLICATE_UNRESOLVED`。不同题目的教师确认结果因此丢失，后续针对练习也取不到第二题。

新富内容题的重复判定要使用版本化、覆盖共同材料/公式/受管图片真实字节的身份；旧指纹保留兼容，并明确新旧版本比较规则。统一校对预览、确认、显式去重操作的口径，原件 byte-identical 的真重复仍应识别。

任务与题库三项证据见 [独立报告](jobs-questions/RESULT.md)、[五条正确行为红断言](jobs-questions/probes-final.log)、[公开 retry 收据](jobs-questions/test_review_jobs_questions.py)。

### B3F-R08 · P2 · OMML 分隔公式静默丢失第二个参数

位置：[RichContentRenderer.tsx:39](../../../apps/web/src/components/ui/RichContentRenderer.tsx:39)、[分隔公式分支:55](../../../apps/web/src/components/ui/RichContentRenderer.tsx:55)。

合法 OMML `m:d` 可以包含多个 `m:e`，中间用 sepChr 分隔；例如 `(x|y)`。renderer 的 `group('e')` 只取首项，呈现 `(x)`，没有“不支持”提示。独立组件诊断覆盖 `|` 和 `,` 两种分隔符，均丢失 y；原 XML 虽保存在折叠详情中，正常题面预览已经失真。

应按顺序完整呈现所有参数及 sepChr，或者对不支持的结构明确回退到原 XML 核对提示，不能显示一个貌似成功但少项的公式。合法性依据为 [Microsoft Open XML Delimiter 文档](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.math.delimiter?view=openxml-3.0.1)；分隔符语义见 [SeparatorChar](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.math.separatorchar?view=openxml-3.0.1)。

证据：[实际 renderer 诊断](rich-renderer/omml.test.tsx)、[运行结果](rich-renderer/vitest-final.log)。**2 passed 表示错误行为被稳定复现，不表示产品正确**。初次探针配置遗漏自动 JSX 导致的 React 引用错误保存在 vitest.log；补齐探针配置后复现，不修改产品。

## 验证范围与剩余观察

| 本次实际命令范围 | 结果 | 证据 |
| --- | --- | --- |
| 成绩/施测/出勤/精度/预览/tabular 11 个既有文件 | 127 passed / 1 skipped；exit 0 | [scores/RESULT](scores/RESULT.md) |
| 显式启用 200×100 后端单项 | 1 passed；exit 0 | 同上；前一轮跳过不能冒称规模通过 |
| 成绩独立正确行为 | 1 failed / 1 passed；exit 1 | 截断失败；旧固定卷/人次/矩阵在新修正后保持通过 |
| 公共任务/模型守卫/题库富内容与发布窄回归 | 91 passed；exit 0 | [regression.log](jobs-questions/regression.log) |
| 任务与题库独立正确行为 | 5 failed；exit 1 | [probes-final.log](jobs-questions/probes-final.log) |
| 前端 15 个既有相关文件 | 195 passed；exit 0 | [regression.log](frontend/regression.log) |
| 前端独立正确行为 | 3 failed；exit 1 | [反例结果](frontend/score-edit-probes-3.log) |
| 受控迁移两文件 | 10 passed；exit 0 | [migrations.log](migrations.log) |
| 实际 renderer 的 OMML 诊断 | 2 passed；exit 0 | 诊断错误行为，非产品验收 |

这些计数分别属于独立命令，不合并重复样本，也不把旧交付的 1523/check1069/E2E153 记成本次重跑。窄回归通过与反例失败同时保留。

观察项 O1：131,073 字符的 CSV 备注（整文件约 131KB，小于文件大小限制）触发 `csv.Error`，返回纯文本 500，零导入。后续需统一字段上限与结构化解析失败，尚未列作本轮主要阻塞。

观察项 O2：XLSX dimension 元数据缩小会使 read-only 读取漏掉原件中后续行，被当缺行 missing；确认仍需教师承认 missing。该探针涉及不一致元数据，列作读取完整性加固，不等同于正常 Excel 文件都漏行。见 scores/probe-results.json。

未执行：本次全量 API/check/build/E2E、真实浏览器视觉复验、真实供应商/模型质量、Word/WPS、Qdrant、正式数据迁移、超基线压力、多进程跨库协调。后端均在任何 `app.main` 导入前隔离 ZQKY_DATA_DIR；前端用独立 jsdom。没有读取正式业务数据或凭证，没有启动监听服务；本次新增临时数据目录保留登记，旧六个审批拒绝删除目录没有处理。

## 下一阶段范围

复制 [B4 总控启动提示词](../../design/teaching-loop-v1/B4_总控启动提示词.md) 到执行会话：先按本报告完成 G1 修复与独立正确行为复验，再推进 T70 学情事实/证据、T80 针对练习/审核/DOCX/施测回流及相应页面。F20 已完成的导入、出勤、修正、历史能力继续复用；T90 学情驱动 AI 教案留下一批，保留既有本地教案能力。

本报告与提示词是本次交付的文档。当前 review 会话没有执行 G1 或 B4，不把尚未完成的修复改写为已关闭。
