# B4-F-BROWSER real-fifth v1

冻结 r13 的第五轮实际完整闭环单轮通过：1 test / 1 passed / 0 failed / 0 retries，child PID24916、exit0、24647ms，外层 session2379 实际 exit0。冻结 spec 含118个 matcher 表达式（115原件、R08导航同步1、R11历史状态2）；该静态数不冒充运行时断言次数。未改源或重试。Node 的 NO_COLOR/FORCE_COLOR 警告原样保存在328字节stderr，stdout307字节；所有原始流、完整命令与收据保留。

候选 `CANDIDATE-b4-r13-ui-final.json` SHA256 `68b9222de673e2abd6601c1001a6198b3e8e1d84276a1a1a483d2a1885f2327b`：前审199ms、后审198ms，各exit0；878产品/43可执行QA/5契约全部零漂移，next-env原字节一致。本轮绑定新构建 `ST2AWsfwxRYxFKZb_qsip`、2007构建文件、8001代理；构建身份JSON SHA256 `fb25165fa1c0d25dda45f519a8a5876094ad29815fb99bb745fd5a6fc2612d42`。实际前端PID3820/后端PID11984由CTRL核验；本Agent未操作它们生命周期。

新种子 `C:\Users\96022\AppData\Local\Temp\zqky-b4-v00-0wcy3811\browser-seed.json` SHA256 `bb1783bd9568d999401f64e047ad75d7a9653761fa3dd6a81ccaf0dd58865cfb`，与真实标准main ControlledProvider返回完全相同。浏览器从初测历史点击固定成绩分析，显式选择同学生人次，创建报告和备注，再实际完成缺口手动生成、人工改题/校对/确认入库、查看正式题、返回练习选题、晚成功保留后续编辑、原包审核重放、三份下载、转换T30、下载模板写入成绩、真实T60上传映射确认、新T70回流及旧固定事实不变。没有跳到预先完成的B4种子状态。

两处R11新增matcher均是实际成功的Frame.expect：初次 `call@62 / expect@73` 于2581.424→2584.446ms收到“报告 3909f4b1d1304f578f0d7b4df9a4794e · 已准备”；回流 `call@603 / expect@458` 于17906.358→17910.101ms收到“报告 4f7a52deaff148f09fe9c9565d3f11f3 · 已准备”；均matches=true、无error。初次history的白字蓝底“已准备”也已实际查看 keyboard-visible-focus.png。真实import `c40b7573b7494a15ac43b2384eb30c21` 的两次GET均200，响应分别needs_review/confirmed；17个合成身份探针（4姓名、4学号、4学生ID、5participant ID）不在实际模型request及生成提交请求内。真实模型request包含实际目标KP，与chain和测试Provider实际捕获精确一致，调用1次。

三份实际下载均与API元数据、成功Job、受管资产的身份/完整字节数/SHA一致；标准库解压全部条目和CRC核查，学生DOCX全部18条目不含教师答案/解析标记，教师DOCX18条目含标记，模板XLSX10条目实际4人名单/2计分叶、字符串前导零、空白分数。DOCX保留OMML、图片、表格、共同材料且不重复材料，完整题号/满分与固定练习、转换、模板一致。此轮尺寸/SHA分别为学生37639字节/8d93af0d4039ebc79f05dc32214368b1a460401b4ac1219edbb5f5cfab720150；教师37731字节/2237f0bd869ff4cf78acb2378245071be55bbecce4bcdbb90d0ad501916ea415；模板6297字节/152cf9a917f0e30de1a772fcfea341609c8be16fa37ac9d957f02f16621a4c8b。

四库只读oracle实际退出0：完整性全部ok/FK0，逐叶全部2映射为16(1)/250与2/200，practice/paper内容、节点、分值、实际analysis来源一致；回流8证据按手写预期0/150、250/missing、absent/absent、250/200核查；旧报告12证据和原score/matrix/practice固定事实保持原样。独立离线子命令每个单次实际exit0：pixels140ms、download verify302ms、fill295ms、DB139ms，各完整流/命令收据在本轮artifact内，不与browser或旧轮计数合并。

全部17张PNG均由本Agent逐张view。1440/1920/390实际截图及DOM度量无页面横溢或控件越界；实际rich图片、公式、表格和来源映射可读，保存草稿的完整16(1)/2.50可见。Tab键实际focus-visible、solid 2px；正常悬停150ms有running动画，reduce下1e-05s且两帧稳定无running，真实像素分别改变3371/3367。截图仍受main内部滚动位置限制，390px导出阶段截图主要是参测名单，回流截图是实际富证据并未包含history；本Agent不把这些盲区宣称已拍到。CTRL另行实际执行8张mobile补屏/contrast检查（exit0/2085.439ms、0写请求、白字蓝底5.16855556），其证据身份保持独立。

完整trace ZIP472条目全部读取SHA/CRC，无损坏，SHA256 `d8baf1f5c69ac6d31d9a10e6a4a68652998365a2d8f6c6f8434940eca0f45ec4`。页面trace224网络snapshot，其中page pageref API143+route.fetch API7，request trace27snapshot/22API；chain.apiLog139。这些边界分别记录，不相加冒充单一请求数；全部网络均无>=400。Close context `pw:api@532` 23919.186→23930.063ms、request/page/context fixture及AfterHooks均完整无error。trace没有独立page.close/APIRequestContext.dispose显式事件，只据fixture/context teardown完成描述。真实子进程自然退出，所有流完整；离线ZIP文件/只读DB连接均关闭，无自有监听，临时根保留、未删除、旧所有证据未改。

精确chain路径：`H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-G1-RESUME-B4-20261002\b4-v00-browser\browser-artifacts-real-fifth\real-browser-真实-history→明确-03476-下载→转换→T60→新T70；晚响应-未知原包-三视口\chain.json`；SHA256 `36eee41a6827ef7d7cc34893070b598f04a2095d708d14e74ae48790d79ef594`。完整全entry/DB/下载/PII原始合成输入、布局和每个artifact SHA见 browser-real-fifth-evidence-read.json，实际关闭/两R11/真实import响应见 browser-real-fifth-closure-read.json，视觉逐图范围见 browser-real-fifth-visual-read.json。

本轮证据已全部收口并停写；原first图片夹具失败、second导航/500事实、third业务通过而outer1、fourth实际通过但手动发现R11状态问题均保持原样。后续全量E2E与资源最终关闭由CTRL执行，本RESULT不代替其门禁。
