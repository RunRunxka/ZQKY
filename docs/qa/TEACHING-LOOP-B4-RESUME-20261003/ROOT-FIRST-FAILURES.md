# 今日首败记录

准备时点历史：首败原件保留，各轮分别计数。昨天152/1书籍中断及其它首败仍在昨日历史报告，不追改；准备时尚未执行业务回归。现已实际完成固定后两UI 2/2、原聊天14/14、原全量153/153；以下原首败正文保持。

- root初期只读读取不存在的根tsconfig.json报Cannot find path，未运行业务或改源；后续使用实际apps/web/tsconfig.json（若需专用测试TS配置另声明）。
- A起点SHA审计的首外层包装过早解析尚未完成的空增量输出，原审计只是读取/散列；实际新审计exit0/974.9698ms/0漂移，不能算产品fail或测试pass。具体收据见独立DAY-BASELINE-AUDIT。

准备期审查事项（不是已发生业务测试fail）：独立文档v1发现4处旧启动/等待/链接残留，CTRL修正后v2关闭，原v1保留。CTRL读取R14-QA v1发现finally清理assert可能覆盖主体首败，要求v1.1仅补首败保留逻辑；v1静态收据保留，不当作v1.1检查结果。

- CTRL准备期只读rg误列不存在的ScenarioSettings.tsx/BookReader.tsx路径，actual exit1/os error2；无写入或业务执行。随后rg --files核实实际ScenarioSettings位于BooksRoute.tsx、阅读器为PageReader.tsx，correct lookup exit0；合法UI故障标签和strip文案已读实际源码，不影响产品门禁计数。

## r18 QA联合static首败（尚未业务执行）

qa-types-first：child exit2/PID12208/2214.16ms，独立r14-recovery.spec.ts第199/243行TS7006（pages.filter/every item隐式any）；完整命令收据和log保留。同期qa-lint-first exit0/PID7084/3109.518ms，两轮newOS根保留。r18前后879/53/5/2007/3043与next-env/head/build/保护全部0漂移；不因lint通过放行。仅拟集合显式类型补全、不改运行行为/oracle/原期待/timeout，修后新r19候选与新static单轮，不覆写r18。

准备工具独立静态发现3项保护缺口（未启动任何服务，未发生覆盖或泄漏）：candidate未核冻结baseline/count/nextenvSHA、结果run目录可被新label复用、launcher异常未等待自有child/关闭stdout。接受只改ROOT两工具的守卫与诚实生命周期记录；不改变业务/原spec/config超时，待新r19与独立复核。

- CTRL准备期rg误列不存在的question-bank-f20i/textbook-f10-real spec及Windows字面*.ts路径，actual exit1/os errors2/123；随后rg --files正确定位assessments/question-bank-real，原自管API Windows finally为taskkill /T /F＋closed事件/日志收口，执行卡已修正不宣称优雅退出。未运行测试/服务。
- A r19首inline哈希脚本误用旧candidate不存在buildFiles字段KeyError，未写报告/未运行业务；改用旧独立binding buildPre实际字段新单轮哈希audit0，详情纳新独立R19报告，不把包装首败算产品失败。

独立r19静态：全共同源/AST/三工具守卫通过；P finally附件info.attach若拒绝可能覆盖主体首败的窄边界尚未通过（未发生业务/附件实际失败）。保留r19候选与P字节，仅拟try/catch记录secondary附件异常、已有主体首败原样传播，再新r20冻结，不改变任何业务assert/UI/timeout。

- CTRL r20前端只读首guard actual exit1（Existing user frontend changed）；没有写ready或操作PID/测试/服务。诊断确认ConvertFrom-Json把ISO变System.DateTime，再Parse强转字符串丢4910140小数：错误639265864010000000 ticks，原记录与CIM均639265864014910140，PID/argv完全同。改用已记录Int64 UTC ticks＋DateTime直接UTC ticks新核通过；不能将此包装首败当作服务重启或业务fail。


2026-10-03 r20运行首败：R14独立首轮1通过/1失败，真实Continue点击后4ms误判再次中断；82DOM独立审查确认busy被当作执行恢复。故障终态/ID/锁断言未执行，不据后来的error-context代替ready。两ZIP/4实际PNG/所有收据不覆盖，v2仅修测试判据。root接手时读错chat-resume-first.json（不存在）为只读包装错，随后rg定位实际chat-resume-first-command.json，原14实际通过收据完整，无运行重试。

root只读包装错补记：摘要中R14-FIRST-PATHS.json不存在；rg实际定位为R14-FIRST-ASSERTION-PATHS.json及既有MANIFEST等。未触发测试/服务/重跑，运行首败原件不变。
