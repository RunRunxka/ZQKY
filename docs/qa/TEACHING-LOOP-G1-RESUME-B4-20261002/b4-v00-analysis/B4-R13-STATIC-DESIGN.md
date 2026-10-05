# B4-R13 题库受限 query 导航 · 修复前独立设计审阅

只读快照 2026-10-02T15:30:52.254437+00:00。结论：CTRL拟定方案可覆盖现有导航缺口；尚未审修复差异或执行红测，**本卡不是修复验收**。

当前server只验证返回练习ID，Workspace固定imports起步并只在mount读hash；Library也仅以初始prop初始化Modal。只修改URL或初始prop，无法覆盖同一已挂载库切换generation。

拟实施边界：

- **NAV-01** Thin server route validates exactly imports|library|generation; use existing repeated/blank/trim/length guards then exact enum. Explicit invalid/duplicate tab is an address error, not silent legacy fallback. No module-top window access. 依据：apps/web/src/app/question-bank/page.tsx:7, apps/web/src/services/page-parameters.ts:7。
- **NAV-02** A valid query takes priority even if conflicting legacy fragment exists. Only query absence enables exact legacy #library/#generation at entry and genuine hashchange; do not accept malformed #library#library as a new supported form. 依据：apps/web/src/features/question-bank/QuestionBankWorkspace.tsx:48。
- **NAV-03** generation selects the existing library tab and opens its Modal; keep two real tabs and correct aria-selected/aria-controls/tabpanel. Every imports/library intent must clear generationRequested, including legacy #library, avoiding sticky reopen after imports→library. 依据：apps/web/src/features/question-bank/QuestionBankWorkspace.tsx:23, apps/web/src/features/question-bank/QuestionBankWorkspace.tsx:100, apps/web/src/features/question-bank/QuestionLibrary.tsx:259。
- **NAV-04** React to requestedTab in the same mounted instance. React to initialGenerationOpen true/false in Library, preserving draft/applied filters, offset and library state; do not remount the whole Workspace/library with a navigation key as the fix. 依据：apps/web/src/features/question-bank/QuestionLibrary.tsx:74, apps/web/src/features/question-bank/QuestionLibrary.tsx:79。
- **NAV-05** Library close changes local generationOpen; unchanged true entry prop must not reopen it on unrelated render. This is an entry intent, so refreshing query generation may open it again. A future false→true navigation or the explicit AI button opens it; keep effect dependencies narrow and do not POST or invoke a model merely on navigation. 依据：apps/web/src/features/question-bank/QuestionLibrary.tsx:101, apps/web/src/features/question-bank/QuestionLibrary.tsx:260, apps/web/src/features/question-bank/QuestionBankWorkspace.test.tsx:375。
- **NAV-06** Manual tab applies local selection immediately, clears generation intent, and pushes canonical local query URL with no legacy fragment. Preserve returnPracticeSetId by encoding exactly once; avoid an effect that pushes URL again after every prop update. Legacy listener must clean up on query change/unmount and must not feed query navigation back into hash navigation. 依据：apps/web/src/features/question-bank/QuestionBankWorkspace.tsx:36, apps/web/src/features/question-bank/QuestionBankWorkspace.tsx:81。
- **NAV-07** Confirmed return must use canonical tab=library and preserve both no-context and special-character return IDs. Existing candidate→review and uploaded→review links already encode return IDs; keep them and the final /practices?practiceSetId= link intact. Do not decode and concatenate raw /,+,?,&,# into router URLs. 依据：apps/web/src/features/question-bank/QuestionBankWorkspace.tsx:58, apps/web/src/features/question-bank/QuestionBankWorkspace.tsx:131, apps/web/src/features/question-bank/QuestionLibrary.tsx:270, apps/web/src/features/question-bank/ReviewWorkspace.tsx:848, apps/web/src/features/question-bank/ReviewWorkspace.test.tsx:513。
- **NAV-08** Keep generation human-triggered, existing six-state jobs, frozen request/unknown replay, import confirmation and backend ownership unchanged; this UI navigation fix requires fresh source/build/actual browser binding and cannot claim earlier r13 FE/build all-byte unchanged. 依据：apps/web/src/features/question-bank/ReviewWorkspace.tsx:543, apps/web/src/features/question-bank/QuestionBankWorkspace.test.tsx:387。
- **NAV-09** Read-only extra context observation: Review header /question-bank link and existing ImportBatchList row links currently omit returnPracticeSetId. They are outside the confirmed candidate→review→library core return already encoded; report scope explicitly if root elects to repair them, without quietly expanding this navigation patch. 依据：apps/web/src/features/question-bank/ReviewWorkspace.tsx:596, apps/web/src/features/question-bank/ImportBatchList.tsx:48。

明确导航期望：

| query tab | fragment | 所选页签 | 补题面板 |
| --- | --- | --- | --- |
| imports | #generation | imports | 关闭/不自动执行模型 |
| library | #generation | library | 关闭/不自动执行模型 |
| generation | #library | library | 打开 |
| 缺省 | #library | library | 关闭/不自动执行模型 |
| 缺省 | #generation | library | 打开 |
| 缺省 | 无 | imports | 关闭/不自动执行模型 |
| invalid/empty/repeated | #generation | 地址错误 | 关闭/不自动执行模型 |

CTRL已明确采用：requestedTab prop + [requestedTab] effect；query合法优先；无query才响应首次或真正hashchange。Library以[initialGenerationOpen]同步true/false，不key重挂载；关闭后同一不变prop不会反复重开。手动tab立即本地更新并push清除hash的canonical query，generation=false。非法或重复tab明确报错。需特别让legacy #library也清generation状态，并清理listener，避免重复注册/URL反馈循环。

保留原断言与新增红测：

- apps/web/src/features/question-bank/QuestionBankWorkspace.test.tsx:250,375,387：保留Current click-to-library/filter/API and manual AI panel plus zero POST assertions；新增/适配Initial query choices, query/hash conflicts, same-instance library→generation, close/unrelated render not reopen, generation→library false, manual tab canonical URL and encoded context; history/hash change only absent query.。
- apps/web/src/features/question-bank/ReviewWorkspace.test.tsx:513,527：保留Both undefined and practice /+? fixtures, actual confirm action, exact encoded return identity；新增/适配Canonical query library target while retaining strict context and confirmation checks; only obsolete URL syntax is adapted.。
- tests/e2e/question-bank-real.spec.ts:230,315,316,320,325,367：保留Legacy #library direct entry, actual confirm result/failures/one question, returned aria-selected=true and actual KP-filtered HTTP question search, retry model call counts；新增/适配No fallback click or looser selected-tab assertion; run unchanged actual chain after fix.。
- docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-v00-browser/real-browser.spec.ts:152,154：保留Original B4 business assertions and actual return identity；新增/适配Existing fallback button after invisible panel is not proof of automatic generation entry; separate R13 red test must assert query generation panel visible directly and zero model POST, including an already-mounted library.。

returnPracticeSetId应在已有candidate→review→确认library→返回练习完整链每处编码一次。额外读到Review顶部返回题库及历史ImportBatchList行链接目前不带返回ID；这是具体当前路径边界，是否补修由CTRL明确scope，不能以本卡顺手扩大写入。

所有结论来自实际代码和现有测试文字；本卡未执行业务、测试/collect、服务、浏览器、Git或保护历史重hash，仅新增本MD和JSON后停写。

收口时CTRL已写入并冻结r16：JSON中的reviewedInitialSHA256绑定本卡初读的四个修前原件，后来的sha256是收口时元数据读取，四项已不同；本卡尚未阅读/验收这些修后差异，不将其称为保护漂移或修复通过。另行R16静态卡负责修后审阅。
