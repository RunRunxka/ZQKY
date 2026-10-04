# G2 / B5 最终报告

更新：2026-10-03 22:03。**G2和B5全部必要技术门禁、独立验收、资源退出及精确文档核准完成，CTRL已关闭本批，当前停止。** 授权止于B5；不自动开始下一阶段，不提交/推送/切分支/部署。

## 实施结果

G2三项已独立关闭：练习dirty统一离开决策，首次提交冻结原包和编辑代次，真实PATCH成功receipt可在后来CAS改变后原包重放。原B4关闭与后续G2修复分列，原审查不改。

B5在已有教案工作台增加FastAPI后台列表、新建、显式旧稿导入、保存和固定历史；正文/DraftEnvelope仍schemaVersion1，ProcessItem仍四字段。本地旧键保留，后台恢复缓存按documentId隔离。CAS、owner、成功receipt、不可变修订与来源上下文一起保存，来源意义变化不被正文去重吞掉。unknown重发首次完整包，旧ACK不擦新输入或倒退已知服务端版本；409保留当前稿，教师明确处理。

教师选择固定ready报告的单一班级和知识点、生产RagV2验证的教材依据，以及confirmed固定题或reviewed练习。生成复用三协议供应商适配与公共六态任务；冻结来源与非密模型指纹，租约/attempt/心跳/取消/重启显式retry和原子发布延续现有机制。模型只接受白名单投影，已知学生身份在自由输入处阻断；最终序列化wire已检查，不能据此保证任意未识别身份完全匿名。

AI候选只改coreCompetencies/keyPoints/teachingDesign/process/exercises五个完整字段；课题、总课时、当前课次、课型、其他课型、反思六项由教师控制。教师部分选择应用后追加固定修订，未选字段不补写；候选应用/拒绝终结，撤销是新的编辑与另存版本。分钟与证据保存在候选metadata，不改旧ProcessItem。教案练习文字不自动发布入题库。

## 最终候选与实际门禁

候选B5-r8 SHA c33c85698ba2be8e6b08fe432305622bf3635a1bc5bb0cc515472996ebbe2007：938源码、3061可执行QA文件、33冻结契约、2004构建文件、1702既有本批证据。QA文件数不是测试例数。构建FVU-OXmtBh9WBSHehixfE，实际代理8001，next-env原字节精确恢复。

| 检查 | 实际新单轮结果 | PID / 用时 |
| --- | --- | --- |
| 完整check | 118文件1256单测、类型、零警告lint、build通过 | 22916 / 107857.642ms |
| 原独立组件27 | 27/27，原v11同字节，含R07/R08正确行为 | 27472 / 5529.201ms |
| 原独立真实浏览器8 | 8/8，四视口真实四库链与unknown/dual CAS/历史复制 | 18596 / 43533.495ms |
| 原24spec153全量 | 153/153，0跳过/重试/flaky；R07原两导航通过 | 13224 / 367124.838ms |
| 原2spec14聊天 | 14/14，0跳过/重试/flaky | 29548 / 42953.884ms |
| 完整API | 1918通过/1既有后端规模skip | 21200 / 392504.479ms |
| 独立真实API42 | 42/42 | 20076 / 40948.122ms |

API两轮是在本批早先完成；其410后端/测试/脚本/模板与最终候选逐文件前后同字节，明确是精确绑定，没有冒称R08修后重新执行。各必要前端新门禁都消费修后同一构建与产品源，不跨轮拼绿。

## 独立业务验收

手写完整旧/新数据与受控失败oracle不调用生产merge函数。42真实API覆盖owner/FK/CAS、并发同包/异包409、旧receipt不回退、A→B→A上下文、五字段结构与教师六字段、20非法候选、最终三协议wire、固定来源、租约/retry/cancel/发布失败和quoted SQL/JSONpath变异拒绝。

原27覆盖冻结metadata/模型切换/明确失败、严格三口分页及旧本地600ms串行写/快速导航/慢写继续编辑/失败明确重试/坏稿暂停/导入busy→unknown与恢复unknown。原153补充本地规则警告确认、JSON、撤销重做、刷新、Word与打印等已有完整路径；不是用文件未改代替新行为验收。

## B5新增审查修复

| 编号 | 修复及独立正确行为依据 |
| --- | --- |
| R01 | 短数字名单身份碰撞；独立42与最终wire核实际已知身份不外发 |
| R02 | quoted SQL literal/JSON路径体检绕过；四实际变异startup/recovery拒绝 |
| R03 | Next历史copy intent跨revision remount丢失；原组件与新完整8的真实历史复制/undo/另存通过 |
| R04 | 保存await/unknown原metadata误绑定新模型与422/503后旧候选复活；原27及新8通过 |
| R05 | classes/runs/practices超限与首100截断；原27严格分页、241后页、失败/retry通过 |
| R06 | 迟到来源读取擦掉教师模型/课时/要求；原27与新8四视口保留新输入 |
| R07 | 正常本地pending被离开弹窗阻住；原27串行flush及新153原两例628/453ms通过 |
| R08 | 本地导入busy→unknown只改ref，已开弹窗未刷新；响应式通知与即时guard并存，原27同字节全部后验完成 |

原首败不删除。R07正常离开先等待原串行flush，坏稿、失败、unknown和打印保护保持。R08稳定owner/context lease阻止旧producer清新状态；未观察到越权导航或丢稿，不把提示缺陷夸为已发生数据损坏。

## 浏览器与画面

新完整8覆盖390×844、1024×768、1440×900及1920宽屏/reduced-motion，真实成绩→固定ready报告→单班/KP→旧v1导入→保存→AI替身候选→部分应用→固定历史→撤销新版本→Word/打印。另有原手动保存200丢回执、继续B/nativeBack与两次原包恢复、双标签CAS、键盘Tab/Escape、真实历史复制与intent处理。原成绩/报告/班级/练习4 GET全200且完整JSON深等不变。

独立实际view全部22张B5截图；8 trace CRC通过，11原HTML含新build、53静态响应/12唯一asset与构建SHA匹配，身份来自原验收trace离线读取，不重试被拒额外HTTP。附件fresh188项全算通过：20不可变修订/上下文/hash、4终态决策、4最终wire/3协议、全部6公共备份全11字段与旧键、4Word和4打印。v1/v2非执行审计谓词错误保留，v3完整重算，不改产品/用例或拼绿。

聊天26原图逐张审阅和功能14分列。CV01代码遮字、CV02控件像素与CV03流式按钮图形观察保留，不据功能绿或静图宣布全视觉PASS。RAG-REL与书籍跨批R-14同样保持。

## Word、打印与人工质量

已实际读取4份下载DOCX的ZIP/CRC/XML和全部中文字段/长secondary/特殊字符及教师六项；打印延迟期间冻结source revision/content，4快照内容核对通过。原模板与派生模板散列保全。未实际在Word/WPS打开做长文分页检查；打印窗口不等于已保存PDF，人工分页和实际PDF保存为not_run。

真实收费供应商的教案教学质量、事实准确性与课堂效果未执行。本地provider替身证明技术链与严格结构，不代表质量通过。书籍生成仍为明确本地模拟，规划根页不变。

## 迁移与四库恢复

追加式迁移与六B5表进入体检/备份；新库、有B4数据旧库、注入失败回滚重跑、真FK/完整性、旧0001～0009散列实际检验。ROOT实际四库create/verify/restore演练1/1通过，fullAPI再包含此真实恢复测试；恢复后六新表2/3/3/2/2/2行、所有教学/知识/题库行、2资产和3隔离向量点核对，标准main重装能读应用后教案和生产教材证据。

独立验收者只读16个实际恢复前后SQLite，逐行/六新表/指针/旧9散列/2blob与56文件SHA核查通过并关闭连接；这不是独立重新运行整套恢复。正式Qdrant6333、正式数据根迁移均not_run，本批只隔离演练。

## 压力范围与未执行项

原153中的200人次×100叶UI场景实际通过。完整API有1个原重型规模flag省略所致skip，不能把它计为后台压力通过；超出现有基线的压力未执行。真实供应商、WPS人工分页/实际PDF、正式Qdrant/正式迁移另列not_run，原因是本批隔离与许可范围。

额外r2 Python urllib HTTP HTML/proxy身份复核被自动审批blocked by policy拒绝，保留原not_run收据；未换命令、工具、端口或Agent重试。原计划浏览器的现有trace离线证据分别列示，不将其写成额外HTTP执行。

## 首败、保全与停止

保留全部r1～r7、QA各版、首失败输入/完整日志/候选/收据，包括API首1912/5/1、原浏览器各轮失败、r5全153的151/2、r6 JSX19/8、r7完整26/1、作者各修前及一次旧121 accessible时序首败。r8-unit-first是ROOT错填候选文件名、Popen前失败/tests0，随后正确路径新标签完整27通过；文档regex和preflight记账错误也单列，不修改旧事实。单次全绿不关R-14或其他跨批间歇台账。

全部自有API/stream/frontend使用PID+创建时间+命令归属guard与专属stopFile退出；受控Windows前端child exit1、manager exit0、child/logClosed，不写自然exit0。5174/8001/8002无监听、无自有残留；72 ROOT命令complete、81日志实际独占打开并Dispose。182批次证据引用的OSTEMP目录均存在，包含G2及早先样本，不称全部为B5新根。用户会话/进程未结束，旧拒删根保留；正式.env/数据/凭证/真实草稿未访问。

最终938源码/3061QA/33契约/2004build/1702prior/4136历史、原G2直接589+批准归档2共591、next-env原字节均零漂移。main@6aeb57280f6a7e0d7391cad4d150745479ea58ec，不提交/推送/切分支/部署。最终文档单独保全before/after，独立核准精确after bytes后才应用与关闭；授权止于B5，结束后停止。

## 证据与文档后验

- [候选](CANDIDATE-B5-r8.json) · [B5矩阵](B5-CLOSE-MATRIX.md) · [G2已关闭收据](ctrl/G2-CLOSED-r4-v1.json)。
- [check1256](ctrl/b5-check-prebuild-v6-first-command.json) · [新构建/实际代理](ctrl/B5-R08-BUILD-BINDING-v1.json) · [API410精确原前后绑定](ctrl/B5-R8-API-EXACT-BINDING-v1.json)。
- [独立27](b5-v00/results/EXEC-r8-unit-second-INDEPENDENT-v1.md) · [完整8独立](b5-v00/results/EXEC-r8-browser-first-v2.md) · [fresh188附件](b5-v00/results/R8-FULL-FIELD-ARTIFACT-AUDIT-v3.json) · [固定4业务读取](b5-v00/results/R8-BROWSER-FIXED-READ-v1.json)。
- [原153独立](b5-review/E2E-R8-INDEPENDENT-v1.md) · [原153执行](ctrl/b5-e2e-full-r8-first-command.json) · [聊天14独立](b5-v00/results/CHAT-R8-INDEPENDENT-v1.md) · [26逐图](b5-v00/results/CHAT-R8-VISUAL-v1.md)。
- [实际四库恢复](ctrl/B5-RECOVERY-PROOF-v1.json) · [独立16库只读核查](b5-v00/results/RECOVERY-READ-AUDIT-v1.md)。
- [资源终审](ctrl/B5-RESOURCE-CLOSED-r8-v2.json) · [资源独立](b5-review/RESOURCE-R8-INDEPENDENT-v1.md) · [最终保全](AUDIT-B5-r8-final-preservation-v1.json) · [未执行HTTP政策收据](ctrl/B5-R2-EXTRA-IDENTITY-POLICY-v1.json)。
- [精确文档清单](ctrl/B5-DOC-CLOSE-CANDIDATE-v3/MANIFEST.json) · [本报告整理前原字节](ctrl/B5-DOC-CLOSE-CANDIDATE-v1/before/docs/qa/TEACHING-LOOP-G2-B5-20261003/REPORT.md)。全部历史运行/首败另有原目录与收据，整理只改变当前说明，不追改运行事实。

最终文档采用before/after逐字节清单，由未参与实现的独立文档审查者核准后精确应用。文档差异不计为产品/QA漂移。SOURCE/契约/API/路由/稳定指南与lesson-plan模块说明已经一致，必要AGENTS在最终check与938source绑定中保持；此处只整理七个进度/索引/报告页。范围结束后停止。
