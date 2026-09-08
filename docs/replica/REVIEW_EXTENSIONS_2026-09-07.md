# 扩展目录联动与工具过程面板审查

审查日期：2026-09-07。目标：`H:\备份xuexi\智启课源`。只读参考：`F:\DeepTutor`，本轮核对 HEAD 为 `42fab3cf429a1fbf36b257ab8d116a3814964202`。

## 结论

**主流程基本成立，但本阶段尚未完全达标。** 现有 93 项单测、26 项浏览器测试、类型检查、Lint 和构建在本轮独立复跑均通过；新增审查探针发现了原测试未覆盖的 5 个问题。应先修复 R5–R9，再进入追问交互阶段。编号承接前次审查 R1–R4，避免混淆。

本轮只新增审查报告和 `_work/review-extensions-20260907/` 内的独立探针，未修业务实现、未提交 Git、未修改参考仓库。目标源码多数未被 Git 跟踪，不能靠 Git diff 证明所有历史改动边界；以下结论针对当前源码及实际复现。

## 可以保留的实现

- `ChatServiceEvent` 已改为判别式联合；工具调用必需字段明确。
- 发送与重试会深拷贝扩展快照；重试读取原消息快照，真实 SSE 适配器不转发 `extensions`。
- MCP 模拟调用与 Skill 模拟上下文记录有区分；错误为明确的 `MOCK_TOOL_ERROR`，不存在真实失败自动回退模拟的设计。
- 工具按 callId 原地更新；终态保护、取消及断流收尾、含过程记录的失败尝试保留逻辑成立。
- 目录读取与订阅复用现有服务，没有建立另一套扩展目录。
- 先前的固定模式单仓储、Provider 卸载清理与轮次终态守卫仍在；相关既有回归通过。

## R5 · P2：重新选择历史会话会恢复出无人执行的 running 状态

位置：[store.ts:499](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:499)，对照初始化中的 [store.ts:453](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:453)。

触发步骤：仓储中存在异常中断留下的 `streaming` 消息及 `running` 工具 → 初始化恢复 → 新建/切换会话 → 从历史重新选择原会话。

`init()` 将消息和工具转成 `stopped/cancelled`，但只更新内存。`selectConversation()` 又直接用 `repo.load()` 的原值覆盖内存，没有执行相同的恢复归一化。独立探针实际得到 `streaming/running`，服务调用次数仍为 0。界面将一直显示运行中，也无法按正常停止状态重试。

修复要求：统一所有历史载入路径的恢复语义，包括初始化、再次选择及非最近会话；保留 revision 和原消息内容，不覆盖其他标签页更新。不要为了收尾直接清空历史或关闭冲突检测。

证据：`_work/review-extensions-20260907/recovery.test.ts`，`unit-results.json`。

## R6 · P2：手机多扩展工具栏溢出并把说明文字挤成竖排

位置：[ChatWorkspace.tsx:434](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:434)、[chat.css:297](H:/备份xuexi/智启课源/apps/web/src/features/chat/styles/chat.css:297)、[chat.css:1017](H:/备份xuexi/智启课源/apps/web/src/features/chat/styles/chat.css:1017)。

触发步骤：390×844 → 模拟模式 → 选中一个 MCP 和一个 Skill → 发送并等待结束。

新增选择器、不可换行的 chips、模式说明和发送按钮放在同一条不换行的 flex 工具栏。浏览器实测：模式说明仅宽 33px、高 206px；输入框右边界为 350px，发送按钮右边界为 389.66px；输入框左边界为 -16px。截图可见左侧内容裁切、说明文字竖排、发送按钮跑到输入框外。对方提交的手机截图也已呈现同样问题。

修复要求：为已选扩展设置可换行或独立的布局区域，保证输入、发送/停止和移除操作可见可达；覆盖零、一、多扩展和长名称。不能仅加 `overflow:hidden` 把问题藏起来。

证据：`interaction.spec.ts` 的 390px 场景；`browser-results.json` 的 `mobile-evidence`。

![390px 实际布局](H:/备份xuexi/智启课源/_work/review-extensions-20260907/browser-output-v2/interaction-390px-选择-MCP-和-Skill-后，发送按钮仍应在输入框范围内/mobile-extensions-review.png)

## R7 · P2：收起的详情仍可获得键盘焦点

位置：[ToolProcessPanel.tsx:58](H:/备份xuexi/智启课源/apps/web/src/features/chat/ToolProcessPanel.tsx:58)、[chat.css:847](H:/备份xuexi/智启课源/apps/web/src/features/chat/styles/chat.css:847)。

详情始终挂载，仅通过 grid 行高和 opacity 折叠，没有把内部交互元素移出焦点顺序和可访问树。由于详情复用 Markdown，链接、代码复制按钮等依然可交互。

实际复现：发送带 Markdown 链接的问题；模拟 MCP 的详情包含该链接；卡片保持收起，聚焦标题后按一次 Tab。焦点进入透明度为 0 的详情链接（`https://example.com/review`，未访问此地址）。键盘用户看不到当前焦点，且可误激活隐藏内容。

修复要求：收起时使用合适的 inert/可访问性处理或动画结束后隐藏内容，并处理收起时焦点仍在详情内的情形；保留退出动画和快速开关的正确性。单独添加 aria-hidden 不能阻止 Tab 进入。

证据：`interaction.spec.ts` 的折叠详情场景；`browser-results.json` 的 `keyboard-evidence`（`hiddenDetailHasFocus=true`，`opacity=0`）。

## R8 · P2：弹出层没有退出动画，过程展开的缓动与原版不符

位置：[ExtensionPicker.tsx:88](H:/备份xuexi/智启课源/apps/web/src/features/chat/ExtensionPicker.tsx:88)、[chat.css:923](H:/备份xuexi/智启课源/apps/web/src/features/chat/styles/chat.css:923)、[chat.css:851](H:/备份xuexi/智启课源/apps/web/src/features/chat/styles/chat.css:851)、[motion.css:5](H:/备份xuexi/智启课源/apps/web/src/styles/motion.css:5)。

选择器只有入场 `chat-ext-pop`，关闭时 `{open && ...}` 直接移除 DOM。浏览器测得入场时长 0.16s，但关闭后的第一个绘制帧节点已经断开，因此没有退出过程。这与登记为复刻依据的原版输入区弹出层不一致：原版 [ChatComposer.tsx:1077](F:/DeepTutor/web/components/chat/home/ChatComposer.tsx:1077) 使用 AnimatePresence，定义了入场、退出、位移和缩放，以及 0.16s 缓动。

另外，原版 [TracePresentation.tsx:1843](F:/DeepTutor/web/features/chat/trace/TracePresentation.tsx:1843) 使用 Tailwind 的 `duration-300 ease-out`；参考配置没有覆盖其缓动，Tailwind 3 的 out 为 `cubic-bezier(0,0,0.2,1)`。目标却统一使用 `--ease-out: cubic-bezier(0.16,1,0.3,1)`，这是输入区弹出层/宽度变化使用的另一组参数。不能仅凭同为 300ms 就写“与原版一致”。

修复要求：根据实际对应组件补完整进入/退出状态，保留原版有意不同的缓动；支持快速连续开关和减少动画。更新动画清单，提供起始、过渡、结束与中断的动态证据。未录制或未查看的视频仍应标为未验证。

证据：`interaction.spec.ts` 的退出场景；`browser-results.json` 的 `exit-evidence`；以上目标与参考源码。

## R9 · P3：已打开菜单可以绕过“发送中禁用”

位置：[ExtensionPicker.tsx:56](H:/备份xuexi/智启课源/apps/web/src/features/chat/ExtensionPicker.tsx:56)、[ExtensionPicker.tsx:81](H:/备份xuexi/智启课源/apps/web/src/features/chat/ExtensionPicker.tsx:81)。

`disabled` 只传给触发按钮，选项按钮没有禁用，也没有在生成开始时关闭已打开的菜单。

实际键盘路径：先输入问题 → 打开扩展菜单 → 从搜索框按两次 Shift+Tab 回到问题输入框 → Enter 发送。因为没有 pointerdown，菜单仍然打开；触发器已经 disabled，但选项仍 enabled，组件探针证实仍会调用 onToggle。这与交接里“发送中扩展选择入口禁用”的描述不一致。

本轮快照仍然冻结，不会被这次点击改写，因此该问题优先级低于 R5–R8；但待发送选择和进行中轮次的表现会产生混淆。

修复要求：发送开始时关闭或锁定整个选择器，交互处理同步加保护，焦点落在可操作位置。若有意支持编辑下一轮，则需明确下一轮语义并统一其他 chips 的行为，不能半禁用。

证据：`picker-disabled.test.tsx`；`interaction.spec.ts` 键盘发送场景；`browser-results.json` 的 `disabled-evidence`。

## 实际检查及其边界

| 检查 | 本轮结果 |
| --- | --- |
| `npm.cmd run typecheck` | 通过 |
| `npm.cmd run lint` | 通过，0 警告 |
| `npm.cmd run test:unit` | 93 项通过 |
| `npm.cmd run build` | 通过 |
| `npm.cmd run test:e2e -- --output=_work/review-extensions-20260907-baseline --trace off --reporter=line` | 26 项通过 |
| 独立单元探针 | 2 项按预期行为断言失败，复现 R5、R9 |
| 独立浏览器探针 | 4 项按预期行为断言失败，复现 R6、R7、R8、R9 |
| 390px 截图人工查看 | 发现并确认布局问题 |
| 1920px 全面视觉验收、完整动画录像 | 本轮未执行；不认为已完成 |
| 真实供应商/真实 MCP/Skills | 未调用、未验证；符合当前阶段模拟边界 |
| 后端 `test:api` | 本轮未复跑，本轮未修改后端 |

独立探针不会加入默认正式测试集；它们的失败表示预期行为未满足，不是原有 93/26 项测试失败。初次独立 JSX 探针配置缺少 automatic runtime，已修正后重跑；上表统计为修正后的行为断言结果。基础浏览器测试中真实后端未启动产生的 model-catalog 连接错误属于预期边界，26 项仍通过。独立浏览器探针拦截该目录请求，没有真实模型访问。

复现命令，从目标项目根运行：

```powershell
npx.cmd vitest run --config _work/review-extensions-20260907/vitest.config.ts --reporter=verbose
npx.cmd playwright test --config _work/review-extensions-20260907/playwright.config.ts --output=_work/review-extensions-20260907/browser-output-fixcheck-01
```

每次浏览器验证更换独立产物目录；无需删除以前的截图。不要更改探针预期来消除失败，应把修正后的真实用户场景迁移进正式测试。

原测试的主要缺口：历史恢复只断言 init 后的状态；手机测试只限制菜单宽度，没有断言发送后工具栏边界；没有验证隐藏详情的 Tab 顺序、已打开菜单在发送中的禁用、退出动画和实际缓动。93/26 项全部通过与这些问题并不矛盾。

## 可以直接交给下一个工具的修复提示词

```text
目标项目：H:\备份xuexi\智启课源。
只读参考：F:\DeepTutor，提交 42fab3cf429a1fbf36b257ab8d116a3814964202。

先读根与 apps/web 的 AGENTS.md、当前 DECISIONS/TASKS/HANDOFF，以及
docs/replica/REVIEW_EXTENSIONS_2026-09-07.md。
本轮只修复这份报告中的 R5–R9，不进入追问或产物新功能。

1. 所有历史加载入口共享正确的中断恢复语义；初始化后再次选择会话不恢复出无人执行的 streaming/running。保留 revision、消息、扩展快照和工具历史，不清库。
2. 修复 390×844 下零、一、多扩展及长名称的输入区布局。已选扩展可以合理换行或独立成区，发送/停止、移除按钮始终可见可达；不要用裁切隐藏溢出。
3. 折叠详情内的链接、复制按钮等不能获得不可见焦点；展开/收起时处理焦点与可访问树，同时保留动画和快速开关能力。
4. 按参考组件补扩展菜单退出动画，区分过程展开和弹出层的缓动参数。验证点击外部、Escape、快速开关、减少动画；录制并查看动态证据，未完成就明确记录。
5. 生成开始时关闭或禁用已打开的整个扩展菜单。覆盖“搜索框 Shift+Tab 两次回输入框后 Enter 发送”路径，不只给触发按钮加 disabled。

先运行 _work/review-extensions-20260907 的独立探针复现，再实现修复；把有意义的场景迁入正式测试，不削弱断言。继续保持 R1–R4 的卸载清理、模式单仓储、终态守卫与测试依赖注入语义。

保留当前技术栈、锁文件、真实 SSE、教案、模型管理和本地数据；不接真实 MCP/Skills，不调用付费供应商，不自动提交或推送，不修改参考仓库。
运行 typecheck、lint、test:unit、build 和相关/全量浏览器回归。验证 390×844、1440×900、1920×1080；每次浏览器测试使用新的独立产物目录。
更新本审查报告的修复记录、replica HANDOFF、MOTION_MATRIX 和相关状态文档。最终逐条报告 R5–R9 的代码依据、实际命令、截图/动态证据及未验证项，不以构建通过替代视觉与交互验收。
```

## 修复记录（2026-09-07 下午，用户指定“仅修复 R5–R9”）

修复前先复现：`npx vitest run --config _work/review-extensions-20260907/vitest.config.ts` 2 项失败（R5/R9）；`npx playwright test --config _work/review-extensions-20260907/playwright.config.ts --output=…browser-output-repro-01` 4 项失败（R6/R7/R8/R9）。修复后两套探针全部通过（复现命令同报告；产物目录 `browser-output-fixcheck-01/02/03`）。

- **R5 已修复**：`store.ts` 新增 `normalizeLoaded()`——统一初始化与 `selectConversation()` 的历史载入恢复语义（标注模式、streaming→stopped(disconnected)、running 工具→cancelled），保留 revision、消息内容、扩展快照与工具历史，恢复不重放（服务调用 0 次）。探针场景迁入 `extensions-snapshot.test.ts`“R5：恢复后再次选择历史会话…”。
- **R6 已修复**：`ChatWorkspace.tsx` 输入区重排——已选扩展与选择入口移入独立 `.chat-ext-row`（flex-wrap 可换行，位于输入框与工具行之间，DOM 序保持 Shift+Tab 两步回输入框）；chips 长名称省略（`.chat-ext-chip-name` max-width 150px + title 完整名）+ 移除按钮可见；`.chat-mode-chip` nowrap 不再竖排；发送/停止按钮 `flex-shrink:0` 常驻工具行。无任何容器 overflow 裁切。正式测试 `chat-mock.spec.ts`“R6：390px 多扩展与长名称…”断言 composer.left≥0、send.right≤composer.right+1、说明高度<30（不竖排）、移除按钮可见，含 390px 截图；“R6：1920×1080…”含截图。
- **R7 已修复**：`ToolProcessPanel.tsx` 详情容器改为 `inert={!open}`——收起时移出焦点顺序与可访问树（Tab 不再进入隐藏链接/复制按钮）；收起时若焦点在详情内先移回头部按钮再折叠；展开时详情可进入、再次收起焦点回头部。保留 300ms 退出动画与快速开关（动画由 CSS 承担，inert 只管交互/可访问树）。正式测试 `chat-mock.spec.ts`“R7：收起详情 Tab 不进入隐藏内容…”（折叠/展开/收起三段焦点证据）。
- **R8 已修复**：`ExtensionPicker.tsx` 改为 mounted/open 两态——关闭时面板保持挂载并播放 `chat-ext-pop-out`（对照原版 AnimatePresence：进场 y6/scale.96→1，退场 y4/scale→.97，160ms cubic-bezier(.16,1,.3,1)，transformOrigin bottom left），动画结束再卸载；退场期间 inert，快速开关时取消未完成的卸载定时器、动画正确重启。缓动区分：motion.css 新增 `--ease-standard: cubic-bezier(0,0,0.2,1)`（原版 TracePresentation 的 Tailwind duration-300 ease-out），`.chat-tool-detail`/`.chat-tool-chevron` 改用它；弹出层继续用 `--ease-out`(0.16,1,0.3,1)。动态证据：`chat-motion.spec.ts`（video:'on' 录像 `tests/.e2e-output-20260907-r12/…/video.webm`，已生成）+ Web Animations API 定格中间帧截图 `motion-2-exit-40ms.png`（半透明淡出）、`motion-3-exit-120ms.png`（接近消失）、`motion-4-detail-mid.png`（详情半展开）——以上帧均已人工查看；`chat-mock.spec.ts`“R8：菜单进出场动画与缓动参数…”断言进场/退场动画名、0.16s、两组缓动数值、退场首帧仍挂载且 inert、中断重开与快速开合终态正确。减少动画沿用 motion.css 全局机制（既有用例覆盖）。
- **R9 已修复**：`ExtensionPicker.tsx` 选项按钮随 `disabled` 禁用；`disabled` 变化时自动关闭已打开菜单（程序化关闭不抢焦点，焦点保持在输入区等可操作位置）；退场期间面板 inert 不可操作。探针键盘路径（搜索框 Shift+Tab×2 → 输入框 → Enter 发送）迁入正式测试 `chat-mock.spec.ts`“R9：键盘从打开的菜单返回输入框发送…”；组件探针场景迁入 `ExtensionPicker.test.tsx`“R9：进入发送状态时…”。

期间发现并修正一个布局回归：扩展行初版放在工具行之后，破坏了 Shift+Tab 两步回输入框的探针路径——已改为输入框与工具行之间（DOM 序与视觉一致），探针与正式测试均通过。

### 修复实际验证（全部实际执行）

- `npm run typecheck` 通过；`npm run lint` 通过（0 警告）；`npm run test:unit` 95 项通过（上一基线 93，+2 为迁移的 R5/R9 场景）；`npm run build` 通过。
- `npm run test:e2e`：32 项通过（上一基线 26，+6：R6 390px、R6 1920px、R7、R8、R9、动画录像），产物目录 `tests/.e2e-output-20260907-r5/` 与录像目录 `…-r12/`（每轮新目录，历史产物未删）。390×844、1440×900（既有全量用例默认视口）、1920×1080 均有断言与截图。
- 独立探针（修复后）：单元 2/2、浏览器 4/4 通过（`browser-output-fixcheck-03`）。
- 动态证据已查看：`motion-2-exit-40ms.png`、`motion-3-exit-120ms.png`、`motion-4-detail-mid.png`、`mobile-extensions-390.png`、`extensions-1920.png`、`ext-exit-mid.png`；录像 `video.webm` 已生成（webm 需播放器人工回看，逐帧验证以定格截图为准）。
- 未验证项：真实供应商与真实 MCP/Skills（本轮仍为本地模拟，符合边界）；`test:api` 未复跑（后端零改动）；录屏未包含教案与设置页（范围外）。
- 工具链记录：为生成录像安装了 Playwright 自带 ffmpeg 辅助二进制（`npx playwright install ffmpeg`，写入用户 ms-playwright 缓存，未改动项目依赖与锁文件）。

## 独立复核：R5–R9 修复后（2026-09-07，最新）

**结论：原 R5–R9 的独立探针现已全部通过，但本阶段还有一处新回归 R10，以及录像测试退出超时的验证限制，不能把当前状态记为全部验收完成。** 本次只新增审查探针与提示词、追加复核记录，没有修改业务代码或参考仓库，没有提交 Git。

### 逐项复核

| 项目 | 本轮独立结果 |
| --- | --- |
| R5 再次选择历史 | `normalizeLoaded()` 被 init 和 selectConversation 共用；原单元探针通过，恢复后不重放 |
| R6 手机多扩展布局 | 扩展独立换行、长名称省略，原浏览器探针及正式 390/1920 用例通过；已查看手机与 1920 截图 |
| R7 折叠详情焦点 | inert 及焦点回头部实现存在；原探针与正式展开/收起测试通过 |
| R8 退出动画和缓动 | 两组缓动已区分，退出动画和重开保护已实现；原探针通过，已查看 40ms/120ms/详情展开定格图；外部点击关闭新增 R10 回归 |
| R9 发送时锁定菜单 | disabled 时自动关闭、选项禁用；原单元及浏览器探针通过 |

### R10 · P2：菜单打开时未注册外部点击监听

位置：[ExtensionPicker.tsx:77](H:/备份xuexi/智启课源/apps/web/src/features/chat/ExtensionPicker.tsx:77)。

当前 effect 的开头是 `if (!mounted || open) return;`。菜单打开时 open=true，恰好跳过监听注册；关闭时才注册，而 `closePanel()` 又会因为 open=false 直接返回。因此点击外部永远不能关闭菜单。该问题是本次 mounted/open 双状态改造带来的回归，旧版本打开时会注册 pointerdown。

独立浏览器复现：打开模拟扩展菜单 → 等待搜索框获得焦点 → 点击外部“输入问题”文本框 → 等待 300ms。结果：输入框获得焦点，但菜单仍挂载，触发器 aria-expanded 仍为 true。新探针以预期关闭状态断言失败；原有 4 项浏览器探针没有覆盖此入口，仍全部通过。

建议最小修复：仅在 mounted 且 open 时注册监听，关闭/卸载时移除；保留内部点击、Escape、发送开始关闭、快速重开的现有正确行为。外部点击关闭时不要把焦点从用户刚点击的输入框抢回触发器。补正式回归，不需重做动画架构。

复现文件：[outside-click.spec.ts](H:/备份xuexi/智启课源/_work/review-r5-r9-20260907/outside-click.spec.ts)。证据 JSON 中 `panelStillConnected=true`、`expanded=true`、`focusedLabel=输入问题`。

```powershell
# 从 H:\备份xuexi\智启课源 运行；每次使用新的产物目录
npx.cmd playwright test --config _work/review-r5-r9-20260907/playwright.config.ts --output=_work/review-r5-r9-20260907/fixcheck-01
```

### 本轮实际验证与录像限制

- `npm.cmd run typecheck`、`npm.cmd run lint`（0 警告）、`npm.cmd run test:unit`（95 项）、`npm.cmd run build`：全部通过。
- 原独立探针：2/2 单元、4/4 浏览器通过；浏览器产物 `_work/review-r5-r9-20260907/original-probes/`。
- 全量 E2E：**31/32 通过**，唯一失败为 `chat-motion.spec.ts` 在关闭 context 时超时，错误为 `Tearing down "context" exceeded the test timeout of 45000ms.`。随后仅运行同一录像测试，仍为同样的 teardown 超时。测试体没有报告业务断言失败；这不足以证明前端动画功能故障，但也不能写本轮 32/32 通过。
- 全量日志：[baseline-e2e.log](H:/备份xuexi/智启课源/_work/review-r5-r9-20260907/baseline-e2e.log)。独立录像复跑日志：[motion-retry.log](H:/备份xuexi/智启课源/_work/review-r5-r9-20260907/motion-retry.log)。两轮使用不同输出目录，旧产物保留。
- 新增 R10 探针 1 项失败，属于真实产品行为回归，与录像 teardown 问题不同。
- 已查看原交付手机截图、当前 1920 截图，以及原交付的退出/展开定格图；已确认原 `video.webm` 存在。本轮没有完整播放 WebM，截图检查不应写成连续录像播放验收。
- 真实供应商、真实 MCP/Skills 与后端 test:api 未运行；本轮未修改业务后端。参考 Git HEAD 再次核对为约定提交，工作区无变更。

### R10 修复记录（2026-09-07 傍晚，追问阶段前置）

- 修复：`ExtensionPicker.tsx` 外部点击 effect 条件由 `if (!mounted || open) return` 修正为 `if (!mounted || !open) return`——菜单打开时注册 pointerdown 监听，关闭/卸载时移除；外部点击走 `closePanel(false)`，不把焦点从用户点击的位置抢回触发器；内部点击、Escape、发送开始自动关闭、快速重开行为不变。
- 复现与验证：修复前 `_work/review-r5-r9-20260907/outside-click.spec.ts` 按预期失败（repro-r10-01）；修复后该探针通过（fixcheck-r10-01），原 R5–R9 探针 2/2 单元、4/4 浏览器复跑通过（browser-output-r10check）。
- 正式回归：`ExtensionPicker.test.tsx`"R10：菜单打开时内部点击不关闭，外部点击关闭且不抢焦点"；e2e `chat-mock.spec.ts`"R10：扩展菜单打开时点击外部，应关闭且焦点留在输入框"（断言内部选择不关闭、外部点击后退场卸载、aria-expanded false、焦点留在输入框）。

### 下一阶段提示词的重要修正

旧 HANDOFF 中“提交后以新轮次继续”的提示不符合原版普通 ask_user。参考 [ask_user.py:1](F:/DeepTutor/deeptutor/tools/ask_user.py:1)、[ChatStateAdapter.tsx:2415](F:/DeepTutor/web/features/chat/ChatStateAdapter.tsx:2415) 和 [pipeline.py:1136](F:/DeepTutor/deeptutor/agents/loop/pipeline.py:1136) 明确使用当前 turn 的等待器及 submit_user_reply，然后继续当前轮。

本轮应按“先最小修复 R10 → 追问卡片与同轮续答”的范围继续。完整可复制提示词已写入 [NEXT_PHASE_ASK_USER.md](H:/备份xuexi/智启课源/docs/replica/NEXT_PHASE_ASK_USER.md)，包含预览、单选/多选、自由文本、跳过、提交确认与失败、同轮多卡、取消、失效历史和测试边界；本轮不实现产物工作区及其他复杂能力。
