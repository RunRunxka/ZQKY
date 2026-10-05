# B5-QA9-REVIEW-v1 — v9 两处导航等待独立静态复核

- 负责人：/root/b5_r06_review；可写仅本报告 MD／JSON 两新 nonexec 文件。
- 结论：未确认新增 P1/P2，未发现原断言、场景或预算削弱。v9 仅补齐两处导航完成等待，原产品没有增量；本报告不关闭 B5 或浏览器门禁。
- 新 runtime 由 ROOT 另行执行和验收；本审查未运行测试、浏览器、HTTP、SQL、服务或 Git，也未读取新 runtime 结果来宣称通过。

## 绑定与稳定时点

V00 的 RESULT-QA-v9-PREP-v1 在 UTC 2026-10-03T12:37:07.072597+00:00 声明 READY STOP，ROOT 已确认稳定候选。manifest 201 项，SHA-256 389b5afac9d1443b6fc2dc1e0e2a32ed2f1f4224e4d943d7884813e2d0baeb41。ROOT r5 冻结时点为 UTC 2026-10-03T12:37:35.978457+00:00；候选 SHA-256 14405cb6374181599ead4db1dc0cb3e8051c5de858121e4045f3e202e4362891，构建 ID xWWO3VbSMdUiLTwkXdD2x。

独立 raw SHA 读取开始 2026-10-03T12:38:45.777510+00:00，结束 2026-10-03T12:40:24.402658+00:00：产品 938、可执行 QA 2419、冻结契约 33、构建 2004、旧 v8 原件 177、v9 manifest 原件 201 均零漂移。产品／契约／构建与 r4 完整映射一致；r4→r5 的 executable QA 仅增加 v9 三副本，旧项变化 0、删除 0。原 next-env SHA-256 0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc 仍匹配。

## 三副本精确审查

- independent.spec.ts 与 v8 完整 raw 字节相同，SHA-256 f4a5bb69dd7c00dcf91bfc5abd99242441561ae83a08e45469562d1af5e4ea6c。unknown 真实 200 丢回执→继续 B→native Back→两原包一致→dirty、四视口完整业务链、双标签 CAS、键盘和 reduced-motion 均继承原代码。
- external.config.ts 仅 /v8/browser→/v9/browser 的一次 raw 替换；其余字节相同。仍继承根配置 45 秒 test／10 秒 expect，重试 0、worker 1、完整 8 同名场景、fresh 输出保护及无 webServer。
- history-copy.spec.ts 仅 history→current 与 local→current 两段：列表按钮前注册当前文档 pathname 且 method GET 的真实 response waiter；click 后断言 response 200、完整 latestA；再等精确 http://127.0.0.1:5174/lesson-plans?lessonPlanId=编码ID，因精确字符串匹配不含 revisionId；随后等课题 enabled／aCurrent.title，才调用原 fullCurrentData helper。位置为 v9:148–154 与 157–163。

两段各为 7 行且各出现一次。把每段精确替换回原列表 click 单行，整个 history-copy 文件与 v8 raw 字节一致；因此没有隐藏的其他增量。两段 CRLF 块 SHA-256 分别为 39175b065840de322c49f6969a4e52afdd6f45ac1d890b0f76568003512974a7、639099cd3d246e3fcf439771b812b9f088e95d0f875837dea0be6db9dffe9132。

v8→v9 延续 CRLF，没有 v7→v8 时的换行转换。本轮 raw 相等结论不依赖换行归一化；旧 v8 manifest 177 项原件 raw SHA 零漂移。此措辞与前一轮 QA8 的 LF→CRLF 澄清区分。

原 helper、href 保持断言、cache 前后相等、教师全 11 字段手写 oracle、复制意向取消／放弃／文档 B 隔离／历史与本地清意向、后端当前／固定原历史读均不变；没有新增 clock 或 force。6 次 JSON 备份计划保持：prepareA 被调用 3 次，函数内生成 3 次，再加 3 个直接 clean helper 调用。静态 false 调用点是 4 处，不能直接当成运行次数。审查首次只读计数断言把二者混淆，已按调用结构校正，未改 QA。

## 既有 static／collect 实读

V00 static：Node v24.19.0，PID 19640，exit 0，1004.218 ms，diagnostics 0／private type diagnostics 0，AST unit 19／browser 8。collect：PID 25148，exit 0，953.850 ms，--list 实际 8 同名场景，resultCount 0。两个 childClosed／logsClosed 均 true，原日志 SHA 与回执一致，两个隔离 OS TEMP 保留。

static／collect 的作用是语法与收集准备，不是新浏览器业务通过。本审查仅读取既有文件，未重新执行以上命令。

## 对应 r4 原 trace 的修复必要性与限度

前一轮由本审查者独立读取的原 trace，本轮再次核 raw SHA／ZIP CRC，仍为 7df37f48118879bc54dc478b13bbde62b2e0c73613349103f06f456dde282aa7／CRC 无错误。current 列表 click @421 在 6520.372 ms 返回，6522.019 ms 快照仍为 history URL；原 helper 在下一次 cache evaluate（6523.053 ms）前同步捕获 hrefBefore。真实 GET 200 在 6527.196 ms 完成，6539.446 ms 快照已经是无 revision 当前 URL／当前标题／enabled FIELDSET。导出与 6851.033 ms 下载时均为当前 URL；第四原 JSON 全 11 字段与手写 current A 匹配。

v9 等真实完整 current 响应、精确 current URL 与启用标题后才进入原 helper，直接覆盖该先后关系；local→current 同步补齐相同就绪边界。未删除 URL/cache 断言，也未把下载作为已确认产品导航缺陷。

r4 原完整第二轮保持 7 通过／1 失败，4／6 JSON，后两分支未执行；原失败与前轮 QA8 报告保持，不拼接通过。本静态报告不能证明 v9 新完整 8 已通过；结果和阶段关闭由 ROOT 的新完整单轮及适用门禁决定。

## 写入与证据

仅新增本 MD 与同名 JSON；产品、QA 原件、权威文档、Git、正式数据／凭证均未写。JSON 保存本轮 before／after raw 哈希组、三文件／两块精确 SHA、实际命令回执和旧 trace 引用。结果：STATIC REVIEW COMPLETE，RUNTIME GATE OPEN。

