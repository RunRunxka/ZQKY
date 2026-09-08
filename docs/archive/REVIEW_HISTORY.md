# 历史合并归档：REVIEW_HISTORY.md

归档日期：2026-09-08。以下为过去记录原文，含已作废目标、旧状态与旧提示词，**不是当前执行指令**。当前目标见 [项目说明](../PROJECT_GUIDE.md)，当前进度见 [STATUS](../STATUS.md)。

原文件字节哈希见 [MANIFEST.json](MANIFEST.json)，保留原文内容、换行按仓库规范转为 LF；旧相对链接按原文件所在目录理解。完整原路径版本可从 Git 基线 b8cf71f 查看。

<a id="source-1"></a>

## 原文件：docs/replica/REVIEW_2026-09-07.md

<!-- BEGIN ORIGINAL docs/replica/REVIEW_2026-09-07.md -->
# 统一聊天服务阶段代码审查

审查日期：2026-09-07。参考仓库提交已核对为 42fab3cf429a1fbf36b257ab8d116a3814964202。
目标仓库没有可用的已跟踪变更基线，本次审查当前实现，不声称所有问题均由本阶段新增。
本次未修复业务源码，仅添加本报告和 `_work/review-chat` 下独立复现测试。

## 结论

真实 SSE 复用、显式模拟入口、独立数据库与共用消息组件的方向合理，但不能直接验收为生命周期及隔离全部可靠。先修复下面问题再扩展工具过程。

### R1 [P1] 组件卸载未取消生成

`apps/web/src/features/chat/ChatWorkspace.tsx:81-84` 清理函数只移除监听，不调用两个 store 的 dispose。Next 客户端导航/浏览器返回导致卸载时不一定触发 pagehide，也不一定经过侧栏的 beforeNavigate。实测卸载后请求 signal.aborted 仍为 false，旧流会继续运行及写历史。为 provider/store 建立唯一、幂等的卸载清理责任；兼容 React StrictMode 的 setup-cleanup-setup。

### R2 [P2] 固定模式 store 仍读取两个数据库

`apps/web/src/features/chat/model/store.ts:378-395` 顺序加载真实和模拟数据库，混入同一 docs Map。
实测：真实库 list 挂起会使模拟 store 永远无法 ready；两个数据库内同 ID 的会话会因 docs.has 而跳过模拟记录，模拟列表为空；模拟初始化实际调用了真实仓储。
每个固定模式 store 应仅实例化/加载/读写自己的仓储。由 ChatProvider 持有两个实例即可，不需要每个实例再包含两套数据。

### R3 [P2] 终态后的过程事件仍能修改消息

`apps/web/src/features/chat/model/store.ts:232-240` 的 process/stage/usage 缺少终态守卫。收到 end 后、service.run Promise 尚未结束时，generation 仍匹配，后续 stage 可以改写完成消息。实测完成消息被追加 stageLabel。
明确本轮 terminal 状态；end/error/cancel 后禁止阶段和过程更新。若有末尾用量事件需求，须单独定义接收规则，不连带放行过程事件。

### R4 [P2] 隔离测试断言未检查实际依赖

`mock-mode.test.ts:38-50` 创建的 realRepo 没有注入被测 store；断言它为空无法证明真实库未写。
`mock-mode.test.ts:60-69` 的 calls 属于另一个 mockStore，未关联正在执行的真实 store；断言它为空不能证明没有回退。
必须将 spy 仓储/服务注入被测实例，再检查对应调用。保留真正已有数据并验证内容不变。

## 本次实际验证

- `npm run typecheck` 通过。
- `npm run test:unit` 68 项通过。
- `npx vitest run --config _work/review-chat/vitest.config.ts`：5 项预期行为断言失败，分别复现 R1/R2/R3。独立配置不混入正常测试目录。
- 本轮未重跑 build、Lint、后端测试或全量浏览器测试；原报告中的这些通过记录属于上一轮。
- 真实供应商未验证。

## 下一轮 A：仅修复审查问题

先读本报告、交接文件、相关源码和局部规范。完成 R1-R4，不重写聊天 UI，不接真实 MCP，不升级依赖。
把独立复现迁移成正常回归测试，验证 StrictMode、卸载中止、迟到事件、数据库初始化互不依赖、同 ID 跨模式隔离、终态守卫和真实服务失败不自动切模拟。
事件类型宜改为以 type 为判别字段的联合类型，保证 text.delta、tool.call 等必要字段不能缺失。调整测试适配类型，不虚称已有去重能力。
完成相关类型、Lint、单测、构建和浏览器检查，更新实际验收结果；修复完成再进入下一轮。

## 下一轮 B：扩展目录联动与工具过程

1. 聊天模拟模式订阅 extension-catalog，展示已启用的 MCP/Skills；真实模式继续明确未接入，不能调用外部工具。
2. 在发送时冻结本轮选择快照。设置变化影响下一轮，不追溯修改进行中或历史请求。重试沿用原请求快照；想采用新配置需重新发送。
3. MCP 模拟工具调用；Skills 展示为加载的技能上下文，不自动把每个 Skill 冒充远程工具调用。
4. 消息内工具卡按 callId 更新，覆盖 running/done/error/cancelled，重复更新不产生重复卡片。取消/终态不留“运行中”状态。
5. 模拟脚本覆盖无扩展、单扩展、多扩展、一次失败、取消；过程持久化，刷新显示历史而不重新执行。
6. 对照原版 trace 展开动画；使用已登记的 300ms 参数及减少动画机制，不在每次正文增量重播卡片动画。
7. 验证设置启停到聊天同步、请求快照、重试快照、取消和迟到事件、历史恢复、真实模式零外部调用。提供桌面/手机截图及真实执行记录。
8. 追问、产物工作区和其他页面留待独立阶段，避免扩大范围。

## 修复记录（2026-09-07，用户指定“下一轮 A：仅修复审查问题”）

R1–R4 已全部修复并验证。本报告正文保留原始审查结论，以下为修复后状态：

- **R1 已修复**：`ChatContext.tsx` 的 ChatProvider 承担唯一卸载清理责任——effect cleanup 中对两个 store 调用幂等 `dispose()`（取消生成 + 冲正保存），客户端路由卸载与浏览器返回不再依赖 pagehide 或侧栏 beforeNavigate；`ChatWorkspace.tsx` 中原重复 effect 已移除（保留 beforeNavigate 的导航前保存）。dispose 幂等且不销毁 store，兼容 React StrictMode 的 setup-cleanup-setup。
- **R2 已修复**：`store.ts` 改为固定模式 store 只实例化/加载/读写自己的仓储。`ChatDeps` 移除 `mockRepository` 双仓储注入，仅保留 `repository`（mock 模式默认库仍为 `zhiqikeyuan-chat-mock`，真实库 `zhiqikeyuan-chat` 不变，历史数据兼容）。真实库挂起不再阻塞模拟 store 就绪；两库同 ID 会话不再因共用 docs Map 互相吞没。
- **R3 已修复**：generation token 增加 `terminal` 标志。收到 end/error、取消（stop）、断流收尾后，本轮拒绝一切 stage/process/usage/text/reasoning 事件，完成消息不再被追加 stageLabel。当前真实与模拟服务均在 end 前发出 usage，“末尾用量事件”需求未出现；如未来需要，须单独定义接收规则，不连带放行过程事件。
- **R4 已修复**：隔离测试改为向被测 store 注入 spy 仓储/服务后断言对应调用与数据不变（含“真实仓储已有数据内容不变”）。原复现用例已迁移为正式回归：`mock-mode.test.ts`（11 项，含卸载保存、dispose 幂等）与 `ChatWorkspace.unmount.test.tsx`（2 项，普通 + StrictMode 卸载取消）；新增初始化互不阻塞、跨模式同 ID、终态（end/error/取消）迟到事件、真实失败不自动回退模拟等用例。`_work/review-chat` 独立探针按修复后语义改写（4 项）后独立复跑通过。

“下一轮 A”中“事件类型改为 type 判别式联合”一条未在本次实施（用户指定本次只完成 R1–R4），事件仍为宽接口（type 联合 + 可选字段），留待下一轮与工具过程事件一起改造，不虚称已具备去重能力。

### 修复实际验证（全部实际执行）

- `npm run typecheck` 通过；`npm run lint` 通过（0 警告）。
- `npm run test:unit`：77 项通过（上一基线 68；新增卸载取消、卸载保存、dispose 幂等、初始化互不阻塞、跨模式同 ID、end/error/取消三类迟到事件、卸载后可用等回归）。
- `npm run test:api`：84 项通过（后端未改动，回归确认）。
- `npm run build` 通过。
- `npm run test:e2e`：22 项通过（上一基线 21；新增“生成中浏览器返回离开页面，回来后生成已取消且内容冻结”浏览器回归）。本次因沙箱批量删除守卫拦截旧 `test-results/` 清理，以 `--output=tests/.e2e-output-20260907` 运行（该目录已加入 .gitignore），未删除任何既有产物。
- `_work/review-chat` 独立探针：`npx vitest run --config _work/review-chat/vitest.config.ts` 4 项通过。
- 真实供应商仍未验证（本轮不涉及真实模型调用；无可用进程凭证）。

<!-- END ORIGINAL docs/replica/REVIEW_2026-09-07.md -->

<a id="source-2"></a>

## 原文件：docs/replica/REVIEW_EXTENSIONS_2026-09-07.md

<!-- BEGIN ORIGINAL docs/replica/REVIEW_EXTENSIONS_2026-09-07.md -->
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

<!-- END ORIGINAL docs/replica/REVIEW_EXTENSIONS_2026-09-07.md -->

<a id="source-3"></a>

## 原文件：docs/replica/REVIEW_ASK_USER_2026-09-07.md

<!-- BEGIN ORIGINAL docs/replica/REVIEW_ASK_USER_2026-09-07.md -->
# R10 与追问同轮续答：独立代码复核

日期：2026-09-07。目标：`H:\备份xuexi\智启课源`。参考：`F:\DeepTutor`，本次核实 HEAD 为 `42fab3cf429a1fbf36b257ab8d116a3814964202`，参考工作区干净。

## 结论

**R10 修复通过；追问同轮续答的正常演示路径成立，但本阶段尚未达到完整验收标准。** 107 项现有单测通过，并不覆盖下列遗漏。新增独立探针在当前代码上复现了 7 项单元/组件问题和 1 项浏览器问题，归纳为 R11–R16 六组修改要求。没有修改产品代码。

本报告审查当前工作区文件，而非可追溯的提交差异；目标大量文件仍未跟踪，不能据此宣称历史上其他模块从未被修改。

## 本次实际检查

| 检查 | 本次结果 | 边界 |
| --- | --- | --- |
| `npm.cmd run typecheck` | 通过 | 当前源码 |
| `npm.cmd run lint` | 通过，0 警告 | 当前配置范围 |
| `npm.cmd run test:unit` | 107/107 通过 | 项目已有用例 |
| `npm.cmd run build` | 通过 | 不等于视觉验收 |
| 旧独立 Vitest 探针 | 2/2 通过 | `_work/review-extensions-20260907/vitest.config.ts` |
| 全量 E2E | **37/38 通过** | 录像测试 context teardown 超过 45000ms；未据此认定业务断言失败 |
| 新独立 Vitest 探针 | **7/7 复现不符合验收的行为** | 最终日志 `probes-final.log` |
| 新独立浏览器探针 | **1/1 复现复制遗漏** | 已通过真实界面完成两卡续答再点击复制 |
| 视觉抽查 | 查看 390×844 长自由文本草稿截图，提交按钮可达 | 不是全部长题干、全部状态或 1920px 视觉验收 |
| 真实供应商 / 真实 MCP、Skills | 未调用 | 不把本地模拟当成真实验证 |
| API 测试 / 完整 WebM 播放 | 本次未执行 | 没有扩大到后端实现或完整动态验收 |

R10 的打开时监听、外部点击不回抢焦点，在源码、组件回归和本次全量 E2E 对应场景中均通过。

## R11 · P2 · 异步提交与旧轮次收尾缺少身份守卫

代码：[store.ts:283](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:283)、[store.ts:560](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:560)。

两个独立复现：

1. 进入等待，提交回答但延迟服务确认，点击停止；卡片先变为 `interrupted`。此后返回 `accepted: true`，当前实现把旧卡改成 `answered`，提交返回 `true`。
2. 停止旧轮并开始新轮，新轮已收到 `new-ask`；旧服务此时才返回。旧 `run` 的 `finally` 无条件清空 `waitingInteractionId/submittingReply`，新追问失去有效入口。

事件 emitter 有 token 守卫，但 `await submitReply` 后的成功、拒绝、异常、finally 和 `run finally` 未统一受保护。`markReplyFailed` 还使用完成时的 `get().activeId`，而非发起时会话身份。

要求：以发起时的会话、轮次、助手消息、interaction、submission 身份绑定结果；异步返回只能修改仍由它拥有的状态。取消/切换/新轮后不得覆写旧终态、当前卡或新提交锁。提交接受与续答发事件之间也要定义顺序，避免简单补守卫后把正常同步续答误判为失效。补 delayed ACK、delayed reject、服务忽略 abort、切会话和新提交并发用例。

## R12 · P2 · 新增续答结构未接入上下文、复制及重试保留逻辑

代码：[store.ts:214](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:214)、[context-budget.ts:14](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/context-budget.ts:14)、[ChatWorkspace.tsx:403](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:403)、[store.ts:802](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:802)。

`asks[].followUp` 承载卡片后的正文，但原消费方仍只认 `message.content`：

- 下一轮上下文只有“先确认偏好”，没有已确认回答和最终解释。继续问“展开刚才的例子”时，服务看不到此前实际对话。
- 浏览器实测两卡续答完成后点击“复制回答”，剪贴板只有“【模拟回复】收到你的问题……先确认两件事”，未包含可见续答。
- 直接从追问开始、尚无正文/工具记录的尝试，中断后重试会把旧助手消息删除，连同追问和草稿一起丢失；独立探针已复现。

要求：建立统一、按时间顺序的消息投影；展示、可复制正文、服务上下文、预算计算、备份及重试保留应有明确一致的策略。已确认回答进入上下文，未确认草稿不能冒充已提交答案；不用机械地把界面所有装饰文字拼进模型。旧纯 content 历史兼容、不重复正文，含 ask/产物等有效记录的失败尝试保留并正确排除已取代尝试的请求上下文。

## R13 · P2 · 非空预览无法补全成完整问题

代码：[store.ts:202](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:202)、[AskUserCard.tsx:134](H:/备份xuexi/智启课源/apps/web/src/features/chat/AskUserCard.tsx:134)。

复现：同 id 先收到包含一道未完成题目的 preview，再收到两道完整问题的 waiting。实际仍只有最初一道未完成题目；`intro` 也被第一段固定。现有测试使用相同 preview/waiting 题目，未覆盖真实的逐步补全。

此外目标 preview 只显示“正在准备追问”，已有问题与选项也不展示；参考 [AskUserOptions.tsx:1063](F:/DeepTutor/web/components/chat/home/AskUserOptions.tsx:1063) 会显示只读的已有题目，无题目时才显示骨架。

要求：按稳定 questionId 接收权威题目更新，保留用户草稿与合法选择；明确 preview→waiting 的完整性边界，不让迟到 preview 退回已可回答状态。补 intro-only、部分题目/选项、完整 waiting、已编辑草稿后重复事件等场景。

## R14 · P2 · 已回答卡的重复 waiting 会抢走后续卡

代码：[store.ts:456](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:456)。

复现：回答 first → 收到 second → 再收到 first 的重复 waiting。first 虽保持 answered，但全局 `waitingInteractionId` 被改回 first，second 不能继续正常提交。

要求：活动卡依据经过身份验证和合法状态迁移后的结果确定，不能仅因原始事件标记 waiting 就设置活动 id。已回答/已中断卡不能重新取得等待权；重复、过期、逆序事件不重开卡，不覆盖当前等待。

## R15 · P2 · 单选与自由文本仅单向互斥

代码：[AskUserCard.tsx:78](H:/备份xuexi/智启课源/apps/web/src/features/chat/AskUserCard.tsx:78)。

复现：单选题允许自由输入，先填写文本，再选择选项 A 并提交。实际同时提交 `labels: ['选项A']` 和之前自由文本。参考 [AskUserOptions.tsx:959](F:/DeepTutor/web/components/chat/home/AskUserOptions.tsx:959) 选中单选项会取消自定义回答选中态。

要求：两方向均互斥。可以保留未激活的自由输入草稿供切回，但序列化答案必须只提交当前有效分支。多选题按参考允许选择和补充文本共存。补两种操作顺序的组件与浏览器用例。

## R16 · P2 · 追问卡新增了原版没有的进场动画

代码：[chat.css:1101](H:/备份xuexi/智启课源/apps/web/src/features/chat/styles/chat.css:1101)、[chat-mock.spec.ts:504](H:/备份xuexi/智启课源/tests/e2e/chat-mock.spec.ts:504)。

当前追问卡套用弹出菜单的 160ms `chat-ext-pop`，E2E 还断言它必须存在。参考 AskUserOptions 的该卡片没有这项装饰进场；本地 MOTION_MATRIX 也明确记录了这个差异。这违背本阶段提示词“原版没有动画的位置不额外添加装饰效果”。

要求：移除这项偏离，保留源码实际存在的选择/按钮反馈、骨架与提交状态；按来源校正测试和动画矩阵。不能通过把不匹配实现写进断言来证明复刻完成。其余卡片结构（多题标签、自定义选项、只读摘要等）仍需逐项完成，而不是将子集直接写成全量复刻。

## 验证设施尚未闭环

`chat-motion.spec.ts` 本次再次出现 `Tearing down "context" exceeded the test timeout of 45000ms`，日志在 `e2e.log:555`。现有证据只能确认此症状复现，不能断言根因一定是 ffmpeg、环境负载或应用代码。业务检查与录像产物收尾分开报告，诊断后再验收稳定性；不能删测试、降低断言或挑选通过的复跑覆盖原失败记录。

## 独立复现与证据

探针均使用注入服务、内存仓储或隔离浏览器，不调用真实供应商，也不改真实用户数据库。

```powershell
# 在 H:\备份xuexi\智启课源 执行
npx.cmd vitest run --config _work/review-ask-user-20260907/vitest.config.ts
npx.cmd playwright test --config _work/review-ask-user-20260907/playwright.config.ts --output=_work/review-ask-user-20260907/NEW-UNIQUE-OUTPUT
```

- [单元/组件探针](H:/备份xuexi/智启课源/_work/review-ask-user-20260907/ask-boundaries.test.tsx)
- [最终探针日志](H:/备份xuexi/智启课源/_work/review-ask-user-20260907/probes-final.log)
- [复制回答浏览器探针](H:/备份xuexi/智启课源/_work/review-ask-user-20260907/copy-reply.spec.ts)
- [复制遗漏日志](H:/备份xuexi/智启课源/_work/review-ask-user-20260907/browser-2.log)
- [全量 E2E 日志](H:/备份xuexi/智启课源/_work/review-ask-user-20260907/e2e.log)
- [390px 长草稿截图](H:/备份xuexi/智启课源/_work/review-ask-user-20260907/browser-output-2/copy-reply-Copy-answer-mus-3b964-visible-same-turn-follow-up/ask-mobile-long-draft.png)

初版浏览器探针对多题提交按钮用了单题名称，因此曾在定位器阶段失败；更正为界面实际“提交回答”后，最终在剪贴板内容断言处复现上述产品问题。初版与最终日志分开保留，最终结论使用 `browser-2.log`。

## 后续

执行 [完整剩余任务提示词](H:/备份xuexi/智启课源/docs/replica/FINAL_REPLICA_EXECUTION_PROMPT.md)。先修 R11–R16 并完成针对性回归，再推进全部剩余前端工作。最终区分页面、交互、动画、模拟验证、真实服务验证五项完成状态。

## 修复记录（2026-09-07 晚，S0：R11–R16）

修复前复现：独立单元探针 7/7 失败；修复后 7/7 通过。浏览器复制探针修复后通过（fixcheck-01）。全部改动未削弱探针断言。

- **R11 已修复**（`store.ts`）：提交发起时冻结身份（sessionId/turnId/ownerToken/interactionId/submissionId，并登记 `activeSubmissionId`）；确认返回后按"未中止、未被新轮顶替、同会话、提交身份一致"判定归属——中止（停止/取消）或被新轮顶替后迟到确认返回 `false` 且不改写 interrupted 历史；`markReplyFailed` 写入发起时会话而非完成时的 activeId；`run` 的 finally 仅在 `generation === token`（本轮仍活跃）时释放 waiting/submitting，不清掉新轮身份；catch 路径同样受归属约束。**事件顺序定义**：确认（accept）→ 续答/收尾事件 → 提交返回值——合法同步续答可能在确认返回前推进到下一张卡甚至 end，归属判定不因此误拒（探针 old-run-finally 与 formal 测试覆盖）。`submissionId` 实际用于归属判定与服务侧单次消费，不再只是声明。
- **R12 已修复**（`context-budget.ts` + `ChatWorkspace.tsx` + `store.ts`）：新增 `conversationProjection()` 统一投影——正文 + 已确认追问回答（"问题：回答"行）+ 逐卡续写，按时间顺序；`selectMessagesForRequest` 对含追问的消息先投影再预算（服务上下文与预算一致）；复制回答改用同一投影（包含可见续答与已确认回答，不含未提交草稿）；重试保留条件加入 `asks`（仅有追问交流、无正文的失败尝试不再被删除）。旧纯 content 历史原样返回。
- **R13 已修复**（`store.ts` upsertAsk + `AskUserCard.tsx`）：新 wait-user 事件为权威数据，按稳定 questionId 整体更新题目与引言（部分预览可被完整 waiting 补全），已填草稿保留；`preview` 不把 `waiting` 降级；卡片预览态按原版呈现已有题目（只读、禁用），无题目才显示骨架。
- **R14 已修复**（`store.ts`）：wait-user 处理先 upsert 再按**更新后的卡片状态**决定活动卡——只有合法迁移到 waiting 的卡才取得 `waitingInteractionId`；已回答/提交中/中断的卡被重复事件命中时不抢走当前等待。
- **R15 已修复**（`AskUserCard.tsx`）：单选双向互斥——选中选项清空自由文本（此前只单向），序列化只提交当前有效分支（单选：有选项则不带文本；多选：选项与文本共存）；组件探针场景迁入正式测试。
- **R16 已修复**（`chat.css` + e2e + MOTION_MATRIX）：移除原版不存在的追问卡 160ms 进场动画；e2e 断言改为 `animationName === 'none'` 防回归；动画矩阵同步修正。
- **探针场景迁移**：7 项单元/组件场景全部迁入 `ask-user.test.ts`"审查 R11–R16 回归"describe（断言不弱化，另补投影/草稿保留细节）；浏览器复制场景保留 `copy-reply.spec.ts` 探针并通过。
- **录像 teardown 诊断（S0 要求项）**：`chat-motion.spec.ts` 连续 3 次独立复跑（4.4–4.8s/次，产物 `tests/.e2e-output-20260907-teardown-1..3`）均正常收尾，未复现 `Tearing down "context"` 超时；录像 webm 正常产出。应用行为、录制关闭与产物完整性三方面均无异常证据，**根因未知**——疑似与复核时环境负载相关，保持独立文件隔离，持续观察；不以"环境问题"销项，也不据单次通过宣称稳定。

### S0 实际验证

- `npm run typecheck` 通过；`npm run lint` 通过（0 警告）；`npm run test:unit` **114 项**通过（107 → 114，+7 为探针迁移）；`npm run build` 通过。
- 独立探针：单元 7/7、浏览器 1/1 通过。
- `npm run test:e2e`：**38/38** 通过（产物 `tests/.e2e-output-20260907-s0`）。
- 真实供应商/真实 MCP、Skills：未调用（模拟边界）。

<!-- END ORIGINAL docs/replica/REVIEW_ASK_USER_2026-09-07.md -->

<a id="source-4"></a>

## 原文件：docs/replica/REVIEW_S0_S2_2026-09-07.md

<!-- BEGIN ORIGINAL docs/replica/REVIEW_S0_S2_2026-09-07.md -->
# S0 修复、S1 矩阵与 S2 深链：独立续审

日期：2026-09-07。目标 `H:\备份xuexi\智启课源`；参考 `F:\DeepTutor`，本轮再次确认提交为 `42fab3cf429a1fbf36b257ab8d116a3814964202`，参考工作区干净。

## 结论

**既有修复有实质进展，但“S0 全部完成、S1 全部完成、深链已验收”仍不成立。** 原 7 项独立单元/组件探针与原复制浏览器探针全部通过；本轮在相邻边界上复现 3 项单元问题和 3 项浏览器问题。应在当前实现上补齐，修复后直接继续 S2–S8，不重做已通过的部分，也不再次把修复批次当成整个项目的终点。

本轮只新增审查探针与文档，未修改产品代码、依赖、真实数据或参考仓库，未提交 Git。目标仍有大量未跟踪文件，审查针对当前工作区，不能以提交 diff 证明历史修改范围。

## 优先处理的代码问题

### R17 · P2 · 深链把会话锁死在初始 URL

位置：[ChatWorkspace.tsx:109](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:109)，相关用户操作见 [ChatWorkspace.tsx:204](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:204)。

effect 依赖整个 `store`、会话列表和 `activeId`；只要当前 id 与 `initialSessionId` 不同，就再次选择 URL 中的旧会话。新建和列表切换只修改 store，没有同步改变 URL 的目标。

独立浏览器复现：

- 在 `/chat/alpha` 点击“新建对话”，最终仍显示 `answer-alpha`，没有停留在新会话。
- 在 `/chat/alpha` 点击打开 beta，最终又显示 `answer-alpha`，无法停留在 beta。

现有 2 项深链测试只证明首次直达与无效 id 提示，未覆盖进入后操作。要求：确定路由与活动会话的统一规则，明确区分 URL 导航和用户主动新建/切换；刷新、前进后退、删除当前会话也保持一致。不可简单删掉依赖掩盖旧闭包问题。路由切换时继续遵守草稿保存、运行取消和真实/模拟模式隔离。

### R11 补充 · P2 · 错误/断流后迟到确认仍会改写中断卡

位置：[store.ts:309](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:309)。

复现：开始提交 → 服务发 error 或无 end 返回形成断流 → 卡片已为 interrupted → 最后提交 Promise 返回 `accepted: true`。两种情况当前都返回 true，并将卡改成 answered。

原因：`generation === null` 一律被当成“未被顶替”，且正常结束、错误、断流没有在接受判定中区分。注释中的“确认→续答→返回值”没有让所有消费方获得可核实的确认事实，不能据此把任何迟到 accepted 都当成已经合法确认。

要求：显式区分已确认后合法同步续答与未确认就失效的等待。可以使用带身份的接受事件/记录或有同等约束的服务句柄；以可测试的事件顺序和所有权判定实现，不只补注释或更换布尔条件。保留当前正常两卡同步续答的测试，同时补 error/断流/取消/换轮后的 delayed ACK、reject 与 finally。已经确认的回答也不能因正常收尾丢失。

### R13 补充 · P2 · 迟到 preview 保留了 waiting 状态，却替换了完整题目

位置：[store.ts:214](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:214)。

复现：先收到两题完整 waiting，填写第二题，再收到同 id 的旧 partial preview。状态仍是 waiting，但问题列表退回只有一题“半题”，选项清空，第二题不再参与当前提交。当前逻辑只保护 status，没有保护已经确认完整的数据。

要求：waiting/failed 之后的过期 preview 不得覆写完整题目、选项或引言。预览阶段允许补全，开放作答后的数据变更需有明确合法规则；草稿按稳定 questionId 保留。新增回归须同时断言状态、问题、选项、引言与提交答案，而不仅断言 status。

### R12 补充 · P2 · 纯追问续答消息仍没有复制按钮

位置：[Message.tsx:119](H:/备份xuexi/智启课源/apps/web/src/features/chat/Message.tsx:119)。

浏览器预置 `content: ''`、包含已答卡及 `followUp: '最终解释可以复制'` 的历史：正文可见，但“复制回答”按钮不存在。回调已改用统一投影，按钮显示条件仍检查旧的 `message.content`。

要求：操作的可用性判断与实际投影一致；有可复制回答就提供操作。保留空白占位不显示无意义复制按钮的行为。覆盖纯正文、纯追问续答、纯结果说明及旧历史；产物阶段再按其语义扩展，不重复引入只认 content 的判断。

## R18 · P2 · S1 尚未达到完整规格要求，进度统计也不一致

证据：[HANDOFF.md:10](H:/备份xuexi/智启课源/docs/replica/HANDOFF.md:10)、[PAGE_MATRIX.md:64](H:/备份xuexi/智启课源/docs/replica/PAGE_MATRIX.md:64)。

交接同时写“S1 全部完成”与“逐页组件级参考源码核对未一次性完成”。实际矩阵仍主要是路由与一句摘要，尚缺 S1 要求的组件来源、弹窗/抽屉、状态、出入路径、持久化、错误恢复及完整动画记录。因此只能标记为矩阵框架完成、规格部分完成。

直接统计现有表格：

- 除内部调试外是 **53 行**，其当前标签为 **已验收 5 / 部分实现 2 / 待实现 46**，并非 51 / 4 / 2 / 45。
- AI 表实际 **18 行**，并非 17。
- 53 行包括参考产品页、目标自有教案页和目标兼容入口。应区分产品页与重定向别名，不把别名当成等价的页面完成量。
- 上述只是文档标签统计，不代表本次认可 5 页都完成了全部验收；尤其深链条目应回到“实现待修复/部分实现”。

要求：修正状态与统计，建立可自动核对的分母和条目分类。每个实施批次先细化对应组件与状态，再实现验收；在 S1 真正完成前保持“部分完成”。允许规格细化伴随实施推进，但不能提前宣称规格齐全，也不能只改表格不继续产品实现。

README、DECISIONS 及历史交接还有默认入口和当前基线的不同陈述；将已被取代的陈述明确标记为历史，当前入口按用户已确认的决定统一，避免后续工具擅自来回修改首页。

## 本轮实际验证

| 检查 | 结果 |
| --- | --- |
| typecheck、Lint | 通过，Lint 0 警告 |
| 现有单元测试 | 114/114 通过 |
| 原独立单元/组件探针 | 7/7 通过 |
| 原复制回答浏览器探针 | 1/1 通过 |
| build | 通过，包含动态聊天路由 |
| 全量 E2E | **39/40**；chat-motion 在 context teardown 超过 45000ms |
| 本轮新增单元探针 | 3/3 复现上述 preview、error ACK、disconnect ACK 问题 |
| 本轮新增浏览器探针 | 3/3 复现新建、切会话、纯续答复制问题 |
| 真实供应商、真实 MCP/Skills、API 测试 | 本轮未执行 |

新增浏览器探针先保留 trace 运行，业务断言失败后也遇到测试收尾超时；随后用相同断言关闭 trace 在新目录复跑，三个业务失败仍复现，且没有该额外收尾超时。此操作仅用于区分业务失败与采集问题，不修改正式套件、不降低业务断言。全量录像问题仍未销项，不能据此确定根因是 trace、ffmpeg 或具体环境因素。

记录已过原探针，不等于否定这次修复；新增探针证明原探针覆盖面之外仍有遗漏。后续应按状态迁移与操作组合补回归，避免每次仅针对最后一条失败断言修补。

## 复现命令与证据

在目标根执行，输出目录每次取未使用名称：

```powershell
npx.cmd vitest run --config _work/review-s0-s2-20260907/vitest.config.ts
npx.cmd playwright test --config _work/review-s0-s2-20260907/playwright.config.ts --trace off --output=_work/review-s0-s2-20260907/NEW-UNIQUE-OUTPUT
```

- [本轮单元探针](H:/备份xuexi/智启课源/_work/review-s0-s2-20260907/residual-guards.test.ts)
- [单元失败日志](H:/备份xuexi/智启课源/_work/review-s0-s2-20260907/residual-probes.log)
- [本轮浏览器探针](H:/备份xuexi/智启课源/_work/review-s0-s2-20260907/deeplink-actions.spec.ts)
- [排除 trace 后的浏览器复现日志](H:/备份xuexi/智启课源/_work/review-s0-s2-20260907/browser-no-trace.log)
- [全量 E2E 日志](H:/备份xuexi/智启课源/_work/review-s0-s2-20260907/e2e.log)
- [原探针复跑日志](H:/备份xuexi/智启课源/_work/review-s0-s2-20260907/previous-probes.log)
- [原复制浏览器复跑日志](H:/备份xuexi/智启课源/_work/review-s0-s2-20260907/previous-copy.log)

## 修复记录（2026-09-07 晚，继续批）

修复前复现：单元 3/3、浏览器 3/3 失败；修复后全部通过（fixcheck-01），且未修改任何探针断言。

- **R17 已修复**（`ChatWorkspace.tsx`）：深链改为**一次性定位**——`deepLinkHandled` 状态守卫，仅首次就绪时按 URL 选择或标记缺失；用户新建/列表切换/删除当前会话后不再被 URL 强制回跳（浏览器探针 A/B 场景通过）；刷新与前进/后退重新挂载时按 URL 重新定位；草稿保存、运行取消与模式隔离语义未变。曾出现的 lint 依赖告警以守卫恒真说明处理（disable 注释+理由）。
- **R11 补充已修复**（`store.ts`）：generation token 增加 `endReason`（'end'/'error'/'stop'/'disconnect'，五个收尾点分别记录）；提交归属判定改为「未中止 ∧ 未被新轮顶替 ∧（轮次仍活跃 ∨ 以 end 正常完成）∧ 提交身份一致 ∧ 同会话」——error/断流后迟到的 accepted ACK 一律拒绝（interrupted 不被改写为 answered），正常两卡同步续答与已确认答案保留。迁移回归 `ask-user.test.ts`"R11 补充：error/disconnect 后迟到的 accepted 确认不得重开中断卡"。
- **R13 补充已修复**（`store.ts` upsertAsk）：`waiting/failed` 之后的过期 `preview` 不覆盖完整题目、选项或引言（仅同为 preview 时允许逐步补全）；草稿按 questionId 保留。迁移回归断言状态、题目、选项、引言与草稿四个维度。
- **R12 补充已修复**（`Message.tsx`）：复制按钮可用性改用 `conversationProjection` 判定——纯追问续答消息有正文即提供复制；空白占位不显示。浏览器探针 C 场景通过。
- **R18 已修正**：PAGE_MATRIX 统计改为 53 非调试条目（已验收 4 / 实现待验收 1 / 部分实现 2 / 待实现 46），分类标注参考产品页 50 + 目标自有 1 + 兼容别名 2；S1 标注为"框架完成、规格部分完成"；深链条目由"已验收"降级为"实现待验收"；`docs/DECISIONS.md` 默认入口行标记历史陈述并统一为现行 `/`→`/chat`。AI 表 18 行以实际条目计。

### 修复验证

typecheck 通过；lint 0 警告；正式单测（chat 目录）72 项通过（含迁移的 3 项）；独立探针 3/3 单元 + 3/3 浏览器（fixcheck-01）通过；build 通过。深链 e2e 4/4（含 2 项 R17 回归）。原 7+1 探针与既有回归未复跑失败。

## 继续执行

使用 [持续实施补充指令](H:/备份xuexi/智启课源/docs/replica/CONTINUE_TO_FINAL_2026-09-07.md)，与既有 [完整执行提示词](H:/备份xuexi/智启课源/docs/replica/FINAL_REPLICA_EXECUTION_PROMPT.md) 一起执行。先修本报告问题，再在同一任务中继续完整输入区与后续 S3–S8。修复通过是继续开发的条件，不是再次等待用户指定下一阶段的条件。

<!-- END ORIGINAL docs/replica/REVIEW_S0_S2_2026-09-07.md -->

<a id="source-5"></a>

## 原文件：docs/replica/REVIEW_DELIVERY_2026-09-07.md

<!-- BEGIN ORIGINAL docs/replica/REVIEW_DELIVERY_2026-09-07.md -->
# 当前版本的交付级别复核与新会话接续

日期：2026-09-07。审查目标为 `H:\备份xuexi\智启课源`。再次确认只读参考 `F:\DeepTutor` 为 `42fab3cf429a1fbf36b257ab8d116a3814964202`，工作区干净。

## 交付判断

**当前是可接续开发、可演示部分聊天流程的开发版本，尚未达到完整前端交付标准。** 上轮针对性修复的 3 项单元和 3 项浏览器探针均已通过，但本轮仍复现两种终态顺序错误、一项深链刷新问题；Lint 和全量 E2E 也没有全部通过。

即使修复这几个问题，仍不能将产品整体交付：S1 规格只完成框架，S2 完整输入区尚未完成，S3 产物工作区、S4 复杂能力、S5 大部分页面、S6 设置补齐、S7 视觉/动画和 S8 最终验收均有必需工作。页面表 53 个非调试条目中，仍有 46 项标记待实现；4 个“已验收”条目还包含兼容重定向，不宜用 4/53 表示产品完成度。`FINAL_ACCEPTANCE.md` 当前不存在。

已有源码和交接足以交给新会话继续，不需要重新初始化或重写总方案。代码审查无法验证另一个 AI 是否实际耗尽上下文；这里仅依据当前文件、命令结果和恢复点判断接续条件。

## 本轮实际验证

| 检查 | 实际结果 |
| --- | --- |
| 类型检查 | 通过 |
| 正式单元测试 | **117/117 通过** |
| 上轮独立单元探针 | **3/3 通过** |
| 上轮独立浏览器探针 | **3/3 通过**：新建不回跳、切换不回跳、纯续答复制按钮 |
| 构建 | 通过 |
| Lint | **失败**：1 条未使用变量警告，项目要求 0 警告 |
| 全量 E2E | **41/42 通过**；录像用例 context teardown 超时 |
| 新终态顺序探针 | **2/2 复现错误**，见下文 |
| 新深链刷新探针 | **1/1 复现错误**，见下文 |
| 真实供应商 / 真实 MCP、Skills / API 测试 | 本轮未执行 |

交接中的“预期 40/40”已过时，当前全量浏览器套件为 42 项。该数量来自实际执行，后续新增后继续据实更新，不把数字当成固定验收目标。

## P2：error 已经到达，但 run 尚未返回时仍能接受迟到 ACK

位置：[store.ts:313](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:313)。

当前 `turnAlive = generation === ownerToken` 只判断运行对象是否还保留，没有判断 `terminal` 或已收到的 `endReason`。当 error 事件已经令卡片 interrupted，而服务的 run Promise 暂时未返回时，`turnAlive` 仍为 true。此时迟到 accepted ACK 被接受，卡片重新变为 answered。

| 事件顺序 | 应有结果 | 当前结果 |
| --- | --- | --- |
| 提交 → error → run 仍挂起 → accepted ACK | 拒绝；卡保持 interrupted | 接受；卡变 answered |

上轮探针在 ACK 前先等待 run 返回，所以没有覆盖这个窗口。要求：业务终态与 Promise 生命周期明确区分；已经进入 error/stop/disconnect 的等待不因运行对象尚未释放而恢复可提交性。

## P2：正常 end 被通用收尾覆盖成 disconnect，合法确认反而丢失

位置：[store.ts:652](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:652)。

`patchStoppedIfStreaming` 只在修改消息时检查 streaming，但在此前无条件重写 `token.endReason`。正常 end 后 service.run 返回也会调用它，于是 end 被改成 disconnect。根据当前自己声明支持的“合法同步续答可在 ACK 返回前 end”契约，稍后 accepted ACK 应仍记录确认答案，但当前被拒绝。

| 事件顺序 | 应有结果 | 当前结果 |
| --- | --- | --- |
| 提交 → 正常 end → run 返回 → 合法 accepted ACK | 接受；保留 answered | 拒绝；卡保持 interrupted |

要求：明确终态只进入一次，通用断流兜底只适用于尚未收到明确终态的流，不能覆盖正常 end 或 error。把这两项与已通过的取消、断流、正常两卡续答组合成完整的状态迁移测试，避免继续只补前一条失败路径。

## P2：深链的立即回跳修复，但 URL 与当前会话仍不同步

位置：[ChatWorkspace.tsx:112](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:112)、[ChatWorkspace.tsx:241](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:241)。

浏览器实际操作：打开 `/chat/alpha` → 列表选择 beta → 正常显示 beta，说明上一轮修复有效；但地址仍是 `/chat/alpha` → 刷新后重新显示 alpha。

一次性定位守卫解决了用户操作被立即覆盖的问题，尚未实现完整深链契约。复制当前 URL、刷新及浏览器历史不能准确表达正在查看的会话。

要求：用户主动新建/切换/删除会话时同步地址或采用等价且可恢复的路由设计；URL 与活动会话之间的来源明确，避免双向更新循环。覆盖刷新、后退/前进和真实/模拟模式，保持草稿保存、正常生成和取消语义。该项继续作为 S2 未完成部分处理，不必推翻已通过的新建/切换修复。

## 工程门禁与交接准确性

- [ask-user.test.ts:666](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/ask-user.test.ts:666) 声明了未使用的 `emitWaiting`；实际 `npm.cmd run lint` 返回 1。删除该冗余声明或按需要使用，不能关闭规则掩盖。
- 录像测试再次出现 `Tearing down "context" exceeded the test timeout of 45000ms`。这是当前完整套件未通过的原因；不能据此断言动画业务一定错误，也不能把问题销项为“偶发环境因素”。采集收尾问题需单独诊断，正式业务断言和动态证据仍要保留。
- replica/HANDOFF 和页面表已经修正 S1、53 条目等信息，但根 TASKS 的旧当前摘要仍写 S1 完成、51 条目，根 HANDOFF 的“最新”部分仍是更早阶段。应让新会话有一个准确入口，旧内容明确标成历史，避免重复误判进度。

## 证据与复现

所有新增探针使用注入服务、内存仓储或独立浏览器测试数据，不访问真实模型、不修改用户会话。

```powershell
# 在 H:\备份xuexi\智启课源 执行；浏览器输出目录替换为未使用名称
npx.cmd vitest run --config _work/review-delivery-20260907/vitest.config.ts
npx.cmd playwright test --config _work/review-delivery-20260907/playwright.config.ts --output=_work/review-delivery-20260907/NEW-UNIQUE-OUTPUT
```

- [终态顺序探针](H:/备份xuexi/智启课源/_work/review-delivery-20260907/terminal-order.test.ts)
- [终态顺序失败日志](H:/备份xuexi/智启课源/_work/review-delivery-20260907/terminal-order.log)
- [深链刷新探针](H:/备份xuexi/智启课源/_work/review-delivery-20260907/route-refresh.spec.ts)
- [深链刷新日志与 URL 证据](H:/备份xuexi/智启课源/_work/review-delivery-20260907/route-refresh.log)
- [Lint 日志](H:/备份xuexi/智启课源/_work/review-delivery-20260907/lint.log)
- [全量 E2E 日志](H:/备份xuexi/智启课源/_work/review-delivery-20260907/e2e.log)
- [上轮单元探针复跑](H:/备份xuexi/智启课源/_work/review-delivery-20260907/previous-probes.log)
- [上轮浏览器探针复跑](H:/备份xuexi/智启课源/_work/review-delivery-20260907/previous-browser.log)

本轮新增探针和交接文档，并在当前交接入口加入本次独立结论；未修改产品代码、依赖、参考仓库或真实数据，未提交 Git。

## 新会话该怎样继续

选择目标项目 `H:\备份xuexi\智启课源` 作为工作目录。让新会话读取 [NEXT_SESSION_START.md](H:/备份xuexi/智启课源/docs/replica/NEXT_SESSION_START.md)，再按其引用读取完整 FINAL 任务。

执行顺序：本轮收尾问题 → 完整 S2 输入区和首次发送过渡 → S3 产物工作区 → S4–S8。每批检查通过后直接继续，不以旧探针通过或写完交接作为总任务结束条件。当前缺少真实供应商凭证不阻塞其余模拟前端实施。最终分别验收页面、交互、动画、模拟与真实服务。

<!-- END ORIGINAL docs/replica/REVIEW_DELIVERY_2026-09-07.md -->

<a id="source-6"></a>

## 原文件：docs/replica/REVIEW_S2_S3_2026-09-08.md

<!-- BEGIN ORIGINAL docs/replica/REVIEW_S2_S3_2026-09-08.md -->
# S2 / S3 进度与代码复核（2026-09-08）

结论：**有实际功能进展，可继续迭代；S2 仍需修复，S3 仅部分实现，完整前端未达到交付标准。** 本轮独立审查发现 R19–R25 共 7 项业务问题，以 7 个浏览器场景和 2 个单元场景复现。审查未修改产品代码；新增诊断探针、日志和接续文档。

审查目标：`H:\备份xuexi\智启课源`。只读参考：`F:\DeepTutor`，HEAD 实核为 `42fab3cf429a1fbf36b257ab8d116a3814964202`，参考工作区干净。目标大量文件未跟踪，不能用 Git diff 证明所有历史修改边界。本报告基于当前源码、实际运行和证据，不以实施者总结代替验证。

## 必须先修复的问题

### R20 · P1：提交契约不一致，附件被清空而没有发送；真实模式还能静默忽略附件

- [ChatWorkspace.tsx:473](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:473) 调用 `void store.send(...)` 后立即清空一次性附件和引用。
- [store.ts:828](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:828) 仍对空文本直接 return；UI 则允许只附件或只引用提交。
- 独立复现：模拟模式选择 `only.txt`，不输入文字，点击已启用的发送按钮。没有用户消息、没有执行轮次，附件卡已消失，无错误说明。丢失的是待发送状态，磁盘源文件未删除。
- [ChatWorkspace.tsx:480](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:480) 的真实路径只拦截空文本；拖入/粘贴入口仍可加入附件。输入“请分析附件”后会发出纯文字请求，附件没有传给服务，也没有就此通知用户。本轮通过拦截本地 SSE 的夹具复现，未调用真实供应商。
- 修复：统一 UI 与 store 的可提交条件。模拟的只附件/引用请求应形成明确标识的轮次；完全空请求拒绝。发送接口区分“未接纳”和“已接纳的轮次”，只有接纳成功才能清理本次消耗的选择，不能等生成结束才清理，也不能无条件清理。真实模式在添加或提交前明确处理未支持内容，保留用户输入；用户明确移除不支持内容后才能继续纯文字请求，不偷偷剥离字段。
- 验收：只文件、只引用、文字加文件、完全空请求、配置受阻、发送拒绝、等待追问、发送期间新选择、真实模式粘贴/拖入均一致；失败不吞选择，不引入真实上传。

### R19 · P2：编辑配置后确认不失效，非法配置仍可发送

- [ChatWorkspace.tsx:1141](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:1141) 和手机分支 1180 直接传 `onChange={setCapForms}`，未执行 `setCapConfirmed(false)`。
- [ChatWorkspace.tsx:295](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:295) 的门控只看 confirmed，不看 `capErrors`；因此清空已确认的出题主题后，界面同时出现红色错误和“已确认”，发送按钮仍可用。
- 独立浏览器场景先确认合法主题，再清空，预期“先确认能力配置”按钮，实际不存在。截图已查看。
- 修复：配置变更统一撤销确认；配置有效性在提交边界再核对。确认应对应当前能力及当前配置版本，不能靠旧布尔值授权新的配置。桌面、手机、键盘提交共用路径；不要只对出题输入加特例。

### R21 · P2：声明为会话级的人设与知识选择实际共享，串入新会话

- [ChatWorkspace.tsx:110](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:110) 的选择存在 ChatPage 局部状态，未按模式/会话归属；[fresh():497](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:497) 只切换 store 会话，没有切换这些选择。
- 独立复现：先建立 A，选择“耐心的小学老师”，再新建 B，确认 URL 已换为新 id，B 仍带 A 的人设引用。
- 知识选择具有同样源码结构。矩阵原已将人设选择的持久化安排在 S5，因此“尚未持久化”本身不作为新增缺陷；当前会话之间串状态是已实现交互的错误。
- 修复：为会话配置定义模式+会话归属；新会话采用明确默认，切回 A 恢复 A。若分批实现持久化，先保证当前会话隔离；最终补刷新恢复。待发送附件/引用和异步文件读取也需明确归属，不把 A 的迟到结果加入 B。
- 验收：A/B 两组不同选择、新建、再选、模式切换、目录失效、刷新；既有发送快照和重试语义不变。

### R22 · P2：打开产物后，“先确认能力配置”无法显示配置卡

- [ChatWorkspace.tsx:462](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:462) 仅 `setInfoOpen(true)`，而 [1113](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:1113) 优先显示非 null 的 artifactOpenId。
- 独立复现：打开已有产物 → 选择智能出题 → 填文字 → 点“先确认能力配置”，右侧仍是产物，配置卡没有挂载。用户要额外猜测关闭结果工作区才能继续。
- 修复：让配置请求明确激活配置视图并定位/聚焦；用明确的面板选择状态协调配置、会话信息、产物，保留需保留的结果标签。手机抽屉遵循同一选择语义，不靠两个互相遮挡的布尔值。

### R23 · P2：并发附件读取绕过总量配额

- [ChatWorkspace.tsx:323](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:323) 仅以读取完成的 attachments 计算配额，await FileReader 后才追加。
- 独立复现：控制 FileReader 延迟，两次连续加入 16MB 文本。两次都按 0 已用量校验，最终同时显示两个 16MB 卡片，超过 25MB，无错误。探针仅延迟文件读取，不改配额或业务逻辑。
- 修复：为排队/读取中的文件预留配额，或用串行接纳队列；完成时再核对会话/选择批次身份。捕获读取失败并释放额度，提供可恢复错误；发送、新建、移除及卸载后旧读取不得重新插入。
- 扩展验收：同时选取/拖入/粘贴、一个读取失败、部分不支持/超限文件、读取期间切会话和发送。不要只把容量上限改大。粘贴预过滤也必须保留 rejected 原因，不能吞掉错误反馈。

### R24 · P2：结果工作区丢失轮次身份，同 id 产物打开错误内容

- [ChatWorkspace.tsx:272](H:/备份xuexi/智启课源/apps/web/src/features/chat/ChatWorkspace.tsx:272) 将消息产物 flatMap 成裸数组；打开入口只传 artifact.id。
- [ArtifactPanel.tsx:40](H:/备份xuexi/智启课源/apps/web/src/features/chat/ArtifactPanel.tsx:40) 用裸 id 找第一个结果。服务事件有 sessionId/turnId，并不意味着产物 id 全局唯一。
- 独立复现：同会话的 A/B 两轮各有 `id=report`，点击 B 的消息产物入口，结果工作区显示 `payload-A`。截图已查看。这个场景使用独立浏览器仓储夹具；当前模拟脚本的 id 通常带 turn 前缀，正常单轮演示不会覆盖此问题。
- 修复：从消息入口到 tab key、当前选择、复制下载使用复合身份（模式/会话/轮次或稳定消息 id/产物 id），保持当前事件契约的作用域，兼容旧历史。不通过让测试 fixture 的 id 全局唯一规避问题。
- 验收：同轮同 id 更新、不同轮同 id、不同时段关闭再打开、切会话/模式、复制下载对应点击的内容、迟到更新与历史恢复。

### R25 · P2：耗时在正文流式阶段消失，部分终态继续计时

- [Message.tsx:70](H:/备份xuexi/智启课源/apps/web/src/features/chat/Message.tsx:70) 标题区只在非 streaming 渲染 TurnDuration；另一个位置仅在没有正文且没有 reasoning 时渲染。有了第一段正文后，活动耗时就消失。
- [store.ts:701](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:701) 的异常兜底未写 finishedAt；[normalizeLoaded():734](H:/备份xuexi/智启课源/apps/web/src/features/chat/model/store.ts:734) 恢复 streaming 也未处理耗时终态。组件把没有 finishedAt 当成计时中。
- 两个独立单测失败：流式已有正文时应有一个耗时节点，实际 0；服务 Promise 抛错后消息已 error，但 finishedAt 为 undefined。恢复路径遗漏为源码核对结论，需补独立回归。
- 修复：统一轮级状态行，正文/推理/工具/追问/产物期间只显示一处活动耗时；全部结束路径停止计时。恢复时采用可解释的冻结值或“耗时未知”，不能将离线经过时间当推理耗时，也不能每次载入重新计算一个更大的结束值。未知旧历史保持兼容。

## 实际验证与边界

全部从目标根执行；完整日志在 [_work/review-s2-s3-20260908](H:/备份xuexi/智启课源/_work/review-s2-s3-20260908)。未访问真实供应商、真实 MCP/Skills、文件解析或语音服务。

| 检查 | 本轮实际结果 | 证据 |
| --- | --- | --- |
| npm run typecheck | 退出 0 | typecheck.log |
| npm run lint | 退出 0，0 警告 | lint.log |
| npm run test:unit | 153/153，退出 0 | unit.log |
| npm run build | 退出 0 | build.log |
| 原 terminal-order 探针 | 2/2，退出 0 | terminal.log |
| 原 route-refresh 探针 | 1/1，退出 0 | route.log、route-output/ |
| 正式全量 e2e | **53 通过 / 1 失败，退出 1** | full-e2e.log、full-e2e/ |
| 本轮边界单元探针 | **2/2 失败，符合缺陷复现预期** | timing.test.tsx、probe-unit.log |
| 本轮最终浏览器探针 | **7/7 失败，符合缺陷复现预期** | composer-boundaries.spec.ts、probe-final.log、probe-final/ |
| test:api | 本轮未执行，后端未修改 | 不等于真实服务验收通过 |

全量 e2e 失败为 `chat-motion.spec.ts:16`：`Tearing down "context" exceeded the test timeout of 45000ms`。本次仍复现，不能沿用实施者“未复现/54 全过”作为本轮结论。业务断言没有报告失败，关键帧和 trace 已产生；不能据此认定动画业务必错，也不能称完整录像验收成功。根因仍未定位，后续须分别检查录制关闭、进程退出和产物完整性，保留失败记录，不靠关闭官方采集或改成跳过销项。

本轮浏览器探针首版 R21 在外部点击时被弹出层遮挡，未到达目标断言，未将该失败算成人设串会话证据。后改用正常 Escape 收起，并补“先建立 A、再新建不同 URL 的 B”前置条件；最终 probe-final 中在目标断言复现。所有旧产物保留，正式业务测试未改。最终 7 个浏览器用例对应 R19、R20 两条路径、R21–R24；R25 对应两个单测。

实际查看：本轮 R19/R24 缺陷截图、390/1920 输入区截图、过程展开中间帧。未完成参考与目标全站同内容比对，未逐段播放本轮 WebM，不宣称 S7 通过。650ms 宽度的源码参数对照 [ChatComposer.tsx:708](F:/DeepTutor/web/components/chat/home/ChatComposer.tsx:708) 成立，正式采样用例通过；这不代表完整首次发送及全部面板动画已验收。

## 进度结论与文档纠偏

- 上轮终态和 URL 修复：本轮相关独立探针通过，继续复用，不恢复旧错误重做。
- 保存队列：目前按尾 Promise 串行处理 dirty，保留 revision 合并；正式新增队列回归包含在 153 项内并通过。本轮未发现必须重写该队列的依据。
- S2：能力/附件/引用/人设/语音占位与 650ms 已有实现，但上述问题使“完整输入区已交付”不成立。修复后还需视觉与状态补验。
- S3：产物基础和计时初版已有；结果身份、面板选择、计时待修；引用/消息操作、多标签/宽度/更多渲染器未齐。
- S4：不能把复述能力配置和三种简单产物计为完整复杂能力闭环。
- S5：实际路由构建仍主要是 chat/settings/lesson-plans 和规划页。矩阵 **53 个非调试条目 = 50 参考 + 1 自有 + 2 兼容别名**；逐行统计 **4 已验收 / 1 实现待验收 / 2 部分实现 / 46 待实现**。46 包括空间扩展入口迁移；不要换算成精确总体完成率。
- S6 部分设置已有，完整设置尚未补齐；S7 全站视觉/动画待验；S8 未形成最终验收。

当前文档有过时陈述：replica/HANDOFF 顶部写 S3 未开始；根 TASKS 写 44 待实现和 149 单测，而当前矩阵为 46、正式单测为 153；旧 NEXT_SESSION_START 仍要求重做已修的终态/URL和 S2；FINAL 部分正文仍写教案默认入口；AI_INTERACTIONS 底部仍称 artifact 消费方待接入。本次更新当前入口与摘要、标明现行 `/`→`/chat`；历史记录保留。下一位实施者应以当前源码、最新复核和新的入口继续，不循环执行旧阶段。

## 下一位实施者

直接执行 [NEXT_SESSION_START.md](H:/备份xuexi/智启课源/docs/replica/NEXT_SESSION_START.md)。顺序是 **R19–R25 → S3 剩余 → S4 → S5-A 至 I → S6 → S7 → S8**，S1 的组件/状态规格随对应批补齐；S2/S3 修复通过后不等待新的阶段授权。

本报告中的缺陷尚未修复。最终完成需五项分别有证据：页面、交互、动画、模拟验证、真实服务验证；无凭证不阻止其余前端复刻，但真实验证列必须如实保留。

<!-- END ORIGINAL docs/replica/REVIEW_S2_S3_2026-09-08.md -->
