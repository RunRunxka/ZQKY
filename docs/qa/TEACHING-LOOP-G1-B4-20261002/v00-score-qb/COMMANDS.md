# 独立命令与退出码

工作目录均为 `H:\备份xuexi\智启课源`。每次 pytest 前 shell 设置 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、`ZQKY_ENV=test`、`PYTHONPATH=<root>/apps/api`、全新系统 temp `ZQKY_DATA_DIR`；随后脚本在任何 app.main 导入前另设全新 bootstrap 根。每场景 Settings 的 data_dir 是新根，credentials_file=None。shell 根见各 `*-shell-root.txt`（首轮为 shell-temp-root.txt，第二轮 recheck-shell-root.txt）；bootstrap/病例根见 resources.json。

SHA 初检：

```powershell
apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-score-qb/verify_freeze.py before
# exit1，825项仅 next-env 在总控构建窗口异；暂停等待恢复
apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-score-qb/verify_freeze.py before-restored
# exit0，825项零差异，再开始行为验收
```

五次 pytest 命令使用同一精确参数，仅证据 stem 依次为 `first`、`recheck`、`final`、`accepted`、`accepted-v2`；每次标准输出/错误均用 Tee 保存 `.log`，退出码取 `$LASTEXITCODE` 另写 `.exit.txt`。完整命令：

```powershell
apps/api/.venv/Scripts/python.exe -m pytest -c apps/api/pyproject.toml docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-score-qb/test_independent_score_qb.py -x -q -o addopts='' --tb=short --junitxml=docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-score-qb/<stem>.xml 2>&1 | Tee-Object -FilePath 'docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-score-qb/<stem>.log'
$exitCode=$LASTEXITCODE
$exitCode | Set-Content -LiteralPath 'docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-score-qb/<stem>.exit.txt'
exit $exitCode
```

| stem | 单次结果 | pytest 时间 | exit |
|---|---|---|---|
| first | 20 passed / 1 failed / 0 skipped | 7.04s | 1 |
| recheck | 31 passed / 1 failed / 0 skipped | 9.50s | 1 |
| final | 41 passed / 1 failed / 0 skipped | 13.40s | 1 |
| accepted | 41 passed / 1 failed / 0 skipped | 13.38s | 1 |
| accepted-v2 | **53 passed / 0 failed / 0 skipped** | **16.15s** | **0** |

四个首败的夹具原因与修正见 RESULT.md；所有原收据保留。XML各自记录实际 case 数/失败/跳过/耗时，自动摘要见 EVIDENCE.json。不将不同运行计数相加。最终测试源 SHA 固定记录在 EVIDENCE.json。

验后与证据保护：

```powershell
apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-score-qb/verify_freeze.py after-r1
# exit0，825项零差异
apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-score-qb/verify_freeze.py after-r2 CANDIDATE-g1-r2.json
# exit0，826项零差异；r2只扩展安全.env.example覆盖，候选产品未变化
apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-score-qb/collect_evidence.py
# exit0，旧629证据零差异、53最终测试、147原表源、190临时病例根资源登记
```
