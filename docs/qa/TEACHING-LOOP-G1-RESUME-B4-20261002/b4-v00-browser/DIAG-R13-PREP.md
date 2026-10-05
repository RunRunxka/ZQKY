# B4-F-R13 — 原第117例导航首败与独立QA准备

分类为产品导航/标签选择回归，原E2E正确预期保留。第117例真实人工确认POST200，返回failures=[]和1正式题；查看已入库按钮点击实际完成。末次expect在10000ms内13次得到library aria-selected=false，最终导入批次选中。不是确认后端失败或只缺一个立即URL读取同步。

精确trace为 `b4-e2e-real-first/artifacts/question-bank-real-真实-AI-补题-queued-0→attempt-1→人工校对确认→知识点检索/trace.zip`，105条完整CRC、SHA `ccedf777c065f40e7801d6d44513b55fb7c189ae5ca7e34f06cb6ac3fb0fbfa0`。确认POST于333578.069ms、response资源 `a4705ce5896a82852afb106b966a9161ede74079.json` 为200；点击 `pw:api@114/call@6538` 333610.693→333639.661ms完成无error。随后 `expect@116/call@6542` 333641.773→343658.819ms超时，主帧afterSnapshot343656.382ms URL实际是 `http://127.0.0.1:5174/question-bank#library#library`，imports=true/library=false。先前beforeSnapshot333643.996ms仍是import详情。新RSC GET333637.577ms到/question-bank?_rsc=…返回200。

双fragment是实际浏览器URL采样，已只读核安装Playwright：snapshotterInjected.js:537直接取location.href，snapshotter.js:99原样存入frameUrl，不是本QA额外拼hash。具体Next缓存、commit和hash追加因果仍未通过trace直接证实，不先认定框架根因，也不升级或改依赖。

冻结源码依据：QuestionBankWorkspace.tsx:47–51仅挂载[]读取一次hash，严格等于#library/#generation；初始化imports。薄page目前只白名单returnPracticeSetId，缺显式tab意图；ReviewWorkspace onOpenLibrary只有hash URL。因此迟到hash或观察到的重复hash不能可靠承担明确打开已入库页的产品意图。最小方案是CTRL登记受限tab=library|generation|imports并通过实际server page传requestedTab，显式query优先、初始化/同步工作区；手动切换同步query，保留旧hash兼容。已有QuestionLibrary的generationOpen是初始props useState，需明确处理同已挂载library收到generation新意图的情况（可由Workspace最小key/生命周期处理），不能只传新initialGenerationOpen后声称面板已开。

独立准备恰两例，真实serverpage/Workspace/QuestionLibrary均不替换；补题内容、列表/分类数据与无关组件为显式替身，只验导航。受控hash晚到和重复hash，不随机重试；验证query选库/已有库query补题、编码return context、手动tab查询意图与legacy #library/#generation。没有猜测新Workspace prop，没有改原测试或原断言。

新增源SHA：r13-navigation.test.tsx `183e71e0a1a8f361630825b2fc654c0102076ee4255a7f1503215b7c2d584315`；vitest.r13.config.ts `73cd980526f787f4c213d2fec3a93499eb0f4c654b9e12c701c1607bc687cf21`。精确原source SHA、原before/after trace片段、响应原合成JSON和prepared边界见 DIAG-R13-PREP.json；任务和待冻结命令见R13-NAV-TASK-CARD.md。

当前红测、types、seed、browser与服务均未执行。所有exe源已停写，等待CTRL正式候选冻结与单轮红测授权。未写产品/原QA/旧证据，所有ZIP已关闭。
