# B4-V00-A v1 首轮 · 停止，独立 QA 过严

候选 `CANDIDATE-b4-a1.json` SHA256 `95e10b6cb927422688a21a163477e275dc70619c99dff9f4a2c06a1e87ae50af`。本验收者此前为前端作者，本轮仅独立验 T70 后端。可执行 QA 四文件身份见 SOURCE-MANIFEST.json，执行期间无产品或 QA 源变更。

正式执行首轮 exit **1**；完整场景通过计数 **0/8**，第一场景于第 32 个真实 HTTP 请求后停止。该计数不将已完成的局部断言冒称整场景或 T70 全验通过。

首败为 `probe_analysis.py:147/247`：GET `/api/v1/analysis-runs/foreign` 返回 HTTP404、`ANALYSIS_NOT_FOUND` 及非空 message/requestId、retryable=false；独立 QA 通用错误信封检查错误地强制要求 `details` 字段，抛 `AssertionError: missing error-envelope field details`。

只读核现行 `contracts/teaching_loop.py:ApiErrorEnvelope` 声明 details 可空，`schemas/errors.py:error_response` 仅在 details 非空时输出。此响应符合现行错误信封约定，归因为 **独立 QA 过严**，不是 T70 产品反例。本轮原样保留，尚未调整 QA 或重跑。

首败之前实际执行了 202 接受与非 ready 的四种报告409、提交同包重放／异包409／新提交同固定输入复用、真实 JobEngine 完成、全四人总分900/null/null/800整数单位（9/null/null/8分）、8学生知识点行、2班级行及全12证据分页、来源富内容、14错误返回包变体拒绝，以及真实筛选分页／历史列表筛选。原始包与错误变体拒绝收据在 run-first/probe；这些是局部已执行事实，不代表整场景完成。

**未执行**：原始备注／服务缺失及第一场景剩余断言；其余7场景（额外 missing/exempt/retake、多班历史变更、损坏源／创建故障、全子表 seal、发布故障／公共重试／取消、失效租约及原 attempt CAS、200×100全20k及冷热性能）。原因：首败即停止。

资源和执行收据：2026-10-02T12:18:27.7405525Z 至 12:18:30.8089702Z；现有 venv Python3.12；launcher PID13776，probe PID6224 已退出，Python进程1701ms，探针1413.069ms。test/UTF8/credentials_file=None/空教材源/16333/embedding9 在 app.main 前已核。临时根 `C:/Users/96022/AppData/Local/Temp/zqky-b4-v00-a-68f9e5181e9345e6888f6c9e9222cfbd` 全部保留。

没有启动任何监听服务。create_app+TestClient 生命周期已关闭；日志中的127.0.0.1:8001只为 TestClient base_url，没有连接既有8001或5174。PID6224已退出且无所属监听，前端未触碰。

执行前 PRE-AUDIT-first.json 核877产品+15可执行QA+4共享契约共896项；探针候选 before/after 各896项，全部 **0漂移**，next-env原字节未变。P/F独立QA准备目录明确不属于本轮A候选；此处没有冒称它们被本轮冻结审计覆盖。

执行准备路径更正：CTRL首次给出的 b4-root/CANDIDATE-b4-a1.json 不存在，只读 rg 找到本批顶层文件；核 SHA 与授权一致且CTRL随后确认才启动首轮。这是准备路径问题，不是业务 probe 首败。

证据入口：run-first/receipt.json、stdout.log、stderr.log、hardware.json；probe/first-failure.json、result.json、candidate-before.json、candidate-after.json、literal-base-full-packet.json、oracle-rejected-wrong-outputs.json、http/0001.json…0032.json。44文件，512871字节。首轮 stdout/stderr/JSON没有覆盖，等待CTRL决定最小QA适配、重冻和全轮重跑。
