# S5-D 沉浸阅读独立代码审查

审查日期：2026-09-08。目标代码基线 `b8cf71f`，只读参考 `F:\DeepTutor` v1.6.5 / `42fab3cf429a1fbf36b257ab8d116a3814964202`。本次检查实际源码并运行独立探针；**没有修改产品实现**。本文 R26 起承接历史编号，与既有 R1–R25 区分。

**结论：不符合 S5-D 完整交付要求。** 文本材料、工作区、部分选区操作、同步模拟回复、笔记本本地联动已有；原有用例能通过。但用户数据保留、批注定位、路由、位置与布局存在可复现错误；参考伴生 AI 和材料流程仍有缺项。矩阵改为“实现待修复”，不能沿用“全部验收通过”。

## R26 · P1：载入演示覆盖用户记录，并能创建重复材料 id

源码：[reading-store.ts](../../apps/web/src/services/reading-store.ts) 第 513–590 行，尤其 555、566、575 行。`loadDemoReading` 向材料/工作区追加，却直接把批注、书签、会话键写为只含演示项的数组。用户先创建笔记、书签和会话，再首次载入演示，三者被删除。删除演示集合后材料保留，再载入又追加相同固定 id 的材料，产生重复身份。

独立存储用例前两项复现：三类用户记录均不再存在；第二次载入后材料数 4、唯一 id 数 2。原测试只覆盖“载入两次且演示集合一直存在”，没有覆盖用户先有数据和删除后再载入。

修复门槛：所有集合按稳定 id 无损合并，用户修改优先且不覆盖；演示存在与否不能只靠 workspace 一个标志；重复载入/部分删除/中途写入失败可恢复。断言保留已有记录**内容和关联**，不是只比较条数。

## R27 · P1：损坏存储被当空库，下一次写入覆盖可恢复原数据

源码：[reading-store.ts](../../apps/web/src/services/reading-store.ts) 第 98–109、136–164 行。`readList` 捕获所有读取/解析错误返回 `[]`，非数组也返回 `[]`；`createMaterial` 随即写入新数组。损坏 JSON 因而被永久替换。页面上的“读取失败，原数据未修改”无法收到被吞掉的错误。

独立第三项用例先存截断 JSON，再新建材料，实测既不报错也不保留原始字节。其他四组库共用此函数，同类风险存在。

修复门槛：区分不存在、解析损坏、格式错误、存储拒绝；仅不存在才初始化。写前确认可安全加载，失败显示可恢复错误并保留原始内容与用户编辑。显式修复/导出不能自动覆盖；补结构错误、读异常、写满和多键部分失败测试，保持旧数据兼容。

## R28 · P2：材料库按钮只改 URL，没有切换实际页面

源码：[ReadingWorkspace.tsx](../../apps/web/src/features/reading/ReadingWorkspace.tsx) 第 236、304–307 行，以及添加材料弹窗中的同一 helper。自制 `routerPush` 用 `history.pushState(null, ...)` 后派发 `popstate`，没有使用路由导航。

浏览器实测点击“材料库…”后地址变为 `/reading/materials`，但“阅读材料库”标题不出现，仍保留工作区内容。不能只验证 URL 正确就算导航成功。

修复门槛：用项目当前 Next 路由接口完成页面跳转，同时遵守离开前保存/清理。覆盖两个材料库入口、返回工作区、前进/后退、刷新深链、无效 id；断言 URL 与渲染内容一致。会话 URL 同步和真正页面导航分开处理。

## R29 · P2：quote-only 批注错误高亮重复段落

源码：[ReadingWorkspace.tsx](../../apps/web/src/features/reading/ReadingWorkspace.tsx) 第 470–492、596–615、631–651 行，以及 [reading-store.ts](../../apps/web/src/services/reading-store.ts) 的 ReadingAnnotation。选区已拿到 locator，但保存时只传 quote；渲染逐段匹配相同字符串，无法分辨选择的是哪次出现。

浏览器选择第二段“相同的句子。”并高亮，实测两段都出现 mark（期望 1，实际 2）。[实际截图](evidence/reading-20260908/duplicate-highlight.png) 已人工查看。跨段选区无法在单段字符串中完整匹配、标题不走 mark 渲染也属于同一实现限制，但本轮没有为这两项另跑浏览器探针。

参考依据：`F:\DeepTutor\web\lib\reading-w3c-annotations.ts:37` 解析 TextPositionSelector 的 start/end，并用 TextQuoteSelector exact/prefix/suffix 回退，不是全页字符串替换。

修复门槛：记录材料身份、范围/段落定位、偏移与 quote 上下文，重复/跨段/标题可准确恢复；旧 quote-only 历史迁移不能猜错位置，歧义显式提示。回归选中/滚动跳转/刷新/删除/重叠高亮及笔记导出。

## R30 · P2：切到阅读位置为零的材料仍停在前一材料位置

源码：[ReadingWorkspace.tsx](../../apps/web/src/features/reading/ReadingWorkspace.tsx) 第 522–547 行。恢复只在 `positionPct > 0` 时设置 scrollTop，同一 ReaderPane 的滚动元素被复用，零位置没有重置。

浏览器在 A 中滚到约 60%，切到初始位置为 0 的 B，实测 scrollTop 仍为 **3199**。此外 300ms 定时器持有旧 material，却读取当前容器，切材料时未取消 timer/rAF；此异步串写风险为源码判断，本轮探针只直接证明零位置错误。

修复门槛：包含零位置的统一恢复；所有 timer/rAF 带材料/实例身份并在切换/卸载时取消或结算旧位置，不能旧任务读新视图再写旧材料。选区/笔记浮条同步失效，补快速切换、离开、刷新恢复和待写状态回归。

## R31 · P2：收起导航后正文缩窄，遗留空列

源码：[reading.css](../../apps/web/src/features/reading/reading.css) 第 2–5 行；[ReadingWorkspace.tsx](../../apps/web/src/features/reading/ReadingWorkspace.tsx) 第 239–240 行。导航节点卸载，但 grid 仍固定三列，正文从中列移到 250px 第一列，右侧留空。

1440px 浏览器实测正文宽度 **338 → 250px**，收起后的布局与预期相反。[实际截图](evidence/reading-20260908/collapsed-navigation.png) 已人工查看。

参考 `F:\DeepTutor\web\components\reading\workspace\ReadingWorkspace.tsx:339` 随 navigatorCollapsed 改为两内容列并保留拖拽分隔；当前目标没有对应列变更。

修复门槛：布局随显示状态变化，保留正文最小空间；补右侧宽度调节的真实交互、键盘与移动面板。覆盖三视口和快速开关，不用 overflow:hidden 裁切掩盖。

## R32 · 交付范围缺口：显式模拟没有覆盖参考的完整前端

1. **伴生 AI**：目标第 805–825 行 send() 同步 append 用户与模板回复，未走已建 ChatService，无流式/取消/工具/追问/错误重试/产物消费。参考 `ReadingCompanion.tsx:40,119,175,529` 复用 ChatMessageList、ChatStateAdapter、useChatAutoScroll；`ReadingComposer.tsx:18,49,120` 复用 StandaloneComposer、submitUserReply、cancelStreamingTurn。模拟可以用统一服务提供确定性事件，不能缩成固定字符串就算齐全。
2. **材料/布局**：目标 SourceKind 只有 text；非文本导入、解析状态、对应视图与恢复没有齐全。参考工作区有 380 默认宽度、300–640 范围、1280 分界及右栏拖拽；目标固定 340px，小屏简单堆叠。这些是待补齐，不是已批准差异。
3. **会话编辑上下文**：目标 draft/pendingQuote 是组件状态，focusSession/newSession 没有保存或清理归属；应专项验证切会话、工作区、材料后的草稿和引用，不把“消息数组持久化”称为完整编辑状态恢复。本轮未单独执行这组浏览器用例。
4. **相关旧批次**：书籍源码 BookBlockType 只有 text/section/callout/quiz/placeholder；旧记录明确 14 类仅做 4 类、练习答案不持久化、暂停恢复省略、课程会话未接。依据用户的全量前端目标，下调相关矩阵为部分实现，后续逐项核查；本轮不是对所有旧页面的完整二次审计。

实现这些缺口时先补状态规格与接口，再复用已有能力，不重写稳定主聊天基础。以每项可演示闭环、保存和跨页引用验收，真实未接入保持显式边界。

## 实际验证与可复现命令

PowerShell，工作目录 `H:\备份xuexi\智启课源`。日志完整保存在 `_work/review-reading-20260908/`；精选 [存储失败日志](evidence/reading-20260908/storage-probes.txt)、[浏览器失败日志](evidence/reading-20260908/browser-probes.txt) 与探针源码已纳入 Git。

| 检查 | 本次结果 |
| --- | --- |
| typecheck / 整理后 lint | 通过 / 0 警告 |
| 正式单测 | 原命令 164 通过/42 失败；本机 Node v26.2.0 原生 webstorage 影响 jsdom，禁用该实验功能后 **206/206 通过** |
| build | 通过，阅读五条路由存在 |
| 独立单元 | **3 个失败**，复现 R26/R27，断言未弱化 |
| 独立浏览器 | **4 个失败**，复现 R28–R31；关闭 trace 的独立复跑相同断言仍失败，没有 teardown 超时干扰 |
| 正式 e2e | **91 通过 / 1 失败**；reading.spec.ts 原 5 项均通过。失败是 chat-motion context teardown 超过 45 秒，不能称全绿 |
| 人工查看 | 本轮查看重复高亮和收起布局的实际 1440px 截图，非完整三视口/动画验收 |
| 未执行 | 真实供应商、真实 MCP/Skills、解析/STT、test:api；产品后端未改 |

测试环境说明：本轮没有升级 Node 或依赖。Node 26 原生 localStorage 的实验功能在 jsdom 下暴露为 undefined；此次用进程级 `NODE_OPTIONS` 复跑，产品代码与断言未改。后续应选择项目支持的运行环境或在测试 setup 明确浏览器存储归属，不能把这 42 项环境失败误报为 42 个业务缺陷。当前未声称已永久修复工具链。

```powershell
# 原环境信息
node --version
npm.cmd run typecheck
npm.cmd run lint
# Node 26 本轮使用的单测兼容复跑；只影响当前终端
$savedNodeOptions = $env:NODE_OPTIONS
$env:NODE_OPTIONS = '--no-experimental-webstorage'
npm.cmd run test:unit
npx.cmd --no-install vitest run --config tests/review/reading-20260908/vitest.config.ts
$env:NODE_OPTIONS = $savedNodeOptions

npm.cmd run build
# 每次改为新的目录后缀；不要删除旧证据
npx.cmd --no-install playwright test --config tests/review/reading-20260908/playwright.config.ts --trace=off --output=_work/review-reading-20260908/browser-probes-next
npm.cmd run test:e2e -- --reporter=line --output=_work/review-reading-20260908/full-e2e-next
```

探针配置文件位于 [tests/review/reading-20260908](../../tests/review/reading-20260908/)，独立于默认正式测试集，**当前按正确业务预期失败**。下一批修复后迁入正式回归，不删掉失败条件。首次浏览器探针的 webServer 相对 cwd 配置错误已修正后重跑；只有实际业务断言失败的第二次及 trace-off 复跑用作本审查证据。

全量中的模型目录请求出现 127.0.0.1:8000 ECONNREFUSED，因为本轮没启动后端；记录为环境边界，不视为真实供应商验证。动画录像 teardown 在本轮再次出现，trace-off 专项再跑仍在 context teardown 超时（45 秒），根因未确定；结果同时记录在 STATUS；无论该复跑结果如何，均保留这次正式全量失败，不用复跑结果覆盖首跑。

## 修复验收与版本边界

先修 R26/R27，再修 R28–R31；随后补 R32 前端差距，继续剩余阶段。修复须保留旧数据、迁入正式回归、三视口相关交互验证，同一 review 追加“修复依据、实际命令、证据、未完成项”。当前审查不宣称缺陷已修。

本次只改开发文档、审查探针、精选证据与 Git 忽略保护；产品 apps、锁文件、模板和原始规划均未改。基线 `b8cf71f`/`checkpoint/pre-reading-review-20260908` 可回退。历史文档原文和 SHA256 已合并归档；当前目标与进度见 [PROJECT_GUIDE](../PROJECT_GUIDE.md)、[STATUS](../STATUS.md)。

## 修复记录 · R26–R31（2026-09-09）

同一 review 追加修复依据、实际命令与结果；R32 未在本批处理。

### 修复依据与实现

- **R26**：`loadDemoReading` 改为按稳定 id 无损合并（`mergeById`，已存在条目原样保留、只补缺失演示条目），五个键单批原子提交；演示批注补 `segments` 精确定位（引用为所在行子串，按 includes 定位行、indexOf 定位偏移）；演示书签 locator 修正为「生活中的分数」实际标题行。
- **R27**：`readList` 严格化——仅键不存在返回空数组；JSON 损坏/格式异常/读取被拒抛 `ReadingStorageError`，不再当空库。新增 `commitLists` 多键原子写入：先严格校验全部键，逐键写入，任一失败回滚本批已写键并抛错。`deleteMaterial`/`deleteWorkspace`/演示载入改走单批提交。页面刷新与渲染路径（ReadingLibrary、MaterialLibrary、SourceNavigator、ReaderPane、CompanionPane）读取均容错显示可恢复错误；演示载入按钮捕获异常提示，不再静默。
- **R28**：删除自制 `routerPush`（pushState+popstate），改用 `next/navigation` 的 `router.push`；Tab 条与添加材料弹窗两处材料库入口均真实导航，跳转前 ReaderPane 卸载清理即结算待写位置。
- **R29**：`ReadingAnnotation` 新增 `segments`（locator+start/end，块级 TextPositionSelector 形态，可跨块）。选区经 `collectSelectionSegments` 捕获（`Range.toString().length` 计算块内偏移，避免 mark 片段化 DOM 误差）；渲染改为按区间渲染（重叠先到先得），标题同样渲染 mark；单段定位须仍覆盖 quote 才接受，否则回退 quote 匹配；旧 quote-only 历史按全文唯一匹配回退，多处命中标记 ambiguous 并在导航点击时显式提示，不再猜位置。演示数据同步携带 segments，旧存量演示批注经唯一匹配兼容。
- **R30**：阅读位置生命周期按材料 id 重构：切换/卸载时取消 rAF 与待写定时器；滚动时捕获 `{materialId, pct}` 待写值（pct 按滚动当时内容计算，杜绝旧任务读新视图再写旧材料），cleanup 结算；位置恢复统一执行——零位置也回到顶部；切材料时选区浮条/笔记表单同步失效。
- **R31**：桌面（≥1280px）列模板由组件按状态内联设置——导航显示 4 列（`minmax(184px,230px)`＋正文 `1fr`＋5px 拖拽轨＋伴生），收起后 3 列，正文获得导航空间（对照参考 navigatorCollapsed）；新增伴生栏拖拽手柄（默认 380、范围 300–640、本地持久化 `zhiqikeyuan:reader:companionWidth`、指针拖拽与左右方向键键盘可达、焦点可见）；<1280px 维持单列堆叠。手机抽屉/面板属 R32 待补。

### 实际命令与结果

| 检查 | 结果 |
| --- | --- |
| typecheck / lint | 通过 / 0 警告 |
| 正式单测 | **214/214 通过**（`NODE_OPTIONS=--no-experimental-webstorage`；含新增 R26×3、R27×5 用例） |
| build | 通过 |
| 独立存储探针 | **3/3 通过**（修复后复跑，未删失败条件） |
| 独立浏览器探针 | **4/4 通过**（`--trace=off`，产物 `_work/reading-fix-20260909/browser-probes`） |
| 正式全量 e2e | **96/96 通过**（含迁移后的 R28–R31 正式回归与既有 5 条阅读用例；上轮 chat-motion context teardown 超时本轮未复现） |
| 真实供应商/解析/STT | 未调用，未验证 |

迁移说明：R26/R27 存储探针迁入 `apps/web/src/services/reading-store.test.ts`（断言保留“内容和关联”，新增回滚/格式异常/键不存在用例；本环境 Storage 方法在原型上、`vi.spyOn` 拦截不生效，写失败用例改用 `Object.defineProperty` 替换 localStorage 实现）；R28–R31 迁入 `tests/e2e/reading.spec.ts`（断言未削弱，另补前进/后退、刷新恢复、切回旧材料位置、拖拽与键盘用例）；探针原件保留于 `tests/review/reading-20260908/` 作历史证据。

未完成项：R32（伴生 AI 复用统一 ChatService 与消息组件、材料类型与解析模拟、会话草稿归属、移动端抽屉/面板）与 S3/S4/S5-A～C 差距核查不在本批；三视口完整验收在 S7。
