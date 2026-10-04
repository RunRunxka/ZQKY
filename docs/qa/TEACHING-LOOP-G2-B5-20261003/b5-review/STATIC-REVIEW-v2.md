# B5-REVIEW v2：F30 与公共生命周期静态审查

2026-10-03；独立审查者 `/root/b5_review`。结论：**发现 B5R-R04（P2）与 B5R-R05（P1）；B5R-R03 首次窄修的合法参数重挂缺口已由 CTRL 补修，另确认跨文档残留复制 intent（P2）并交 FE v2。不能据本报告关闭 B5。** 本轮只读取源码、作者原件与冻结契约，没有运行产品、测试、服务、TCP、模型、迁移、恢复或独立业务 oracle。

审查起点是停写 BE v2（45/45 作者）、AI v2（144/144 作者）和 FE v1（50/50 作者）；作者通过不是独立验收。完整用户原请求、根/API/web/lesson 指令、CURRENT_STATUS、PROJECT_GUIDE、B5-CONTRACT-v1、冻结 33 件及公共装配卡已在前轮读取。实际分支/HEAD 由 CTRL 卡提供为 main@6aeb57280f6a7e0d7391cad4d150745479ea58ec，本轮不执行 Git。后半程 FE v2 已获授权且由其唯一作者修复；下述发现保留发现时源码与快照，不因后续作者修复改写原判定。

## B5R-R05 · P1：固定报告班级读取违反真实分页契约，阻断实际生成入口

发现时位置：`apps/web/src/features/lesson-plan/components/SourcePanel.tsx:41`；实际适配 `model/workspace-services.ts:12` → `apps/web/src/services/teaching-loop-b4-api.ts:31-32`；后端 `apps/api/app/api/v1/analysis.py:42`，并由 `apps/api/app/services/analysis/service.py:149-152` 再限制。

触发：在真实 F30 来源面板选择任意合法 ready 固定报告，或从 `analysisRunId` 参数/当前教案 context 自动加载该报告。`selectRun` 的 Promise.all 每次请求 `listClassesReport(id, { limit: 1000 })`。适配器直接传入实际 HTTP query，没有截断或替代接口；后端 Query 上限和服务上限均为 200。

预期：班级报告读取成功，目标班级资格与固定知识点可选；报告超过一页时仍能正确发现目标班级，不静默丢失后续班级。

实际：参数校验先返回 422，Promise.all 进入错误分支，成功分支的 setRun/setRunClasses/classReady 不执行。完整真实路径无法选 KP 和成为 ready，随后 `ProposalPanel.tsx:60` 拒绝生成。来源 mock 的成功返回没有覆盖真实 limit 契约，因此作者组件通过不能证明该入口可用。

最小反例建议：独立真实 API/browser fixture 建一个合法 ready run，选择其报告，检查 classes HTTP 为 2xx、目标班级和 KP 可选择、生成前置条件可成立；另建或替身精确模拟 >200 班的分页，并把目标班级放在第二页，验证全部分页/目标班级读取。请求 limit 必须 ≤200，不能只把 1000 改成 200 后忽略 total。**这是接口契约与调用链的确定性静态推导，本轮未发送 HTTP。**

缺陷源 SHA：SourcePanel.tsx `d340e5029a7d5ff7e91e6b8485f38defbab3c8a5368fee41a51d2d7942fbdc10`；workspace-services.ts `ff25129abe4f39c4121c429ae088ae02bcd45103307bea5356d2cff15b9a776c`；teaching-loop-b4-api.ts `ee64f465f2543ba0c9d2c7f70eafd58bf3f1861baa65ff74a472e2f6fd042b68`；analysis 路由 `98d7ee8ccb0057f23578839b4b3224d61c456a1a52c7a4dd70a57cce285999f1`。归属 FE，CTRL 已发 FE v2 修复卡；需稳定版本另复核。

## B5R-R04 · P2：旧生成载荷被重新绑定到新来源签名，过期候选仍可应用

发现时位置：`apps/web/src/features/lesson-plan/components/ProposalPanel.tsx:61-71`，陈旧判断 `:53`，应用前置判断 `:80,103`；不增加编辑代次的模型控件 `SourcePanel.tsx:78`。冻结契约要求编辑/来源变化使候选过期，恢复/重试保持首次操作身份、原输入与代次。

反例 A（保存等待窗口）：选模型 M1，点击生成，`await server.flush()` 等待保存；期间改模型到 M2，控件未锁。await 后 `payload` 从点击闭包中的旧 inputs/doc.selection 构造（M1），但 `capturedKey` 从最新 `currentInputKey.current` 读取（M2），代次从当前 store 读取。收到候选后 generation.selectionKey 为 M2，当前输入也是 M2；仅模型改变不会增加 editor.revision，因此 stale 判定不会因这次来源变化成立，M1 候选可以在 M2 面板状态下应用。更一般地，等待期间的编辑/选择与旧闭包冻结边界也不一致。

反例 B（unknown 原包重试，不能仅靠锁 flush 修复）：首次按 M1 发生成请求，服务端可能已收包，但浏览器得到 status=0。generation.current 只在 API 成功返回后的 callback 中登记，所以本次仍为空；原 operation 在 server cache 保持。将模型改成 M2，然后“重试原生成包”，`generate.pending.payload` 正确仍是 M1，但是 `capturedKey` 重新取 M2。成功时因为 generation.current 没有原操作签名，`selectionKey` 被赋为 M2。原请求 metadata 的 edit/load 与当前仍一致，stale 检查通过，旧 M1 结果仍可采用。相同提交 ID 和冻结 HTTP 包本身没有被更换，缺陷是它们对应的来源签名被换成了重试时签名。

预期：来源签名与冻结生成载荷、首次编辑/加载代次同属一个原操作；输入改变后的原候选必须显示过期、禁止采用。unknown retry 只能重放原载荷和原签名。

实际：签名第一次持久化发生在 HTTP 成功返回后，并且从发送/重试时的可变 ref 取得，不能代表原载荷的真实来源。两条反例均不需要后端 CAS 冲突：模型变化不修改正文，也不创建服务器新修订，所以后端采用条件不补救该客户端适用边界缺失。

最小反例建议：独立组件/浏览器 oracle 分别控制 flush 延迟和首次 generation ACK 丢失；只把模型 M1→M2，其余 edit/load/base 不变。逐字节检查 HTTP 包、submissionId 与 generation 持久签名，M1 结果必须 stale 且 apply 不发 HTTP。再覆盖 reload 恢复 unknown 原包；若只在等待窗口 disable 控件而不在首次 HTTP 前持久化原签名，反例 B 仍成立。**本轮只静态推导，没有运行 oracle。**

缺陷源 SHA：ProposalPanel.tsx `d2f961eddf790d4cf3efe0499db2c37ac5624299b68a7543ff9e5f2b813ea572`；SourcePanel.tsx 同 R05。两件发现时原字节保存在 `SOURCE-SNAPSHOTS-v2/`。归属 FE，CTRL 已发 FE v2 修复卡；需要新停写清单和独立复验。

## B5R-R03 补充：只移除 doc/revision key 尚未覆盖合法 analysis 参数

R03 原因由 CTRL/FE 在本轮前已确认：page key 含 doc/revision，历史→当前 URL 更新使整个 Gateway 重挂，pendingCopy 丢失。v2 起点 root page 首修 key 仅 `analysisRunId/error`，SHA `3cac49059512cc11dd71349a6985e96567f9178df43b6096408f05a6a6962aeb`。

本轮发现合法 `/lesson-plans?lessonPlanId=D&revisionId=R&analysisRunId=A` 仍会触发同类丢失：pageParameters 允许该组合；`DocumentGateway.tsx:75` 先 setPendingCopy，`:58-59` 打开当前时 URL 仅保留 lessonPlanId，key 从 A→空，Gateway 再重挂。预期明确复制按钮应保留，复制成为当前编辑后可 undo，save 创建新 revision 且不改历史。

已即时报 CTRL，CTRL 补修当前 `apps/web/src/app/lesson-plans/page.tsx:9` key 仅 routeError，SHA `17dcba67e41b9926bf3467c04fe9d075a98d2f1eb9e7377c4a4ece78f187ff8f`。Gateway `:40` 在新 props 与已切换 doc/revision 相符时不清 pendingCopy；内层 Provider `:80` 按 mode/doc/revision 建新编辑会话，保留外层 Gateway 待复制状态。这消除了上述具体静态重挂原因。**没有据此关闭 R03；真实 Next RSC 更新、copy→undo→save 新修订需 V00 oracle。** 原首修前字节由 CTRL 保存在 `ctrl/lesson-route-before-copy-v2.bin`，SHA `16af099d106aba530a85b9a9ca82c57ffa49f1e3cb3307d549aa0131b8c1a69e`；本轮未改产品或该原件。

另外确认 R03 的一个剩余会话边界（P2）：Gateway 保活后，`openDocument:60` 不清 pendingCopy，`DocumentsPanel.tsx:73` 只判断 pendingCopy 与 server 存在，没有校验复制来源 lessonPlanId 等于当前文档。historyA→currentA 留下待复制 intent A，尚未确认复制便打开 DocB；props 同步与内部 doc/revision 一致，Gateway:40 直接 return，所以 pendingCopyA 保留。在 B 显示的“明确复制历史正文到当前编辑”刷新核对的是 B 的 baseline，然后直接 `editor.replace(A.data)`。预期历史回编辑动作只在所属文档的当前会话保留，换 doc/history/local 或取消应清除该 intent；实际可以把 A 正文套到 B 当前编辑，并按 B 的 context/source 保存。这是同文档复制动作的身份隔离缺口，不需要后端 CAS 失败才触发。CTRL 先提出该疑点后，本审查对具体源码准入条件独立确认并即时回报；FE v2 已获授权补 same-document gate 和 intent 清理，本报告仍记录发现时快照，未验证新修复。最小反例：A 历史→A 当前准备复制、切到 B，B 不得显示/执行 A 的复制；另核切 history/local、leave 取消及多次切换。Gateway 原 SHA `4d69bdf70520bc32c179744bc149f20aaff4e37a5a64be62b2f70f557d2e34f7`，DocumentsPanel 原 SHA `2d1778034a5d05006a472bf6a54da3cc7fbcf9afa722b31d1ce455be041ef3a2`。

## R01/R02 的静态复核与其余已读边界

R01：读取 AI v2 的 preparation/privacy/service/validation 完整相关路径。新检查把服务端严格产生的 schema keys、opaque alias、合法汇总整数及规范化分钟放在已知结构路径中校验；自由文本仍检查已知姓名/学号/ID和身份标记。三协议 check_wire 检查实际 body 的固定角色/消息数、严格 JSON user 与已冻结 payload 相等，并拒绝未知 keys/tools/messages。candidate 在严格 validate 后才做路径感知 privacy。当前源码没有再确认 v1 短数字碰撞反例或新的具体泄漏路径；**静态未发现不等于三真实协议 wire 独立通过**，144/144 为作者证据。

R02：读取修后 `lesson_schema_gate._normalized`，仅折叠引号外空白，quoted literal/JSON path 原字节与 SQL case 保留，比较实际声明并查 FK。v1 的 ai_applied→AI_APPLIED 与 $.subjectId→$.subjectid 不再被 lower 抹平。未确认此窄修的新问题；CTRL 的 10/10 和两真实 SQLite mutation 为作者证据，本轮未执行 gate/restore，旧 v1 发现和原件保持。

F30 阅读覆盖：server cache 独立键与读取失败保护；恢复 load generation、edit generation、late ACK 和已知更高 CAS/fixed identity；原包落盘后才 HTTP、unknown 不自动发送；StrictMode effect 清理及显式重试；AI apply 的 whole-field 选择、原包恢复和旧 ACK 保留较新编辑；导航 leave 一次决策与公共根 hasProvider 装配；历史只读、历史复制到当前编辑的刷新基线与 store undo；旧本地稿原键/完整信封、显式 import/失败保留；Word/JSON 的点击数据及 source label、PDF 的 print snapshot 和编辑/切换锁。除上述具体问题外未确认新 P1/P2。相关路径的源码观察不是完整会话、双标签并发、真实浏览器生命周期、导出内容/布局通过证明。

一项明确契约文字缺口（不另计运行阻塞）：B5-CONTRACT-v1.md:66 要求界面明确“需求不填学生个人信息”和已知来源阻断适用边界。发现时 SourcePanel 教师要求 textarea（:81）及模块生产 UI 文案没有这条说明。已报 CTRL 补文案，需稳定 UI 对照确认，不以后台 privacy 异常提示代替输入前说明。

## 源绑定与未执行范围

`SOURCE-BEFORE-v2.json` 在初始作者停写清单/冻结件上绑定 98 个存在文件，authorAndFrozenDrift=[]；它记录的 NavigationGuardBridge.tsx 是检索候选路径缺失，实际公共装配在 app/layout.tsx 与 services/navigation-guard.tsx，本报告不据该不存在文件宣称能力缺失。`SOURCE-ADDITIONAL-BEFORE-v2.json` 补绑 7 件（其中一件与前者重叠），合计 104 件。`SOURCE-AFTER-v2.json` 合计 104 件，仅 3 件有变更：CTRL 授权 root page R03 补修，以及 FE v2 授权在途 ProposalPanel/SourcePanel 修复；分别登记前后 SHA 和归因。这些授权修改不是源码一致性违规，也不是稳定候选已通过。

冻结 33 件与原 v1 报告/结果在本轮绑定前后未漂移；冻结清单 SHA `8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db`。发现时三件产品快照及 manifest 均只写在本审查目录。正式 .env/.local-data/凭证/真实草稿/Qdrant/收费模型、产品/原测试/权威 docs/冻结件/Git 未访问或修改。本轮没有执行 check/API/153/14、完整恢复/并发/三协议 wire/Next/browser/export oracle。后续必须对新的停写稳定候选独立复核 R01–R05，不能将本报告或作者新测试当整批验收。
