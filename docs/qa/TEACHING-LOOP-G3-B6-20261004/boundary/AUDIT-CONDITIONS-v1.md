# G3-BOUNDARY-v1 独立边界审核条件

日期：2026-10-04。负责人：G3-BOUNDARY；CTRL 为产品候选与阶段结论的唯一批准者。本卡只写本目录的审核条件、独立探针和结果；产品、契约、迁移、锁文件、权威文档和旧 QA 只读。准备不构成验收通过，稳定候选停写后才执行。

本轮任务来源：用户附件 `9c072f16-e318-4b90-b2bb-0e77e693b3b6/已粘贴的文本.txt`，先关闭 G3，再启动限定 B6。开工来源 `main@6cb6a40db890390f0261d547213e319040f64785`；旧 B5-r8 源清单和实际五分组核对由 CTRL 提供，历史测试数不记成本轮新执行。

## G3-R01 正文、恢复包和写入权限

| 场景 | 必须核对的正确行为 |
| --- | --- |
| 改全字段 A 后明确放弃，旧树持续挂载超过多个 600ms 周期 | 保存新增调用为 0，真实教案 CAS、固定修订、正文/context/历史数量不变；恢复键不再生 A；可信保存基线恢复，或明确封存写能力 |
| 所有自动与手动入口 | 订阅、effect、已排队 callback、save 完成续排、pagehide、beforeunload、keep、flush、markRule、setContext、setOperation 不得继续提交或恢复 A |
| 可信基线 | 文档、serverRevision、serverRevisionId 和已知固定正文身份一致；dirty cache.data 不是保存基线；known 较旧时不得把旧正文冒充高 CAS 的可信正文 |
| 成功恢复 | 全 11 字段及 process 四字段、context、来源标签对应同一固定事实；不创建伪新编辑；Undo 不复活明确放弃的 A；不删除历史修订模拟撤销 |
| removeItem 抛错 | 返回 false、不放行；唯一内存输入和恢复包保持，调度撤销、明确暂停自动写并显示恢复错误；keep/flush/pagehide 不能隐式把 A 发给服务器 |
| busy / unknown / cache_blocked / exclusive | 返回 false；不撤销已发 HTTP，不删原包、不编造取消后的服务器结果 |
| 目标路由失败或取消，新编辑 B | 恢复/暂停状态可解释，B 是新操作，可正常或明确重新保存；不能永久失能，也不能重新提交 A |
| 三种离开意图 | 保存后离开、保留缓存后离开、明确放弃分别核正文与写次数；立即卸载对照独立保留 |
| 本地模式 | writer 无在途时清 pending 与 timer，恢复真实 lastSaved；卸载 flush 不重写 A；新 B 仍可正常保存；在途/坏缓存拒绝 |

正文 oracle 覆盖 `title/totalLessons/currentLessonNo/lessonTypes/otherTypeText/coreCompetencies/keyPoints/teachingDesign/process/exercises/reflection`，process 逐项核 `id/stage/design/secondary`。不只核 toast 或 title。

## G3-R02 等待历史读取的身份

| 场景 | 必须核对的正确行为 |
| --- | --- |
| 等待真实 GET 时教师编辑 B | B 的全正文和恢复包保持；旧响应不清复制 intent；教师重新明确复制后才应用历史 |
| 不编辑正常复制 | 原 CAS、文档/store/load/意图仍相同；固定历史首次深冻结，完整 replace 只发生一次；形成一个 Undo 单元，Undo/Redo 后正常保存新版本 |
| 双击或同一事件周期重复点击 | 同一 owner 只启动/应用一次；旧 finally 不释放另一请求的 busy |
| 切文档、重载、返回同一文档 | 旧 store/load/sequence 失效；迟到正文与 notice 不改当前文档/恢复包 |
| 切历史或新复制意图 | 即使相同 revisionId/hash，也核新意图代次；旧请求不得读取新 pendingCopy 或清新 intent |
| A→B→Undo | 正文相同也仍有编辑代次变化，不让旧请求自证可用 |
| 实际 CAS 改变 | 核请求前冻结 CAS，而非 refreshLatest 后刚更新的基线；保留当前稿和 intent，显示人工对照 |
| GET 失败与重试 | 错误可见、正文与 intent 保持；只释放本 owner；重新明确点击可正常完成 |

真实浏览器要求合法目标路由响应延迟及实际业务 GET 延迟，使用隔离 FastAPI 和样本。读实际教案、历史、正文与恢复键；不得用 router mock 或 toast 替代浏览器结论，不执行被拒的额外 HTTP 身份核查。

## 证据与独立性

- `session-boundary.test.tsx` 为第三人手写全字段 oracle，审查真实 persistence hook 与本地 writer；预期正文不由生产 merge/restore 计算。
- 原审查两项 required 断言保持原文件与首败，由 CTRL/V00 在本批单列运行，不编辑旧证据。
- 候选前后产品、执行 QA、契约、构建及旧证据逐文件绑定；本目录准备后新增文件另列，不回写旧 r8。
- 结果分开：本批新跑、原同源引用、教师未验、not_run。待真实候选、浏览器和门禁完成后才给独立结论。

## B6 需求与剩余范围（只读建议，尚未启动）

| 需求 | 现行实现和原证据 | 本批剩余检查 |
| --- | --- | --- |
| 固定成绩→报告→单班/KP→教案→候选→partial→历史/Undo→导出 | B5-r8 真实八场景已覆盖，见 `../../TEACHING-LOOP-G2-B5-20261003/REPORT.md` 与其 `B5-CLOSE-MATRIX.md` | G3 CLOSED 后在稳定候选串联课堂练习/模板→新施测→教师分数→新报告；不拼 B4/B5 两批断开的证据宣称本批全链 |
| 固定旧事实 | 原四业务 GET 完整 JSON 深等，20 immutable/修订/hash 核对 | 新串联前后完整 JSON/SQL、context、映射和 source label 不变；题库改、KP 归档、名单改名不改旧事实 |
| 异步可靠性 | 原保存 unknown/CAS/丢响应/模型漂移/cancel/失权/原包已有 27/42/8；后审查 55/41/112 相关技术检查 | 只补 G3、新代码影响、未覆盖需求或新失败；不把旧测试数记为新跑 |
| 迁移与恢复 | 0010 六表、四库 SQLite/Blob 实际 restore 与独立 16 库只读已有证据 | 无 DDL/恢复代码改动时精确引用；正式 6333/正式迁移保持 not_run，不新建第二后台 |
| 教学质量 | 技术替身/wire 不证明教学质量；计数重叠与 RAG-REL 保留 | 12 匿名案例、人工 oracle、六维 rubric、执行器、feedback 和试用说明；live_run 待明确模型/案例/费用或 token 范围，teacher_review_pending |
| Word/WPS/PDF | 原 4 DOCX 结构级/4 冻结打印技术通过；不能冒充 WPS 或 PDF 保存 | 四类当前固定样本正文/来源/文件/模板 SHA、结构检查、可打开材料与逐页清单；实际未做项目单列 not_run |

本卡未启动 B6，不宣称原 B6/B7 整体完成，不申请真实模型或外部连接。
