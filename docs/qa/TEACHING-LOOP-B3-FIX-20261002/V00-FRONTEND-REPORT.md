# V00-FRONTEND v1 独立验收

负责人：`/root/v00_frontend`。产品只读，与实现者分离；初始写入范围仅本报告、`V00-FRONTEND-probes/` 和 `logs/v00-frontend*`；V00-FINAL收口仅更新本报告与`browser-reviewed-r7.json`。**最终前端验收 PASS：独立5文件105个新场景全部通过，六项组件首败关闭；r7移动端溢出V00-F07也已以新图片/布局JSON独立复核关闭。总控r7真实6条链全过，已独立读取JSON/重放附件并查看9张关键图片。最终全量E2E实际153 passed，0 unexpected / 0 flaky / 0 skipped；其中本批6条真实链全部通过。收口对r7全168项SHA-256核验零漂移。全量回归不等于每个旧模块的真实API业务验收。**

## 候选与隔离

- 起始冻结 `FROZEN-CANDIDATE.json r1`，`main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`，158 项磁盘字节 SHA256 全部相符。证据 `V00-FRONTEND-probes/hash-before.json`。
- 最终验收 `FROZEN-CANDIDATE-r3.json`，165 项；前置 `2026-10-02T05:47:39Z`、后置 `2026-10-02T05:54:13Z` 均零漂移，见 `hash-before-r3.json`、`hash-after-r3.json`。r1→r2 的 React commit 测试等待修正、r2→r3 的六项产品修复/Decimal 解析/名单探针行号等，均由总控授权调整后重新冻结；没有把这些合法候选变化称为本验收期间的写入漂移。
- 总控最终r4继承核验：`2026-10-02T05:59:49Z` 对 `FROZEN-CANDIDATE-r4.json` 全167项逐文件核验，零漂移；r3→r4差异严格只有 `apps/api/tests/test_jobs_engine.py`、`test_rag_sessions.py`、`test_scores_confirm.py` 三项Python测试记录，所有产品/前端SHA保持相同。证据 `hash-reviewed-r4.json`，因此105例前端产品结论继承至r4，没有宣称对Python delta重新执行前端或API测试。
- 最终r7核验见 `hash-before-r7.json`（06:09:30Z）/`hash-after-r7.json`（06:13:45Z）：168项全部匹配、前后零漂移。r3→r7所有JS/backend产品保持相同，后续仅授权测试调整与r7模块CSS约束；105条组件结果继承，新增CSS由真实6链的三视口测量和实际图片验证，没有用jsdom通过冒称布局通过。
- 已读取根/web AGENTS、原 B3 审查及其 UI 探针、当前任务卡、F10/F10-GUARD/F20/ROSTER 结果卡；核查共享 renderer、workflow 客户端、三个任务 hooks、导入/校对/确认工作区和双侧前端契约。
- 独立 Vitest 配置、缓存和测试均在本批新证据目录。实际 React 组件/hooks/observer/API 客户端；仅 HTTP fetch 边界返回受控值，Next navigation 提供测试路由适配，jsdom dialog/object URL 提供缺失的浏览器 API shim。
- 未启动服务/端口、未操作浏览器、未读取真实凭证/草稿、未导入 Python 应用、未修改产品/既有测试/配置/锁文件/权威进度或 Git。`NODE_OPTIONS=--no-experimental-webstorage`。

## 独立首败与阻塞

| ID | 优先级 | 实证问题 | 原始证据 | 总控处置 |
| --- | --- | --- | --- | --- |
| V00-F01 | P2 | 成绩确认回执丢失后，刷新相同批次 r4→r5、preview9→10、assessment7→8；再次确认新建 submissionId，并把三个版本偷换为最新值，未原包重放 | `logs/v00-frontend-first.log`；`confirmation-boundaries.first.tsx` | CLOSED：r3 刷新后第二次请求逐字段等于首次冻结包 |
| V00-F02 | P1 | 创建施测结果未知时标题仍可编辑；重试换 title 与 submissionId，可能重复建立施测 | 同上；`first-failures-r1.json` | CLOSED：r3 锁编辑，向输入派发改值也不能替换重试原包 |
| V00-F03 | P2 | 成绩修正结果未知时改理由，再提交换 reason 与 submissionId，原成功结果不能重放 | 同上 | CLOSED：r3 理由/修正/基线/提交 ID 原包重放 |
| V00-F04 | P2 | 题库确认结果未知时仅冻结 ID；再标记草稿已校对使 r4→r5后，同 ID 的 expectedDraftRevision 被替换 | `logs/v00-frontend-question-first.log`；`question-confirmation.first.tsx` | CLOSED：r3 编辑/拆分/重复决策锁定；只读刷新到 r5 后仍发送原 r4 与 link_existing 决策 |
| V00-F05 | P2 | 题库网络丢回执 status0 时错误文案声称“没有任何题目被入库”，实际结果未知 | 同上 | CLOSED：r3 明示“结果未知”，不再声称零入库；HTTP200+failures 仍明确整批未确认 |
| V00-F06 | P1 | 知识点 AI 候选初次 queued0 的合法 claim1 被知识点 hook 当成接管；页面留 queued0、终态回调0 | `logs/v00-frontend-knowledge-create-first.log`；task-observation initial knowledge 用例 | CLOSED：r3 实际 knowledge hook 接受 queued0→terminal1；三域 queued N/N+1 及 N+2 拒绝全部通过 |
| V00-F07 | P2 | 完整真实链修正到v2后，390px原生人次select内长classId撑宽修正表单，根scrollWidth413>390；内部矩阵横滚正常 | `logs/root-browser-layout-diagnostic.txt`；`browser-layout-first/.../complete-history-390.png`，本验收者已查看实际图片 | CLOSED：r7 field及select约束；实际新390图片控件在卡片内，根scrollWidth390，三个视口均无页面溢出 |

F01–F03 的字段差异逐项抄录原 Vitest equality 输出到 `first-failures-r1.json`；该 JSON 不冒称新增 HTTP 运行。首次 66例结果为60通过/6失败，其中另3失败来自独立新探针的 selected assessment GET 返回了列表 DTO，已仅修复新探针路由；不把这3项记产品缺陷。原始日志及首轮测试快照保留。

## 正确行为与功能审查

| 范围 | 独立证据与静态检查 |
| --- | --- |
| G0 RV09/RV10 | PASS：三个真实 hook 各一条 StrictMode 已终态收据单次回调；各自 retry/cancel × 迟到成功/失败 × reset/switch/unmount 共36条零旧回调、视图或错误污染。knowledge 初次窗口首败 F06 修复后在最终合跑中复验通过。 |
| R01 六态 | PASS：knowledge/question/teaching queued0→running1→succeeded/failed/interrupted/cancelled 均通过；三域 attempt2 接管拒绝并停止旧观察。任务观察最终55例。以终态 DOM commit 为屏障，再核回调一次、attempt及观察状态；源码的同步终态回调可早于 React commit，原 root 测试只 await 回调不足以保证界面已提交，保留全部正确性断言而改等待方式是合理测试修复。 |
| R02 四态承认 | 原始空白分别配 recorded0/missing/absent/exempt，真实 ScoreImportReview 使用权威 DTO 发送准确 absences/missing；缺少权威字段禁确认。5条通过，不以原空格推导缺口。 |
| R08 旧创建 | PASS：卸载/同面板选择切换 × 200/409/422 六条零旧选择/父级改变回调。选中施测 GET 夹具已修为实际 detail DTO，最终六条全部执行通过。 |
| 名单 | PASS（前端传输/决策）：CSV/XLSX multipart、sheet/manual header、身份按 studentId 的 link/create/ignore、leading-zero 学号显示、未知原包与class切换4条；名单 rowNo 是不含表头的1基数据行。静态核批次恢复、CAS校对；RosterPanel 转班发送 expectedStudentRevision/fromClassId/toClassId/movedOn 并显示有起止日期的 memberships，失败保留选择、网络未知提示先对照历史。转班没有新增独立组件探针，XLSX测试字节仅验证传输；真实解析/转班事务不据此标 PASS。 |
| 原卷 | 独立测试覆盖21个完整源块20/页、结构化 supplement_text实际字段、内容损失无exclude选项、共同材料保留、手工容器/叶子/满分/知识点、确认读自己的固定修订标题、固定读失败零选择、unknown同包及卸载零父级副作用。AI入口静态明确模型/CAS、公共queued窗口、候选显式关联正式知识点并审核应用/拒绝；不自动发布。 |
| 参测/补考/出勤 | PASS：ready 学生已有attempt2仍可选择→默认3→POST明确studentId/attempt3；出勤unknown锁字段并原包重放、卸载200/409零父回调3条。ParticipantAdd 源码无“已有attempt就disabled”规则；select仅等待读取ready，故总控初始loading快照的catch22猜测未成立。 |
| 成绩映射/历史 | 静态核 attendanceColumn/totalColumn 可选保留与PATCH；施测/出勤更新后需要独立 POST refresh，发送import/assessment/base三字段，校对 PATCH 不能暗中刷新参测快照。原件/校正/有效状态分别显示。历史取固定 revision 的 participant/item snapshots及分页矩阵，不在前端重算旧矩阵；修正形成新版本。未知确认 F01–F03 已以真实组件原包 equality 复验关闭；数据库旧修订不可变依 G0/SCORES 真实后端验收。 |
| F10 正式关联 | PASS：formal links 名称/修订/学科快照与 legacy text标签分区；未改动不发整表、显式清空传[]；学科变更冲突由后端核完整有效集合。草稿/正式题切换200/409/422六条零旧回调、旧409不读回。r3额外3条验证 StrictMode 同轮新server快照不擦本地文本/显式清空关联，以及旧409在切换后立即编辑时零旧回调、保留新文本和空关联；保存空关联确实发[]与新CAS。 |
| F10 分类/补题 | 静态核 ContentForm 的学段/年级/学科/版本来自taxonomy四组正式ID，字典不可用有手填ID说明，legacy knowledgeTags 不参与正式知识点筛选。知识点学科内编码身份、同学科active父级、CAS与内容revisionId/version、显式clearFields和归档历史提示可读。GenerationPanel发送真实profileId/正式knowledgePointIds/题型/难度/数量和instructions，重试冻结模型；成功仅生成待人工校对批次，采用真实question hook的queued窗口，无自动正式入库。 |
| rich 权威 | 旧 Markdown 不盖 rich题干/共同材料/选项/答案/解析；显式转换先richContent=null，再允许文本编辑；旧输入对象不变。共用唯一renderer，不复制第二套。 |
| rich 安全/资产 | 独立11例全通过：HTML/远程图/javascript link不生成可执行/外载DOM、KaTeX安全参数；合并表格rowspan/colspan；OMML白名单MathML及原XML，DTD/异命名空间明确原文fallback；同assetId跨对象/修订abort旧读取，迟到字节不createURL，current URL在切换/卸载revoke；StrictMode/unmount迟到不创建URL，SVG MIME拒绝。 |

## 命令与首轮结果

根目录使用：

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-B3-FIX-20261002/V00-FRONTEND-probes/vitest.config.ts
```

| 日志 | 选择范围 | exit / 真实结果 |
| --- | --- | --- |
| `v00-frontend-first.log` | 最初2文件 | 1；60pass/6fail，其中3产品fail+3独立夹具错误 |
| `v00-frontend-rich-jobs-first.log` | 排除 confirmation 文件，rich11/jobs49 | 0；2文件60pass |
| `v00-frontend-question-first.log` | question-confirmation | 1；7pass/2产品fail |
| `v00-frontend-knowledge-create-first.log` | `-t 'knowledge AI candidate initial'` | 1；1产品fail/49未选择skip，非49执行通过 |
| `v00-frontend-r3-first.log` | 最终新5文件首次合跑 | 1；104pass/1fail，唯一失败为新增只读刷新探针的“修订 r5”匹配3个元素；产品编辑锁及读回已正确，定位未能走到最终重试断言 |
| `v00-frontend-r3-final.log` | 最终新5文件完整合跑 | 0；105pass/0fail/0skip，保留原包深相等断言，精确限定“草稿编辑”region并新增 link_existing 决策校验 |

## 未执行

- 本验收者未执行 build、全量 check/API/e2e、真实服务浏览器链、人工键盘或 reduced-motion 操作；按任务卡由总控组织。已独立查看总控3张真实浏览器像素和 r2 Playwright JSON，见下节；图片复核不冒称本人操作浏览器。
- 未调用真实模型、Word/WPS、Qdrant、正式迁移或超基线压力；没有将这些能力写为验收通过。
- 真实名单XLSX解析、补录出勤→显式刷新→确认完整HTTP事务、DOCX解析/OMML资产与浏览器滚动由总控/后端执行；本验收者没有亲自执行。最终r7真实DOCX完整链、200×100规模已有PASS证据并独立核读，见末节；独立fetch探针仍不把替身扩大成真实服务证明。

## 最终冻结复验

| 探针文件 | 实际执行 | 结论 |
| --- | --- | --- |
| `task-observation.test.tsx` | 55 | PASS |
| `confirmation-boundaries.test.tsx` | 18 | PASS |
| `rich-boundaries.test.tsx` | 11 | PASS |
| `question-confirmation.test.tsx` | 12 | PASS |
| `import-review.test.tsx` | 9 | PASS |

最终日志 `logs/v00-frontend-r3-final.log`：2026-10-02 13:53:51（Asia/Shanghai）开始，6.75秒，5文件105例全通过。随后对冻结r3全165项逐文件散列后验零差异。

总控在r3后验结束后纠正三项旧Python回归测试并冻结r4；已独立核实delta仅在测试记录，167项磁盘SHA全部匹配r4。前端产品结果从r3继承至r4；全量API/最终浏览器门禁仍按总控最终证据判定。

## 总控浏览器证据的独立只读核验

- 已实际查看 `manual-history-1440.jpg`、`manual-history-1920.jpg`、`manual-history-390.jpg`（总控r2真实IAB会话）：两个桌面尺寸的有效0、2.5、缺考、空白状态和含非recorded人次的“不展示总分”可读；1920刷新按钮蓝色键盘焦点可见。390标题/流程/状态说明和矩阵容器边界可读；图片仅截到矩阵表头，内表滚动行为引用总控实际操作记录，本验收者未亲自滚动。
- 非阻塞可读性：班级/施测上下文显示长ID、未选原卷时显示“未选用”。数据足够区分对象，但教师识别成本偏高；没有据此阻塞本批功能验收。
- 已解析 `browser-r2/results.json`：**3 passed / 2 failed / 1 skipped**。通过的是空态/错误恢复/键盘/reduced-motion/390检查、五步成绩真实链、公共retry（Provider实际两次）；完整名单→原卷链停在名单错误行号“第5行”，AI人工校对链停在题干定位，200×100为未执行。原始首败保留；这些是r2阶段结果，当时待跑项没有记为PASS；r7最终重跑另见末节。

七项前端问题均已关闭；全量E2E最终结果已独立核实通过。总体B3是否接受，由总控合并V00-G0/V00-SCORES及各项证据后判定。

## V00-BROWSER-DIAG v3：真实候选审核首败诊断

总控r4真实链日志 `logs/root-browser-final-r4.txt` 与保全 `browser-r4/` 为 **3 passed / 2 failed / 1 did not run**；不能记成完整链通过。AI生成已成功、候选题干可实际编辑，但编辑后立即点“标记已校对”，界面显示修改正文、修订r1和“已保存；服务端当前校对状态：待校对”。

结论：**E2E尚未完成后端要求的独立人工审核步骤，非前端回调/React commit 丢失**。`DraftEditor.tsx:201` 同包发送当前编辑content、metadata和reviewState；`service.py:793` 将它们交给catalog。`apps/api/app/repositories/question_bank/catalog.py:552` 的既有规则要求 content/metadata/正式关联实际变化后回到needs_review，`catalog.py:610` 明确除excluded之外，即使同包指定reviewed也回退。`apps/api/tests/test_question_bank.py:448` 的既有测试对这条规则有直接断言，`test_question_bank_confirm.py:96` 的 `set_content_and_review` 辅助函数同样先落内容再单独审核。

最小修正是测试先“保存修改”，等真实PATCH200并检查新题干、needs_review/r1，再在内容不变的情况下点“标记已校对”，使用新CAS得到reviewed/r2后确认；保留人工审核守卫与最终真实入库断言。总控已仅修改两个E2E spec并冻结r5，原卷上传测试同时改为真实代理保留multipart二进制/显式buffer fixture。该上传结论来自总控诊断，本验收者没有执行上传链。

只读核验r5全167项SHA零差异（`hash-reviewed-r5.json`，2026-10-02T06:04:40Z）；r4→r5恰好只改变 `tests/e2e/assessments.spec.ts` 和 `tests/e2e/question-bank-real.spec.ts`，产品/前端/Python记录散列完全不变。105条独立前端产品结果可继承r5；两条被修正真实链与200×100规模仍等待总控重跑结果。

证据限制：保全r4的AI trace.zip可读到ZIP头但缺少中央目录，标准ZIP读取失败，本诊断未从该trace声称捕获首PATCH网络body；结论依据真实页面error-context、首败日志和请求/后端守卫源码的相互印证。

## V00-BROWSER-DIAG v4：移动端修正表单溢出

`logs/root-browser-final-r6.txt` 实际 **4 passed / 1 failed / 1 did not run**：AI独立人工审核链与公共retry通过；完整链已执行名单→富原卷→score未知回执同包重放→修正v2，并断言v1旧JSON及矩阵不变，随后移动宽度门禁失败，不能写成整条PASS。

本验收者只读检查HistoryPanel、assessments/space/workspace-shell样式和实际390/1920图片。完整链诊断 `logs/root-browser-layout-diagnostic.txt` 在截图后读取布局：1440/1920根宽均等于视口，390根scrollWidth413；390图片实际看到修正人次/计分叶/状态select及加入按钮伸出卡片，故为稳定产品溢出，非未等待布局。该页面当前没有公共导航壳，根为.space-page→main.space-content→HistoryPanel；模块壳宽度不是此处来源。

最可能撑开点是HistoryPanel修正人次select中32字符classId形成原生控件intrinsic宽度。矩阵表本身right约753，但根仅413，且图片在约353处裁剪正常，表格外层overflow-x:auto/relative发挥了作用；诊断的前20个offenders被表格内部元素占满，不能据这些越界坐标误判为表格裁剪失败。

总控r7仅给.assessments-field添加max-width:100%，给其.space-select添加min-width:0/max-width:100%，作用域限定.assessments-page；该缩放约束符合问题，不使用overflow:hidden遮挡内容。本验收者未修改CSS/产品。`hash-before-r7.json` 已对冻结r7全168项校验零漂移，r6→r7候选差异只有该CSS新纳入与测量spec，所有JS/backend不变。105条JS组件结果继承；新真实图片与JSON已复核，F07关闭如下。

## r7真实链、图片与附件最终核读

总控执行 `assessments.spec.ts question-bank-real.spec.ts`，`browser-final-r7/results.json` 实际expected6/unexpected0/skipped0/flaky0，`logs/root-browser-final-r7.txt`为6 passed、24.6s、exit0。本验收者已解码JSON内的附件并另存核对摘要 `V00-FRONTEND-probes/browser-reviewed-r7.json`，未依赖继续全量运行会覆盖的test-results临时目录。

- 重放附件两次confirm输入完全相等、submissionId相同、结果revision相同，replayed分别false/true。history只有v1/v2，附件oldRevision深等于history里的v1，v2基线等于v1；4人次/3计分叶。旧矩阵不变另由spec中实际HTTP回读深相等断言和该用例PASS取证，附件本身未包含旧矩阵，不冒称从附件直接再次比过矩阵。
- AI附件实际queued0→succeeded1；两次真实PATCH返回needs_review/r1和reviewed/r2且改后正文相同，确认failures0、入库1题，finalStats.providerCalls1。公共retry queued1→succeeded2，总累计ProviderCalls3，相对上一生成用例1增加2；没有把累计3误写成本轮retry3次。
- 1440/1920/390布局附件根scrollWidth分别等于1440/1920/390，均无页面溢出。已实际查看3张complete-history图片：有效0、缺考/空白无总分、v1/v2与基线可读，390修正select及加入按钮均收在卡片内；长ID仍可选但不撑页面，矩阵保留内部横滚。
- 已实际查看complete-paper-1440、generation-succeeded、candidate-reviewed、knowledge-filter、public-retry-succeeded及assessments-scale-1440共6张图。富原卷固定修订、共同材料、公式x+1与原XML入口、合并表头和管理图片可见；正式知识点关联可读。题库过滤返回正式知识点“有理数”的1条入库题，生成/重试界面明确待人工校对、不会自动入库；candidate-reviewed图片为滚动后的可见区，reviewed状态以真实PATCH附件取证。
- 200×100真实规模链PASS：528526字节XLSX解析、映射resolved200/missing0、确认HTTP200；从建立200名学生起总耗时3718ms，矩阵50行首屏336ms、翻页339ms。图片显示第2页/共200人次/每页50与Q1等计分叶；诊断表宽7605、wrap宽1146且overflow-x:auto，根1440，表宽由内部滚动容纳。这是单次受控本机样本，不代表所有硬件或恒定性能保证。

总控r7工程check已报告108文件1069tests、typecheck/lint/build exit0；本验收者没有重复运行这些根资源。

## V00-FINAL v1：全量E2E收口核验

已独立读取保全的`browser-full-r7/results.json`与`logs/root-e2e-full-r7.txt`。该次运行开始于2026-10-02T06:10:46.811Z，JSON duration为361326.657ms；原始日志末尾实际为`153 passed (6.0m)`，总控执行exit0。逐层枚举得到153个test、153个实际result，全部status=passed、expectedStatus=passed；统计为expected153、unexpected0、flaky0、skipped0，没有失败、重试通过或未执行项。

全量结果中的`assessments.spec.ts`四条与`question-bank-real.spec.ts`两条均为passed、retry0、errorCount0：空态/错误恢复/键盘/reduced-motion/390、五步成绩链、名单→富原卷→未知成绩回执重放→修正历史完整链、200×100规模、AI补题→独立人工校对→确认→知识点检索，以及公共retry。**这6条已包含在153条之内；独立105条组件探针、前次6条窄跑与最终153条分别记证据，不把重复运行计数相加。**

收口后验时间2026-10-02T06:19:49.7435536Z，对`FROZEN-CANDIDATE-r7.json`全168项逐文件计算磁盘SHA-256：checked168、driftCount0、differences[]。实际统计、六条用例明细与最终散列后验已写入归属摘要`V00-FRONTEND-probes/browser-reviewed-r7.json`的`fullRegression`和`finalHashAudit`；首败日志、快照与各候选历史结果保持原样。

全量E2E证明该冻结候选的既有浏览器回归门禁通过；旧模块用例含受控边界及UI回归，**不据此宣称每个旧模块均完成真实API业务验收**。本批真实6条链的业务HTTP、重放与图片证据按前节限定取证。本验收者未亲自执行根全量命令或浏览器操作，完成只读核验后停止写入。
