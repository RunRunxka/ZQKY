# B6-UI-QA-COLLECTION v1

2026-10-04，ROOT授权 g3_impl 仅修 own `b6-integration/browser.config.ts` 的测试收集排除规则。ROOT构建与产品STOP，候选530005e…/LkFgY8qsEnCOUbC11Dm1T保持。

browser-r7显示Running15tests，而本路实际业务测试仅1条；QA第一轮失败归档 `source/**` 包含旧spec，被默认递归收集。先存原config/收集输出/当轮CLI身份与停止结果；不将多份归档执行计入验收。自有Popen CLI及由它持有的PW子树可按持有handle/PID出生命令关闭，用户与未知进程不操作，全部TEMP/日志/输入保持。

最小变更只给既有testIgnore追加`**/source/**`，保留`**/qa-source/**`，不改spec、业务断言、trace:on、0retry、timeout或产品。执行前新标签`--list`确认严格1条，留收集日志/命令/QA SHA。新config STOP后直接browser-r8新完整单轮，失败先分类不续改；成功交RESULT-final-v1新叶。独立V00审收集差分和实际trace/JSON/图。旧r7和以前全部首败保持，不拼结果。
