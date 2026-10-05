# CHAT-VISUAL-v1 — 原 14 chat 单轮截图目视登记

任务：B4-CHAT-VISUAL v1；独立审阅者：`/root/g1_resume_browser`；日期：2026-10-03。

26/26 张实际 PNG 已逐张通过 `view_image(detail=original)` 查看，无工具阻断；图像逐个前后 SHA256 相同。已登记手机代码文字遮挡等可见异常，**不将整套视觉标为 PASS**，B4 不在此关闭。

输入只来自本批 `b4-chat-resume-first/artifacts`。14 passed / 43832.314 ms 是父任务与 F `CHAT-ACTUAL v1` 已有实际运行事实，本任务未重跑或重新验算报表。r20 来源已由此前独立审查绑定；当前新候选准备阶段未读取其变动源码。

## 可见异常与边界

- CV-01：第 18 图，390×900 长回答中，浮动“回到最新”按钮遮住代码块两行部分字形。此为截取滚动位置的实物，应由 CTRL 登记和处置；不推断永久遮挡。
- CV-02：第 22–24 图，减少动画旁小空方框与灰色开关同时可见；第 22 图 section tabs 左侧另见窄空按钮样区域。仅登记像素观感，未用 DOM/CSS 验证控件语义。
- CV-03：第 25 图，标题为“正在回答0s”，输入区圆形按钮图形似向上发送箭头。单帧可能包含更新过渡，不能据此断言停止/发送行为失败。
- CV-04：第 4、6、13、15 图保留流中未闭合公式原文本；终态和恢复图可见完成公式正常渲染。保留暂态事实，不把它判为最终公式失败。

## 逐图实际查看

### 1. chat-reasoning-正文开始后推理继续增量：用户重开后仍跟随，手动上滚不被抢占/reasoning-post-answer-paused.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-正文开始后推理继续增量：用户重开后仍跟随，手动上滚不被抢占/reasoning-post-answer-paused.png>)；1280×720；136091 bytes。
- SHA256：`57172b37e052269efb93e7bf1c3c9b74e645b448c9c1ad0056b3f6ba1cae6f03`。
- 实际查看：正文“正文已开始，推理仍在继续。”与展开推理面板并存；灰色推理约第28–47行，面板顶部切入一行，仍在回答7s；底部停止按钮可见。
- 滚动／边界：内部推理已滚动，静态图不能证明暂停后不被抢占。
- 异常标记：未见需另列的像素异常。

### 2. chat-reasoning-正文开始后推理继续增量：用户重开后仍跟随，手动上滚不被抢占/reasoning-post-answer-follow.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-正文开始后推理继续增量：用户重开后仍跟随，手动上滚不被抢占/reasoning-post-answer-follow.png>)；1280×720；136658 bytes。
- SHA256：`40647471ca7822ae5f654eaf814d8f56df49cb1bdf6b1a4f58dedb0e0ddec5a6`。
- 实际查看：同一会话正文与展开推理并存；面板约第22–40行，仍在回答6s；内容和输入区处于可见边界。
- 滚动／边界：同组时间不同的截面，不能仅图证明自动跟随。
- 异常标记：未见需另列的像素异常。

### 3. chat-reasoning-正文公式：text-delta-原文逐字保留并在流中、终态及刷新后渲染/body-math-terminal.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-正文公式：text-delta-原文逐字保留并在流中、终态及刷新后渲染/body-math-terminal.png>)；1280×720；90885 bytes。
- SHA256：`039935acc3a89288a2e66c6bbbfca3327775afbaab5fca6107e276986b09f437`。
- 实际查看：终态矩阵两行等式清楚；代码块保留美元/括号文本；q、r²与闭合x+y=z公式渲染，最后一段已释放。
- 滚动／边界：外层视口已滚到答案下部，顶端内容被视口裁切。
- 异常标记：未见需另列的像素异常。

### 4. chat-reasoning-正文公式：text-delta-原文逐字保留并在流中、终态及刷新后渲染/body-math-streaming.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-正文公式：text-delta-原文逐字保留并在流中、终态及刷新后渲染/body-math-streaming.png>)；1280×720；87144 bytes。
- SHA256：`7ef533edabfe842f81fb319aa3885145321aed080dbb3b4c304274de004e91b0`。
- 实际查看：流中表格E=mc²、矩阵两行与代码可见；底部未闭合$x+y和转义公式原文仍作为文本显示，停止按钮可见。
- 滚动／边界：答案下部截图；可见内容未越过右边界。
- 异常标记：STREAMING_TRANSIENT_RAW_MATH_TEXT_OBSERVED_FINAL_RENDER_CHECKED_IN_OTHER_IMAGES。

### 5. chat-reasoning-正文公式：text-delta-原文逐字保留并在流中、终态及刷新后渲染/body-math-restored.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-正文公式：text-delta-原文逐字保留并在流中、终态及刷新后渲染/body-math-restored.png>)；1280×720；90755 bytes。
- SHA256：`24216d16cdab81ca3b7cf37303bb6e3bf51a7aedaa63b9b5a7d790567b53d59f`。
- 实际查看：刷新恢复图与终态一致：矩阵、q/r²、闭合x+y=z与代码块均可见，输入区为非生成态。
- 滚动／边界：外层答案下部；不证明数据库原文，仅可见恢复画面。
- 异常标记：未见需另列的像素异常。

### 6. chat-reasoning-教学问答模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-streaming.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-教学问答模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-streaming.png>)；1280×720；78232 bytes。
- SHA256：`54ad245458d6d98345864123d6cdb6246a97954182860e64b1976afb742ab2c9`。
- 实际查看：教学模型流中为“正在推理0s”，展开灰色推理中代码美元文本与未闭合$x+y显示原文，正文尚未出现，停止按钮可见。
- 滚动／边界：推理面板下部内容可见，暂无跨图动作因果证明。
- 异常标记：INCOMPLETE_REASONING_MATH_REMAINS_LITERAL_DURING_STREAM。

### 7. chat-reasoning-教学问答模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-restored-mobile.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-教学问答模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-restored-mobile.png>)；390×844；47981 bytes。
- SHA256：`191b32642c2cff388c24feacb43327f69e68020953f02b57d84c77a9e3ecf027`。
- 实际查看：390手机恢复图：已完成1s推理展开，a²+b²=c²与E=mc²可见；正文结论与1/2+√x、两段文字及输入区完整宽度内。
- 滚动／边界：推理面板下边缘截断下一公式，属有界内滚动；模型名以省略号压缩。
- 异常标记：未见需另列的像素异常。

### 8. chat-reasoning-推理滚动：流式跟随、主动上滚暂停与回到底部恢复/reasoning-follow-streaming.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-推理滚动：流式跟随、主动上滚暂停与回到底部恢复/reasoning-follow-streaming.png>)；1280×720；137610 bytes。
- SHA256：`b57119689fecc74a5340b24c3c16914f0d69d56805bebc529821997935918b71`。
- 实际查看：推理跟随组流中4s，灰色面板约20–33行，上边缘切行，页面输入区与停止按钮稳定可见。
- 滚动／边界：当前面板为中后部，可见截面不能证明持续跟随。
- 异常标记：未见需另列的像素异常。

### 9. chat-reasoning-推理滚动：流式跟随、主动上滚暂停与回到底部恢复/reasoning-follow-resumed.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-推理滚动：流式跟随、主动上滚暂停与回到底部恢复/reasoning-follow-resumed.png>)；1280×720；148512 bytes。
- SHA256：`dd44cc198f6b495a23900b6f936051779274f274dc314b7a9a8ade74b024b867`。
- 实际查看：推理跟随组“正在推理5s”，面板约24–39行，流中文字保持灰色折行，无页面内容挤压。
- 滚动／边界：可见推理位置比paused图更后；不能仅图证明用户滚动事件。
- 异常标记：未见需另列的像素异常。

### 10. chat-reasoning-推理滚动：流式跟随、主动上滚暂停与回到底部恢复/reasoning-follow-paused.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-推理滚动：流式跟随、主动上滚暂停与回到底部恢复/reasoning-follow-paused.png>)；1280×720；147638 bytes。
- SHA256：`1bdac9f61657c1743bb62704ec00e0b5663154768c7bf7aac5bfcf293c43ef36`。
- 实际查看：同组“正在推理4s”，面板约11–26行，顶端切行；正文尚未出现，停止按钮可见。
- 滚动／边界：paused图可见更早内容，具内部滚动截面；不认证不抢占动态行为。
- 异常标记：未见需另列的像素异常。

### 11. chat-reasoning-性能：50k-推理-正文公式受控流/performance-50k-terminal.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-性能：50k-推理-正文公式受控流/performance-50k-terminal.png>)；1280×720；88719 bytes。
- SHA256：`cff8c216bec6897f840b60a845c6e322aa44847c72c484f177af7532eb69c8f2`。
- 实际查看：50k终态截图显示四组正文a²+b²=c²与块级E=mc²，公式清晰，末尾工具/模型名与输入区无相互遮挡。
- 滚动／边界：只看到长答案尾部四组，不能视觉证明50k总量或性能。
- 异常标记：未见需另列的像素异常。

### 12. chat-reasoning-性能：20k-推理-正文公式受控流/performance-20k-terminal.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-性能：20k-推理-正文公式受控流/performance-20k-terminal.png>)；1280×720；88739 bytes。
- SHA256：`d01ba7cd6567c46d283014b82e8b3835b3ef0411da68d97c5c012d34d30c2de3`。
- 实际查看：20k终态与50k组类似，四组行内/块级公式正常可见，右边界内，输入区处于非生成态。
- 滚动／边界：长答案尾部截图，未覆盖完整长推理。
- 异常标记：未见需另列的像素异常。

### 13. chat-reasoning-Responses-模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-streaming.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-Responses-模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-streaming.png>)；1280×720；78021 bytes。
- SHA256：`224b3aa9dfd7f7a8c28860f58a7fb9780086e9e0e7a682daeca4cdc56a8a5afa`。
- 实际查看：Responses推理流中0s，灰色展开推理含代码块美元文本与未闭合$x+y；Responses模型身份标签与停止按钮可见。
- 滚动／边界：推理面板下部视图，正文尚未出现。
- 异常标记：INCOMPLETE_REASONING_MATH_REMAINS_LITERAL_DURING_STREAM。

### 14. chat-reasoning-Responses-模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-restored-mobile.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-Responses-模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-restored-mobile.png>)；390×844；48798 bytes。
- SHA256：`1ef7090e090bccdb0523b57671199e018788f82fded8197e1a39d3ecace9d5a5`。
- 实际查看：Responses手机恢复：完成1s，展开推理及E=mc²；正文a²+b²=c²、分数/根式和两段文字清楚，footer输入9/输出12tokens在边界内。
- 滚动／边界：推理面板下一公式被内滚动底边裁切，手机模型selector省略号。
- 异常标记：未见需另列的像素异常。

### 15. chat-reasoning-Anthropic-模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-streaming.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-Anthropic-模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-streaming.png>)；1280×720；77780 bytes。
- SHA256：`aeb85dc89f6de0fb2ba816ca0d807f95db3abb845b87ac1cfe672597f56a3cc3`。
- 实际查看：Anthropic推理流中0s，代码美元文本和未闭合$x+y可见，模型身份/停止按钮清晰；无错误横幅。
- 滚动／边界：推理面板下部，截图只能证这一时点。
- 异常标记：INCOMPLETE_REASONING_MATH_REMAINS_LITERAL_DURING_STREAM。

### 16. chat-reasoning-Anthropic-模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-restored-mobile.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-reasoning-Anthropic-模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-restored-mobile.png>)；390×844；49223 bytes。
- SHA256：`7a4ff5145e21ee74716cb2441d1331736041dad2761ab0a9dfc6b27284e2d344`。
- 实际查看：Anthropic手机恢复：完成1s，推理与正文公式均可见，分数/根式无横向越界；footer输入未知/输出12tokens。
- 滚动／边界：同组手机恢复面板有界切行，selector文本省略号。
- 异常标记：未见需另列的像素异常。

### 17. chat-live-长回答-Markdown-公式与响应式布局/chat-empty-1440.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-live-长回答-Markdown-公式与响应式布局/chat-empty-1440.png>)；1440×900；91926 bytes。
- SHA256：`e55806fdbcb1330ec2ebc164aaa7a7974887571749df6c4a8ffdb5653b6028df`。
- 实际查看：1440空会话：品牌蓝/sidebar、中心欢迎文案、模型选择输入区及三个建议按钮完整，当前无历史。
- 滚动／边界：空页不存在长内容滚动，布局可见范围无越界。
- 异常标记：未见需另列的像素异常。

### 18. chat-live-长回答-Markdown-公式与响应式布局/chat-answer-390.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-live-长回答-Markdown-公式与响应式布局/chat-answer-390.png>)；390×900；67160 bytes。
- SHA256：`cbcc2c9d9f4fcc91f1c02ed2c43d2e70cb99535a815d6b96ae639a5315178f20`。
- 实际查看：390长回答：中文标题/列表、E=mc²、三列表格及Python代码均折行适应宽度，手机壳与输入区可见。
- 滚动／边界：答案停在中段，显示浮动“回到最新”；按钮覆盖代码两行中部部分字符，未操作后续滚动。
- 异常标记：VISIBLE_MOBILE_RETURN_LATEST_BUTTON_PARTIALLY_OVERLAPS_CODE_VIEWPORT_CONTENT。

### 19. chat-live-长回答-Markdown-公式与响应式布局/chat-answer-1440.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-live-长回答-Markdown-公式与响应式布局/chat-answer-1440.png>)；1440×900；120783 bytes。
- SHA256：`300ef901136cf01c4a1cdb332df68b3139f05ea09090242ff1ed628a9def46d9`。
- 实际查看：1440长回答：正文/列表/公式、三列表格和两行代码清楚；已完成0s；侧栏会话条目/输入区保留。
- 滚动／边界：当前在答案中段，下一个标题从输入区上方视口边界切入；回到最新悬浮于代码区底部空隙。
- 异常标记：未见需另列的像素异常。

### 20. chat-live-长回答-Markdown-公式与响应式布局/chat-answer-1024.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-live-长回答-Markdown-公式与响应式布局/chat-answer-1024.png>)；1024×900；116901 bytes。
- SHA256：`9d2bd76441689cb2cd1433d57f96428dd1e67213cba6f14b1f60726fb818f4c1`。
- 实际查看：1024长回答与1440一致，三列表格与代码宽度在内容区内，侧栏不挤压正文。
- 滚动／边界：同样答案中段/回到最新，底部正文由可滚动区域边界裁切。
- 异常标记：未见需另列的像素异常。

### 21. chat-live-教学问答模型-经真实代理在最后分块释放前显示中文/stream-in-progress.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-live-教学问答模型-经真实代理在最后分块释放前显示中文/stream-in-progress.png>)；1280×720；73713 bytes。
- SHA256：`2ff905da722451fee55d025f974877cbe4344a0b3c6d31f9e08a4af0aca1bc3b`。
- 实际查看：教学问答模型在“正在回答1s”时已有中文首段，模型标签/停止按钮可见，正文布局无错位。
- 滚动／边界：短正文未滚动，不能凭图证代理时序。
- 异常标记：未见需另列的像素异常。

### 22. chat-live-模型发现追加、默认模型同步、表单冲突保留/models-390.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-live-模型发现追加、默认模型同步、表单冲突保留/models-390.png>)；390×900；46872 bytes。
- SHA256：`9e75a1b95b1d0b8353a9d085ec85ac988519ce6f40f54ea08776c384019b71fe`。
- 实际查看：390设置：顶部移动壳/横向分类导航，问答模型三连接四模型；卡片一列、当前教学服务标蓝、无明文凭证。
- 滚动／边界：停在外观尾部与模型区交界，Responses卡从底边切入；分类条最左可见空白窄按钮；减少动画附近小方框和滑动开关并存。
- 异常标记：VISIBLE_SETTINGS_CONTROL_QUIRK_SMALL_EMPTY_BOX_PLUS_SWITCH_NOT_DOM_DIAGNOSED。

### 23. chat-live-模型发现追加、默认模型同步、表单冲突保留/models-1440.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-live-模型发现追加、默认模型同步、表单冲突保留/models-1440.png>)；1440×900；104644 bytes。
- SHA256：`e73c3147d5ed1083f81ec727a5c3b18dd443330f7f59f043aae0d2dfd063c342`。
- 实际查看：1440设置：模型服务/Responses/Anthropic三卡横排，三连接四模型与当前模型标记清楚，添加连接按钮完整。
- 滚动／边界：视图停在外观尾部与模型区交界；减少动画前方小方框+开关并存。
- 异常标记：VISIBLE_SETTINGS_CONTROL_QUIRK_SMALL_EMPTY_BOX_PLUS_SWITCH_NOT_DOM_DIAGNOSED。

### 24. chat-live-模型发现追加、默认模型同步、表单冲突保留/models-1024.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-live-模型发现追加、默认模型同步、表单冲突保留/models-1024.png>)；1024×900；104099 bytes。
- SHA256：`817b41f695df3159706ccb5eb41aef0b170d16201477227b424b36f21a7a0583`。
- 实际查看：1024设置：两列卡片自动排布，三协议服务和添加连接占四格，内容均在边界内。
- 滚动／边界：同样外观尾部/模型区交界；小方框+灰色开关同时可见。
- 异常标记：VISIBLE_SETTINGS_CONTROL_QUIRK_SMALL_EMPTY_BOX_PLUS_SWITCH_NOT_DOM_DIAGNOSED。

### 25. chat-live-Responses-模型-经真实代理在最后分块释放前显示中文/stream-in-progress.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-live-Responses-模型-经真实代理在最后分块释放前显示中文/stream-in-progress.png>)；1280×720；73728 bytes。
- SHA256：`fb305f55d6d93be5a3c47d8f09ede4f3d6a9e785dd8083cbe49eae0277a052e7`。
- 实际查看：Responses正文首段中文已显示，标题“正在回答0s”与模型身份可见；输入区圆形按钮的截图图形似向上发送箭头。
- 滚动／边界：正文很短，底部输入区完整，画面无可见横向溢出。
- 异常标记：VISIBLE_STREAM_STATUS_AND_COMPOSER_ARROW_GLYPH_NOT_CONTROL_BEHAVIOR_PROOF。

### 26. chat-live-Anthropic-模型-经真实代理在最后分块释放前显示中文/stream-in-progress.png

- 文件：[PNG](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat-resume-first/artifacts/chat-live-Anthropic-模型-经真实代理在最后分块释放前显示中文/stream-in-progress.png>)；1280×720；73306 bytes。
- SHA256：`77248eae59967b89f4a2abec57ca834e5318426ad631892a7a02f4e2fd18102b`。
- 实际查看：Anthropic正文首段中文已显示，标题“正在回答0s”与模型身份可见，输入区显示方形停止图形。
- 滚动／边界：正文很短，底部输入区完整，画面无可见横向溢出。
- 异常标记：未见需另列的像素异常。

## 局限与收口

- 只审原运行 PNG，未执行 DOM、网络、实时浏览器、服务或测试，未读取或修改正在准备的产品/QA源码。
- 截图不能独立证明自动滚动跟随、主动上滚不被抢占、刷新持久化、协议分块释放时序、控制按钮交互或20k/50k总量和性能预算；这些须由既有运行断言/trace另证。
- 有限视口中推理框顶部/底部和外层内容底部截断是可见滚动区域边界；未据此推断内容丢失。无明显横向裁切的目视观察不是scrollWidth测量。
- 流中未闭合公式保留原文本已明确记录；终态/恢复图的对应完成公式可见正确渲染，未将流中暂态当最终渲染失败。
- 三项视觉异常仅按像素登记，未判断DOM实现或扩大为控制逻辑失败；手机代码文字遮挡需CTRL明确处置。此报告不标整套视觉PASS，也不关闭B4。
- 14passed/43832.314ms来自父任务与F CHAT-ACTUAL的既有实际结果；本任务未重跑或独立重新验算14例报表。

只新增本报告 MD/JSON；26 图无修改。未执行 DOM/HTTP/浏览器/服务/测试，未改产品、QA执行源或权威文档。报告完成后停写。

