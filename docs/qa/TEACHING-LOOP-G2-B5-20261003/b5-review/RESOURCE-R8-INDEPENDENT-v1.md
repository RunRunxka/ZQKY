# B5-RESOURCE-R8-INDEPENDENT-v1

负责人 `/root/b5_r06_review`；当前资源观察已 STOP，UTC **2026-10-03 13:54:17 UTC**。只读 CIM、监听、FileShare.None 日志打开、候选／历史原件与已完成收据；仅新增本 MD 与同名 JSON，未执行测试、HTTP、SQLite、服务启停、Git，也未结束任何进程或修改产品、QA、权威文档、旧证据。

## 当前结论与待核边界

当前 **5174／8001／8002 无监听，CIM 无自有 marker 进程；72 个 ROOT 命令全部 complete，10 个 B5 自有 service 均 closed，81 个实际日志均能独占只读打开并立即释放。182 个批次引用临时目录全部存在，293 个唯一 origin JSON 实际解析零错误／零缺失。** 所有候选与保全组 raw SHA 零漂移，next-env 和磁盘分支／HEAD 保持。

**V00 离线附件与图审仍未按本报告收到 STOP，最终 SQLite 连接闭合待其确认。** 本报告只封存此时点的资源观察，不 approve 或关闭 B5；ROOT 后续结合 V00 STOP 形成最终资源 v2。

## OS 与日志实读

- CIM／监听独立观察 UTC `2026-10-03T13:52:16.7194094Z`；端口监听数组和自有 marker 数组均为空。早一轮 UTC 13:50:29 同时查询最新已归属 PID6564／18956／26832／4152／29548／13224，亦未匹配到进程。仅核归属，没有操作 PID。
- ROOT ctrl 目录72个 `*command.json` 均实际读取为 complete；所有有声明的日志 SHA 与实际一致，未将历史非零测试 exit 当成运行中或伪造全通过。
- 其中24个旧命令收据没有完整写出 childClosed／logsClosed 布尔字段，JSON保留 null，未补成 true；没有 false 闭合值。其实际日志独占读取成功，文件与临时目录无缺失。这是旧元数据字段缺省，与 JSON解析或原件缺失分别记录。
- 72 个命令日志与10服务日志映射后共81个不同实际路径。用 `FileMode.Open + FileAccess.Read + FileShare.None` 全部打开成功，随后 finally Dispose；零共享锁失败。完整逐日志结果与逐命令元数据在 JSON，未只相信 logClosed 字段。
- stream 服务收据无 logFile；其真实输出由 wrapper 收据对应 `b5-stream-r8-owned.log`，已包含在上述81日志。没有把猜测的 `b5-stream-r8.log` 当成应保全原件。
- 10 服务收据 SHA 均与 CTRL 资源 v1 完全一致；实际状态、stopRequested、sampleRetained 及服务各自的 child/server/watcher/logClosed 字段按原件记录，没有把某类型不存在的字段补成 true。

| 服务收据 | 状态 | 记录 PID | 闭合语义 |
| --- | --- | --- | 
| b5-frontend-r1-service.json | closed | 27964 | 受控 child exit1 |
| b5-frontend-r3-service.json | closed | 23196 | 受控 child exit1 |
| b5-frontend-r8-service.json | closed | 4152 | 受控 child exit1 |
| b5-runtime-r1-service.json | closed | 23196 | server/watcher closed |
| b5-runtime-r2-service.json | closed | 18736 | server/watcher closed |
| b5-runtime-r3-service.json | closed | 21820 | server/watcher closed |
| b5-runtime-r4-service.json | closed | 24384 | server/watcher closed |
| b5-runtime-r5-service.json | closed | 27068 | server/watcher closed |
| b5-runtime-r8-service.json | closed | 29412 | server/watcher closed |
| b5-stream-r8-service.json | closed | 6564 | server/watcher closed |

## 受控停止与原门禁

本轮前端 manager26832／node4152：CTRL 会话52231返回 manager exit0；persisted service 实际 child exit1、ownedHandleTerminationRequested=true、childClosed/logClosed=true。这是已归属 Windows 句柄受控结束，**不能写成 node 自然 exit0**。manager 会话返回依据 CTRL 交接，service 原件只记录子进程 exit1。

stream server6564：CTRL 专属 guarded stopFile；wrapper 命令 PID18956、exit0／149041.614ms，session79318返回。原服务 serverClosed／watcherClosed 和样本保留成立。本审查员没有执行 stop。原14 chat 的命令 PID29548、exit0／42953.884ms、原8和153的命令闭合只用于资源核对；业务／逐画面审查另属对应报告。

## 保全与现场身份

资源 v1 `ctrl/B5-RESOURCE-CLOSED-r8-v1.json` SHA `9bce6a43cda8410f9fec4570d4bdb5c0e1d319fa098633366828c8f1133e0904`。独立实测其182临时目录均存在，且引用它们的293个唯一JSON实际可解析、无缺失。这182目录包含 G2、B5、作者／独立私有轮次及失败样本，**不等于182个本次B5新根**；只检查目录存在，没有读取正式数据／凭证或清理目录。

候选 `CANDIDATE-B5-r8.json` SHA `c33c85698ba2be8e6b08fe432305622bf3635a1bc5bb0cc515472996ebbe2007`。独立逐件复核938 source／3061 executableQA／33 frozen／2004 build／1702 prior／4136历史，全 raw SHA 零差异。G2完成组为589个不可变原件＋2个批准原文archive，共591精确保持；live README／REPORT继续由CTRL维护，未混作旧不可变原件。

next-env实际 SHA `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`。直接读磁盘 `.git/HEAD` 与 `refs/heads/main` 得到 **main@6aeb57280f6a7e0d7391cad4d150745479ea58ec**，与候选一致；没有调用 Git 命令，不凭历史 PID 结束任何进程。当前无源或 build 派生写。

## 精确证据与后续

同名 JSON 保留81个日志独占打开结果、72个已完成命令的原 SHA／PID／exit／闭合字段、10服务收据 SHA、各分组 SHA 核查计数、CIM／监听观察时间和 V00 pending。报告是本时点快照；ROOT 在 V00 STOP 后再核其离线连接并形成资源 v2，不能把此报告当全部验收关闭。

STOP：当前资源与保全独立观察完成；未发现本任务范围的新资源问题，最终 V00 连接闭合及 B5批准仍待ROOT收口。
