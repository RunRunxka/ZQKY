# B5-QA8-REVIEW-v1 — 独立只读审查

- 负责人：/root/b5_r06_review；归属：ROOT 授权的新报告两文件。
- 范围：V00 v7 → v8 的三份 browser 副本、已有 static/collect/manifest、r3/r4 原 trace 与 r4 第二轮结果；未运行测试、浏览器、HTTP、SQL、服务或 Git。
- 结论：静态范围未确认新增 P1/P2，未发现旧 oracle、预算或完整场景削弱。r4 第二轮仍为 7 通过／1 失败，B5 与相应浏览器门禁保持未关闭。ROOT 后续授权的 v9 不在本报告范围内。

## 候选与保全

审查开始 UTC 2026-10-03T12:24:42.606537+00:00，结束复核 UTC 2026-10-03T12:30:29.392125+00:00。r4 候选 SHA-256 为 c4c61ff50e2284d023a7f513c96b92ea43a808b0235f1f0b2afef66c7d56b668，构建 ID 为 xWWO3VbSMdUiLTwkXdD2x。

独立读取并 raw SHA 校对：产品 938、冻结契约 33、构建 2004、旧 v7 原件 104、v8 manifest 177，开始／结束均零漂移；产品、契约、构建也与 r3 一致。完整路径与 SHA 见同名 JSON。旧失败、原件和封存文件均未修改。

## v7 → v8 精确差异

1. external.config.ts 仅改变 testDir 到 v8；原 45 秒单例、10 秒 expect、完整 8 场景、重试 0、worker 1、fullyParallel false、trace on、无自动 webServer 与隔离输出守卫保持。
2. history-copy.spec.ts 的首次 prepareA 增加参数，在 current 列表按钮前登记精确文档 GET；随后等待 GET 200、完整 latestA 与当前标题／重点／反思，在首次实际下载前暂停时钟到 03:00:01。移除原先首次下载后的暂停。其余 prepareA 参数默认 false，原完整 11 字段 helper、历史手写 oracle、复制／撤销／重做／保存及全部 dirty intent 分支保持文本相同。
3. independent.spec.ts 仅把 unknown 场景时钟安装／暂停放在填写 A 之前，增加干净状态标题／反思／保存启用检查。真实 route.fetch 200、丢回执门控、等待中编辑 B、原生 Back、两次原请求包一致、dirty、后端仍 A 的检查保持。四视口完整链、双真实标签 CAS 409、键盘焦点与 Escape、reduced-motion、Word XML、print 和旧成绩／报告／练习身份断言保持。

没有新增 force click 或 DOM 事件替代业务操作，没有删除断言或扩展预算。四视口为 390×844、1024×768、1440×900、1920×1080，仍设 reducedMotion: reduce。

**证据措辞校正：**旧 v7 browser 是 LF，新 v8 三份副本是 CRLF。除新增调度及 LF→CRLF 外，原块文本相同；上述原块是在显式 LF 归一化后比较。V00 自审使用 read_text 后的 ByteExact 标签不能解释成 raw 字节相等。旧 v7 原件 104 的 raw SHA 前后零漂移。首次独立 raw 块相等断言未通过，仅为此换行区别，未产生文件写入；旧封存保持原样。V00 的首次自审失败也保留，随后只修正 delta 判断，不改 browser 可执行文件。

## 已有静态与收集记录

V8 静态记录：Node 24.19，PID 28400，exit 0，993.859 ms，private 编译诊断 0，AST 识别 unit 19／browser 8。V8 收集记录：PID 13748，exit 0，909.575 ms，实际 --list 收集 8；只收集，不代表业务验收。manifest 原件为 177 项，SHA-256 b6257c223b124f3e40ff5e90aa14c75f37b5914426073946224ca70b5dbb4684。这些均为实读既有证据，本审查者未执行命令。

## r3 原 trace 归因

独立打开两份原 ZIP 并验证 CRC：

- intent：clockInstall 成功；实际干净 JSON 下载在 4471.036 ms，新页事件在 4484.360 ms，之后 clockPauseAt 在 4658.761 ms 开始而无结束；dirty 填写 0。可确认停止于时钟调度，不能宣称后续 intent 分支通过，也不能据未保留的新页 URL／类型证明时钟内部失效的唯一原因。
- unknown：填写 A 在 73100.838 ms 结束；保存 click 在 73106.344 ms 开始而未完成；自动 PATCH route.fetch 在 73701.314–73732.301 ms 收到真实 200，回执被门控。等待 click 因不稳定再禁用而阻塞，测试未抵达编辑 B／abort；B 填写 0。调度死锁有原 trace 支持，但 r3 未完成 unknown／重放验收。

r3 完整 8 为 6 通过／2 超时；原失败保持，不与新轮结果拼接为全绿。

## r4 原结果与精确导航时序

ROOT 首轮使用错误环境变量名 B5_V00_SEED，所需为 B5_V00_SEED_JSON；PID 7872，exit 1，902.201 ms，收集失败且业务执行 0。原命令回执与错误日志保持。

ROOT 第二轮 PID 29456，exit 1，36583.939 ms，完整 8 实际为 7 通过／1 失败／0 跳过／0 flaky，无超时。unknown 原完整用例通过；intent 在 history-copy.spec.ts:149 调用 helper 后，由 helper:42 的 href 保持断言失败。实际只产生 4／6 个备份，后两 clean backup／local 分支未执行。本审查不把框架通过等同于自身重新运行或总控关闭。

独立读取 intent 原 trace：history 后禁用检查通过；当前 A 列表 click @421 为 6495.335–6520.372 ms，after421 快照 6522.019 ms 仍为历史 URL。helper 同步读取 hrefBefore，随后 cache evaluate @423 在 6523.053 ms 开始。真实 current GET 为 6519.500–6527.196 ms，200，revision 2／currentRevisionId a143daf038d04331af8772d87421df2c。before423 快照 6539.446 ms 已为无 revision 的当前 URL，当前标题，FIELDSET 已无 disabled。导出按钮 6546.208 ms 后与实际下载 6851.033 ms 的各快照均为当前 URL。

因此本次 URL 差异发生在 helper 提前捕获历史 URL 后、未完成的 current 导航提交时；原 trace 未显示下载触发路由变化。精确 current URL／GET／UI 就绪应在 helper 前等待，原 URL／cache／完整 11 字段断言应保留。此归因已发 ROOT 与 V00，未据此修改 QA 或产品。

第四实际 JSON 原包 SHA-256 为 2707b0f3dd2f06abd4053160651d0e99f556844cd75cb08d504987ec2822733d。独立手写 current A 全 11 字段 oracle 比较：schemaVersion 1、字段 11、完整匹配；此事实说明该原包内容正确，不能补足未执行的后两分支。

## 未执行与待总控门禁

本审查未运行任何测试／浏览器／HTTP／SQL／服务，未改产品、QA 原件、权威文档或 Git。这里只封存静态保留性与已有原 trace 归因；需后续稳定 QA 新版本的完整 8 场景独立运行和适用门禁证据，才能由 ROOT 判定 B5 关闭。

