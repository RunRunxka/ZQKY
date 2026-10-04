# G2/B5-r8 后续代码审查

日期：2026-10-03，北京时间。请求为“review此阶段代码，给出下阶段提示词”。本批只读产品，新增隔离探针/窄回归和审查文档；**本审查未修复产品、启动G3/B6，也未执行Git提交、推送或部署**。审查期间观察到一次外部HEAD前移，下文单列归因。

## 结论

确认 **2 项 P2**，均是教案编辑的异步边界：明确放弃后仍被自动保存、复制历史的迟到读取覆盖后续输入。建议下一执行批 **先G3关闭两项，再按实际剩余做B6集成与教学质量验收准备**。后台保存/固定修订/原包幂等/应用事务与AI固定来源主链，本次范围未发现新增可复现缺陷。

原G2/B5已完成技术门禁与关闭仍是历史事实，不追改[原报告](../TEACHING-LOOP-G2-B5-20261003/REPORT.md)、首败或冻结件。两项新编号B5F-R01/R02不同于原G2三项与原B5 R01～R08。技术通过也不等于真实教学质量、WPS/PDF、正式Qdrant或正式迁移通过。

## B5F-R01 · P2 · 明确放弃后的旧组件仍自动保存被放弃正文

位置：[useServerPersistence.ts:186](../../../apps/web/src/features/lesson-plan/model/useServerPersistence.ts:186)、[LeaveProtection.tsx:50](../../../apps/web/src/features/lesson-plan/components/LeaveProtection.tsx:50)。

`discard()`只删除恢复键并返回true，没有取消600ms timer、封存会话写能力或恢复可信后台正文。离开保护据此放行router.push；如果目标路由较慢，旧组件继续挂载，原timer仍会发送被放弃输入、追加后台版本并重新建立恢复键。

本轮用实际hook及完整LessonPlanWorkspace复现：改“明确放弃的正文”→点公共导航→点“明确放弃未保存编辑后离开”→已调用router.push且缓存删除→保留旧树600ms→saveLesson被调用1次，载荷正是被放弃正文。立即卸载对照不发送。单独正确行为断言“零保存且缓存不再生”失败。

证据：[前端详细报告](frontend/REVIEW.md)、[hook正确行为首败](frontend/discard-correct-behavior-first-failure.log)、[实际工作区诊断](frontend/workspace-diagnostic.test.tsx)。本次使用jsdom/fake timers及受控API，未声称跑了实际Next延迟路由或后台网络写入；代码路径已证明组件会发出错误保存意图，真实浏览器列为G3必验。

修复须同步撤销自动写调度/旧epoch，处理store订阅和所有后续入口；导航失败留页也不能再提交原已放弃稿。先深冻结原未保存输入，缓存删除失败应保留输入并拒绝放行；不能为放弃覆盖教师唯一稿后才发现删除失败。成功时恢复可信已保存内容或明确封存写能力，后续新编辑可正常恢复保存。pending/unknown不伪装可取消已发HTTP。

## B5F-R02 · P2 · 历史复制的迟到读取覆盖教师新编辑

位置：[DocumentsPanel.tsx:76](../../../apps/web/src/features/lesson-plan/components/DocumentsPanel.tsx:76)。

“明确复制历史正文”先await refreshLatest，再仅检查后台CAS匹配，然后replace历史数据并finishCopy。未冻结/复核本地editRevision、加载/文档身份及复制intent，等待期间编辑器仍可输入。

完整工作区诊断：从历史打开当前稿准备复制，点击明确复制，延迟真实API接口替身的GET回执；教师此时输入B。回执返回原相同后台版本，页面及恢复缓存都被“历史复制正文”覆盖，复制intent被清除。正确行为期望“保留B/缓存B/保留复制意图”的三个断言均失败。**Undo可恢复B，本轮没有定为永久丢稿。**

证据：[前端报告](frontend/REVIEW.md)、[历史正确行为首败](frontend/history-correct-behavior-first-failure.log)、[完整输入/缓存/intent断言](frontend/history-correct-behavior-copy-intent.log)。这是实际组件异步行为，不是本轮真实浏览器或全链重新验收。

首次点击应冻结store/文档/加载/编辑代次、固定历史ID及原后台revision/revisionId。回执回来仅当这些仍匹配才复制；有新编辑则保留输入和intent，要求教师重新确认，或从一开始明确锁定编辑。不能拿refreshLatest刚更新的基线与自己比较来证明无变化。正常复制仍可撤销，保存追加新固定修订，旧历史不改。

## 未发现新增缺陷的范围与观察

- [存储审查](storage/REVIEW.md)：保存/导入/固定上下文、owner/CAS、receipt优先、部分应用/终结、失败回滚、六表迁移/FK/版本体检、四库备份恢复。新4个oracle及既有51回归通过。恢复为真实隔离SQLite/Blob，Qdrant为声明MockTransport，不是正式或真实Qdrant证明。
- [生成审查](generation/REVIEW.md)：单班固定计数、已知PII阻断、最终三协议wire、教材/题/练习来源、冻结模型指纹、取消/失权/同事务发布。41项窄检查通过，包含新5项。合法删除教材后执行前RAG_SCOPE_CHANGED且Provider新增调用0。
- **缓存观察**：生产ImmutableSource在warm情况下可复用原SHA正确的已验证不可变内容；直接磁盘损坏cold会拒绝，warm仍可用缓存。合法scope/修订/分类/归属/删除仍核查。本轮不将直接磁盘bitrot缓存行为定为P2，也不称每次都重读当前磁盘bytes。
- **计数质量观察**：incompleteCount和noEvidenceCount可重叠，needsCount也可能与信息不全重叠，不能让模型把它们相加当互斥人群。真实教学质量评审应明确此语义，而非仅验JSON合法。
- **未来迁移观察**：新增ALTER教案表时，需为lesson_schema_gate增加按已登记版本的结构检查；不能改旧0010散列或关闭体检。当前没有0011，此项不是现有产品缺陷。
- 现行PLAN和设计README的旧启动入口仍描述“先G2再B5”，与新阶段落后；本轮仅修正文档索引，不当成产品故障，不追改旧报告。

## 本轮实跑与限制

| 检查 | 实际结果 | 原件 |
| --- | --- | --- |
| 存储独立oracle与相关回归 | 55 passed（4新+51既有），exit0 | [结果](storage/RESULT.json)、[首轮日志](storage/PYTEST-first.txt) |
| 生成/来源/任务/wire | 41 passed（5新+36既有），exit0；另合法删除纯服务探针通过 | [生成结果](generation/REVIEW.md)、[最终窄日志](generation/narrow-second.log) |
| 前端当前三文件回归 | 112 passed，exit0 | [前端结果](frontend/REVIEW.md) |
| 原独立组件六文件本轮重跑 | 27 passed，exit0 | [前端结果](frontend/REVIEW.md) |
| 新诊断 | 4/4成功复现，pass只表示捕捉现行问题 | [工作区源](frontend/workspace-diagnostic.test.tsx)、[前端证据清单](frontend/EVIDENCE-MANIFEST.json) |
| 两个新正确行为案例 | 2 failed，分别为放弃后的0写、历史复制保持新输入 | [R01](frontend/discard-correct-behavior-first-failure.log)、[R02](frontend/history-correct-behavior-copy-intent.log) |
| 保全 | 938/3061/33/2004/1702五分组0漂移；旧QA捕捉9152文件，其中9151历史文件未变，1现行QA索引修改明示；外部HEAD前移明示 | [BASELINE](BASELINE.json)、[首次差异](FINAL-VERIFICATION-first.json)、[声明](DECLARED-DELTAS.json)、[FINAL-VERIFICATION](FINAL-VERIFICATION.json) |

前端首个工作区探针遗漏React导入，未执行业务断言；修QA后留新日志，原错误保留。生成首轮两项为新oracle/写端口使用错误，修独立探针后41通过；原first-command中appMainImported字段误记另有解释，产品未修。各首敗不删、不拼绿。

**未执行**：本轮全量check/API/build/E2E、真实浏览器/像素、真实收费模型/教师教学评审、Word/WPS/实际PDF、真实或正式Qdrant、正式迁移、超基线压力。原1256/153/14等是历史运行，不算本轮重跑。Python业务探针在app.main导入前设新临时ZQKY_DATA_DIR/ZQKY_ENV=test，Settings.credentials_file=None；Node使用必要flag；数据保留。

被拒的额外HTTP身份复核未重试，也未变命令/工具/端口/Agent绕过。隔离ASGI/TestClient业务probe与其分开；本轮没有TCP监听/浏览器，不检查或管理用户进程。

## 下一阶段材料

[B6总控提示词](../../design/teaching-loop-v1/B6_总控启动提示词_20261003.md) 已按现行代码写到修复伪代码与验收：**G3两项关闭 → B6剩余集成与质量验收准备**。真实模型运行需明确模型/样本/预算，缺失时先交完整离线样本、评审表和教师试用包，不虚构质量通过。原B6教案前端与部分B7技术工作随B5已完成，不重复搭系统或擅自宣布整个B6/B7关闭。

本轮仅增加新证据/提示词及权威进度/接手/索引后续说明。产品、历史QA、候选、构建、next-env逐字节保持；原G2/B5报告及已核准after字节保持。`docs/qa/README.md`是本轮主动更新的现行索引，原捕捉9152项包含它，不能把全部9152项写成零差异。

收尾观察HEAD从`6aeb57280f6a7e0d7391cad4d150745479ea58ec`变为`6cb6a40db890390f0261d547213e319040f64785`，直接父提交为开工HEAD，作者RunRunxka、提交时间2026-10-03 23:07:17+08:00。只读Git核查显示该提交包含114个既有受跟踪文件；本次新审查证据与提示词仍未跟踪，六份本轮索引/进度修改仍在工作区。**本审查没有执行Git写入**，没有撤销或覆盖该外部操作；候选五分组仍逐文件相等，审查结论针对同一产品字节。首次严格检查的HEAD/现行QA索引差异保留为FINAL-VERIFICATION-first.json，随后仅按精确before/after SHA与直接父关系分类，不覆盖开工基线、不改旧候选身份。详见[执行与后验入口](EVIDENCE-COMMANDS.md)。
