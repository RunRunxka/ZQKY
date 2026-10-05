# G1-QB v1.1 命令收据

所有命令在仓库根目录 PowerShell 执行。每次调用 Python 前均执行下列隔离前置，`<prefix>` 与根记录一一对应；新测试的显式 Settings 另指定 `credentials_file=None`。TestClient 使用真实 FastAPI/四库与 8001 地址语义，没有启动监听服务。

```powershell
$taskDataRoot=Join-Path ([System.IO.Path]::GetTempPath()) ('<prefix>'+[guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $taskDataRoot | Out-Null
$env:ZQKY_DATA_DIR=$taskDataRoot
$env:ZQKY_ENV='test'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH=(Join-Path (Get-Location) 'apps/api')
```

下面的各命令完整参数记录了实际运行。每次 stdout/stderr 经 `2>&1 | Tee-Object -FilePath <同名>.log` 保存，捕获 `$LASTEXITCODE` 到 `<同名>.exit.txt`，再 `exit $taskExit`；每次计数独立，不相加为通过总数。

```powershell
# first：zqky-g1-qb-tests-，temp-root.txt
& apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_g1_question_duplicate_identity.py -q -o addopts='' --junitxml=docs/qa/TEACHING-LOOP-G1-B4-20261002/g1-qb/first.xml

# second：zqky-g1-qb-tests-，second-temp-root.txt
& apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_g1_question_duplicate_identity.py -q -o addopts='' --junitxml=docs/qa/TEACHING-LOOP-G1-B4-20261002/g1-qb/second.xml

# regression-first：zqky-g1-qb-regression-，regression-temp-root.txt
& apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_question_bank_confirm.py apps/api/tests/test_question_rich_content.py apps/api/tests/test_question_publication_boundaries.py apps/api/tests/test_question_generation.py -q -o addopts='' --junitxml=docs/qa/TEACHING-LOOP-G1-B4-20261002/g1-qb/regression-first.xml

# batch-first：zqky-g1-qb-batch-，batch-temp-root.txt
& apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_g1_question_duplicate_identity.py -k two_true_repeats -q -o addopts='' --junitxml=docs/qa/TEACHING-LOOP-G1-B4-20261002/g1-qb/batch-first.xml

# final-correct：zqky-g1-qb-final-，final-temp-root.txt
# 旧探针原文件只读执行材料正确行为用例，XML/log 写本批目录，不覆盖旧件。
& apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_g1_question_duplicate_identity.py docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/jobs-questions/test_review_jobs_questions.py -k 'not expired_lease and not engine_last_read and not failure_cas and not retry_while' -q -o addopts='' --junitxml=docs/qa/TEACHING-LOOP-G1-B4-20261002/g1-qb/final-correct.xml

# regression-final：zqky-g1-qb-regression-final-，regression-final-temp-root.txt
# 中间记录：暂排除已证明是新算法数量契约的旧断言，由 CTRL 登记后更新。
& apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_g1_question_duplicate_identity.py apps/api/tests/test_question_bank_confirm.py apps/api/tests/test_question_rich_content.py apps/api/tests/test_question_publication_boundaries.py apps/api/tests/test_question_generation.py -k 'not test_derived_fingerprint_is_versioned_and_does_not_rewrite_legacy_column' -q -o addopts='' --junitxml=docs/qa/TEACHING-LOOP-G1-B4-20261002/g1-qb/regression-final.xml

# accepted：zqky-g1-qb-accepted-，accepted-temp-root.txt
# CTRL v1.1 分别核 derived-v1/surface-v1 各一行，总2，旧列/补算断言均保留；无排除。
& apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_g1_question_duplicate_identity.py apps/api/tests/test_question_bank_confirm.py apps/api/tests/test_question_rich_content.py apps/api/tests/test_question_publication_boundaries.py apps/api/tests/test_question_generation.py -q -o addopts='' --junitxml=docs/qa/TEACHING-LOOP-G1-B4-20261002/g1-qb/accepted.xml

git diff --check -- apps/api/app/services/question_bank/service.py apps/api/app/services/question_bank/fingerprint.py apps/api/app/services/question_bank/rich.py apps/api/app/repositories/question_bank/catalog.py apps/api/tests/test_g1_question_duplicate_identity.py
```

| 运行 | 一次运行结果 | 首败/修复意义 |
| --- | --- | --- |
| first | 11 failed、8 passed、1 warning，6.74s，exit1 | 本次新增算法未识别内部 snake_case 富内容，预览错误；首败保留 |
| second | 19 passed、1 warning，7.45s，exit0 | 统一 camelCase/snake_case 后同一组正确行为通过 |
| regression-first | 96 passed、1 failed、1 warning，23.30s，exit1 | 仅原指纹表总行数固定1断言与新增第二算法冲突 |
| batch-first | 2 failed、19 deselected、1 warning，0.77s，exit1 | 一次确认包先全查后插的原路径创建两条真重复；原包应去重/整体拒绝 |
| final-correct | 22 passed、4 deselected、1 warning，7.95s，exit0 | 当时21新用例+旧R07原文1材料探针；4条公共任务用例不在本任务范围 |
| regression-final | 118 passed、1 deselected、1 warning，31.12s，exit0 | 中间收据；22新用例+96既有用例，数量断言等待CTRL更新 |
| accepted | 119 passed、0 deselected、1 warning，30.31s，exit0 | 22新用例+97既有回归，含CTRL登记更新的算法数量检查，无排除 |

`accepted` 的最终实际计数见 [RESULT.md](RESULT.md) 与 [accepted.xml](accepted.xml)；`regression-final` 不代替包含该用例的最终回归。每轮 warning1 都是既有 Starlette/AnyIO BlockingPortal 弃用说明。
