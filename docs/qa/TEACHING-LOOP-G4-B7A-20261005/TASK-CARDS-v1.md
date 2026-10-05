# G4 → B7-A 任务卡 v1

2026-10-05，ROOT。用户限定本批为离线工具与验收准备。依赖：开工保全完成 → G4 四项实现 STOP → 独立正确行为、真实隔离浏览器与适用工程门禁 → ROOT 关闭 G4 → B7-A 离线接入与准备 → 独立验收和文档后验 → STOP。

| ID / 版本 | 负责人 | 独占可写范围 | 验收条件 |
| --- | --- | --- | --- |
| G4-E v1 | g4_e | 教案 model/useServerPersistence、useLessonOperation、EditorContext；components/ServerControls、LeaveProtection、DocumentsPanel、ProposalPanel；新增模块行为测试；本批 edit/ | 公共完整缓存重试；读取损坏仍保护；持久化并读回原包前零 HTTP；原操作/ACK 清理/unknown/CAS/跨会话守卫；全部11字段及 secondary/context/source 不丢；现有 G3 和生成逻辑保留 |
| G4-S v1 | g4_s | 教案 components/SourcePanel；新增 sources 作者测试；本批 sources/ | 独立 verifyIntent 撤销首次 null→null；getSource/verify/catch 均守卫；双清除、迟错、新核验、跨会话/年级/discard；保留 metadata、pending report 和下一片段参数原语义 |
| G4-Q v1 | g4_q | 新 scripts/teaching-quality/{common,aggregate_review,scope_preflight}.py 及专属 tests/；本批 quality/ | 冻结预期 manifest/SHA 与显式集合，少例/重复/额外/缺产物/hash/ZIP/来源坏均非零；15/15 与明确14/14分列；strict JSON/类型/预算/身份，合法仅供人审；无应用导入/网络/凭证 |
| CTRL-INTEGRATION v1 | ROOT | DocumentContext / DocumentGateway 恢复阻断状态接线；共享文档、候选、隔离运行器、构建与资源管理 | recoveryBlocked 精确发布与会话守卫；基线归因、next-env 原字节、历史 QA 保全；check 与现行29spec/174 E2E；有影响才新增专项重跑 |
| V00 v1 | 独立于被验实现者 | 后续单独释放本批 v00/；只读稳定产品/工具 | 稳定候选字节绑定；独立反例和真实业务响应；不以作者测试代签；首败保持；pass/fail/not_run 分列 |
| B7-A v1 | G4 关闭后释放 | 新工具离线接入、范围/预算执行准备、试评矩阵、空教师/页评表及说明 | 复用15匿名固定样本和4 DOCX/13 PDF页的精确SHA；教师字段空；live0；原生排版未验；真实执行不得由预检 READY 自动授权 |

实现者结果卡须列：任务/版本/STOP时间、完整改动路径与 SHA、首次失败原件、实际命令/PID/时间/单轮计数、身份与数据守卫、未执行项及理由、资源和 TEMP。ROOT 独占权威文档/契约/锁/Git 操作；本批不写 Git，不改共享分支，不更改原计划任务，只添加可剥离状态。

## G4-Q v2：物理旧样本缺失的模式区分

作者首轮 author-r1 在准备阶段发现旧 offline-third TEMP 目录仍在但 SQLite 文件不存在；0 tests/exit5 原件保留，不猜清理原因，不改旧收据、不重建原库或重复15案例生成。ROOT 允许显式 `frozen-source-binding` 模式：对用户冻结候选中的原 case-bound-v3 全列记录/来源/Blob散列证据先核精确文件SHA及canonical行SHA，再关联完整输入/wire/固定身份/来源标签；材料缺项或绑定错误仍硬失败。此模式的当前物理库/Blob检查必须单列 `not_run_source_temp_unavailable`，不得计作本轮新查四库通过。

`readonly-catalogs` 模式保留显式数据根与真实只读核查，源库/Blob不存在必须非零失败。独立复验须覆盖两模式差异和缺源负例；技术材料计数、实际DOCX结构、冻结来源绑定、当前物理来源、教师/live/WPS六者不合并。新模式不构成真实试评执行资格。

旧证据和旧工具只读。任何间接导入 app.main 之前须设置新 TEMP、ZQKY_DATA_DIR、ZQKY_ENV=test、PYTHONUTF8=1，并确保非 live Settings.credentials_file=None。测试从未访问正式 .env/数据根/草稿；原额外 HTTP 身份核查仍 not_run，不重试或替代绕行。自有5174/8001由 ROOT 管理，未知或用户进程不操作。

## G4-E v2 / V00-P v2 / CTRL-browser v2 追加卡

触发：新增真实浏览器第三整轮 9/11 的发送前缓存故障，使公开恢复入口因 stale busy 禁用。E 独占仅 `model/useServerPersistence.ts` 与新 `g4-recovery.test.tsx`、`edit/` 新证据；finally 清同一 promise 后仅通知同 mounted/document/load/epoch 会话，不去掉任何 busy/exclusive/读回/原包守卫。新增公开行为和迟到旧会话回归；旧 RESULT-v1 与失败原件只读，形成 RESULT-v2 后 STOP。

V00-P 只强化原独立公开用例的故障持续时恢复/刷新按钮可用及原包/编辑仍阻断 oracle，原38项其余断言保持、原公共测试快照保留；新冻结后完整重跑38。ROOT 独占新浏览器 QA，将坏缓存注入移至新页 initScript，完整坏字节/读阻断/零后台增量断言不变；第三轮原测试保留。新产品必须完整 check/build 后再独立整轮、完整新11场景、原适用14场景、当前174 E2E，不转签旧产品的通过轮。

## B7A-Q / B7A-V00 v1 追加卡

G4-CLOSE-v1 于13:39:48关闭，之后先交B7A-REQUIREMENTS-MATRIX-v1（SHA d6f533aad487ea2c3010564f4560f384b440dcd499d28e305d8dd0be24125d10），才释放实施。Q 独占新增 `scripts/teaching-quality/prepare_review.py`、专属测试和新说明、本批 `b7a/`，独占新plan私有契约；已验三工具/旧52测试/旧样本不可改。S 独立只写 `v00/b7a/`，先手写预期与反例准备STOP，ROOT新候选冻结后才执行；不照抄作者测试或结果充expected。ROOT独占权威状态、矩阵、候选与后验。

范围仅离线：复用新失败闭合聚合器和固定manifest/index SHA，15案例、逐例DOCX、代表四DOCX/四PDF/13页、rubric/原空feedback只引用；新增材料索引/native逐页空表和说明，不生成原材料、不实现live执行器。完整/显式子集/缺项/错误集合/SHA/ZIP/来源坏/secret/JSON/人审非空/覆盖拒绝须独立反证，网络/应用/.env均0。原生实际页号/页数/应用/真人字段空，按教师实际每页追加，PDF13页不预填native页数。所有首败/实际命令/PID/时间/exit/字节绑定/资源/TEMP保留后STOP；原B6/B7整体、RAG-REL不关闭。
