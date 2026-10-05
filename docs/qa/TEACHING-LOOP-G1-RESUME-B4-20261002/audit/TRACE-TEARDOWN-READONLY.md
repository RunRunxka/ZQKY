# G1R-AUDIT v1.2 · trace 收尾只读定位

2026-10-02，独立核对者 `/root/g1_v00_fe`。本次唯一新增文件是本报告；仅读已安装 Playwright 代码、第一轮新 QA 结果及两份原始 ZIP，在内存中有界解压已有局部记录，没有写 ZIP、解包到磁盘、启动浏览器/服务、改 runtime/依赖或改冻结源码。

**最可能挂点是最终 TestTracing.stopIfNeeded → mergeTraceFiles → bundled yazl.addReadStream 的压缩/排空链。第二用例的 After Hooks 已完成，不能将此次 timeout 定位为 After Hooks 本身，也不能先认定 Node 26 是原因。** 这是本地冻结安装库的测试收尾故障；当前证据没有新的产品行为断言失败，不使整项测试成为 PASS。

## 直接证据

第一轮 JSON 为 unexpected=2/expected=0，墙钟 544943.77ms。第二用例 result.status=timedOut、duration=2636ms、仅 `Test timeout of 180000ms exceeded`，业务结果 JSON 已附加。安装版本 Playwright/playwright-core 均 1.58.2；只读运行环境 Node v26.2.0、zlib `1.3.1-e00f703`、libuv 1.52.1、win32/x64。版本只登记环境，不证明因果。

两 ZIP 保留原始字节，均有 local header、没有中央目录/EOCD。按 local header 定位，并使用 `inflateRawSync(..., {info:true,maxOutputLength:16*1024*1024})` 在内存中读取可完成项；不修复、不重写原文件。

| 原文件 | 字节 / SHA256 | 只读定位 |
| --- | --- | --- |
| `v00-browser/browser-artifacts-first/real-browser-G1-independen-2170f-ewly-confirmed-score-matrix/trace.zip` | 58083 / `2e1ab46ceb066f75c5a54d57d519d1446c4eed3df28c05212a8ab46d2517e041` | 前两项完整；第三项 `resources/87ae3ef8054f1bfdb647457015b0c868730f44cf` local offset=7811，DEFLATE 为 `Z_BUF_ERROR: unexpected end of file`。原业务体还存在已登记的 disabled 出勤控件操作顺序错误，两类失败不能混为产品修复票。 |
| `v00-browser/browser-artifacts-first/real-browser-R08-actual-DO-28ae1-board-actual-reduced-motion/trace.zip` | 53264 / `465e1f9ed1387354df569ebf19088c18dba15a652cb04905e3eee892d8cc7728` | 前两项和 `test.trace` 完整；`test.trace` 为621条 JSON 事件。下一项 `1-trace.trace` local offset=28499，DEFLATE 不完整，尚未完成该 entry，更未到 central/EOCD。 |

第二包 `test.trace` 的末尾给出明确闭合事件：

- `hook@334` 的 After Hooks before startTime=365292.25，after endTime=365422.41，约130.16ms。
- `fixture@337`（context）含 `pw:api@338` 的 Close context before=365407.712、after=365419.579，context fixture after=365419.614。
- page/context/baseURL/viewport 等 fixture 都已有 after；最后记录是 `hook@334` 的 after，没有该 hook 的错误。

因此 2636ms 是 reporter 给出的 test+afterHooks duration，不能精确称为纯业务体耗时。更关键的是 After Hooks 并未耗满180秒。最终 ZIP 流当前项被截断，也比“仅中央目录写完后等待文件 close 回调失败”更早。

## 安装源码对应关系

[workerMain.js:329](H:/备份xuexi/智启课源/node_modules/playwright/lib/worker/workerMain.js:329) 给 After Hooks 独立 slot，并执行 fixture teardown；[workerMain.js:392](H:/备份xuexi/智启课源/node_modules/playwright/lib/worker/workerMain.js:392) 在其后另建 tracingSlot，await `testInfo._tracing.stopIfNeeded()`。第397行最终 duration 只加 defaultSlot 和 afterHooksSlot，排除了 tracingSlot。因此完整业务与 After Hooks 很快完成，而 runner 再等180秒仍可报告 duration=2636ms、status=timedOut。

[testTracing.js:148](H:/备份xuexi/智启课源/node_modules/playwright/lib/worker/testTracing.js:148) 先用 yazl.addBuffer 写测试事件/附件，再在第199行调用 mergeTraceFiles；[testTracing.js:288](H:/备份xuexi/智启课源/node_modules/playwright/lib/worker/testTracing.js:288) 在多临时包分支中以 yauzl.open/openReadStream 读各 entry，经第324行 `zipFile.addReadStream(readStream, entryName)` 重压缩。第332-339行写目标 ZIP，等待输出文件 close，随后删除自有临时输入才 resolve。第二最终包含 `test.trace` 与重命名的 `1-trace.trace`，直接表明进入了此多包 merge 路径。

[index.js:617](H:/备份xuexi/智启课源/node_modules/playwright/lib/index.js:617) 的 context 关闭先 stop tracing；本地 [client/tracing.js:93](H:/备份xuexi/智启课源/node_modules/playwright-core/lib/client/tracing.js:93) 使用 entries 模式并调用 localUtils.zip；[localUtils.js:82](H:/备份xuexi/智启课源/node_modules/playwright-core/lib/server/localUtils.js:82) 同样用 bundled yazl 与文件 close Promise。第二 `Close context` 已闭合；现场最具体的挂点在其后的最终 merge，而非最初 trace 录制或产品 API。

只读 [zipBundleImpl.js](H:/备份xuexi/智启课源/node_modules/playwright-core/lib/zipBundleImpl.js) 的本地写包实现：

- ZipFile.outputStream 是 Node PassThrough；addReadStream 的文件 pump `hr()` 为 input → CRC Transform → byte counter → DeflateRaw → byte counter → outputStream，最后一段 `{end:false}`。
- 只有最后 byte counter 的 readable `end` 回调才写 data descriptor、将 entry.state 从 FILE_DATA_IN_PROGRESS 设为 FILE_DATA_DONE，并再调用 `N()`。
- `N()` 在所有 entry 完成后才写 central records/EOCD、outputStream.end()，进而触发目标文件 close；若某项压缩/流动/排空未结束，这整条等待链会保持 pending。

当前缺少实时事件/stream state，不能单凭截断包分辨具体是输入流、DeflateRaw、计数 Transform、输出背压还是其它 I/O 等待，也不能证明 Node 26 的兼容性缺陷。两份输入 ZIP 的存在和已完整读取的项只证明 merge 开始，不能代替最终全部 entry/CRC/SHA 等效验收。

安装代码身份：workerMain SHA `1cd04668c4bf6bb49e60fe6c28531c5b2cf68a4bf02752a05d21a5d6e6fffd42`；testTracing SHA `2e88907a30dfde8b39a671ea4967dfd49037ffa6d98d870a39fa8a1eeebbcb22`；zipBundleImpl SHA `9552c87b175ac3ce5a1eade1e3ebde4e7c2a37031253e4ecabecc51b4a24ddf6`。第一结果 JSON SHA `3946bcbbe15180f20b616bb15e7e3fff5f35f6cd2db977abc35137f22874f873`。

## 安全最小验证建议

由已登记资源写入者在新 QA 根执行**同一安装 bundle 的无端口 Node 小样本**，不跑浏览器/业务服务，不覆盖第一轮包。保留当前压缩方式与写包路径：分别走 addBuffer、addFile、addReadStream，并复现 yauzl.openReadStream → yazl.addReadStream 的多包 merge。使用固定小/中样本和非零条目，记录每项读流 end/close、writer entry state、readable/writable buffered 长度、输出 drain/finish/close 以及 watchdog 当时的完整状态；压缩流本身的实时状态能将 pending 缩到具体层。

每个小样本须以最终 EOCD/中央目录可读、全部预期 entry 存在、逐 entry 解压内容 SHA 完全相同为成功，不能只看生成文件、close 或退出0。保存首败和 watchdog 原记录。关闭/放宽 trace、超时或 sources/attachments 的方式不构成修复，也不能将本次两项失败改判通过。

若 CTRL 选择新增 QA runtime drain adapter，应先登记精确版本/范围并冻结；之后独立核其输入与输出 ZIP 的全部 entry 名称/解压 SHA 等效，覆盖压缩/空项/重复名字按原合并规则的行为，以及业务回调、config.trace、timeout 和断言完全不变，再执行原浏览器门禁。此处仅提出验证条件，没有实施适配，也没有改变依赖或安装库。

本次相关 Node 只读命令（require 后仅读函数 .toString；读取 minified helper；有界解析既有 local records；runtime/文件 SHA）均 exit0，输出在对应工具结果，未新增脚本或日志文件。`Z_BUF_ERROR` 是只读诊断中按项捕获并保留的原包不完整证据，不是成功 trace 解析。准备完成，停止写入；等待 CTRL 的后续精确新冻结任务。
