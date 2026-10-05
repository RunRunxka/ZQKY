# B6 完整 check 两轮首败独立只读诊断 v1

责任人 `g3_boundary_review`，2026-10-04。状态：**测试等待语义缺口已确认；完整 check 仍 FAILED／待新轮门禁，STOP**。诊断对应两轮旧QA完整check及适配前的只读源码快照；随后qa3适配的独立差分另见新签核leaf。本卡使用 node_repl 的 readFile 与 SHA 运算只读原件，没有执行 shell 命令、测试、服务、产品导入，也没有改产品或原测试。

## 原事实与来源

候选 `CANDIDATE-B6-R01-r2.json` SHA `5eb04bd73a5e1ccc9b1f2e2294c240da8cfb9f523a756d54598b5d9a5b91c6d7`；942 source。此前 G3 frozen SHA `1ef1756283abc1fda103c2263c3a49034c5d3ffec4f06669c0735488134efcbb`；941 source。

| ROOT 原运行 | PID／时长 | 完整结果 | 唯一失败 |
| --- | --- | --- | --- |
| b6-check-r01-r2-first | 23004／97601.115ms | 121文件／1285单测通过，1文件／1例失败；exit1 | 旧 local flush discard，lesson-workspace.test.tsx108:641，同步getByRole找不到可访问放弃按钮 |
| b6-local-flush-first-diagnostic | 26172／11088.591ms | 原整文件96/96；exit0 | 无；原文件SHA未变 |
| b6-check-r01-r2-second | 21976／98102.674ms | 121文件／1285单测通过，1文件／1例失败；exit1 | 旧 local flush retry，108:1454，最后同步queryByRole absence仍看到open dialog |

两完整 check 的 typecheck／lint已完成，unit失败后 `&& build`未执行，不能称完整 check 或新 build 通过。两轮 changedSources／changedQA 均空，next-env均按原字节恢复。单文件96通过是独立诊断，不能与两完整首败拼成绿。

原日志 SHA：first `eaccd927782ba59a11633e8204264b16958de825e0a74194948a8144864017cc`；second `bc1aa9d6d574f67b58774b494549061fdbfd4eb9b3d9ba235f46cf7a8edaac14`；diagnostic `385806fb3b3e91b16e9560cb169acf95aac2e15c22104951bd805a5a32599e45`，实际读取与各收据一致。原首败保持。

## 确定的等待缺口

`lesson-workspace.test.tsx`第107～108行同组四决策的顺序为：明确本地失败 → `await screen.findByText(/保存失败，当前教案保持：受控本地写入失败/)` → 检查导航未发生、正文、原缓存和保存次数 → **同步** `getByRole`找动作 → 非cancel分支等待router.push并检查完整保存／缓存／原包 → **同步** `queryByRole(dialog).not.toBeInTheDocument()`。

本地真实组件机制：

- `LeaveProtection.tsx`第25～36行在异步flush失败后设置error／open；第38行的 `finish` 先解决导航Promise，再排队setOpen(false)。第40行以 **useEffect** 调 `dialog.showModal()`／`close()`，第43行dialog始终渲染在DOM，第45行错误文本位于dialog内部。错误文本出现不等于open属性已经写入；router.push被观察到也不等于close在DOM中的最终效果已经完成。
- 第39行测试polyfill的showModal／close仅写入／移除`open`属性。installed jsdom default-stylesheet明确`dialog:not([open]) { display:none }`。
- installed `@testing-library/dom` 的text.js使用querySelectorAll和文本匹配，没有可访问性过滤；findByText只是waitFor该文本getter。role.js默认hidden=false并过滤isInaccessible；role-helpers检查节点及祖先display:none／hidden／aria-hidden。这两种查询等待的条件不同。
- React Testing Library当前asyncWrapper会等待0ms timer以排空microtasks，因此不能简单声称“findByText从不等待任何调度”；它仍没有保证该dialog的showModal／close effect已形成可访问DOM状态。

这确认了旧测试在打开和关闭两端未等待其真正要断言的 **可访问角色状态**。禁止改成hidden:true来让隐藏按钮可点击，也不能删除原正文／缓存／写次数／导航断言。

## 两轮原因的证据强度

**首轮明确观察到**：栈108:641定位到动作getByRole；之前的findByText及正文／缓存／次数断言已执行，没有在那些断言失败；accessible roles中没有目标按钮。日志的prettyDOM被截断，未包含完整dialog，也没有dialog.open／showModal时间戳。

**首轮合理推断**：错误已渲染而showModal的最终可访问状态尚未形成，可以直接解释findByText已返回但getByRole失败，且是静态可实现的顺序。不能把该轮具体dialog.open=false或effect调度顺序冒称已捕捉事实，不能因此写“环境失败已证实”。

**第二轮明确观察到**：错误原件完整打印`<dialog class="modal lesson-leave-dialog" open="">`，动作与旧错误仍在；失败发生在最终absence断言。原执行已越过router.push恰好1次、repository.save恰好2次、第二原包等于第一次、缓存更新断言。这证明“导航观察通过”与“对话框关闭完成”是不同等待条件。

**第二轮推断边界**：结合finish／effect实现，close的最终DOM效果在该断言点尚未完成；日志没有区分setOpen(false)的React commit与passiveeffect close的具体时刻，也没有采到随后何时关闭。当前不能仅凭静态审查宣称某种系统负载、Node版本或React内部调度是唯一外因。

原同文件96例独立诊断通过支持可在另一运行条件下完成，不证明两完整首败可忽略，也不能据此判永久产品故障或确定环境根因。

## 本次 SourcePanel 影响判断

失败case由`leaveLocalHost(repository)`进入普通local模式，没有后台documentId，也没有展开来源details／点击刷新来源。`SourcePanel`的details默认闭合，metadata load入口为明确展开的onToggle或刷新按钮；当前case没有这两项操作。其挂载effect只登记alive；local模式discardGeneration为0且seenDiscard为0，discard effect不触发输入重置。B6新增metadata owner／pendingReport等逻辑在此case没有来源读取入口，未发现它改变local writer或LeaveProtection的直接调用路径。

旧test、LeaveProtection、useDraftPersistence、autosave、DocumentGateway、EditorContext、ServerControls、tests/setup与vitest.config当前SHA均精确等于G3冻结。唯一相关B6产品差异为SourcePanel，当前SHA`bb4399c57492ea1a7b96ded0dc79a9f1aab5e648417ea2618fd83aa1aad1d9c8`，与B6候选相同；旧test SHA`1f869cc95d897b344d22786755022f87754e6e2e2d239a358094671d8d8d74ef`未改。

因此目前证据指向旧测试等待条件不足，**没有静态证据将该local failure归因于本次来源读取修复**。不能据此排除执行顺序、负载或未记录的运行条件带来的间接时序影响；本卡没有跑新的反例或环境诊断。

## 最小建议（未实施）

只改同组两个等待边界，原四决策、原所有业务断言与默认可访问性语义全部保留：

```tsx
// 保留原findByText以及全部正文／缓存／次数断言。
fireEvent.click(await screen.findByRole('button', {
  name: names[decision as keyof typeof names],
}));
// 原各分支导航、正文、缓存、保存次数与原包对照保持原样。
await waitFor(() => expect(screen.queryByRole('dialog', {
  name: '离开当前教案',
})).not.toBeInTheDocument());
```

也可在同步getByRole之前增加`await screen.findByRole('dialog', {name:'离开当前教案'})`；二者选择一个即可。使用默认等待预算，不添加任意sleep、不加hidden:true、不延长超时、不减少用例或放宽原业务预期。这里最后absence仍指不可访问的关闭dialog，因为产品dialog节点本来持续挂载；不改为要求物理节点删除。

ROOT仍需冻结实际QA增量、保留两轮首败和原整文件，再跑相关原整文件与一次新的完整check；新轮失败继续定位，不重复拼绿。本报告为只读分类与建议，不作门禁PASS。

**STOP：未实施建议；产品、旧测试和旧QA均只读。**
