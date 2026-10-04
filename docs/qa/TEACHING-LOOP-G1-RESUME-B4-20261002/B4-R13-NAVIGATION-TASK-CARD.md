# B4-R13 导航修复任务卡 v1.0

CTRL/root 独占实现；F/g1_v00_fe 独立正确行为；A/g1_resume_browser 只读设计与最终差异审查；P/g1_resume_e2e 原全量门禁。共享 main/6aeb57280f6a7e0d7391cad4d150745479ea58ec，不进行 Git 写入。

## 首败与范围

稳定 r13-ui-final 原24 spec/153 case单轮为152通过、1失败，无跳过、重试或flaky。第117例真实模型候选经过人工修改、校对与确认HTTP200后，点击“查看已入库题目”，已入库标签仍为false。trace最终实际URL是 `/question-bank#library#library`。这是导航产品回归；不据此推断Next内部原因。原E2E和首败所有原件保留。

产品可写：`apps/web/src/app/question-bank/page.tsx`、题库 `QuestionBankWorkspace.tsx`、`QuestionLibrary.tsx`、`ReviewWorkspace.tsx`、`QuestionBankWorkspace.test.tsx`、`ReviewWorkspace.test.tsx`；另根README的已实现/验收边界文字。其余源码、API后端、依赖与锁、既有B4契约不改。CTRL独占CURRENT_STATUS/API/ROUTES/批次新增权威文档。

## 导航契约与验收

- 正式query `tab=imports|library|generation`，薄server page读取并验证非重复、合法值，传递显式意图；query优先于legacy fragment。
- 确认入库返回canonical `?tab=library`；有练习context时保留编码的 `returnPracticeSetId`。手动标签同步local state与query；同已挂载组件收到新意图能正确切换。
- legacy `#library`/`#generation`继续兼容；generation在已挂载库上到达也打开真实补题面板，保留库筛选状态，关闭后不凭同一不变prop重复打开。
- 不引入第二后端、不调用模型作为导航副作用、不读用户浏览器草稿。浏览器API仅生命周期内访问。
- 现有Review两条URL契约期望由hash改query，明确登记为契约更新；原测试集合及其他断言保留。原153 E2E与完整B4浏览器断言不删不放宽。

F新增独立2例使用真实薄page、Workspace和QuestionLibrary，受控迟到/重复fragment、query library/generation、context编码、手动标签和legacy兼容。准备后停写；CTRL冻结诊断清单；先单轮红测实际退出与前后散列闭合，之后root才实施。固定候选后独立原2例复验、相关作者单测与完整check；新build仍由用户手动停止/启动5174，root只核验归属。新构建再跑完整B4链/三视口/手机、原全量153和原聊天14。未完成前B4保持未关闭。

## 证据与资源

产品before字节与SHA写新 `b4-root/R13-NAV-BEFORE.json` 及 `.before.txt`，独立QA文件SHA见F任务卡。每轮单独命令/真实exit/计数/耗时/日志/临时根/散列，不覆盖首败。后端仅本批新隔离根与8001；每次独占并关闭连接/进程/日志，保留目录。用户5174不由Agent结束或重启。
