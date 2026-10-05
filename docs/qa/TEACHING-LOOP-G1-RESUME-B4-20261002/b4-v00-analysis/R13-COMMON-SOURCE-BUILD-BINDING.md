# R13 最终共同源、前端与构建身份独立绑定

结论：**PASS（静态来源/构建字节/既有收据身份）**。候选 `CANDIDATE-b4-r13-ui-final.json` SHA256 `68b9222de673e2abd6601c1001a6198b3e8e1d84276a1a1a483d2a1885f2327b`。本审阅在 CTRL 构建完成并恢复 next-env 后，独立前、后两次核 **878 产品 / 43 QA / 5 契约全量0漂移**。

r13 的451前端文件全部匹配冻结和实际字节；相对 r9/r10 原前端448份不变，严格只改 LearningAnalysisWorkspace.tsx、原模块单测和 styles.css 三份已声明文件。CSS scoped block/选中 metadata inherit、手动/终态报告与当前历史同步的独立静态审查保留。r12→r13 只改变 Workspace 中 stable reload 的显式解构和 callback 名称/依赖：逆替换可精确还原 r12 文件 SHA `1816f14a671a1edf8790d64e425a682060e487e9b4ed72b2e6e239d46bb33432`。取的是相同 stable 函数，没有换成随 render 变化的 resource 对象依赖，旧源 epoch/abort/key 和 adopt 身份去重行为不变；QA43/契约5与 r12 完全同源。

真实新 `BUILD-IDENTITY-b4-r13.json` SHA256 `fb25165fa1c0d25dda45f519a8a5876094ad29815fb99bb745fd5a6fc2612d42`；BUILD_ID **ST2AWsfwxRYxFKZb_qsip**。独立枚举其相同排除规则（cache 与 trace/trace-build 除外）下实际 **2007 文件**，清单无新增、缺失、漂移；逐文件散列前后均0漂移。实际 BUILD_ID 相符，routes identity API proxy 指向8001，next-env SHA为原 `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`，恢复收据确认构建临时字节已精确恢复。本审阅没有沿用旧 r5 构建作为新前端依据，也没有执行构建或操作前端服务。

CTRL canonical `check-ui-final-first` 原真实命令收据绑定 r13：**exit0 / 104654.563ms**，完成时间与完整日志SHA匹配。日志明确串联 typecheck、ESLint `--max-warnings=0`、单测 **111 files / 1105 tests passed**、生产 build compiled/static17页完成。r12 首轮缺 resource 依赖的 lint exit1及未执行 unit/build事实仍保留，没有用这一轮覆盖旧失败；实际 type/lint/unit/build完成是 CTRL 执行结果，本 Agent 仅读取验证。

**后端与原验收证据绑定。**apps/api 全部业务/配置/测试/夹具及 tests/fixtures8原件合计368项，当前实际字节与 r9/r10全部相同。32根级共同输入亦精确同源，共享契约5份不变。r9 全 API完整日志 **1698pass/1skip/exit0** 原SHA与收据匹配；变化只在三份前端文件，后端与 API测试均相同，因此按精确同源保留，原执行候选仍记为 r9。

P 实际 r10 owner-fixed-second 原四执行QA、全部后端/夹具精确同源；QA manifest SHA与原收据相符，exit0/真实processExited/两流关闭/日志独占读取收据完整，stdout逐案例有64条唯一PASSED，与summary64pass/0fail/0skip/0setup error及64案例逐项passed交叉一致。不是在本轮或r13又跑一次P64。

独立 A 实际 r2固定-first **8场景/165HTTP/exit0** 原完整20k证据/100分页和前后零漂移保留。T70作者14项（6业务源/7测试/1脚本）与作者/r2/r13及实际文件全部同SHA，A原4QA也同源；相关固定 facts/Analysis分支/教学owner与快照来源路径未受三FE改动影响。因此按共同源绑定已有A8，不重标执行候选或重做规模测试。

本报告只证明上述身份和适用范围，**不是新的真实浏览器视觉验收或B4最终关闭**。P原两例在r13的独立行为收据、F第五轮新构建下真实全链及手机截图/对比度、后续适用E2E/chat由各验收者及CTRL独立收口。保护历史1150条的零漂移是CTRL报告，本审阅没有另重哈希整个旧保护集合，不把它混入独立878/43/5与2007检查。

仅写此 MD/JSON；未 app.main/test/collect/HTTP/service/data/Git 动作，未改产品/可执行QA。所有 .next读取均在收到新构建完成放行后进行。报告完成停写。
