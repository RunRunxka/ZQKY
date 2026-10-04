# G1 任务租约与重试代码复查

2026-10-02，审查者 `/root/g1_jobs_review`，只读产品。范围为 JobStore、JobEngine、Registry、公共 workflow 路由，参考本批 G1 报告、关闭矩阵、实现者测试与独立 52 项探针。**未发现需要新增阻塞票的租约/重试缺陷。** 此结论不替代 G1 尚未执行的浏览器/E2E 门禁，也不代表 B4 已开工。

## 源码核对

- [JobStore](../../../../apps/api/app/repositories/jobs/repository.py)：`claim`、`heartbeat`、`complete`、`mark_cancelled`、`fail_if_current_lease` 在实际写事务取得后核时；有效期、原 token/attempt/running 与取消标志的判定在写锁内。失权或到期无人接管时不发布，不借当前行令牌伪装旧执行者。取消优先限定于有效原租约，过期执行者不会写取消终态。
- [JobEngine](../../../../apps/api/app/services/jobs/engine.py)：按目标 attempt 去重；queued 新轮等待上一轮 finalizer，不把旧 tracking 当新轮已调度。done callback 以任务对象身份删 tracking；shutdown 同时取消并等待旧轮与 pending 轮。执行前只读闸门与最终事务内闸门各司其职，前者不能替代后者。
- [Registry](../../../../apps/api/app/services/jobs/registry.py) 与 [公共路由](../../../../apps/api/app/api/v1/workflow_jobs.py)：公开 retry 将 accepted queued 新轮送入同一引擎；重复 queued 请求补调度且按目标 attempt 去重。没有另起无租约执行器。
- 顺带核题库 `record_organize_batch`/`record_organize_failure`：生产不传测试 `now`，有效期的统一时钟核对在题库实际写锁内；取消和原 attempt/token 在同事务核对，没有把测试固定时钟误当生产读钟。

## 本次独立补充与窄回归

最终单次 [review-jobs-r3.xml](review-jobs-r3.xml) / [log](review-jobs-r3.log)：**22 passed、0 failed、0 error、0 skipped，exit 0，pytest 2.900s**。其中 20 项为两个既有窄回归文件，另 2 项为本次自建 [test_retry_extra_boundaries.py](test_retry_extra_boundaries.py)：

1. 旧轮 failed 已提交但 cleanup 未退出；第一 retry queued 后被取消，再次三次并发 retry；解除旧轮屏障后 attempt 2 恰好一次，发布记录仅 `[2]`，冻结输入、hash 与模型快照不变。
2. 连续 attempt 1、2 都失败，各自 cleanup 尚未退出时接受下一轮 retry；第三轮阻塞中让旧 done callback 实际运行，tracking 仍属于第三轮；最终执行顺序 `[1,2,3]`，仅第三轮一条业务发布。

自建 fixture 使用新 TeachingCatalog 与 JobStore，不调用既有测试 helper；事件屏障只延长真实异步 finalizer 窗口。公共请求用 httpx ASGITransport 和真实 workflow 路由；没有监听 8001 或 5174，没有返回替身业务成功响应。

PowerShell 根目录实际命令（最终轮）：

```powershell
$env:ZQKY_DATA_DIR = (Get-Content -LiteralPath 'docs/qa/TEACHING-LOOP-G1-REVIEW-20261002/jobs/TEMP-DATA-ROOT.txt').Trim()
$env:ZQKY_ENV = 'test'
$env:PYTHONUTF8 = '1'
& apps/api/.venv/Scripts/python.exe -m pytest `
  docs/qa/TEACHING-LOOP-G1-REVIEW-20261002/jobs/test_retry_extra_boundaries.py `
  apps/api/tests/test_g1_job_lease_retry.py apps/api/tests/test_retry_dispatch.py `
  -q --junitxml=docs/qa/TEACHING-LOOP-G1-REVIEW-20261002/jobs/review-jobs-r3.xml
```

完整 stdout/stderr 与退出码分别保存在 r3 log、[exit](review-jobs-r3-exit.txt)。首次收集因我写错 Settings 的 import 路径而失败（exit 2）；第二轮自建两项因漏写必填 `allowed_origins` 而失败（exit 1），其余 20 项通过。两次均为审查夹具前置错误，修正只发生在新证据探针，原 [首轮 log](review-jobs.log)、[第二轮 log](review-jobs-r2.log) 及各自 XML/exit 完整保留，不计产品缺陷，也不将多轮加总。

## 边界与保全

新临时根见 [TEMP-DATA-ROOT.txt](TEMP-DATA-ROOT.txt)，在任何 app 模块/pytest 导入前注入；ASGI Settings 显式 `credentials_file=None`。本次没有导入 app.main，没有读取 `.env`、正式业务库或旧被拒删除目录。全部连接关闭、引擎 shutdown 等待完成；临时根和 pytest 临时库保留，没有删除操作或审批绕过。

本次未执行全量 API/check/build、浏览器/E2E、三视口、Word/WPS、真实模型/Qdrant、迁移演练、超过既有基线的压力、多进程发布协调或恶意损坏任务行。没有产品、共享契约、迁移、锁文件、权威状态文档或 Git 操作写入；新证据仅在本次 review/jobs 目录。
