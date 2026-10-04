# F10-GUARD v1 实现结果

- 状态：`ready_for_review`，2026-10-02；实现者完成自检后停止题库、名单及 fixture/spec 写入。
- 负责人：`/root/question_frontend`。
- 范围：草稿与正式题目编辑写入的迟到响应、校对批次操作及冲突读回保护；草稿富内容预览；organizer 首次 queued 观察窗口。

## 精确修改文件

1. `apps/web/src/features/question-bank/DraftEditor.tsx`。
2. `apps/web/src/features/question-bank/QuestionDetailPanel.tsx`。
3. `apps/web/src/features/question-bank/ReviewWorkspace.tsx`。
4. `apps/web/src/features/question-bank/DraftEditor.guard.test.tsx`（新增）。
5. `apps/web/src/features/question-bank/QuestionDetailLinks.test.tsx`。
6. `apps/web/src/features/question-bank/ReviewWorkspace.test.tsx`。
7. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/F10-GUARD-RESULT.md`（新增）。
8. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/f10-guard-first-run.log`。
9. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/f10-guard-regression.log`。
10. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/f10-guard-regression-final.log`。
11. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/f10-guard-eslint.log`。

保留总控已写入的正式题目资产 loader 与 rich 预览，冲突比较预览也使用同一 loader/scope。本任务未修改共享客户端、contracts、hooks、styles、fixture/spec、权威文档、`next-env.d.ts` 或 Git。之前 F10 与 ROSTER 结果分别见 `F10-RESULT.md`、`ROSTER-RESULT.md`。

## 实现行为

- DraftEditor 以 `importId|draftId` 建立独立编辑会话。mounted、写请求代次及提交中的 ref 共同守卫保存/校对/拆分；旧成功响应不回调父级，旧失败不写错误、不启动冲突读回，finally 不清除其他会话的 busy。
- 冲突读回前后均检查有效性，并把 `isCurrent` 传给 ReviewWorkspace.reloadDraft/silentRefresh。即使冲突读取已在进行，切换草稿后也不会用旧详情覆盖父级当前批次/新草稿。
- 草稿使用单一 QuestionPreview 显示当前内容。受管图片走 `getQuestionAsset('draft', draftId, assetId, signal)`，资产 scope 为 `draftId|revision`；修订变化重新读取字节并撤销旧 object URL。
- QuestionDetailPanel 以 questionId 建立独立会话；初始读取、保存、归档删除及409读回都在 await 后核查 mounted/代次。旧保存不 onChanged，旧删除不 onChanged/onClose；冲突读取失败显示错误且保留编辑。
- ReviewWorkspace 以 importId 建立独立会话；读取/静默刷新有 mounted 与读取代次保护，merge/apply/ignore/confirm/initial organize/retry 的成功、失败与 finally 均有有效性检查。建议应用另检查 observationEpoch，原任务观察的 jobId/attempt/代次/abort 保护保留。
- organizer 初次 queued@N 观察 `[N,N+1]`，允许 claim 后 running/terminal@N+1；初次 running@N 精确观察 N。N+2 终态建议被拒绝，重试 `[N,N+1]` 规则保持。

## 组件回归

真实组件和真实业务客户端，仅 fetch 边界替身；没有 mock 组件或观察器。

- DraftEditor 12 项：save/split × 200/409 × 切换/卸载，409 读回中的切换，当前对象成功回调，rich 权威题面及真实草稿资产 URL/修订 scope。
- QuestionDetailLinks 19 项：原知识点与来源回归；新增 save/delete × 200/409 × 切换/卸载，409 读回中的对象切换。
- ReviewWorkspace 57 项：原有27项全保留；新增 queued@0→running@1→succeeded/failed@1 正确行为，queued/running 接管拒绝；merge/apply/ignore/confirm/organize × 200/409 × 切换/卸载；retry × 200/409 × 切换/卸载，retry queued@1→succeeded@2；草稿409读回不覆盖新选择。
- 最终共 88/88 通过。停止观察不取消服务端任务。

## 首败与修复

在产品守卫实现后首次运行新增正确行为回归：`f10-guard-first-run.log` 退出码1，24失败/59通过。失败均来自新增测试夹具或断言：DraftEditor 的全路径延迟 fetch 把独立知识点查询也返回了旧写入响应，资产读取统计也误计知识点查询；Review 测试 GET 请求统计遗漏默认 method；failed 状态错误码文案有多处匹配，且既有 SuggestionPanel 只为 interrupted 提供「重试整理」按钮。分别改为按真实请求路径路由、按资产路径统计、GET 缺省归一与明确失败横幅定位；没有为错误断言改变业务接口或失败状态入口。

第二次 `f10-guard-regression.log` 退出码1，82/83通过，剩余为重复错误码文案匹配；改为定位「本次 AI 整理失败」横幅后，再增加5项 retry 回归。最终88项通过。以上首败不是原产品缺陷的 pre-fix 复现证据；本次原缺口依据总控检查及源码核查记录，当前正确行为由组件回归证明。

## 命令与退出码

工作目录为仓库根目录；单测均设置 `$env:NODE_OPTIONS='--no-experimental-webstorage'`。

| 日志 | 命令 | 结果 |
| --- | --- | --- |
| `f10-guard-first-run.log` | `npm.cmd run test:unit -- apps/web/src/features/question-bank/DraftEditor.guard.test.tsx apps/web/src/features/question-bank/QuestionDetailLinks.test.tsx apps/web/src/features/question-bank/ReviewWorkspace.test.tsx` | 退出码1；24失败/59通过 |
| `f10-guard-regression.log` | 同上 | 退出码1；1失败/82通过 |
| `f10-guard-regression-final.log` | 同上 | 退出码0；88通过 |
| `f10-guard-eslint.log` | `npx.cmd eslint apps/web/src/features/question-bank/DraftEditor.tsx apps/web/src/features/question-bank/QuestionDetailPanel.tsx apps/web/src/features/question-bank/ReviewWorkspace.tsx apps/web/src/features/question-bank/DraftEditor.guard.test.tsx apps/web/src/features/question-bank/QuestionDetailLinks.test.tsx apps/web/src/features/question-bank/ReviewWorkspace.test.tsx --max-warnings=0` | 退出码0；零警告 |

## 真实 retry 浏览器证据交接

未改已交总控的 `tests/fixtures/teaching_loop_backend.py` 与 `tests/e2e/question-bank-real.spec.ts`。只读检查时，总控已有 `failures_remaining` 与受控 Provider 首败路径，可直接验证生成首次失败→公共 retry→attempt2 成功，观察真实 model call 数量从1到2，并确认失败轮未产生候选/正式题；无需本实现者再修改 fixture。真实浏览器证据与最终整合由总控执行。

## not_run

- 未执行全量 unit/typecheck/lint/check/build/e2e；由总控串行完成及独立V00核查。
- 未启动端口、服务器或浏览器；未执行真实 API/UI 业务验收。
- 未执行 Git 操作、推送、部署、真实凭证读取或外部消息。

`ready_for_review` 表示实现者自检完成，不能等同于独立验收已通过。
