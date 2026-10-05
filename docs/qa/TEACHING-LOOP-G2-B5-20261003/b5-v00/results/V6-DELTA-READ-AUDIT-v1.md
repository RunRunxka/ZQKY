# V6 独立静态 delta 与 coverage/gap 审计 v1

审计者 `/root/b5_v00/v6_delta_review`；2026-10-03，只读审计完成于 11:32 UTC。仅新增本非可执行报告；创建前两次确认路径不存在。没有修改产品、旧 QA、v6 QA、共享契约或 Git，没有执行产品、Playwright、测试、HTTP、下载或服务启动。

结论：逐行差异未发现删除业务正确行为断言、放宽预算或跳过原场景；v6 的定位/异步/clean 观察修正与公开实现一致。这个结论仅是静态审查，不能标记 v6 runtime 通过，也不能关闭 B5。

## 完整入口与逐行差异

原 `browser/independent.spec.ts` 与 v6 完整副本做逐行 diff；原 `v3/browser/history-copy.spec.ts` 与 v6 完整副本做逐行 diff。完整入口仍是四个 viewport 展开实例、两个独立保存/CAS 实例、两个历史实例，共 8 个。没有删 case、过滤 case、重试通过或拼接绿结果。

| 差异 | 原断言保留与增强 |
| --- | --- |
| independent type import | 仅因副本深度增加，将根相对路径改为六层；类型来源不变。 |
| 固定来源读取 | 在明确 selectRun 前注册真实 GET `/analysis-runs/{seed.run}` 与带精确 `analysisRunId` 的 `/practice-sets` response 等待，各断言 200。SourcePanel.selectRun 真实调用这两个公开读取口；没有 mock/fulfill 业务响应。 |
| KP 相对 has | 内层 legend 定位改成 `page.locator('legend',...)`，供外层 fieldset 的相对 `has` 解析，不再重复嵌套 source 祖先。未改变“明确选择知识点”的目标范围。 |
| KP 异步集合 | 原 `.all()`/逐项 check 保留，之前增加 seed KP 数量 >0、实际 checkbox 数量精确等于 seed 的自动等待；每次 check 后新增 `toBeChecked()`。排除“零集合循环成功”的假前提。 |
| 完整旧稿导入 | 原 status201、importEnvelope 完整深等、旧 key 原字节不变均保留；新增导入正文深等、固定 analysisRunId、analysis snapshot 的 run/score 身份、知识点 ID 集合精确深等。没有降低 context 要求。 |
| dual-tab 课题 | Escape 后课题 locator 新增 exact:true；原 A200、B409、B 本文保留、Tab、焦点限 dialog、Escape、显式 latest 基线、new save 与最终 v3 原断言全部保留。 |
| history textarea | process 教学设计/二次备课从 exact label 改为 exact textbox role，值断言不改。Field 是包裹 span 与 textarea 的 label；FormPanel 的两个 textarea 未另写 aria-label，role 直接选择真实可编辑控件。环节名称、过程数量、课题、重点、反思断言保留。 |
| clean 全 11 字段读取 | helper 默认仍为 requireDirtyCache=true，所有 dirty/undo/redo 调用继续精确轮询恢复 cache.data。仅 4 个 clean 调用点显式 false：prepareA、打开 B、从 history 返回 current、从本地返回 current。原“clean 必有恢复 cache”的前提替换为真实公开备份全文检查。prepareA 在完整序列复用三次，故这 4 个调用点若全部执行会产生 6 次 JSON 下载；这是静态推导，不是实际下载计数。 |

四个 viewport 的原 `page.emulateMedia({reducedMotion:'reduce'})` 没有改动。dual-tab 的 `keyboard.press('Tab')`、`expect.poll(activeElement.closest('dialog').aria-labelledby).toBe('lesson-leave-title')`、`keyboard.press('Escape')` 三项原键盘断言逐字保留；主 V00 首轮 trace 已实际执行这几步，本审计不重新执行。

原候选 partial 的只选 keyPoints/exercises、未选及教师字段深等、人工反思/课题值、Word ZIP/XML marker、真实 print 捕捉、undo 新保存 revision、只读 history、旧 score/report/classes/practice 全对象 GET 深等全部保留。history-copy 的 dirty cache、edit/ACK 代次、base v2、明确 copy、undo/redo、v3 copy 保存、v4 undo 保存、三份固定旧修订、完整四版本集合、cancel 保留 A、B/history/local 清 intent 与最终 A/B 不变全部保留。

## clean 下载与配置事实

v6 clean helper 通过公开“导出教案 → 备份草稿”捕获真实 download，检查 filename 为 .json，保存原文件，JSON.parse 后检查 schemaVersion=1 与 envelope.data 深等手写的完整 LessonPlanData。expected 的 11 字段及 ProcessItem 的 id/stage/design/secondary 由 JSON 全对象深等覆盖，含 lessonTypes 顺序/重复项，不用生产 merge 作 oracle。

下载前读取真实 URL 和该文档的 cache 原字节；若 cache 已存在，先检查它的 data；下载后 URL、cache 原字节必须完全相同。没有在 clean 分支 setItem、人工编辑、复制、保存、生成或自动制造 cache。ExportMenu 直接调用 EditorContext.backup；backup 仅以 makeEnvelope(data,revision) 生成 Blob/公开 download，然后关闭菜单和 notice。makeEnvelope 返回 schema1/原 revision/新 ISO 时间/data；download 仅创建 blob URL、anchor.download/click 和延迟 revoke。此路径未调用 store.set/replace、HTTP operation、persist/cache writer，notice/menu 仅 UI 状态。运行是否符合这些断言仍须新轮验证。

v6 config 仍沿根 original 的 timeout=45000、expect.timeout=10000、retries=0、workers=1、fullyParallel=false、baseURL5174、trace:on、webServer:undefined。与旧 v3 的间接配置相比，只改为 v6 两完整文件、修正根 import 深度，并把新 evidenceRoot 放入 results/run-{freshLabel}。fresh label 校验和禁止覆盖旧结果的检查保留，JSON/JUnit/list reporter 保留。没有增加超时或减少预算。

主 V00 另报告静态诊断 0：PID28520/exit0/1025.849ms；CLI --list 收集完整 8：PID25936/exit0/913.534ms、actualRuntimeResults=0，旧54/source938 before-after0。本子审计未执行或复跑这两个准备命令；收集结果不能称业务执行。

没有另外发现足以要求改动的同类 locator/异步错误；这仅限此次只读范围，不能代替下一轮实际失败分析。

## 独立 coverage/gap 评估

依据完整用户原要求、冻结 B5-CONTRACT/TASK-CARDS、公开装配 delta 与实际结果原件；“已实际”指原收据所记录的执行者，绝不将本审计读文件算作重新执行。

| 要求/门槛 | 已实际证据 | 仍待完成或边界 |
| --- | --- | --- |
| 保存/完整导入/版本意义/并发幂等/owner/真 FK/固定内容/五字段应用与六教师字段保留/三协议 wire/PII/Job/失败收敛 | 独立 private API42 在 prebuild-v1 完整单轮 42/0，PID20076/exit0/40948.122ms；后续产品只有三 FE 源 delta，CLOSE-MATRIX 明确 410 后台同字节绑定。原首败与原完整 API 输入保留。 | 本审计未重跑 API；不能将无真实付费请求的隔离 wire 技术通过解释成教学质量通过。 |
| 会话 unknown/原包/新输入/旧 ACK/cache/来源/过期候选/后页分页/Word/延迟 print 组件行为 | 独立 private18 新单轮 18/0，PID15572/exit0/2361.519ms。原15 的 QA缺jobId与产品后页失败、原16 的 R04/R05产品失败保留；18 实际完成 R04 的422/503。 | capability unit 并非真实 Next/HTTP/浏览器。原 18 主门槛不缩减；不能用18替代下列8或153。 |
| 固定成绩→ready报告→单班/KP→导入/保存→候选→partial→history→undo另存→Word/print；四 viewport/键盘/reduced-motion/逐图；原固定业务不改 | 原 browser8 单轮 1 passed/7 failed/0 skipped，PID18580/exit1/216349.337ms。仅真实 lost-save/continuedB/nativeBack/深等原包重放完成；四固定 GET 后验全对象不变，5张当时可见图已逐图查看。 | v6 仅准备。四完整链、dual-tab 最终 new-save、两历史完整链均待新候选单轮完整8；原首轮 Word0/print0，候选/history 四视口图未生成。必须实际下载并查内容、实际 print snapshot 和逐图查看，不能以 QA 归因或 unit PASS 关闭门槛。 |
| 旧本地完整链 600ms串行/快速导航/失败重试/坏稿暂停/恢复/规则确认/undo/JSON/模板Word/打印，以及整体 E2E/chat | ROOT 新完整 check 实际118文件/1224单测、type/lint/build通过，PID4448/exit0/106554.366ms；原完整API XML1918 pass/1既有规模skip，PID21200/exit0/392504.479ms。 | ROOT 原153 E2E与14 chat 目前是准备/待跑；按 ROOT 已安排在 v6 browser 后、关闭8001后顺序执行。旧 B4/r21 或G2153/14历史不能冒称本批重跑。check/build不替代旧本地集成行为；新153实际结果及适用chat14必须绑定新源/正确构建代理。 |
| 新0010/有数据B4/失败回滚重跑/hash/FK/四库恢复/固定教案建议历史资产 | fullAPI1918 XML实际包含有数据B4追加B5、missing structure拒绝、quoted语义变异、教案备份恢复等实例，无failure。作者 b5-backup-recovery-v2 实际restore1，PID26092/exit0/2601.856ms，最初cleanup失败原件保留。V00另以16只读连接核 source/canonical/archive/restored 各4库：完整性/FK、业务全行、六新表、9原hash、两blob、9备份文件、3假向量点，56输入前后hash0，连接全部闭。 | 作者restore1的单轮收据只绑定5源、candidate:null；独立16库审计是独立数据核对，不是V00重新执行backup/restore/启动/RAG/Qdrant。最终应保留这两种证据的执行者与绑定范围；不得写“独立恢复运行通过”。是否以作者实际实验+独立全行核对满足总体恢复验收，由CTRL在关闭矩阵明确判定，不能省略该区分。 |
| 当前资源退出/历史与next-env精确保全/契约与新构建/最终文档 | 原运行收据记录源/QA前后、首败保全、child/log关闭，check next-env 原字节恢复；原r1浏览器源/QA/构建0漂移。 | 最终源/契约/构建/G2与旧证据/next-env后验、文档delta核准、全部本批自有服务/端口/浏览器退出仍为整体关闭前必需动作。当前已退出API与仍运行前端须由ROOT逐项最终记录，保留用户进程。 |

主要缺口是必需执行与最终绑定，未发现需要删除 private42/18/8门槛才能推进的理由，也不要求添加新 case。优先完成稳定 v6 完整8，再完成 ROOT153/14、最终资源/保全/文档审计；若新轮发现真实产品问题，保留首败、停写候选、另修/另冻，不拼轮次。

明确允许保留 not_run 的边界：真实供应商教学质量与真实付费 provider；Word/WPS 人工排版和实际另存 PDF；正式 Qdrant6333/真实向量生产验收；正式数据根迁移（另需用户授权）；超既有规模压力。Word/WPS 人工未执行不能免除隔离浏览器真实下载内容/print 技术门槛。既有 fullAPI 唯一规模 skip 是100叶×200人次，其 XML 理由为 read-only worksheet 逐格取值成本估算20+分钟、须 ZQKY_RUN_SCALE_BASELINE=1；按已有台账单列，不能称全规模通过。RAG-REL/R-14/旧CV边界保留。

## 输入散列与保全

独立实际核 QA-MANIFEST-v5 的 54 个 sourceFiles 全 SHA256 相等；11:28 与11:32 UTC两次 mismatch=[]。manifest 原 SHA `2784016cde55ab949f563d0b0d177200a543f8e0ba2e519bc59b0df78b828ae0`。没有编辑清单或其中任何文件。

| 输入（仓库相对路径） | SHA256 |
| --- | --- |
| b5-v00/browser/independent.spec.ts | 01b6475053ae28bb97f3d601e67169178e546f89472c918067de83ebbfb61037 |
| b5-v00/v3/browser/history-copy.spec.ts | 76787fd43c9fdafe05b1a7370c59a90369264f3a1d715d5c379a6bfbabe1177e |
| b5-v00/browser/external.config.ts | 12ea21e95dba5f6bed7b4a92a5683db311439c9c4b8ec170b274c2defb15f60a |
| b5-v00/v3/browser/external.config.ts | df59e9edc27b84b98eae435e9b5ff7a8ec444d29a71eeac790c518c7a76b22c3 |
| b5-v00/v6/browser/independent.spec.ts | 9169ae7b0260fbf1f9746d7a2dd5270bee98c72006e2604085dfbe119c70adea |
| b5-v00/v6/browser/history-copy.spec.ts | 33cf4479c248708f5c8c5d4fd9826bcd1d951f1e7b4aa87d42cbc7a7e8c8b87c |
| b5-v00/v6/browser/external.config.ts | b548ebd4bc38f7ea461d5db4f458b1396a31de30d27e70a4cb6cc82ab1b64a85 |
| apps/web/src/features/lesson-plan/components/ExportMenu.tsx | 8712ce364ff9a924d744840763cace57f4690b823476f3dc2320bd852442a01b |
| apps/web/src/features/lesson-plan/model/EditorContext.tsx | 6b49d5531cf54844c6fbceb9ee043fc7dcf9e2d6ea883f490088f553d2a0f7e0 |
| apps/web/src/components/ui/Field.tsx | f6b8bd6fd3b84cb907529273c8a7eda03152dc5b02aeae14311ac11a5c6a1681 |
| apps/web/src/features/lesson-plan/components/FormPanel.tsx | 4192baaf3d1406429b9081b2f4479338a96577d74033b2d759e97d7086ecd25e |
| apps/web/src/features/lesson-plan/components/SourcePanel.tsx | e42ff4957820485991dc73319427233023646e81078d4ccf69cb0fa6cafdafe6 |
| apps/web/src/features/lesson-plan/services/drafts.ts | cb6d1534c5f6c0c1acd6fd07429fcff8983a2fac194a3e27094676a3bdc2ca7e |
| apps/web/src/features/lesson-plan/services/export.ts | 44c4ecc75fe255ad01ebe481b15b79afb4b2e4c2790b805efae3d83406c2c501 |
| playwright.config.ts | dd32a2826a686f95a13b8b4b12c756af3beca26c0bdfe8673cc740485cfa9df0 |
| ctrl/USER-REQUEST.original.txt | 8aec3f8a527102cec1187dec1b63b09031b96dd23195a7b70eb0b6d78dfca02d |
| B5-CONTRACT-v1.md | c0c3231d6855e3fe9a3fd7431cf6d01441d17f38b0febd81db7f0628f5909096 |
| B5-TASK-CARDS-v1.md | d366776d1f3ffc6c9b130ec6a36731f2fe7d151f498953541cb40b76fdb9f3d0 |
| B5-CTRL-SOURCE-RUNTIME-DELTA-v1.md | 7dc87a820d2ab38b0c438bf38b12817cb30b26725548faeee1ca78f9ca46c788 |
| b5-v00/results/EXEC-FIRST-ROUNDS-v1.md | 7a5cc95d38657af695b6501381be0ea9e12a13530df558a88fda3fc255e87f66 |
| b5-v00/results/EXEC-PREBUILD-v3-UNIT-v1.md | 8b28a32b02e7669590d2de1bfdc692b0a04b0c9101be13112858720de9915e67 |
| b5-v00/results/EXEC-R1-BROWSER-FIRST-v1.md | bc0d69b55681a68c47e3ee5432e00288996db2ac375347c2c1addf08a5027444 |
| b5-v00/results/RECOVERY-READ-AUDIT-v1.md | 991fa01350a1d250085e5a18be580862c1c6ceb56450882fd53cdfb48dce73f0 |
| B5-CLOSE-MATRIX.md | 4d7636b90f2c4759cd05b75e0e0a08c9709673703a162b79c356f65b377b115c |
| ctrl/b5-check-prebuild-v3-command.json | 7763aeace5632fe52649295fdd70a6b6d0021bc0c2c8c1209fffabfbf66bf00e |
| ctrl/b5-api-full-prebuild-v1-command.json | 320036a1860faa1c40a3a76d4894d17fede5a4599f0de4700706c0b932f2943f |
| ctrl/b5-api-full-prebuild-v1.xml | fa22fabd5b17b5d4a8df9b2c65e6200bf7961004d0735f00abac64d8d5955b2b |
| ctrl/b5-e2e.external.config.ts | ea41a2625fd56fe84006a7b7558ac370fe78f5905625945163a6de556349bd46 |
| ctrl/b5-chat.external.config.ts | 754295325ce351f0304b946a88ca1600527db2c2921bcba7bc174b9ab7ac87d7 |

表中 b5-v00/、ctrl/ 与 B5- 文件均相对于 `docs/qa/TEACHING-LOOP-G2-B5-20261003/`；apps/与根配置相对于仓库根。STOP：报告交付后停止写入与执行，等主 V00 封存新 manifest；本审计无自有 TCP/浏览器/数据库连接需要释放。
