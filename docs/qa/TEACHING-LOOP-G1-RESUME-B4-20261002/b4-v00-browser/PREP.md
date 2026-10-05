# B4-V00-F v1 独立验收准备

状态：prepared / 已停写，等待 CTRL 冻结 QA 后明确执行。T80 原作者 RESULT 已完成；原产品、apps 测试、契约和旧 QA 本轮均未写入。这里的独立角色是 FE／浏览器核对，T80 业务独立验收由其他作者承担。

初始候选 `CANDIDATE-b4-r1.json` 877源＋11旧执行QA，SHA `e42edc7f0d74fa29380fb9603d055063302a383480c6a21f7a55f4016310c9e8`。CTRL 已告知之后旧 B0 fixture 登记适配；因此这里只记录原参考身份，正式执行必须绑定 CTRL 新冻结候选。不能将当前准备认作稳定候选已通过。

本目录 11 个新可执行源与 1 个 TS 配置的全部 SHA／字节数见 PREP.json。请把 `tsconfig.json` 同时纳入 QA 配置冻结；类型检查范围依赖它。所有可执行源已停写。

## 准备的验证

- 独立 FE 18 个计划组件案例：保存晚响应与新 CAS、409／422 保留、远端版本显式采用、旧建议拒收、StrictMode／卸载、审核／创建／转换／备注原包、备注晚响应后新输入、错误导出收据／任务／元数据、旧产物过滤及字节不足不下载。组件服务替身只算组件证据。
- 实际浏览器 1 个完整连续链。种子只含初测已确认成绩与 1 正式题，B4 五类业务行必须全零。A 第一／第二人次由真实 T30 建立，初测真实 T60 XLSX 消歧、承认并确认；浏览器实际点击历史固定成绩链接，明确换人次后选 A 第一人次＋B/C/D，固定 literal 总分 A9/Bnull/Cnull/D8、K1 2/3、K2 1/3，12 全题富证据与追加教师备注。
- 练习请求 2 题，正式池只有 1 题，必须真实显示缺口且模型调用仍 0。随后实际手动补题、修改题干、保存、独立校对、正式确认，经保留练习 query 的现有返回链接回练习，再显式采用两正式题。受控 Provider 返回绑定本初测正式 F10 知识点，捕获实际合成 LLMRequest 并拒绝本样本学生姓名／学号／studentId／participantId 出现在请求中。
- 保存 PATCH 真实 route.fetch 后延迟响应，在等待期间编辑分值；验证服务端已存版本与后续本地编辑分别保留，再次保存采用新 CAS。审核与导出真实提交成功后丢响应，未知期间锁定，重试逐字同包／同 submissionId。不会构造业务成功响应。
- 固定完整题号 `16(1)` 与分值2.50/2.00，真正转换真实名单施测、两 DOCX＋当前名单 XLSX 的浏览器下载，逐一核任务／产物／版本／assessment 身份。独立 ZIP 全项 CRC／内容 SHA，学生包整个 ZIP 无教师私有标记，教师保留答案解析，富表格／OMML／真实图片及材料保留，模板学号为字符串、分数空白。
- 直接填写浏览器实际下载的空白模板，再通过 F20 现有映射、承认、确认进入新历史，并实际点击新固定成绩链接创建新 T70。只读四库完整性／FK、真实 score cell、practice node／conversion mapping／analysis item snapshot／evidence 一一对账，旧成绩／旧报告／审核版练习再读原样。
- 1440×900、1920×1080、390×844 四个链阶段画面；文档横溢与可滚动事实表单独记录，真实键盘 Tab 与可见2px焦点。真实 primary 按钮 hover 的正常动画／减少动画帧状态和实际截图 RGB 像素变化，未注入 QA CSS。完整 trace:on，截图待实际人工查看。

## 执行入口（均尚未执行）

由 CTRL 给现有 Node24 绝对路径。以下仅命令方案，不是已运行收据；每个 `run` 参数必须新名称，不覆盖原件。

1. `apps/api/.venv/Scripts/python.exe <本目录>/run.py types <run> --node <现Node24>`：独立 QA 类型检查。
2. `apps/api/.venv/Scripts/python.exe <本目录>/run.py fe <run> --node <现Node24>`：计划18组件案例。
3. `apps/api/.venv/Scripts/python.exe <本目录>/run.py seed <run>`：新 `zqky-b4-v00-*` OS 临时根；输出 browser-seed.json 及四库路径。只进入标准 main TestClient，不监听端口。
4. CTRL 独占 backend.py:app 的8001生命周期。继承 seed 收据外层 env：test/UTF8/ZQKY_QDRANT_URL16333/embedding9/新空教材；显式 Settings.credentials_file=None，导入 main 前核临时根。禁止连接未知8001。
5. 用户旧5174停好后 CTRL build、用户重启并由 CTRL 核新构建／8001代理；随后 `run.py browser <run> --node <现Node24> --seed <CTRL新种子>`。Playwright 配置没有 webServer；浏览器实际核v24.19.0并记录exe SHA。
6. `audit.py <新候选清单> <精确SHA> <本目录新JSON>`：仅读源码、next-env与共享契约身份，不代表行为通过。正式行为前后另由 CTRL 冻结审计。

run.py 保存每次完整 argv／cwd／外层隔离 env／PID／start/end／耗时／exit、完整 stdout/stderr 原字节与单轮计数。浏览器子 Python 的每次完整命令、流、exit／耗时也独立保存。任何首败保全并报告 CTRL，不能边验边修；新源码修改必须另卡与重冻。

## not_run 与资源

类型检查、18组件、种子、实际浏览器、下载／ZIP／像素／DB 核查均 **未执行**，原因是本卡只授权准备，仍等待 CTRL 新候选与执行指令。CTRL 最新只读核对5174监听和原PID6836已不存在，等待新构建与用户手动重启；本 Agent 未替其启动／停止。没有创建数据临时根、监听8001、打开浏览器或使用 Git。

CTRL 另告独立 P 首轮完整题号 `16(2)` 回流出现 `16/16(2)`，该关联链已停止，产品仍冻结等待批量诊断。这里只记录外部已知反例；本 Agent 尚未执行，不能冒称自己的首败或改掉完整题号断言来通过。正式验收等待 CTRL 修复卡／新候选。聊天14集成适用门禁由 CTRL 另行掌管。

不宣称真实模型质量、Word/WPS实际排版、正式库迁移已验。组件替身、源码哈希、准备文件不替代独立实际闭环；B4门槛未因本准备关闭。
