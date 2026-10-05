# B7-B 预算执行器只读审查

本轮没有发现新增、可复现的产品缺陷。结论只覆盖当前离线执行器和已声明的 DI 接口；没有把缺少 live 宿主、授权及模型计费证明当作回归，也不据 fixture 通过宣称任何真实模型可调用。

## 证据

- [独立正确行为探针](probe_budget.py)、[完整首轮日志](probe-r1.log)、[原始机器结果](RESULT-r1.json)。未导入作者测试或旧 QA builder；匿名数据复用当前 `SourceScene`，真实业务经过生产 prepare/build_request/execute、JobEngine、proposal 与三协议 Provider，最终 HTTP 使用显式 MockTransport。
- 命令：`& apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G6-B7B-REVIEW-20261005/budget/probe_budget.py`。本轮首个完整测试轮退出 0：**19 个 unittest 方法，0 fail、0 error、0 skip**，包含 9 个生产链场景、8 次 fixture 发送，真实调用 0；不把表驱动 subtest 数量另加为方法数量。
- Python 实际 worker 自报 PID 25760，内部实测 7.488 秒；原 `startedEpoch`/`finishedEpoch`/argv 见结果 JSON。PTY 返回 8.512 秒是启动、导入与输出在内的宿主耗时，不能混作同一个测量。
- 六个 `controlled_*.py` 字节 SHA 与冻结 `CANDIDATE-B7B-offline-r1.json.sourceFiles` 完全一致。本轮没有修改产品文件、正式配置、旧 QA 或原控制状态目录。
- 首轮没有测试首败。后续只读定位命令曾把 Windows 通配符直接交给 `rg` 而返回退出 1，改用 `rg -g controlled_*.py` 后正常；这是定位命令错误，没有放宽或重跑正确行为探针。原测试日志保留。

## 独立核对结果

| 判据 | 实测 |
| --- | --- |
| 恰好预算上限 / 超出一 token | 已结算 10 后下一例拒绝；生产预算 5095 对 5096 上界拒绝，零发送、零新 attempt |
| 已核用量为 0 | 结算 0 仍消耗一次 attempt；换 label 后按原 attempt 闸门拒绝 |
| 同 authorization 改 scope | SCOPE_DRIFT，原账本字节保持，不生成空账本 |
| reserved/dispatched/responded 重启 | 三状态均转 unknown，完整保留预留且停止后续发送 |
| 坏账本 | 负数、bool、状态/发送数冲突及 attempt 序号冲突均 LEDGER_CORRUPT，坏字节不覆盖 |
| 排他锁 | 同进程第二 owner 立即 LEDGER_BUSY；原 owner 退出后重新获得锁 |
| usage 形状 | bool、非整数、不一致 total、附加 reasoning 字段及超证明上界均拒绝；合法零用量接受 |
| 三协议成功 | chat/responses/anthropic 各一个真实生产链，单次 fixture 发送、已核 200 结算、教师六字段保持 |
| 业务 JSON 与 length 失败 | 两条链均保留早于业务校验的 200 用量，消费 attempt；未用 unknown 替代已核 usage |
| unknown / 越界 / HTTP500 | 各条链均保留 5096 完整预留并停止；HTTP500 没有据状态码猜测未计费 |
| live CLI | 未给 authorization 路径与给不存在路径分别 AUTHORIZATION_MISSING / BILLING_BOUND_UNSUPPORTED；均退出 2，路径没有被打开或创建，真实调用 0 |
| 人工结论 | 所有 fixture 结果仍 teacher_pending / native_pending，selectionActor=qa |

Guard 在生产导入前建立 `ZQKY_DATA_DIR`、`ZQKY_ENV=test`、`PYTHONUTF8=1` 与全新 TEMP。原结果记录合法生产导入 184、TEMP SQL 1124、asyncio self-pipe 9；正式 env/data/DB、未隔离 main、真实网络五项禁止计数均 0，`mainImported=false`。所有 scene 在 finally 关闭，不启动服务或额外子进程，不删 TEMP。

## 下一阶段最小前置

1. 用户明确授权一个具体 `modelProfileId` / `modelId`，精确 `caseIds` 与等长 `sampleCount`、每例 `maxAttempts`、当前支持的总 token 预算。教师与 native 安排单列，不塞入严格 scope。
2. 可信宿主把人的真实授权来源绑定稳定 `authorizationId` 和不可变 scope；经既有后端配置/凭证机制获得生产 handle。不得把用户可写 JSON 或自报 `human_verified=true` 当真人授权，不读正式业务库。
3. 只为该模型建立可查证的 BillingProof，绑定最终 wire、input/output/reasoning/其他收费项的完整上界与可核 usage 语义。当前 fixture 1000/4096 证明不得复用到真实模型；成本模式和额外 usage 维度仍未支持，不能只补数字或 switch 后放行。
4. 固定控制 namespace，并承接该授权既有账本。使用原生产 Provider、单次可核 HTTP 发送与无隐藏重试 transport，保留现有预留、未知停止及原收据重放判据。当前 live DI 只允许 HTTPS 非回环端点；如用户选本地模型，应明确增加有证据的受控本地宿主支持，而不能称其已可用或把回环都冒称 fixture。
5. 先独立离线验收新宿主/proof 的失败边界，再按明确真实范围执行；按实际用量、实际发送、未选案例及 STOP 后未运行案例分别交付。未返回真人/Word-WPS证据时继续 pending。

本轮没有重新跑全站 check/E2E，没有执行 live、教师评价、Word/WPS、Qdrant、正式迁移或正式数据读写。独立多进程锁与取消/落盘故障更广覆盖属于原 V01 技术证据，本轮只读审阅，没有冒称本轮重跑。
