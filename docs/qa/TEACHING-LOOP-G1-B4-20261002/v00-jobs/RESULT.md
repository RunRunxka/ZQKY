# G1-V00-JOBS v1 独立验收结果

负责人 `/root/g1_v00_jobs`，冻结起点 `g1-r1`，`main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`。结论 **pass**：自建正确行为探针一次 **52 passed、0 failed、0 error、0 skipped，exit 0**，pytest 6.10 秒；启动器墙钟 6.51 秒。没有产品修复或既有测试改写，没有将原诊断失败计作通过。

验前恢复后与验后 **825 项完整 SHA 均为零差异**，清单本体 SHA `1c6ba3c16f5db6e0e008ed1c24e9629e521ce9f852dd4b8077e392ed278ed305`。旧 **629 份证据零差异**。最早预检恰遇 CTRL 的 typegen/build 窗口，仅 next-env.d.ts 临时差异，已原样保存在 sha-before.json；收到原字节恢复通知后，完整重核 sha-before-restored.json 全同，随后才执行探针。最终见 sha-after.json、protected-after.json。

## 独立正确行为覆盖

- R05 到期无人接管：三域 teaching/question/knowledge，准确到期秒 3 与到期后秒 4，有取消与无取消共 12 例。complete 均为 409 LEASE_LOST；publish 回调未调用，业务哨兵为空，整行字段及 checkpoint 均与基线完全相同。
- R05 真实 SQLite 等锁：独立第二连接持 BEGIN IMMEDIATE，工作线程的 SQL trace 确认实际尝试 BEGIN IMMEDIATE 且阻塞。complete/fail/cancel/heartbeat × 取消标志两态共 8 例；等锁期间零读钟，拿锁后只读取秒 4；全部零业务、零 checkpoint、零终态写入，heartbeat 为 false。没有沿用旧探针的锁前读钟屏障。
- claim 等锁跨到期后领取新 attempt 2，租约恰为秒 4+3=7，未延长 TTL。引擎最后一次只读闸门之后才跨到期，complete 仍拒绝，失败收敛也无权写终态；原 running/attempt/token/到期点/checkpoint 保持。
- 有效期内 complete 与 fail 均取消优先；错误 token、错误 attempt、已被 attempt 2 接管的旧租约 × 四操作共 12 例，完整任务行及业务全部零写。
- R06 16 例真实 ASGI POST retry：旧轮已提交 failed（公开错误或内部错误）、cancelled 或 interrupted，真实 heartbeat finalizer 屏障尚未退出；三次并发重复请求均 200 queued@1。释放旧轮后，正常路径只运行 attempt 2 一次；新执行器保持阻塞时验证旧 done callback 没有删掉新 tracking。第二轮成功/错误、排队阶段 HTTP 取消、shutdown 后新引擎显式补调度均有最终终态和冻结输入/模型快照/hash 不变证据；未用单轮 sleep 判定完成。每次成功只有一笔业务发布。

Fixtures、假钟、数据库哨兵、原始 SQL 行 oracle 与 ASGI fixture 全部自建；不引用既有 tests helper，也不以生产 lease/identity 检测函数充当期望值。只调用被测 JobStore、JobEngine、Registry 和真实 workflow 路由。旧审查报告与探针只读参考，未执行或覆盖旧证据。

## 实际命令与证据

PowerShell 根目录：

```powershell
& apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-jobs/audit_candidate.py sha-before-restored.json
& apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-jobs/run_validation.py independent-first
& apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-jobs/audit_candidate.py sha-after.json
& apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-jobs/finalize.py
```

完整 pytest argv、起止时间、退出码、环境值与资源根在 independent-first-run.json；完整首跑日志/XML 在 independent-first.log / independent-first.xml。52 条逐例收据在 receipts.json，分组计数在 SUMMARY.json。**首败：无**，独立探针仅执行一次，没有择优合并多次计数。

Python 3.12.14；启动器在 pytest 与任何 app 模块导入前注入新的系统临时根 `C:\Users\96022\AppData\Local\Temp\zqky-g1-v00-jobs-34w2girq`、ZQKY_ENV=test、UTF8、PYTHONPATH。未导入 app.main；ASGI Settings 显式 credentials_file=None。8001 仅 ASGI 地址语义，未监听端口、未启动构建、未连接供应商/Qdrant/正式库/真实浏览器。连接全部 finally 关闭，线程全部 join，引擎 shutdown 已等待；新临时根保留，无递归删除。

not_run：全量 API/check/build/E2E、浏览器/Word/WPS、真实模型质量、Qdrant与压力规模；这些不在本独立 JOBS 子任务范围内，由 CTRL 和其他指定验收任务分别负责，不以此报告宣称整体 G1 或 B4 完成。多进程发布锁与恶意任务行损坏是既有范围外事项，本任务没有扩展结论。

产品/共享契约/迁移/锁文件/权威文档/Git 操作零写入；可写范围仅本批 v00-jobs。无残余阻断项；交 CTRL 汇总。
