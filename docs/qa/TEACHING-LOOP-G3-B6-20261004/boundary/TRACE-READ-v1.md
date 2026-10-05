# G3-TRACE-READ-v1 独立只读归因

时间：2026-10-04T13:20:22.333241+08:00。结论：**CONFIRMED_RUNTIME_DEPENDENT_TRACE_MERGE_FAILURE；原14例仍待最终errors，G3不能据业务断言完成直接关闭。**

本卡只读日志、已安装实现、归档字节及CRC；没有执行QA、离线诊断或任何业务/服务操作，没有修改产品、QA、依赖、trace或Node配置。离线双运行来自ROOT，我独立核执行收据与输出。新增仅本报告和JSON。

## 已确认共同链路

当前安装 `playwright` / `playwright-core` / `@playwright/test` 均1.58.2；根 config timeout45000，G3 external config trace='on'，单worker/0retry。真实用例业务动作和截图短时间完成，list每例约0.8–4.8s仍显示x；archive bytes只含local file headers/部分compressed payload，未写central directory或EOCD。

- `playwright/lib/worker/testTracing.js:288-339` 将多个临时ZIP经yauzl读出，再由yazl.addReadStream重压缩合并，并等待目标写流close。`testTracing.js:136-200` 在结束时调用该流程、完成后才附trace.zip。
- `playwright-core/lib/zipBundleImpl.js` 的 minified hr 函数将 input→CRC/bytecount→DeflateRaw→bytecount→zip.outputStream 连接；末段stream发end后才把entry标done并推进下一条，所有entry完成后N才写central和EOCD。当前观察与该流未完成相符，不是完成ZIP仅漏附件链接。
- `playwright/lib/worker/workerMain.js:392-395` 单独为 `testInfo._tracing.stopIfNeeded()` 分配 `project.timeout` tracingSlot（45000）；`:397` 展示duration只合并test默认slot和afterHooksSlot。故list显示业务2–3秒但归档额外耗45秒、最终x，可以由该归档超时产生；必须等完整errors判每例是否另含业务失败。

## ROOT同代码同输入对比（独立核验）

ROOT `ctrl/trace-merge-diagnostic.cjs` 复制已安装merge的核心：相同去重/trace命名、yauzl.openReadStream→yazl.addReadStream→end/close；输入只读、输出新OS临时目录，不发HTTP。两个命令唯Node执行器不同，输入路径/SHA相同，日志SHA与收据一致，source/QA前后相同、漂移空。

| runtime | PID /exit | 外层 /内部耗时 | 输出及实际检查 |
| --- | --- | --- | --- |
| 系统Node v26.2.0 | 25464 /1 | 7086.363 /7008ms | 未完成、1/14输入stream ended；156184bytes，EOCD=-1，Python ZipFile拒绝；SHA `a0380165d333aeea51231556d41680a1c2c1b5725cac75973a68fe2b5af392fb` |
| 现有bundledNode v24.19.0 | 24904 /0 | 89.234 /18ms | 全14 stream ended；202013bytes，EOCD offset201991；14 entries CRC全部通过（testzip=None），SHA `639594e15b69bfe934320ca629876b6b83ca03ca36cbf42afa08d447c7003f23` |

Node24合并的截图resource内容SHA1与条目名相符；test.trace共有98 before/98 after且无error事件。这个样本证明对应归档输入可以完整读取和合并，不证明原14个浏览器测试全通过，也不替代原最终report/重新绑定的完整浏览器门禁。

输入两个原临时fragments当前不在 `.playwright-artifacts-0`，现场只读CRC时FileNotFound；ROOT诊断日志保有输入SHA `162013e3a92fa8fd6db87fa2e0443325ebae1fa683c98c631419d21e1ad7aa4c`、`5f3327a82d17d04956955ab110eae2c052643a1892dc266e8925aa5ad2d088cc`。因此本报告不声称现存原inputs独立CRC已核。Node24现存输出CRC已独立核。临时清理不会被记成作者/验收者改了产品或测试；如果ROOT有原fragment保全副本应另做保全绑定。

## 最小执行层修复建议

下一轮保留候选、14例原断言、依赖版本、trace='on'、隔离服务及8001/5174；使用现有绝对Node24执行器 `C:\Users\96022\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe` 调同一 `node_modules/@playwright/test/cli.js` 和同一external.config，使用全新run/output。这属于单条测试执行命令的runtime选择，不需要重构建、升级依赖或改产品。记录node.execPath/version、候选/build/proxy、首失败保留和新运行收据；新14例必须真正exit0并最终JSON/XML/全部trace有效再登记该浏览器门禁。

本卡已证实当前installed trace merge的runtime依赖失败；未证明Node26内部哪项stream/zlib语义变化，也不把这一未经定位的底层原因写成既定事实。原14最终JSON此刻仍未生成（已见13条x）；待ROOT完整errors，若存在业务断言失败须单独登记与修复。系统Warning DEP0205/NO_COLOR没有形成此归档因果证据。

G3-BOUNDARY先前8受控components PASS保持；本归档诊断不能把truebrowser gate自动转PASS，B6仍未授权前置启动。完成本报告后STOP，等待ROOT原14final及runtime适配后的新卡；没有新增exec文件或重新执行。
