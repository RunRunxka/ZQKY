# B3 公共任务与迁移独立审查证据

审查日期：2026-10-01。产品代码、已冻结 QA 文件与正式数据均未修改。
每次 standalone 导入 `app.main` 前，探针先将 `ZQKY_DATA_DIR` 指向新临时目录；
模型为受控替身；无真实网络、模型、Qdrant 请求。

## 独立探针

工作目录：`H:\备份xuexi\智启课源\apps\api`

```powershell
$env:PYTHONUTF8='1'
uv run --no-sync python 'H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B3-REVIEW-20261001\probes\jobs_late_failure_and_cancel.py'
```

退出码 0。探针断言所发现的当前错误行为，不能将其退出码理解为产品正确性通过。

| 场景 | 实际结果 |
| --- | --- |
| 模型名额尚未到手、尚无 provider 调用时，先请求取消；随后释放名额 | `cancel_requested=true` 后仍调用模型 1 次；最终 `cancelled`、未发布批次 |
| 旧整理 worker 已读 checkpoint、正要写任务失败；此时过期租约被新 attempt 接管，新 worker 经真实 CAS 批提交成功 | 新 attempt=2 与 token 未被覆盖；新建议在 DB 存在；已推进的 `nextBatchIndex=1` 被旧 worker 无条件写回 0，`suggestionIds` 丢失，checkpoint 只剩旧 worker 的 `jobError` |

第二场景只在临时库修改租约到期时间以确定性触发接管；新持有者的建议与进度由产品
`record_organize_batch` 提交，并非伪造 checkpoint。插入时序在旧 worker 的真实读/写间隙。

## 既有窄测试

```powershell
$b3JobsReviewData=Join-Path ([IO.Path]::GetTempPath()) ('zqky-b3-jobs-tests-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $b3JobsReviewData | Out-Null
$env:ZQKY_DATA_DIR=$b3JobsReviewData
$env:PYTHONUTF8='1'
uv run --no-sync python -m pytest tests/test_b3_score_migrations.py tests/test_jobs_engine.py tests/test_question_lease_batches.py tests/test_retry_dispatch.py tests/test_model_drift_guards.py -q -o addopts=''
```

退出码 0：**56 passed, 1 warning in 8.39s**。warning 为 Starlette TestClient
引用 anyio `BlockingPortal` 弃用别名，未出现失败或 skip。上述两条独立探针覆盖了这组
既有测试没有构造的取消与失败写 checkpoint 时序。

## 未形成缺陷的检查

- registry 的 `JobExecutor` 现从 engine 导入，装配在域服务构造之后，真实 retry 测试通过。
- publish 抛错由引擎使用原始 `JobLease` 收敛，租约匹配与取消优先正常。
- 0007 按新建/拷贝/删旧/改名流程，事务外关闭 FK、单事务恢复触发器、读全 FK 检查与
  integrity_check、失败回滚且 finally 恢复 FK；旧业务数据升级路径通过。
- DB 封存触发器主要保护 draft→confirmed UPDATE；直接 SQL 插入 confirmed 空修订能绕过
  该闸门，但现行服务没有这一写入路径。作为 DB 纵深保护观察项，未列为 API 产品缺陷。
- 模型指纹仅覆盖 `modelId/protocol/baseHost/apiFormat`；端口/路径差异不计入。
  `PROJECT_GUIDE.md` 明确冻结这个计算口径，本审查未将它列为新缺陷。

未执行：全量 pytest/npm check/e2e、正式数据迁移、真实模型、真实 Qdrant；本次为只读
审查，只跑与迁移/任务相关的窄验证和独立临时数据探针。
