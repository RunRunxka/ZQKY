# B3-FIX r7 成绩/施测后端只读审查结果

任务：SCORES-REVIEW v1；负责人 `/root/b3fix_scores_review`；日期 2026-10-02。

候选现场为 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec` 加未提交工作区。读取根/API AGENTS、CURRENT_STATUS、PROJECT_GUIDE、原 B3 审查与 B3-FIX 报告，审查 scores 服务/仓储/契约、tabular、assessments 出勤接口及迁移约束。仅在本 `scores/` 证据目录新增探针、日志、XML、散列核对与结果；未修改产品、旧证据或权威文档，未暂存、提交、切换分支或推送。最后本范围 12 个产品文件逐一与 r7 manifest 的磁盘 SHA 一致，见 [scope-hashes.json](scope-hashes.json)。

## 正式发现 S01 — P2：XLSX 截断可将非法原分数变为可封存正式分数

定位：[tabular.py:244](<H:/备份xuexi/智启课源/apps/api/app/services/tabular.py:244>)，成绩公式视图与缓存视图均调用通用 `_cell_to_text`；该函数在 [tabular.py:51](<H:/备份xuexi/智启课源/apps/api/app/services/tabular.py:51>) 静默截到 20,000 字符。精确分数解析本身已修正，但执行时得到的是改变后的文本。

隔离触发：程序生成合法 XLSX，C2 为 `"1." + "0" * 19998 + "1"`（20,001 字符），D2=2、E2=3；原卷 Q1/Q2/Q3 满分 2/3/5。原完整文本直接交 `parse_score_text` 得到 `SCORE_CELL_INVALID`（无法表示为百分之一分整数）。XLSX reader 删掉末尾非零位，读取长度变成 20,000，内容变为精确的 1 分。

真实 HTTP 实际结果：上传 **201**，预览无 issues，C2 显示 `recorded/scoreUnits=100`，`originalText` 也只剩截后的 20,000 字符；没有 missing/absences 需要承认；确认 **200**，正式矩阵 `[100, 200, 300]`、总分 `600`。因此并非只有显示截断，非法源数据已进入不可变正式版本，后续学情分析会读取这个错误版本。原件 blob 字节仍正确，但预览证据与分数解释已经失真。

独立正确行为断言 `test_xlsx_overlong_score_must_not_be_truncated_into_valid_units` 实际失败，`201 != 422`，退出码 1。探针的退出码 0 只表示诊断运行成功，不表示候选产品通过。原始数据与 HTTP 收据摘要见 [probe-results.json](probe-results.json)、[probe-log.txt](probe-log.txt)，正确行为失败见 [review-assertions-log.txt](review-assertions-log.txt) / [review-assertions.xml](review-assertions.xml)。

修复与验收建议：成绩输入的文本转换应保留完整权威文本，或在明确的字符上限处以带原表行列位置的 422 拒绝；不得先截断再验证或封存。不必顺手改变名单/知识点通用读取策略。验收要覆盖公式视图与缓存视图、XLSX/CSV 原文本一致、超长非零尾数不能变 recorded、拒绝后导入/正式修订/矩阵零写；并保留当前有效 0、尾随零的精确数值、四态、公式缓存及既有精度回归。修复后重跑本独立正确行为断言，并重新冻结后由独立验收者核对。

## 原 B3-R02～R07 及版本边界复核

相关既有回归实际通过：列大小写与身份/计分/元数据物理列占用；同 sheet 表头和身份映射重提取并保留仍有效的坐标编辑；未知/重复身份表头上传进入人工映射；UTF-8-BOM 与 GB18030 中文原文/标记；recorded 的空白/缺考/免考修正定位 422、有效 0 成功；缺考/免考按有效全矩阵生成权威承认而不产生伪 missing。这里只继承服务端 B3-R02 口径；前端实际组件由另一审查任务覆盖。

检查并执行三版本独立 CAS、明确 refresh、active/base 漂移阻断、重复物理行逐行阻断、补考与历史修正、提交幂等和四态/总分规则。独立新增正常链也通过：v1 完整确认 → 当前人次出勤校正 → 增加第二人次 → 从 active v1 修正第一人次 Q1 建 v2；再读取 v1 修订详情与全矩阵逐项相等，固定 `paperRevisionId`、旧 `participantSnapshot` 和旧分数不变，v2 有两人次且新补考矩阵为明确 missing。

固定卷读取通过成绩修订所属施测的不可变 `paper_revision_id` 关系；确认卷本身、施测换卷与成绩矩阵都有约束。B4 应接受明确 `scoreRevisionId`，读取其自己的 participant/item snapshot 与固定 paperRevisionId；不要以当前 active、最新人次或当前出勤代替历史分析输入。成绩状态与冻结施测出勤可能不同，这是现行显式规则，分析必须消费逐格四态。

## 观察项，不列主要业务阻塞

- CSV 有 131,073 字符备注字段、整文件 131,121 字节（低于 10 MiB 上传限制）时，`csv.reader` 在 [tabular.py:274](<H:/备份xuexi/智启课源/apps/api/app/services/tabular.py:274>) 抛出未封装 `csv.Error`；HTTP 为 `text/plain` 500，导入和正式修订零写。可考虑统一表格解析错误为契约 422；本轮按总控要求保留为输入边界观察。
- 独立构造 XLSX 将 dimension 元数据从 `A1:E3` 缩为 `A1:E2`，保留全部 XML 单元格：reader 信任元数据，只保留物理行 2，乙的真实行 3 被略过，上传 201 / 无 issues / missing=3。需要错误 dimension 的人工构造文件，故本轮只记录观察，不提升为普通教师业务阻塞。

两观察均有 `probe-results.json` 的实际结果，不据此声称完整畸形文件覆盖。

## 实跑命令、隔离与未执行

工作目录均为 `H:\备份xuexi\智启课源\apps\api`。每条命令先设置 `PYTHONUTF8=1` 与新临时 `ZQKY_DATA_DIR`，再启动解释器；探针内部在任何 `app.main` 导入前重新设置专属临时根。Harness 以显式临时 Settings、`credentials_file=None` 装配真四库/服务/HTTP TestClient；原卷种子在隔离教学库走真实确认触发器。没有启动常驻服务、读取 `.env`、正式库、正式 Qdrant 或调用模型。

通用命令前置：

```powershell
$env:PYTHONUTF8='1'
$env:ZQKY_DATA_DIR=Join-Path ([System.IO.Path]::GetTempPath()) ('zqky-b3-review-scores-' + [guid]::NewGuid().ToString('N'))
```

实际命令（stdout 经 Tee-Object 保存，末尾 `exit $LASTEXITCODE` 保留 Python 退出码）：

```powershell
./.venv/Scripts/python.exe ../../docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/scores/probe_score_boundaries.py
./.venv/Scripts/python.exe -m pytest tests/test_b3_review_score_fixes.py tests/test_score_precision_exact.py tests/test_score_preview_boundaries.py tests/test_participant_attendance.py tests/test_scores_imports.py tests/test_scores_confirm.py tests/test_scores_corrections.py tests/test_scores_scale.py tests/test_assessments_api.py tests/test_assessment_held_on.py tests/test_tabular.py --junitxml=../../docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/scores/regression.xml
./.venv/Scripts/python.exe -m pytest -c pyproject.toml ../../docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/scores/test_review_score_boundaries.py --junitxml=../../docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/scores/review-assertions.xml
$env:ZQKY_RUN_SCALE_BASELINE='1'
./.venv/Scripts/python.exe -m pytest -p no:cacheprovider tests/test_scores_scale.py::test_scale_baseline_two_hundred_participants --junitxml=../../docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/scores/scale.xml
```

| 运行 | 实际结果 |
| --- | --- |
| 独立诊断探针 | exit 0，三个场景均实际执行；不是产品通过断言 |
| 11 文件窄回归 | **127 passed / 1 skipped / exit 0，32.76s** |
| 新正确行为与历史断言 | **1 failed / 1 passed / exit 1，1.60s**；失败就是 S01 |
| 被默认跳过的 200×100 单项显式开启 | **1 passed / exit 0，2.21s** |

窄回归跳过原因是既有 `ZQKY_RUN_SCALE_BASELINE` 门控；其旧文字仍提逐格 cell() 成本，但当前实现已采用 iter_rows。本审查随后单独显式开启，成功覆盖 200×100；不把两次运行计数混写成一次。仅有既有 Starlette/AnyIO 弃用 warning。

未执行全量 API、npm check/build、E2E、实际浏览器像素、真实供应商/教学质量、Word/WPS、正式数据迁移、Qdrant、跨进程协调器与超 200×100 规模：本任务是只读范围审查，没有产品修复；这些不在本子任务验收范围。没有清理正式或未知数据；探针临时根保留于 `probe-results.json` 的绝对路径，未删除。

结论：原 R02～R07 与固定修订/历史不变相关回归通过，新增 S01 仍未修复。下一阶段提示词应先列 S01 为需修复并独立验收的当前数据准确性问题；B4 的最小实施片应在明确后续授权、修复验收及重新冻结后使用不可变版本输入。本审查没有开始 B4 或修复产品。
