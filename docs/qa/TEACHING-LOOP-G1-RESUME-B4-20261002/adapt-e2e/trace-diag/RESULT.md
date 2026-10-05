# G1R-TRACE-DIAG v1 · 有界复现完成 / 停写

2026-10-02，`/root/g1_resume_e2e`。只写本目录，没有修改产品/冻结测试/配置/依赖/版本，没有启动浏览器或服务。**已在当前 Playwright 1.58.2 的原合并函数上复现 Node 26.2.0 的大样本收尾阻塞；完全相同源 ZIP 在本机现有 Node 24.19.0 完整通过。** 这是一项测试运行时诊断，不是业务通过，也不能把原浏览器两例 timedOut 改成 pass。

## 相同代码与相同输入的对照

实际读取并在内存额外导出当前 `node_modules/playwright/lib/worker/testTracing.js` 的原 `mergeTraceFiles`，没有重写该函数。源 SHA256：`2e88907a30dfde8b39a671ea4967dfd49037ffa6d98d870a39fa8a1eeebbcb22`。观察器仅为既有 writer prototype 与文件流增加事件监听；不修改依赖文件，不替换 Node 全局版本。

两运行使用同一 512KiB 随机不可压缩 payload，SHA256 `e5b8250d04a334756bd71db3bd303bc03a615945ae5c6bf7ed6a224193ec3d2d`，每个源 ZIP 含44项：trace、network、test、共同资源及40个共享资源条目。两次运行的两个源 ZIP **逐字相同**，分别为：

- source-0 SHA `fa009052f7c24ed1f094d2e60801780c65c67cd1e889ad1699c556db7dec5579`
- source-1 SHA `5c09f1608ded62be510d90965c7ccb41a9b663facaff5eb1789093c44aa5c691`

| 实际运行 | 单轮结果 | 输出与事件 |
| --- | --- | --- |
| Node26.2.0，`NODE_OPTIONS=--no-experimental-webstorage` | **20,120ms，watchdog超时，exit2** | trace.zip 508,074字节；存在本地文件头，central/EOCD均-1；最终writer ended=true / allDone=false，第一条大 entry 停在 state2，未产生最终 destination finish/close或merge resolved |
| 同函数/同输入/同参数，本机现有 Node24.19.0 | **190ms，resolved，exit0** | trace.zip 1,514,154字节；central offset1,511,181，EOCD1,514,132；所有观测输入、writer output、destination均完成并close |

对应 [Node26原完整收据](merge-26.2.0-large-receipt.json)、[Node24原完整收据](merge-24.19.0-large-receipt.json)、[26日志](merge-26.2.0-large.log)、[24日志](merge-24.19.0-large.log)。每个探针 watchdog 为20秒（记录的wall因模块准备和事件调度略多于20秒），均低于授权30秒；没有拉长业务timeout。

## ZIP 内容与 CRC 独立核验

使用 Python 标准库 zipfile/zlib 手写本受控样本 oracle，未调用生产 merge 或 bundled ZIP reader 作期望函数。首轮 **19ms，exit0**，见 [artifact-content-verification.json](artifact-content-verification.json)、[脚本](verify-merge-artifacts.py)、[实际日志](artifact-content-verification-first.log)、[完整命令](artifact-content-verification-first-command.json)。

逐字确认两个运行的两份源 ZIP相同，并完整检查源 CRC。独立按本样本的显式规则建立期望：先source-1，再source-0；仅trace.trace/trace.network添加来源序号，test.trace和共享资源保留先遇到的内容。88源项形成46目标项，42项因同名跳过。核目标条目名字与完整顺序、每项完整解压字节、预期/实际SHA256、实际CRC32与central CRC32，全部一致。JSON保存全部46项名称和逐项SHA/CRC及42条跳过记录。还核central目录的范围、EOCD长度与条目计数，不只检查PK签名。Node26保留的partial ZIP被标准库明确拒绝为`File is not a zip file`。

## 已排除的有限假设

| 窄探针 | 单轮结果 | 证据 |
| --- | --- | --- |
| 当前Node26同bundled writer：buffer/readStream × 默认压缩/store，小样本 | 4个分别exit0；7/7/7/9ms；均central/EOCD及finish/close完整 | [buffer-default](buffer-default-receipt.json)、[buffer-store](buffer-store-receipt.json)、[read-default](read-default-receipt.json)、[read-store](read-store-receipt.json)，各自对应-command.json和.log |
| 当前Node26 exact merge，小体积可压缩ZIP | exit0，128ms | [merge-r2源](merge-r2-source.mjs)、[收据](merge-26.2.0-receipt.json)、[日志](merge-26.2.0-r2.log)、[命令](merge-26.2.0-r2-command.json) |
| 当前Node26，两个512KiB随机readStream，匹配NODE_OPTIONS：end callback中pipe | exit0，24ms | [收据](backpressure-26.2.0-callback-pipe-receipt.json)、[日志](backpressure-26.2.0-callback-pipe.log)、[命令](backpressure-26.2.0-callback-pipe-command.json) |
| 同payload/同writer：立即pipe对照 | exit0，23ms | [收据](backpressure-26.2.0-immediate-pipe-receipt.json)、[日志](backpressure-26.2.0-immediate-pipe.log)、[完整命令](backpressure-26.2.0-immediate-pipe-complete-command.json) |

实际writer高水位为16KiB；callback-pipe的end callback及pipe都在约2ms发生，之后正确消费大流。因此不能用“小样本writer通过”排除大合并问题，也不能将其归因为一般ZIP写入、unknown-size end callback先等全部输入或pipe顺序死锁。当前证据限定到 **Node26 + 当前bundled yauzl→yazl大/多流合并链**。更底层是哪段Node/Transform行为造成缺失end尚未分解，不能冒称定位到了Node某一行；原实际trace卡住与该复现的partial ZIP形态一致属于有依据的归因，不是直接重新运行业务证明。

## 命令、首败与资源

所有执行cwd为 `H:\备份xuexi\智启课源`。大样本实际完整执行输入、绝对runtime/probe/payload、cwd/env另存 [26完整命令](merge-26.2.0-large-complete-command.json)、[24完整命令](merge-24.19.0-large-complete-command.json)。这两份是从原functions.exec调用前保存的实际输入补登，旧仅含probe/exit/at的-command.json原样保留；未重跑或回填旧执行。新命令记录明确标注该来源。

首个merge观察器试图赋值bundled getter而报TypeError，未进入merge，exit1；[首轮脚本](merge-first-source.mjs)、[首轮日志](merge-26.2.0.log)、[首轮命令](merge-26.2.0-command.json)、[首轮新根元数据](merge-first-owned-root-metadata.json)保留。随后只改观察器为既有prototype事件监听，小样本通过；扩大样本前另保留merge-r2-source.mjs，不覆盖已执行轮日志/收据。Node26大样本超时是真实诊断复现，原数据/partialZIP/输入均保留，不混计为产品fail或pass。

每轮只创建自己的新系统temp根，所有根保留于逐轮receipt。exact merge只按其既有行为unlink本轮自己创建的`.work.zip`，原源ZIP副本保留。Node26超时收据先记录失败时流状态，随后destroy自身观察流并退出进程；不冒称失败时已经finish/close。最终[运行时与资源](runtime-and-resource-final.json)没有自有probe进程残留。Python验证的全部ZIP reader已在with中关闭。

[本机依赖路径](runtime-and-resource-final.json)只读确认默认Node26.2.0、bundled现有Node24.19.0；NODE_OPTIONS外层默认未设置，大对照命令显式用原浏览器匹配值。Node24仅按CTRL追加授权执行非业务探针，未用于业务、未改变PATH/全局Node或用户前端进程，没有升级/下载或改锁文件。当前安装代码散列另存[installed-source-sha.json](installed-source-sha.json)。

## 最小适配建议与限制

CTRL已选定本机现有Node24.19.0 **只作为Playwright runner** 的运行时适配：直接指定现有绝对exe，保持同一安装Playwright、测试源、代理构建、外部5174、端口与业务断言，保留原失败与trace，不修改产品或依赖/业务timeout。需登记并重冻适配身份、独立审查后重跑完整两例实际浏览器与后续适用E2E，检查真实trace的中央目录及完整内容；用户持有前端仍由其原Node26进程运行。本任务尚未执行该业务重跑，G1关闭状态由CTRL依据真实门禁决定。

本任务到此停写；不继续无限扩探针，也不自行开始B4。
