# G1+B4 任务卡

CTRL `/root`，v1，2026-10-02。起点 main@6aeb57280f6a7e0d7391cad4d150745479ea58ec，加既有未提交B3-FIX r7；168项0差异。各精确起点SHA以BASELINE.json.sourceFiles为准，新路径起点为不存在。旧629份证据逐字节保护；next-env.original.bin为本次现场保护对象。最多root+3Agent，不切分支/暂存/提交/推送/部署，不读.env/正式业务库，不碰旧六临时目录。

## G1-FE v1

负责人 `/root/g1_fe`。依赖：现行服务契约不变。关闭B3F-R01/R02/R03。

可写产品仅：
- apps/web/src/features/assessments/ScoreImportReview.tsx
- apps/web/src/features/assessments/ScorePanel.tsx
- apps/web/src/features/assessments/AssessmentsWorkspace.tsx
- apps/web/src/features/assessments/AssessmentsPanel.tsx
- apps/web/src/features/assessments/RosterPanel.tsx
- apps/web/src/features/assessments/RosterImportPanel.tsx

对应直接测试可写：上述同名`.test.tsx`六文件（RosterPanel/Workspace测试如不存在可创建）。证据只写本目录g1-fe/。不改contracts、客户端、公共hook、CSS、路由/导航。共享例外无；额外路径先向CTRL提建议并等待登记。

验收：未保存校对所有确认入口零POST，弹窗打开后编辑同样阻断；保存后重新权威预览/承认并持久化新分数；未知响应仍重放原冻结包。映射较新编辑成功/409/422/网络失败/刷新/切换/卸载/StrictMode不丢。真实名单新增/导入/转班通知已挂载施测资源刷新，保留合法勾选/出勤/人次并明确撤销说明。相关Vitest正确行为场景通过。

## G1-SCORE v1

负责人 `/root/g1_score`。依赖CTRL只写tabular.py；关闭R04测试与成绩路径集成。

可写产品仅apps/api/app/services/scores/imports.py、apps/api/app/services/scores/service.py、apps/api/app/repositories/teaching/scores.py（无需改则保留）；直接测试仅apps/api/tests/test_g1_score_text_boundaries.py（新）。证据只写本目录g1-score/。公共tabular/contracts/main/迁移不写，向CTRL提交具体建议。

验收：XLSX/CSV长原值完整或定位422，不截断；身份/出勤/总分/小题、公式/缓存、有效尾零/非零尾/有效0/四态；拒绝后导入/正式矩阵零写，受管原件字节不变。csv.Error和恶意dimension按观察范围审查，触及时补错误信封，不扩成新门槛。隔离根和credentials_file=None在任何app.main导入前生效。

## G1-QB v1

负责人 `/root/g1_qb`。关闭R07。

可写产品仅apps/api/app/services/question_bank/service.py、apps/api/app/services/question_bank/fingerprint.py、apps/api/app/services/question_bank/rich.py、apps/api/app/repositories/question_bank/catalog.py。直接测试仅apps/api/tests/test_g1_question_duplicate_identity.py（新）。证据只写本目录g1-qb/。公共任务/renderer/contracts/迁移不写。

验收：权威共同材料/题干/选项/公式/表格/图片字节参与版本化题面去重；预览、确认、edit_as_new同口径；1mol/L与2mol/L两题均可入库，真正相同题去重，答案冲突仍需教师解决。兼容旧plain题和旧指纹；IO在事务/发布锁外，重放先于当前校验。相关API真临时四库正确行为通过。

## G1-CTRL v1

root独占apps/api/app/repositories/jobs/repository.py、apps/api/app/services/jobs/engine.py、apps/api/app/services/jobs/registry.py、apps/api/app/services/tabular.py、apps/web/src/components/ui/RichContentRenderer.tsx及对应公共测试（test_g1_job_lease_retry.py、test_tabular.py、RichContentRenderer.test.tsx）。关闭R05/R06/R08和R04公共读表。

v1.1共享测试例外：CTRL独占apps/api/tests/test_question_generation.py，仅更新既有派生指纹版本化测试的算法行数量断言，分别验证旧derived-v1与新增question-surface-v1各一行；保留旧列不变和历史补算断言。原97例首败由G1-QB保留，G1-QB不写该文件。

拿SQLite写锁后采时并核原lease/cancel/expiry；等锁跨expiry零写；cleanup retry真实ASGI接受语义兑现且恰好下一轮，tracking身份安全；delimiter多m:e/sepChr完整且安全。root独占共享契约/客户端/资产服务/迁移/装配/导航/权威文档/依赖锁/Git；资源8001/5174/构建由root独占。

## 结果格式与后续门槛

实现者按任务ID/版本/起点、逐文件变化、实际命令/退出码/单次计数/首败、未执行、跨域建议、残余风险、资源写RESULT.md，状态ready_for_review后停止写入。root冻结完整G1产品/测试/配置/锁SHA；独立V00与实现者分离、只读产品，写新独立子目录。验收失败由原写入者修复、重冻、再验，禁止边验边改。

B4未开始。仅G1八项与适用回归全部闭合后，CTRL冻结B4契约/迁移任务卡v2；随后分派T70/T80/F，各精确新路径再登记。不提前起T90/B5。用户授权全文按本次附件执行。

## G1-V00 v1：冻结后的独立验收

起点统一为CANDIDATE-g1-r1.json，825项完整文件及各自SHA；实现者全部ready且停写，CTRL停止修改候选。旧629份证据逐字节保护。无产品/测试/共享文件可写例外。以下三个目录不存在时已核无重叠后登记：

- G1-V00-FE负责人新独立Agent g1_v00_fe：只写本批v00-fe/**，自建配置/fixtures/反例/收据/报告；独立正确行为R01/R02/R03/R08。组件替身覆盖竞态，另在root提供的5174浏览器/8001真API窗口执行名单新增/导入/转班、校对保存后新分数确认；可用延迟/丢响应代理但业务响应必须来自实际FastAPI。root独占build并提供启动完成通知，Agent仅操作隔离浏览器测试上下文，不操作用户浏览器。
- G1-V00-JOBS负责人新独立Agent g1_v00_jobs：只写本批v00-jobs/**；独立R05两条边界及R06真实ASGI收尾barrier、重复retry、tracking身份、取消/重启/错误、过期/失权零业务/checkpoint/终态；写锁barrier在入事务尝试处触发，不能依赖旧探针错误的锁前读钟；不改TTL。
- G1-V00-SCORE-QB负责人新独立Agent g1_v00_score_qb：只写本批v00-score-qb/**；独立R04/R07真实四库HTTP、长原值定位和零写/源保护、材料/富题面查重、同包真重复/答案冲突/旧指纹兼容和原包重放。禁止调用生产identity函数作为期望值oracle，可调用被测服务正常API。

均先核完整冻结清单且记录验前/验后SHA；只读根/api/web AGENTS与原报告、产品实现，独立编写正确行为断言，旧诊断不能当修复通过。所有解释器在间接app.main导入前用新的系统temp数据根，Settings credentials_file=None；不占正式数据/未知端口/旧六目录，不提交等。完整命令/exit/单次计数/耗时/日志XMLJSON/首败/资源写RESULT.md，pass/fail/not_run明确。发现失败立即报CTRL并停候选验收，修复须新版本后复验；禁止边验边修。

## G1-D00 v1：本次暂停点的独立证据核对

负责人新独立 Agent `g1_doc_audit`。起点 CANDIDATE-g1-r2.json，826项及逐文件SHA；旧629份证据保护。只读产品、已有证据与权威文档，唯一可写范围为本批新目录 `d00/**`（登记时不存在），无共享文件例外。依赖：三位V00停止写入；CTRL提供本次REPORT及现行说明完成通知。

验收：从日志/XML/收据独立核对8项正确行为结果、check/API单次计数、真实API与浏览器的区别、r2覆盖扩展及旧证据保护、未执行门禁/B4未开工、资源释放与首败保留。只核文件与事实，不重新运行业务或启动服务，不读取正式数据/凭证、不清理任何目录、不做Git写操作。发现不一致报CTRL，由CTRL修文档；本任务不替代浏览器/E2E验收。结果写 `d00/RESULT.md`，标明核对范围、证据、问题及实际未执行边界。
