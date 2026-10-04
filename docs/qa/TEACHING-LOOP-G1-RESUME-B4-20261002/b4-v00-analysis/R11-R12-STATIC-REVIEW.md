# B4-R11/R12 QA 与修复方案独立静态审查

结论：**PASS（QA 正确性与修复静态范围）**，R11/R12 修后独立验收仍待执行。诊断冻结候选 `CANDIDATE-b4-r11-visual-diagnostic.json` SHA256 `9d46ff61a027b342db19b8f5ee975a14418fb38817a6d1ec1dd410fc7b56c781` 与 r10 全 878 产品及 5 契约同源；43 QA/5 契约当前散列零漂移。审阅时 CTRL 已在三份登记前端文件中落入方案草稿，现行产品相对 r11 恰为这三处，不能声称 r11 当前全产品零漂移。每份修前字节匹配 r11 清单/BEFORE 收据，具体 diff 和当前 SHA 见 JSON。

独立 R11 两例使用真实 useAsyncResource/useObservedJob hooks，受控 API/任务 transport；范围明确是 jsdom 组件行为，不是假称真实后端验收。第一例先创建固定成绩/人次报告并断言请求只一次，任务成功且事实出现后要求相同 run/score 的历史行变为“已准备”并移除“尚未准备”。第二例切换 A→B 源与报告，断言 A observer aborted，刻意发迟到 A 成功并要求 B 源、固定成绩和历史不污染；不发 B terminal，而用真实组件的手动刷新按钮获取字面 ready 视图，要求 B 历史同步且 A 仍不出现。没有删除/弱化断言，没有调用聚合实现作 oracle。

原 first JSON/收据已经完整结束：**2 total / 0 pass / 2 fail，outer exit1**，两例均实败在历史“已准备”断言，收到原“尚未准备”行。这是独立组件红测证据；本审阅没有执行它。first 文件/日志 SHA 均保留并匹配原命令收据。

真实浏览器 QA 在原 spec 中新增初次和回流报告的两个精确历史行断言。独立 TypeScript AST 静态核得直接 matcher **116→118，旧 matcher 缺失0**，2 个 expect.poll 全文本相同，无解析诊断。原 115 业务 matcher、R08 精确 URL 等待、全部真实 API 行为和配置/超时均保留。产品单测新增手动刷新场景，旧 19 matcher 无缺失，只新增2。

mobile QA 读取本批真实合成 chain，在新的 390×844 context 导航真实页面，GET 继续真实服务，任何非 GET 阻断并留记录；不改 DOM 或造响应。它要求三下载按钮、8 个回流题证据、唯一选中历史、0 非 GET、所有截图无横向溢出、12px 选中元数据对比度至少 **4.5**。对比度使用 sRGB 分段 luminance 和标准 max/min 比值，当前两色为不透明 rgb。原 first 实际 **exit1、8 截图、0 禁止写请求、无横向溢出**，选中态 rgb(110,110,110) / rgb(37,99,235) 对比度 **1.0136593990027387**；元数据 bounds 宽 **67.046875px**、高90，context/browser 已关闭。

**视觉验收边界：mobile 脚本只记录窄列 bounds 和截图，没有自动“元数据占满可用行宽”的断言。**因此修后对比度通过和无横溢仍不足以关闭 R12 排布问题，必须人工查看修后截图，确认标题与元数据上下堆叠、长 ID 的可用宽度。

当前实际刷新草稿将父级稳定 `runs.reload` 传为 onHistoryReload；child 的 refreshReport useCallback 只依赖两个稳定 reload 函数，并仅被 terminal 与手动按钮触发。useAsyncResource 的 reload 为 useCallback([], tick setter)，实际列表 GET 由最新 loadRef 和当前 assessment/score/offset key 取得；它不将旧 child 的 row 塞入新源列表。没有在返回 run/resource 对象变更 effect 中反复调用刷新。终态再读可能触发一次 terminal adopt 后的附加刷新，但已有 jobId|attempt|state 去重使后续同终态不再 adopt，未见无限刷新链。

旧源隔离沿用未改共享 hooks：Panel key=runId 切换卸载 old observer，useObservedJob 的 alive/epoch/abort 在 terminal 回调前拦截旧更新；GET 资源也以 active/abort/key 防迟到写入。独立第二例会对实际此边界给出行为结果。本静态审阅只确认控制流，不提前宣称修后测试通过。

CSS 只在两页面 scoped 的 b4-list > button 加 display:block，并在其 primary .b4-meta 加 color:inherit。共享 space-button 原 inline-flex 将匿名标题与 metadata 作为并排 flex item，长 ID 元数据被挤窄；block 恢复纵向行排布，选中元数据继承现有 primary 白色。选择器优先级足以覆盖本模块原 muted 元数据，未改 commonShell/space.css、品牌蓝/字体token、native button disabled/focus/键盘语义或动画。实际 post-fix computed color/bounds 和视觉仍待新构建/冻结后验证。

本审阅仅读取源码、元数据和原结果，进行独立静态 TS AST/散列，仅写此 MD/JSON；未导入 app.main，未测试/collect/HTTP/browser/service，未读取实际数据，未改产品/可执行 QA 或 Git。修复须由新候选绑定后执行组件两例、保留新增断言的真实全链浏览器与手机截图/对比度；旧 r5 构建同源结论不能替代这次前端新源码的构建身份。报告收口停写。
