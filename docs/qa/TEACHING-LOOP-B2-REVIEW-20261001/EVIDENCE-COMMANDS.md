# B2 代码审查 · 复现命令与验证范围

日期：2026-10-01。对应 [审查报告](REVIEW.md)。仅审查和保存证据，没有修复产品。

## 基线

- 实际分支：`main`。
- 实际 HEAD：`0f4b8cb190c2265d819b90e5d6df4e3954ad1906`。
- B2 r2：逐一读取 `docs/qa/TEACHING-LOOP-B2/FROZEN-CANDIDATE.json.files`，重算 SHA256，**84/84，0 缺失，0 不一致**。
- B2 未提交工作区、旧设计交付物与历史证据保留。
- 本机后端 `sqlite3.sqlite_version`：`3.53.1`（只读运行时查询）。

## 现有测试

在 `apps/api` 的独立 PowerShell 进程中，先建立临时目录并设置 `ZQKY_DATA_DIR`，再运行：

```powershell
uv run --no-sync python -m pytest tests/test_b2_migrations.py tests/test_b2_contracts.py tests/test_papers_draft_confirm.py tests/test_papers_import.py tests/test_papers_proposals.py tests/test_assessments_api.py tests/test_question_generation.py tests/test_question_job_engine.py -q
```

实际执行结束，**退出码 0，126 项通过**。命令的 quiet 配置没有输出数字摘要；另以同组参数 `--collect-only -q -o addopts=''` 核对 **126 tests collected**。运行输出保留在本审查会话工具记录，不伪造逐例日志。

有一条既有 Starlette/AnyIO 的弃用 warning；没有测试失败。本次未执行全量 API、check/build/E2E，没有用原 B2 全量报告冒充本次实跑。

## 新探针

**以下 7 个命令均实际执行完成，退出码 0。这里的 0 表示“诊断程序运行成功并捕获缺陷”，不表示产品验收 pass。** 下一批修复后应验证正确行为，不继续以诊断程序 exit 0 作为通过条件。

Python 探针在任何可能导入 `app.main` 的导入前设置独立 `ZQKY_DATA_DIR`，自建临时数据；模型全部为替身。没有启动常驻 API、浏览器或端口。

### 原卷（在 apps/api）

```powershell
uv run --no-sync python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2-REVIEW-20261001\probes\papers_probe.py"
uv run --no-sync python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2-REVIEW-20261001\probes\papers_content_probe.py"
```

- [主探针](probes/papers_probe.py)、[日志](probes/papers_probe.log)、[JSON](probes/papers_probe.json)：未归属块正文缺失、任意 resolution 放行、归档后发布、旧标题漂移、执行模型与来源指纹不同。
- [题面损失探针](probes/papers_content_probe.py)、[日志](probes/papers_content_probe.log)、[JSON](probes/papers_content_probe.json)：必要图形未补录仍确认，空题面仍确认。

### 题库与任务（在 apps/api）

```powershell
uv run --no-sync python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2-REVIEW-20261001\probes\question_jobs_probe.py"
uv run --no-sync python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2-REVIEW-20261001\probes\question_model_probe.py"
uv run --no-sync python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2-REVIEW-20261001\probes\question_lease_probe.py"
```

- [任务/关联探针](probes/question_jobs_probe.py)、[日志](probes/question_jobs_probe.log)、[JSON](probes/question_jobs_probe.json)：公共重试一直 queued；公开归档 API 后题库仍确认；修改学科继续继承跨学科知识点。第一轮保存件为同目录 `question_jobs_probe-first.log/.json`，最后一轮采用公开归档入口。
- [模型探针](probes/question_model_probe.py)、[日志](probes/question_model_probe.log)、[JSON](probes/question_model_probe.json)：排队时同 profile 改模型，实际 model-B，但记录 model-A 指纹。
- [租约探针](probes/question_lease_probe.py)、[日志](probes/question_lease_probe.log)、[JSON](probes/question_lease_probe.json)：旧 attempt 及 interrupted 后仍写入中间批建议/checkpoint。此项为仓储失权注入，不伪称普通 HTTP 能指定 lease token。

### 前端任务与施测（在仓库根）

```powershell
node --no-experimental-webstorage docs/qa/TEACHING-LOOP-B2-REVIEW-20261001/probes/ui_job_probe.cjs
./apps/api/.venv/Scripts/python.exe -X utf8 docs/qa/TEACHING-LOOP-B2-REVIEW-20261001/probes/assessment_date_probe.py
```

- [React/jsdom 探针](probes/ui_job_probe.cjs)、[日志](probes/ui_job_probe.log)、[JSON](probes/ui_job_probe.json)：加载现行 hook，StrictMode 更新失效及旧重试覆盖新任务；两项 `bugReproduced=true`。没有运行真实浏览器。
- [施测日期探针](probes/assessment_date_probe.py)、[日志](probes/assessment_date_probe.log)、[JSON](probes/assessment_date_probe.json)：真实 HTTP 链创建后修改日期，归属不覆盖但仍 200 且未显式确认，`bugReproduced=true`。

## 证据边界

- 探针程序、日志和 JSON 是本次审查证据，不能修改 B2 历史验收记录来使结论一致。
- 候选哈希再次核对在交付前完成；本目录文件及 B3 提示词不属于 B2 r2 的 84 文件清单。
- 未执行：全量 API/check/E2E、真实模型、真实 Word/WPS、Qdrant、正式数据迁移、人工视觉和高负载测试。本次只对代码与隔离复现路径作判断。
