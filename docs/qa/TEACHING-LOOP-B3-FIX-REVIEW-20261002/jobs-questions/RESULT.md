# B3-FIX r7 公共任务／题库后端只读审查结果

任务 JQ-REVIEW v1，验收者 `/root/b3fix_jobs_questions_review`，2026-10-02。仅审查未提交的 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec` 候选；没有修改产品、既有测试、根权威文档或旧 QA。只写本目录。窄回归结束与最终探针结束后候选 r7 的 **168 项 SHA-256 均全部一致、0 漂移**，见 [hash-audit.json](hash-audit.json)、[hash-audit-final.json](hash-audit-final.json)。

**结论：4 条具体 P2 未关闭。** 新建正确行为探针一次合跑 **5 failed、exit1、1.71s**；其中两条分别从仓储和引擎证明同一提交过期问题，其余各证明一条问题。不是将失败探针计作通过。既有相关回归一次 **91 passed、exit0、27.18s**，不能替代新增边界验收。

## 发现

1. **JQ-R01 / P2：过期租约仍可提交业务结果。** [repository.py:521](../../../../apps/api/app/repositories/jobs/repository.py)–523 调用 `_require_current_lease`，其 656–660 只核 `running/attempt/token`，不核 `lease_expires_at`。租约到期且尚无人接管时，`complete()` 仍执行 publish 并置 succeeded。引擎在 268 行的只读闸门不能替代事务内检查：最后一次读有效后，等待 SQLite 写锁／跨过到期点，再进入 `complete` 仍能发布。TTL=3、逻辑时间=4 的真实临时库写入 sentinel `late` 并 succeeded；引擎最后读后推进到 4 的探针亦写 `engine-late` 并 succeeded。正确行为应在拿写锁后核有效期限并零业务写入。证据：[probes-final.log](probes-final.log)，`test_expired_lease_cannot_publish_even_without_a_takeover`、`test_engine_last_read_gate_does_not_replace_publication_expiry_cas`。完整探针：[test_review_jobs_questions.py:36](test_review_jobs_questions.py)。此 `complete` 漏检是候选中仍存在的旧边界缺口，不宣称本批新引入。

2. **JQ-R02 / P2：失败 CAS 用等 SQLite 写锁前的时间，过期后仍写终态。** [repository.py:580](../../../../apps/api/app/repositories/jobs/repository.py)–583 在进入 `write_transaction` 前采 `now`，新增 `_lease_active(..., now)` 因而可能使用过时值。真实第二连接持 `BEGIN IMMEDIATE`；租约到期=3，失败线程在 2 秒读钟后等待写锁，推进到 4 后释放锁，仍将任务改 failed，`finishedAt=2`。这与 R01 的“完全未校验到期”不同：这里虽校验，但检查时点错。正确行为应在获得写锁后重新采时，失权零写。证据：[probes-final.log](probes-final.log)，`test_failure_cas_rechecks_time_after_real_sqlite_lock_wait`；[探针:79](test_review_jobs_questions.py)。

3. **JQ-R03 / P2：不同共同材料的富内容题被自动跳过，且无法显式作为新题确认。** [service.py:1923](../../../../apps/api/app/services/question_bank/service.py)–1929 仍只用旧 `content_fingerprint` 查重，它不含 `richContent.sharedMaterials`。本批允许权威富内容，但已核验／落库的 `derived-v1` 未参与确认比较。两道已审核题题干／选项相同，共同材料分别“实验溶液浓度为 1 mol/L”与“2 mol/L”，派生指纹不同：第一题入库；第二题默认确认 HTTP200、`skippedDraftIds=[第二题]`、`failures=[]`、题目总数仍 1。显式 `edit_as_new` 仍返回 `DUPLICATE_UNRESOLVED`。共同材料是题目条件，不能仅因兼容 Markdown 投影相同当成完全重复。正确行为应以权威题面参与重复判定，同时保留旧指纹／旧题兼容与答案冲突审核语义。证据：[probes-final.log](probes-final.log)，`test_distinct_shared_material_is_not_silently_skipped_as_a_duplicate`；[探针:124](test_review_jobs_questions.py)。

4. **JQ-R04 / P2：上一轮收尾期间点击公共 retry，200 queued 回执后新一轮未自动调度。** [registry.py:91](../../../../apps/api/app/services/jobs/registry.py)–92 将同 job 的旧任务仍在 `_tracked` 当成“本次已调度”。上一轮 failed 已提交后，引擎仍需 await heartbeat cleanup；此窗口 retry 已把任务置 queued，但注册表因旧 task tracking 返回 True，不创建新任务。旧轮收尾删除 tracking 后，库中留下无人执行的 queued。旧收尾结束后再次 POST retry 可以补调度恢复，但首次 HTTP200 已接受的重试仍未兑现。探针只延长现存 heartbeat cleanup 等待，真实 JobStore／JobEngine／Registry＋真实 ASGI `POST /api/v1/workflow-jobs/{id}/retry`：HTTP200 queued@1，释放旧轮后仍 queued@1、tracking=false、执行轮次=[1]。正常 retry 应调度一次 attempt2，或拒绝当前窗口而不返回已接受的虚假调度收据。证据：[probes-final.log](probes-final.log)，`test_retry_while_previous_attempt_settles_is_actually_scheduled`；[探针:155](test_review_jobs_questions.py)。初次直接路由函数复现保留 [retry-probe.log](retry-probe.log)。注册表该分支是候选仍存在的旧边界缺口，不宣称本批新引入。

## 已有覆盖与结果

原 B3-R09/R10 的正确行为回归通过：整理失败 checkpoint 原 attempt/token CAS、旧轮迟到不覆盖新轮、过期 heartbeat 不复活、等模型名额／解析时取消零 Provider 调用。已读执行前指纹守卫与六态／公共 retry 契约，核对题库确认和正式 PATCH 的知识点活动／学科／发布锁复核。

一次相关既有回归覆盖以下 5 文件：[regression.log](regression.log)、[regression.xml](regression.xml)：

- `test_jobs_engine.py`：三域仓储、领取／心跳、接管旧 token 零写、取消、事务回滚、并发与名额等待。
- `test_b3_review_job_fixes.py`：R09/R10、失败 checkpoint 身份矩阵与取消。
- `test_question_rich_content.py`：富内容／Markdown 同步、显式 null、受管与兼容图片真实散列、引用／owner／路径限制、坏主文件不 fallback、提交前 IO 在事务／发布锁外、重放、原版本不变、拆合／AI 应用护栏。
- `test_question_publication_boundaries.py`：显式／继承关联从复核到正式修订提交保持发布锁，归档知识点禁止进入新修订。
- `test_model_drift_guards.py`：排队时模型漂移与缺失指纹零调用／零候选，正确指纹来源。

## 命令与隔离边界

PowerShell，根目录，先设置 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、`PYTHONPATH=<根>/apps/api`、新的系统临时 `ZQKY_DATA_DIR` 再调用已有 `.venv/Scripts/python.exe`。自建探针文件也在任何间接 `app.main` 导入之前设置独立临时数据根。HTTP 为进程内 ASGI／TestClient，8001 是地址语义，未启动监听服务。Harness 的显式 Settings 使用临时数据根且 `credentials_file=None`，未读取正式 `.env`；未连接 Qdrant／真实模型／教材源／真实浏览器。

```powershell
& apps/api/.venv/Scripts/python.exe -m pytest docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/jobs-questions/test_review_jobs_questions.py -q -s -o addopts='' --junitxml=docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/jobs-questions/probes-final.xml
& apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_jobs_engine.py apps/api/tests/test_b3_review_job_fixes.py apps/api/tests/test_question_rich_content.py apps/api/tests/test_question_publication_boundaries.py apps/api/tests/test_model_drift_guards.py -q -o addopts='' --junitxml=docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/jobs-questions/regression.xml
```

两次均只有既有 Starlette/AnyIO BlockingPortal 弃用 warning1。初始4条失败日志 [probes.log](probes.log) 与 XML保留；后续仅把自建 retry 探针升级真实 HTTP，未改产品或既有测试。

not_run：全量 API/check/build/E2E、浏览器视觉、真实供应商教学质量、Word/WPS、Qdrant、正式库迁移、多进程发布锁、压力规模，原因是本任务为指定后端链的只读窄审查；未以旧批报告代替本次实跑。没有提交／推送／切分支／手工清理目录。线程 join、连接关闭、引擎 shutdown、TestClient正常退出；自建临时 bootstrap／pytest 数据保留，不递归删除未知目录。

下阶段应先修复以上4条并用相同正确行为断言回归，重冻候选、独立验收与适用门禁后再决定后续教学闭环批次；本审查没有实施授权。


