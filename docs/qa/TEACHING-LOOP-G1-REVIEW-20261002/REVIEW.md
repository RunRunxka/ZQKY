# G1 修复候选 g1-r2：代码复查与续验入口

2026-10-02。用户请求“review代码，下阶段提示词”。本次只读产品，新增隔离审查证据并更新阅读入口；没有执行 G1 浏览器门禁、启动监听服务、关闭整体 G1、实现 B4 或提交/推送。

## 结论

**本次范围未发现新增可复现产品缺陷，不新增 P1/P2 修复票。** 八项 G1 修复的实现与独立验收记录一致，新增边界探针与相关窄回归通过。下一阶段应接续剩余门禁，不能重新派发已经修复的八项，也不能以本次组件/ASGI 结果替代浏览器验收。

**整体 G1 仍未关闭，B4 尚未开工。** 5174 启动曾被自动审批拒绝，理由仅 `blocked by policy`；本次没有重试或换工具绕过。实际浏览器、三视口像素/键盘/减少动画与适用 E2E 均未执行。本报告是范围有限的代码复查，不声称穷尽全部输入与时序。

实际现场 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`；开工 **g1-r2 826/826 SHA 一致**。清单 SHA `9471f43eb5ba9cde9d79ab65b84f5cf1fcd607729b1ad2388d2bfde5c78a072b`；用户 next-env 原 SHA `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`。本次另保护原 G1 证据目录 359 份文件。见 [开工基线](BASELINE.json)、[最终核对](FINAL-VERIFICATION.json)；源代码与旧报告均保持原样。

## 八项实现核查

| 原问题 | 当前实现与核查结论 |
| --- | --- |
| B3F-R01 未存成绩仍可确认 | [ScoreImportReview:88](../../../apps/web/src/features/assessments/ScoreImportReview.tsx:88) 统一 dirty/保存中/等待权威预览/映射待存守卫；[载荷与提交:197](../../../apps/web/src/features/assessments/ScoreImportReview.tsx:197) 普通确认拒绝未保存输入，未知结果优先重放完整冻结包。服务端已经 confirmed 后的重放仍可操作。 |
| B3F-R02 迟到映射保存擦新输入 | [ScorePanel:250](../../../apps/web/src/features/assessments/ScorePanel.tsx:250) 冻结编辑代次，[回执:302](../../../apps/web/src/features/assessments/ScorePanel.tsx:302) 只 ACK 原保存代次，较新编辑保留 dirty；后续权威 GET 失败不放行旧预览。 |
| B3F-R03 名单变更不刷新施测 | [Workspace:41](../../../apps/web/src/features/assessments/AssessmentsWorkspace.tsx:41) 独立名单变更 token，[施测:104](../../../apps/web/src/features/assessments/AssessmentsPanel.tsx:104) 同 key 刷新并保留合法勾选/出勤/人次；移出有提示，读取失败阻断普通创建而保留草稿。 |
| B3F-R04 原始分数被截断封存 | [tabular:179](../../../apps/api/app/services/tabular.py:179) 成绩原文完整转换后校验长度，超限定位 422；公式视图与缓存视图均经过该路径。CSV 编码与 parser 错误信封有明确拒绝；通用展示截断没有再作为成绩数值输入。 |
| B3F-R05 到期租约仍可写 | [JobStore.complete:504](../../../apps/api/app/repositories/jobs/repository.py:504)、[fail:557](../../../apps/api/app/repositories/jobs/repository.py:557) 实际写锁内读行并取钟，核原 token/attempt/running/expiry/cancel；失权或到期零发布/终态，取消优先限定于有效租约。 |
| B3F-R06 收尾时重试丢调度 | [JobEngine:200](../../../apps/api/app/services/jobs/engine.py:200) 按目标 attempt 排队、等待旧 task 收尾；done callback 以任务对象身份删除 tracking，旧回调不会删除新轮。连续失败与 queued 取消再重试补充探针通过。 |
| B3F-R07 富题按旧指纹误判重复 | [题面算法:148](../../../apps/api/app/services/question_bank/fingerprint.py:148)、[统一查重:813](../../../apps/api/app/services/question_bank/service.py:813)、[当前修订查询:1422](../../../apps/api/app/repositories/question_bank/catalog.py:1422) 使用 question-surface-v1，旧算法并存不改写。随机身份/答案解析不造新题，正式修改后按当前修订查重，历史内容/指纹保留。 |
| B3F-R08 公式静默少参数 | [RichContentRenderer:55](../../../apps/web/src/components/ui/RichContentRenderer.tsx:55) 按序遍历全部 delimiter 表达式，显式/默认分隔符与空项保留；未知结构明确提示并展示安全原文。实际浏览器 MathML 外观仍待验。 |

前端细节见 [frontend/RESULT](frontend/RESULT.md)；任务见 [jobs/RESULT](jobs/RESULT.md)；成绩与题库见 [score-qb/RESULT](score-qb/RESULT.md)。原 G1 的 52/53/20/真 API 1 项是被核对的已有证据，不计成本次重跑。

## 本次实跑与验证边界

| 命令范围 | 单次结果 | 核验目的 |
| --- | --- | --- |
| 任务两个既有文件 + 两个新 ASGI/临时库边界 | **22 passed，exit 0，2.900s** | pending 取消后并发再重试仅执行一次；连续两轮失败 cleanup 中重试到第三轮，旧回调不删新 tracking，只有第三轮发布 |
| 成绩/题库新增窄探针 | **5 passed，exit 0** | GB18030/前导零/20K原文、超限地址、非法编码；真实 ASGI 改题后当前身份/历史保留；答案专用图片不造新题 |
| 前端新增组件边界 | **3 passed，exit 0，1.33s** | 已 confirmed 时未知原包重放；映射保存后 GET500 仍阻断确认；名单刷新失败保留草稿/拒普通创建 |
| 既有前端 assessments + RichContentRenderer | **11 文件 / 111 passed，exit 0，2.93s** | 当前相关窄回归，无源码修改 |

完整实际命令、stdout/XML/JSON/exit 与首败记录见三个子报告。各命令分别计数，不相加为单次全量。新探针首败分别为 Settings import/allowed_origins、不存在的只读 helper、jsdom dialog 夹具问题；仅修审查夹具，原失败日志保留，没有产品正确行为失败或放宽断言。

任务与题库请求使用进程内 ASGI，无监听端口；前端使用独立 jsdom/fetch 边界，不冒称浏览器或真持久化全链。成绩纯读取探针不能当入库链验收；正式改题/确认探针使用真实四库与 TestClient。后端均在间接 app.main 导入前设置新的临时 ZQKY_DATA_DIR、测试环境与 UTF-8，应用凭证显式隔离。

**本次未执行**：全量 check/API/build/E2E、真实浏览器及视觉/键盘/减少动画、真实模型/Word/WPS/Qdrant、正式数据迁移、超基线压力。未启动服务、读取正式凭证/业务数据或操作用户草稿。临时数据目录保留登记，没有删除；原 G1 八项独立行为与工程门禁已有实际证据，本次无需重复。

## 续跑前应处理的配置与 B4 设计事实

下列是已知续验配置/后续设计前置，**不是本轮新增产品 P1/P2 票**：

1. 根 [Playwright 配置](../../../playwright.config.ts:21) 自动启动 5174 且 `reuseExistingServer=false`。用户手动持有 5174 后直接跑默认配置会遇到服务归属/端口冲突。续验应使用新证据目录下无 webServer 的配置，继承原测试集和断言，只使用已获用户手动启动的服务，不设失败后自动启动 fallback。
2. 现行 `.next/routes-manifest.json` 静态核对指向 8001，符合原 G1 构建记录。启动时环境变量不能证明旧构建已经更新代理，后续仍核构建身份与实际目标。本次没有启动前端验证运行期代理。
3. 现有 assessments 与 question-bank-real E2E 各自占用并管理 8001；完成独立浏览器链后先释放该链自有 8001，再串行跑原 E2E，不同时持有两个后端或终止未知进程。两者 afterAll 默认删除本轮临时根及 api.log；续验需明确 opt-in 保留数据/日志的测试适配，停自有服务但不删除。无 webServer 配置并不能禁用此清理；适配源变化须登记新候选，保持全部业务用例和断言。
4. 聊天集成默认脚本另建 `.next-test` 并自动启动 5174/8001/8002；不能与手动前端并发。stream_backend.py 本身在导入 app.main 前未设置临时业务根，外层必须先注入隔离环境。此处是静态前置核查，没有执行风险路径或确认正式数据曾被写入；续跑可保持原业务测试、拆开环境/服务配置，不绕过前端拒绝。
5. 原 G1 已披露当前**没有 export_artifacts 已实现表/服务**，B4 应新增最小产物元数据/DTO/受管资产下载接线，复用现有任务、资产与 T10 renderer，不能假称复用现成下载接口。
6. 原成绩快照含 classId、**不含冻结 className**。旧班名缺失不可凭当前 classes 表补造考试时事实；B4 最小方案以冻结 classId 分组，班名缺失明示，实时辅助标签与历史事实区分。

## 下一阶段提示词

复制 [G1 续验与 B4 启动提示词](../../design/teaching-loop-v1/G1续验与B4启动提示词_20261002.md) 到后续执行会话。它要求：

- 先核 g1-r2 与用户手动前端就绪状态，补齐真实浏览器和适用 E2E；未就绪/仍被拒时保持待验，不启动 B4。
- 不重复八项已修复工作；真实门禁发现缺陷才在对应 G1 范围修复、重冻、复验。
- G1 正式关闭后才冻结 B4 契约/追加迁移，建设 T70 固定学情事实与 T80 正式题练习、审核、DOCX、成绩回流和最小页面。
- 历史班名、导出产物服务、练习来源 FK/确认闸门等按实际源码分期落地；AI 教案留 B5，保留已有本地教案能力。

本次最新阅读入口同步到 CURRENT_STATUS/NEXT_SESSION_START/文档索引。原 G1/B3 报告和冻结件保持当时事实，没有追改为“浏览器已通过”或“本轮已交付”。
