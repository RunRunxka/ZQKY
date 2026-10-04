# G2-V00 浏览器独立首轮结果 v3

2026-10-03，北京时间。状态 QA_WORKER_SETUP_FAILED_BROWSER_BUSINESS_NOT_RUN；G2保持打开。绑定r3 SHA4cb87b15870799f638c6c48527f8fbed34013ac9c9a74a41ec09d27e42168034，真实运行资源API4204/8001、frontend19604/5174、buildY6c5E7notWcBElEjX1GF_，新runtime TEMP与seed身份完整封存。

一次运行CLI PID23340、exit1、1536.616ms，worker9124。Playwright收集8例，报告1个worker/setup failure、7 did not run，业务case执行0、通过0，retry0；没有生成trace/png。不能把准备或框架入口失败记成R01业务断言失败，也不能把7个未执行写成跳过后的成功。

真实原因是external.config.ts:9的防复用guard：主进程首次加载时新browser-artifacts不存在，收集成功并创建本轮输出目录；worker随后重载该配置，guard看到本轮自己创建的目录，误判旧目录并抛 Refusing to reuse an earlier G2 browser result directory。首例0ms且栈在配置而非业务步骤。源/QA原字节、JSON/XML、完整日志及原输入before.txt保持；未重试、未改配置。

rootrun_command原argv/env/exit/ms/PID/source/QA before/after完整保留，source886/QA304均零漂移，childClosed/logsClosed true；next-env前后相等。启动前已封存candidate、v7manifest、spec/config、seed与服务身份精确字节；seed SHA b3f75e0abb03badd6bd5855521b66888b505db5c382e4762c8445dce7990884d，数据仅新系统TEMP，凭证None。外部服务由CTRL持有，本Agent没有起停操作。

CLI及worker已退出，本失败阶段未创建测试浏览器context；没有待关闭自有context。全部生成目录/metadata/TEMP/input snapshots保留。已通过的23组件+11真实API RESULT-v3保持独立事实，原件不改；此浏览器结果不覆盖unit/API结论，也不据其通过关闭G2。

当前停止后续，等待明确QA配置适配与新候选/新运行卡。没有写产品/QA、权威文档、Git或正式草稿/凭证，没有重跑或拓预算。
