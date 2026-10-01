# B3 代码审查命令与结果

日期：2026-10-01。应用数据在临时目录；standalone 探针在导入 `app.main` 之前设置 `ZQKY_DATA_DIR`。TestClient 的 8001 是测试请求地址，不是常驻监听服务。模型为受控替身。

## 1. 定版现场核对

仓库根目录 `H:\备份xuexi\智启课源`：

```powershell
git branch --show-current
git rev-parse HEAD
$b3Manifest = Get-Content docs/qa/TEACHING-LOOP-B3/FROZEN-B3.json -Raw | ConvertFrom-Json
$b3Drift = @()
foreach ($b3Entry in $b3Manifest.files.PSObject.Properties) {
  if (-not (Test-Path -LiteralPath $b3Entry.Name)) { $b3Drift += $b3Entry.Name; continue }
  $b3Actual = (Get-FileHash -LiteralPath $b3Entry.Name -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($b3Actual -ne $b3Entry.Value) { $b3Drift += $b3Entry.Name }
}
```

开工结果：main，HEAD `0f4b8cb190c2265d819b90e5d6df4e3954ad1906`；清单声明 163、实际核对 163、漂移 0。
收尾核对结果与审查文件散列单独记录于 `REVIEW-MANIFEST.json`，不修改 B3 清单。

## 2. 成绩独立 API 诊断

仓库根目录：

```powershell
$env:PYTHONIOENCODING='utf-8'
& apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/scores_review_probe.py
```

最终 exit 0；5 类场景：同表头修正 422、C/c 重复封存错误分数、recorded 非数值三种输入 500、GB18030 乱码、未知身份表头 500。输出为 `probes/scores_review_probe_output.jsonl`，详细解释 `probes/scores_FINDINGS.md`。

## 3. 公共任务独立诊断与既有窄测试

工作目录 `H:\备份xuexi\智启课源\apps\api`：

```powershell
$env:PYTHONUTF8='1'
uv run --no-sync python ../../docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/jobs_late_failure_and_cancel.py

$b3JobsReviewData=Join-Path ([IO.Path]::GetTempPath()) ('zqky-b3-jobs-tests-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $b3JobsReviewData | Out-Null
$env:ZQKY_DATA_DIR=$b3JobsReviewData
uv run --no-sync python -m pytest tests/test_b3_score_migrations.py tests/test_jobs_engine.py tests/test_question_lease_batches.py tests/test_retry_dispatch.py tests/test_model_drift_guards.py -q -o addopts=''
```

独立诊断 exit 0，2 类时序确认当前缺陷；既有窄测试 exit 0，**56 passed、1 warning in 8.39s**。详见 `probes/jobs_review_evidence.md`。

## 4. 前端真实响应来源与实际组件诊断

在 `apps/api` 分别执行：

```powershell
$env:PYTHONUTF8='1'
uv run --no-sync python ../../docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/ui_absence_source.py
uv run --no-sync python ../../docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/ui_generation_source.py
```

两条最终 exit 0。第一条错误承认 422、正确承认 200；第二条真实 202 queued@0→succeeded@1，候选批次真实落库。

仓库根目录：

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/ui_vitest.config.ts
```

最终 exit 0，**3 文件/4 测试**，诊断首次观察、伪 missing 强制确认和卸载迟到响应。使用真实组件/hooks/API 客户端，fetch 返回的前两类响应来源是真实隔离 API；并非真实浏览器 E2E。详见 `probes/ui_FINDINGS.md`。

## 5. 成绩既有窄测试

工作目录 `apps/api`：

```powershell
$b3ScoresReviewData=Join-Path ([IO.Path]::GetTempPath()) ('zqky-b3-score-tests-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $b3ScoresReviewData | Out-Null
$env:ZQKY_DATA_DIR=$b3ScoresReviewData
$env:PYTHONUTF8='1'
uv run --no-sync python -m pytest tests/test_scores_imports.py tests/test_scores_confirm.py tests/test_scores_corrections.py tests/test_scores_scale.py -q -o addopts=''
```

exit 0，**33 passed、1 skipped、1 warning in 10.58s**。warning 为 Starlette TestClient 的 anyio 别名弃用提示。skip 是默认需显式环境开关的 200 人×100 叶基线，默认运行的规模链为 20 人×100 叶；没有把 skipped 写成通过。

## 6. 两条未列缺陷的范围观察

工作目录 `apps/api`：

```powershell
$env:PYTHONUTF8='1'
uv run --no-sync python ../../docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/root_totals_attendance.py
```

exit 0，结果保存 `probes/root_totals_attendance.json`：原表总分 900 单位、计算 600 单位仍成功无警告；教师单格修正可以形成 absent 出勤快照下 recorded/absent 混合单格状态。对这两项的范围解释见 REVIEW.md，不计入 10 项缺陷。

## 未执行

全量后端、npm check、完整 E2E、200 人基线再次实跑、真实模型/Qdrant/Word/WPS、正式数据迁移。原因：本次是定向代码审查和反例验证，使用隔离数据；未修改产品。B3 交付报告中的历史运行数字没有冒称为本次重跑。

**诊断测试的 exit 0 表示已成功复现其断言的错误行为，不表示产品缺陷已修复。**
