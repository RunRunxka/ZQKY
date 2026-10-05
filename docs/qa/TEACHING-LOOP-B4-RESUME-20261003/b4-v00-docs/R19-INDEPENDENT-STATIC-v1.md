# B4-R19-INDEPENDENT-STATIC v1

独立审查者：`/root/g1_resume_browser`。2026-10-03，只读冻结候选 r19；全部 live source 读取已停止，仅新增本 MD/JSON。候选 SHA `83196c9e3bc5c9c3548f05be1d0b569dd9add562de2d3031fc9e07e1d1db2d71`。

结论：共同来源、原断言保留、三个工具守卫静态通过；P 的附件异常可能覆盖主体首败，保留一项红项。CTRL 已接受窄修复，但本报告不放行业务、不关闭 B4。后续 r20 必须另审，不能将新字节算作 r19。

| 实际只读核验 | 结果 |
| --- | --- |
| 当前产品 / 可执行 QA / 契约 / 构建 | 879 / 53 / 5 / 2007，逐文件 SHA 零漂移 |
| 当前 source / QA / build 文件清单 | 无新增、无缺失 |
| 昨日历史保护 / 今日已完成证据保护 | 3043 / 64，逐文件 SHA 零漂移 |
| 原前端 / 原后端业务共同源 / T70 作者源 | 451 / 367 / 14，逐文件相同；后端 368 中仅 API AGENTS 指南变化被明确排除 |
| 旧 QA / 原保护 / 原构建 | 45 / 1150 / 2007，相同 |
| 分支、HEAD、next-env | main / `6aeb57280f6a7e0d7391cad4d150745479ea58ec`；296 字节原件精确相同 |
| 构建身份与实际 rewrite | `Ji-Jz8X9yY2R_79JOPivD`；真实 manifest 代理 8001，与冻结值相同 |

r17 至 r19 仅根 AGENTS、API AGENTS、目标 books QA 源变化，新增 recovery helper；产品前端及后端业务源码未变。全部输入与逐文件 expected/actual SHA 留在 JSON。

静态 TypeScript AST 实际 exit0：原六个标题、其他五个 callback、八个顶层函数字节相同；扣除唯一新增 import 与目标 test，模块其他范围字节相同。原 49 个 matcher 全文按原顺序保留，目标原九个保留；只追加三个 matcher。原目标 `30000×2`、`120000×2`、`180000` 预算及 `await second.close();` 保留。P r18→r19 仅第 54 行 pages 集合类型注解，两个标题及全部 matcher 全文相同。

新 helper 只读存储，经真实可见且可用的“继续生成”按钮恢复；唯一 book/page/note 与 URL、compiling/ready 状态及异常横幅严格核验。真实 stored ready 与 strip 消失才完成；绝对 deadline 不重置；最多一次已武装的 Playwright 点击；错误、再次中断或超时均拒绝。cleanup 幂等，等待 result 并释放 observer/timer/listeners/handle。目标主体首败优先于 cleanup/close/attach 异常，资源断言仅主体成功后执行。

P 两场景分别通过正常 UI 与显式本地模拟整页失败 UI 创建真书、保存真笔记，独立读取完整记录与 native/legacy 锁，另设 DOM capture listener 核 trusted 0/1 点击、stage、路径与点击时原包；同 runId、笔记/全部书籍 ID、finished/ready、所有页可读及清理 flag 均有断言，没有直接种入成功存储。这里只证明 QA 设计，未执行两场景。

工具静态复核：candidate.py 16/19/92–115 行硬绑定原 baseline SHA、原 next-env SHA、冻结 count/manifest 与今日 prior；run_check.py 33–61 行从真实继承环境/default 推导三个 external config 的绝对输出，Popen 前拒绝复用。83–126 行仅持有本次 Popen，异常自然等待后必要终止该句柄并等待，实际记录 child/pipe/log 状态与原异常；descendant/API 释放明确待另核。三执行卡要求此 launcher；配置不加 worker 重加载误伤守卫。四 Python 文件仅 AST 解析，未执行。三配置、stream wrapper、原 fixture/协议/finally 未改变。

红项 **R19-P-METADATA-01**：`b4-v00-e2e/r14-recovery.spec.ts` 254–267 行，catch 已记录并重抛主体失败，但 finally 中 `await info.attach(...)` 无捕获，其拒绝可以覆盖该失败。CTRL 授权下一候选仅捕获此附件异常并加入 cleanupFailures，保留所有业务 matcher/UI/操作/timeout/helper。原 r19 P SHA `6ca6f9281f1e1e13861db15c85c860a126c5d7ca1e23557b5b92e9b4287777a8` 封存于本 JSON。

旧 check1110、API1698、P64、T70A8 和第六 B4 浏览器保留原候选/收据身份，没有今日重跑。重新核收据 SHA、已提供日志 SHA、T70 194 个 artifact、浏览器 chain/HTTP 收据/trace SHA；P 两日志原收据没有 expected SHA，因此仅登记当前 SHA 与原字节数匹配，未伪称原 SHA 已比对。第六 trace `ab6cf7bf4d8e95e5e6e3e45c289b1c4d68db0adeb0b710af57fe2048dfaa4439` 仍同。

实际 inline Python 散列审计 exit0 / 1568.038ms，installed TypeScript AST exit0 / 37.5121ms，最后历史绑定 exit0 / 127.156ms；argv 与完整输入/检查留 JSON。四次只读展示或字段查询错误也记录：PowerShell 空管道、旧候选 buildFiles 字段不存在、目标标题初次匹配错误、P 日志不在保护映射；均未执行业务或改冻结源，纠正后的有效核验结果单独保留。

未运行测试、collect、build、浏览器、HTTP、服务、业务 Python/TS 或数据操作；不触碰 formal env/data、用户进程或历史原件。未认证真实模型教学质量、Word/WPS 人工布局、正式迁移或 B5。报告完成后停写。
