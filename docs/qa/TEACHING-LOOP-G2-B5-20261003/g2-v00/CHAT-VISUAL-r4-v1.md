# G2 聊天原图独立审阅 r4-v1

实际逐张读取26/26原PNG，前后散列及manifest均不变；886源码/304可执行QA当前对r4散列0漂移。仅新增本JSON/Markdown，不跑测试、不操作浏览器/服务/数据库/Git、不修改源图或权威文档。

候选SHA：`8aa0d1aabddeb53c851c2cbc9ec316373578dd4a5df85392e5e254c92259039d`。原聊天2spec14case本轮14/14，均1attempt/retry0，exit0/46437.740ms；这是已完成动态回归的引用，并非本图审重新执行。

保留旧CV台账：第9图390px长回答浮钮遮代码字形（CV-01）；第4–6图空方框/灰色开关同现（CV-02）；第1/2图正在回答状态的箭头图形与第3图停止方形分列（CV-03）。只述静帧，不将这些像素观察改称交互失败、旧问题关闭或全视觉PASS。流中未闭合公式及终态渲染分列（CV-04）。

| 图 | 原图与尺寸 | 实际观察 | 限度 |
| --- | --- | --- | --- |
| 1 | [stream-in-progress.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-live-Anthropic-模型-经真实代理在最后分块释放前显示中文/stream-in-progress.png>) · 1280×720 | 1280×720：Anthropic模型、用户问题与“第一段中文已经到达。”正文清楚；状态为“正在回答0s”，输入区蓝色圆钮图形似上箭头。 | 单帧不证明是否仍在流中或停止/发送按钮语义；CV-03像素观察保留。 |
| 2 | [stream-in-progress.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-live-Responses-模型-经真实代理在最后分块释放前显示中文/stream-in-progress.png>) · 1280×720 | 1280×720：Responses模型与首段中文可见，侧栏和输入区完整；“正在回答0s”旁圆钮图形似上箭头。 | 与第1图同属CV-03像素观察，不能由过渡帧判交互失败。 |
| 3 | [stream-in-progress.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-live-教学问答模型-经真实代理在最后分块释放前显示中文/stream-in-progress.png>) · 1280×720 | 1280×720：教学问答模型、首段中文和“正在回答0s”可见；蓝色圆钮内白色方形可见。 | 静帧只能读到图形，不证明取消操作或分块先后顺序。 |
| 4 | [models-1024.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-live-模型发现追加、默认模型同步、表单冲突保留/models-1024.png>) · 1024×900 | 1024×900：模型与连接区域显示3个连接/4个模型，模型卡为两列，文本和添加连接按钮可见；减少动画旁空方框与灰色开关并存。 | CV-02像素观察保留；未检查两个控件的DOM语义或操作。 |
| 5 | [models-1440.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-live-模型发现追加、默认模型同步、表单冲突保留/models-1440.png>) · 1440×900 | 1440×900：三张模型服务卡横向排布，添加连接卡在下一行；导航、搜索与计数可读；减少动画旁空方框和灰色开关可见。 | 同CV-02；不能从卡片画面证明模型追加、默认同步或冲突保存。 |
| 6 | [models-390.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-live-模型发现追加、默认模型同步、表单冲突保留/models-390.png>) · 390×900 | 390×900：移动品牌、设置横向标签、问答模型操作和单列卡片可见；减少动画空方框/灰色开关与标签左侧窄空框均可见。 | CV-02同视口现象保留；下方卡片超出画面为纵向截取，未证明横向标签可达性。 |
| 7 | [chat-answer-1024.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-live-长回答-Markdown-公式与响应式布局/chat-answer-1024.png>) · 1024×900 | 1024×900：中文标题/列表、E=mc²、三列表格与代码块可读，底部输入区完整；回到最新浮钮覆盖代码块底部附近空白。 | 仅当前滚动位置；后续段落在内容视口边缘截断，不是全文或滚动交互验收。 |
| 8 | [chat-answer-1440.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-live-长回答-Markdown-公式与响应式布局/chat-answer-1440.png>) · 1440×900 | 1440×900：长回答标题、列表、公式、三列表格与代码块清楚，浮钮位于代码块下沿附近；侧栏与输入区完整。 | 不能据静帧证明全部长回答内容、公式源码逐字或滚动位置恢复。 |
| 9 | [chat-answer-390.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-live-长回答-Markdown-公式与响应式布局/chat-answer-390.png>) · 390×900 | 390×900：段落换行、E=mc²、三列表格和代码块在画面内；回到最新浮钮直接遮住代码两行部分字形。 | 明确保留CV-01特定滚动静帧遮字现象；不能推断永久遮挡或按钮点击/可避让行为。 |
| 10 | [chat-empty-1440.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-live-长回答-Markdown-公式与响应式布局/chat-empty-1440.png>) · 1440×900 | 1440×900：空会话品牌图标、欢迎文字、输入区和三枚提示胶囊完整；侧栏无历史会话文案可见。 | 仅该空态像素；不覆盖所有主题、字体或空态交互。 |
| 11 | [reasoning-restored-mobile.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-Anthropic-模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-restored-mobile.png>) · 390×844 | 390×844：Anthropic完成态中结论a²+b²=c²、分式/根号和两段正文可见；展开推理区含E=mc²，末尾在固定高度边缘截取。 | 不以静帧证明刷新恢复或推理先显示/后折叠；推理余文不在本帧内。 |
| 12 | [reasoning-streaming.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-Anthropic-模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-streaming.png>) · 1280×720 | 1280×720：Anthropic“正在推理0s”、代码块中的美元符号原样和未闭合尾段$x+y可见，输入区白色停止方形可见。 | 这是流中静帧；未闭合尾段暂态不视作终态公式失败，时序依动态用例。 |
| 13 | [reasoning-restored-mobile.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-Responses-模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-restored-mobile.png>) · 390×844 | 390×844：Responses完成态，结论公式、分式根号与完整两段正文可读；推理栏下端截取，输入区与模型短名可见。 | 只证明可见渲染，不能由截图证明恢复存储或展开动作。 |
| 14 | [reasoning-streaming.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-Responses-模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-streaming.png>) · 1280×720 | 1280×720：Responses推理态，代码美元符号与未闭合尾段原样可见；主内容、模型标记和输入区未重叠。 | 未闭合公式的完成/刷新处理以已通过动态用例为依据。 |
| 15 | [performance-20k-terminal.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-性能：20k-推理-正文公式受控流/performance-20k-terminal.png>) · 1280×720 | 1280×720：20k终态标题可见，画面显示多组正文a²+b²=c²和居中E=mc²；输入区完整。 | 仅末端可见公式；静图不能证明20k字符总数、性能耗时或SLA。 |
| 16 | [performance-50k-terminal.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-性能：50k-推理-正文公式受控流/performance-50k-terminal.png>) · 1280×720 | 1280×720：50k终态标题与重复正文/块公式可见，输入区和模型标记完整。 | 仅末端截图；不据此判50k总量、帧率、资源上限或性能恒定。 |
| 17 | [reasoning-follow-paused.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-推理滚动：流式跟随、主动上滚暂停与回到底部恢复/reasoning-follow-paused.png>) · 1280×720 | 1280×720：推理跟随验收“正在推理5s”，面板显示约第13至28行中文，顶部文字在滚动容器边缘截取；输入区保持完整。 | paused文件名不是动作证明；静帧不能证明主动上滚后的暂停跟随。 |
| 18 | [reasoning-follow-resumed.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-推理滚动：流式跟随、主动上滚暂停与回到底部恢复/reasoning-follow-resumed.png>) · 1280×720 | 1280×720：同推理面板“正在推理5s”，可见行号约27至40，文字在面板内换行；输入区没有与推理区重叠。 | resumed文件名不证明恢复动作或滚动位置；以动态用例断言为依据。 |
| 19 | [reasoning-follow-streaming.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-推理滚动：流式跟随、主动上滚暂停与回到底部恢复/reasoning-follow-streaming.png>) · 1280×720 | 1280×720：“正在推理4s”，面板显示约第20至35行，正文密集但保持在固定高度区域，底部输入完整。 | 不能用静态行号差异推导自动跟随/抢滚动或时间性能。 |
| 20 | [reasoning-restored-mobile.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-教学问答模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-restored-mobile.png>) · 390×844 | 390×844：教学问答模型完成态，结论、分式根号、两段正文与输入区可读，展开推理下部在视口边缘截取。 | 同三协议移动完成态的可见范围；不覆盖完整推理内容或恢复逻辑。 |
| 21 | [reasoning-streaming.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-教学问答模型：推理先显示，正文出现后折叠，公式与恢复正常/reasoning-streaming.png>) · 1280×720 | 1280×720：教学問答推理态含字面美元符号代码与未闭合$x+y，模型标记和停止方形可见。 | 流中暂态观察；不能替代原文逐字、公式转换或取消的运行断言。 |
| 22 | [body-math-restored.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-正文公式：text-delta-原文逐字保留并在流中、终态及刷新后渲染/body-math-restored.png>) · 1280×720 | 1280×720：正文公式恢复图中矩阵u=v+at/v=v0+at、美元符号代码、q/r²及补齐x+y=z均可见，两段正文完整。 | 静帧只证明可见公式；不能据此证明刷新读取或原文byte一致。 |
| 23 | [body-math-streaming.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-正文公式：text-delta-原文逐字保留并在流中、终态及刷新后渲染/body-math-streaming.png>) · 1280×720 | 1280×720：正文流中矩阵、E=mc²与代码美元符号可见；底部保留转义符文本和未闭合$x+y，输入区为停止方形。 | CV-04流中公式暂态保留；是否逐字保留/末包补齐由动态用例验证。 |
| 24 | [body-math-terminal.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-正文公式：text-delta-原文逐字保留并在流中、终态及刷新后渲染/body-math-terminal.png>) · 1280×720 | 1280×720：正文终态矩阵、q/r²及x+y=z渲染可见，末段已释放；代码中的美元符号仍为字面文本。 | 终态像素与第23图暂态分列，不从静图推导逐字转换、事件或存储正确性。 |
| 25 | [reasoning-post-answer-follow.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-正文开始后推理继续增量：用户重开后仍跟随，手动上滚不被抢占/reasoning-post-answer-follow.png>) · 1280×720 | 1280×720：正文后继续推理图显示“正在回答6s”，展开面板内约22至40行及正文“正文已开始，推理仍在继续。”可见。 | 不能凭follow文件名判定跟随、重开或正文后事件顺序。 |
| 26 | [reasoning-post-answer-paused.png](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/chat-r4-first/artifacts/chat-reasoning-正文开始后推理继续增量：用户重开后仍跟随，手动上滚不被抢占/reasoning-post-answer-paused.png>) · 1280×720 | 1280×720：同场景“正在回答7s”，面板显示约27至46行中文，正文仍位于下方且输入区完整。 | paused文件名/不同滚动行不证明手动上滚不被抢占；只记录可见布局。 |

26张原图每张的path/bytes/前后SHA和manifestSHA见同名JSON。图源未复制、编辑或重拍。滚动跟随、三协议先后、取消、刷新恢复、原文逐字和20k/50k耗时只引用另行通过的动态用例，不据静帧推断。

manifest前后SHA：`1b3f631e8769923b7706d32ab2cd0af5629887abe5462d3115d1a9bcd63519b8`；chat receipt SHA：`cff6310f78fea05044d3ec1e5ef3776a31741271c099aa9d68d6a212e1916a05`；results SHA：`a2426b59ad7a274a636420491687e84b24a7dee50b30dd548a47ca8e1b5e6371`。

待CTRL完成自有服务正常退出、来源/构建/历史与文档最终收口；本报告不关闭G2或宣称B5已实现。
