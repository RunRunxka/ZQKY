# 实跑命令与证据索引

Windows PowerShell，仓库根。全量API、check/build、浏览器服务均由总控串行组织。Node26统一 `NODE_OPTIONS=--no-experimental-webstorage`；Python最终统一 `PYTHONUTF8=1` 与 `PYTHONIOENCODING=utf-8`。应用脚本/服务在任何app.main间接导入前设置绝对OS临时 `ZQKY_DATA_DIR` 与 `ZQKY_ENV=test`，不读正式.env或正式数据根。

| 真实命令/范围 | 结果、退出码 | 日志/证据 |
| --- | --- | --- |
| `npm.cmd run check`，r3 | typecheck/lint/build通过；108文件1069单测全过，exit0 | logs/root-check-r3.txt |
| `npm.cmd run test:api -- -o addopts=-ra --junitxml=../../docs/qa/TEACHING-LOOP-B3-FIX-20261002/root-api-final.xml`，r3 | 1517pass/6fail/5warnings，exit1，208.09s，首败不覆盖 | logs/root-api-final-r3.txt，root-api-final.xml |
| 同一完整API命令，r4，XML改为root-api-final-r4.xml；显式 `ZQKY_RUN_SCALE_BASELINE=1` | **1523pass/1warning，exit0，207.40s** | logs/root-api-final-r4.txt，root-api-final-r4.xml |
| API失敗窄复验（备份/成绩旧上下文/lease/R19）r3 | 24pass/1fail，exit1；R19冷启动317ms实证保留 | logs/root-api-failure-narrow-r3.txt |
| 调整后API窄复验r4 | 26pass/1warning，exit0，29.60s | logs/root-api-narrow-r4.txt |
| `npm.cmd run build`，r5，构建前设 `ZQKY_API_ORIGIN=http://127.0.0.1:8001` | exit0；实际routes-manifest核目标8001 | logs/root-build-isolated-r5.txt，isolated-build-proxy.txt |
| `npm.cmd run test:e2e -- assessments.spec.ts question-bank-real.spec.ts --trace=retain-on-failure`，r4 | 3pass/2fail/1未运行，exit1；原卷转发丢File字节、题库漏先保存再审核 | logs/root-browser-final-r4.txt，browser-r4 |
| 两真实spec，r5初轮 | 代理被旧构建固定8000，已停止；1fail/3serial未运行/题库审核链1pass，exit1，非全验收 | logs/root-browser-final-r5.txt，browser-r5-startup |
| 两真实spec，r5按8001重建后，trace off | 4pass/1fail/1未运行，exit1；实际响应重放正确，仅测试错用fresh成功文案 | logs/root-browser-final-r5-isolated.txt，browser-r5-isolated |
| 两真实spec，r6 | 4pass/1fail/1未运行，exit1；完整业务与修正通过，390页面布局断言失败 | logs/root-browser-final-r6.txt，browser-r6 |
| `npm.cmd run test:e2e -- assessments.spec.ts -g '完整真实链' --trace=off` | 1fail，exit1；1440/1920 root无溢出，390为413px；实际图片复核定位修正下拉框长ID | logs/root-browser-layout-diagnostic.txt，browser-layout-first |
| 两spec `npx.cmd eslint ... --max-warnings=0`，r5 | exit0，不放宽验收条件 | logs/root-browser-spec-r5-lint.txt |
| V00-G0 三自建Python文件合跑 | 60pass/1warning，exit0，11.99s | logs/v00-g0-final-r3.txt，V00-G0-REPORT.md完整命令 |
| V00-SCORES 两自建Python文件合跑 | 71pass/1warning，exit0，21.36s | logs/v00-scores-final-r3.txt，V00-SCORES-REPORT.md完整命令 |
| V00-FRONTEND 五自建真实组件/hook文件合跑 | 105pass，exit0；r3验收前后165 hash一致 | logs/v00-frontend-r3-final.log，V00-FRONTEND-REPORT.md完整命令 |
| V00-G0 `test_clock_audit.py` | 2pass，exit0，1.64s；50ms/70ms精确边界，真实jieba冷加载333ms | logs/v00-g0-clock-audit.txt |

最终r7门禁如下（没有重跑产品API，因为r3后端至r7不变）：

| 最终命令 | 实际结果 | 证据 |
| --- | --- | --- |
| `npm.cmd run check`，r7，构建前代理8001 | typecheck/lint0警告/108文件1069单测/build通过，exit0；单测81.28s | logs/root-check-final-r7.txt |
| `npm.cmd run test:e2e -- assessments.spec.ts question-bank-real.spec.ts --trace=off`，r7 | 6passed/0fail/0skip，exit0，24.6s | logs/root-browser-final-r7.txt，browser-final-r7/results.json，real-chain-receipts-r7/ |
| `npm.cmd run test:e2e`，r7，默认trace策略 | 153passed/0unexpected/0flaky/0skip，exit0，361.327s | logs/root-e2e-full-r7.txt，browser-full-r7/results.json，FULL-E2E-SUMMARY.json |
| `apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-B3-FIX-20261002/finalize_evidence.py`，无app导入 | exit0；168候选0差异、HEAD/分支原样、git diff --check exit0、原next-env SHA匹配；90项源/权威文件含原用户文件 | FINAL-VERIFICATION.json，POST-ACCEPTANCE-DOCS.json，DELIVERY-FILES.json |
| `apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-B3-FIX-20261002/audit_delivery.py`，只读产品 | exit0；168候选0差异，提取全量规模stdout/注释；确认累计3660ms，首屏537ms/翻页569ms，后验权威文档SHA | FULL-E2E-SUMMARY.json，FINAL-VERIFICATION.json，POST-ACCEPTANCE-DOCS.json |

原件同时保留旧模块后端不可用错误路径的日志；这些通过的错误/替身测试不能扩大成所有旧业务真实服务验收。上表不把重复窄验收数字相加成全量计数。实现者的全部窄命令、首败与退出码分别记录在各RESULT卡；独立探针首败/修正全部在三份V00报告和原logs中。

真实浏览器最终命令环境如下，先检查实际构建routes-manifest目的地址与8001一致。Next改代理目标需要重新build，单改start环境不会替换已编译rewrite。

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
$env:ZQKY_API_ORIGIN='http://127.0.0.1:8001'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:ZQKY_RUN_SCALE_BASELINE='1'
npm.cmd run check
npm.cmd run test:e2e
```

8001由spec先核空闲后启动本批临时FastAPI；5174由Playwright独占webServer启动并释放。替身Provider只替代模型输出；名单/原卷/施测/成绩/题库全部真实HTTP与四库。成绩故障注入实际先完成HTTP200业务提交，再丢浏览器响应，第二次严格deepEqual原body且replayed=true同revision。

未执行：真实模型质量、Word/WPS、Qdrant（无16333需求）、正式库迁移、超200×100业务规模/跨进程发布协调。首败trace有写入超时造成不完整ZIP的事实保留，不冒称已读完整trace；JSON/AX/截图/API收据另作独立证据。

资源收口：原next-env通过保存的base64原字节WriteAllBytes恢复，SHA匹配0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc；`Get-NetTCPConnection -State Listen`过滤8001/5174/16333返回空。六个有记录root temp目录的递归删除命令在执行前被工具审批拒绝，返回blocked by policy，没有命令退出码、没有实际删除，也未换方式删除。RESOURCE-CLEANUP.json保留绝对路径和存在状态。IAB本批tab close/viewport reset已完成，未关闭用户tab或未知进程。
