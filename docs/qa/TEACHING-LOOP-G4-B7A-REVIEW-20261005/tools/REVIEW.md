# G4/B7-A 离线工具与材料后续审查

2026-10-05，main@b7f99ab09826c68724e281d01e15215e660c1ce0。只读当前 `scripts/teaching-quality` 四工具、两作者测试文件与本批材料/收据；只新增本目录证据。未修改产品、历史QA、原材料或权威文档，未操作Git，未启动服务/app.main/数据库、读取.env、访问网络或模型。

结论：确认 **1项P2，含两条空人审校验绕过路径**。G4旧B6Q-R01/R02修复未复现回归；当前已交付材料包273条引用、原15行CSV与15案例Markdown、四行native表仍实际合格。本 finding 是新输入下复用工具的失败闭合缺口，不推翻原正常包或G4原关闭。

## B7A-Q01/P2：非空人审材料仍能被标为全空

位置：[prepare_review.py:79](../../../../scripts/teaching-quality/prepare_review.py:79)、[prepare_review.py:89](../../../../scripts/teaching-quality/prepare_review.py:89)，第二路径在 [prepare_review.py:138](../../../../scripts/teaching-quality/prepare_review.py:138)。结果使用 `originalEmptyFeedbackMd`（194行），最终收据固定写 `humanFieldsFilled=0`（243行）。

`blank_feedback`核CSV表头和既定列，但没有核每行的完整字典形状。`csv.DictReader`把多于表头的额外单元格放入 `row[None]`；在C01行末加一格 `synthetic human verdict PASS`，所有既定人审列仍空，工具实际exit0并发布 `OFFLINE_MATERIALS_PREPARED`、`humanFieldsFilled=0`。这是未被拒绝的异常CSV行。

另一条路径是Markdown。`feedbackMd`只在 `ref` 核路径/SHA，没有核案例身份、空评分/结论或者与已核CSV一致性。仅把C01的 `真人结论：____` 改为 `真人结论：合格（synthetic reviewer placeholder）`，仍实际exit0；MATERIALS把这份含结论的文件标为 `originalEmptyFeedbackMd`，收据仍称填入人审字段0。

这两条反例均在新label复制原文件，给新路径及新字节建立显式artifact索引并固定新SHA，计划也提供新SHA；原文没有写回。**更新SHA用于穿过完整性检查、检查内容判据本身**，与原作者“非空CSV reviewer”反证采用的重新绑定方法一致，不是绕过现有旧冻结材料SHA。正常在既定CSV `reviewer` 列填写同类synthetic值，工具正确exit2/`NONEMPTY_HUMAN_FEEDBACK`，说明工具确有独立的人审空字段判据，但其覆盖范围不完整。

需求矩阵要求“非空伪评语…必须失败”；这两份材料被列为原空表引用供教师复制使用，因此不应把未核列或含结论Markdown声明为已核空人审。没有真人评分或live调用发生，不将此表述为真实教学质量被验收。

建议统一以严格反馈schema核CSV每行：禁止 `None` 额外键、缺列及字段数量不符，再核所有人审列空白。Markdown须核固定案例/hash、字段占位及CSV一致性，或从已经严格核验的空CSV生成新的可读表，并明确输出类型与来源。所有检查结束前不写 `originalEmptyFeedbackMd`/`humanFieldsFilled=0` 成功结论。

首个完整反例轮原件均保留：

| 路径 | 预期 | 实际与证据 |
| --- | --- | --- |
| CSV额外结论单元格 | exit2，不发布PASS | [输入](runs-first/prepare-extra-csv-cell/feedback.csv)、[计划](runs-first/prepare-extra-csv-cell/plan.json)、[RESULT](runs-first/prepare-extra-csv-cell/output/RESULT.json)、[MATERIALS](runs-first/prepare-extra-csv-cell/output/MATERIALS.json)、[COMMAND](runs-first/prepare-extra-csv-cell/COMMAND.json)：exit0 |
| Markdown填结论 | exit2，不发布PASS | [输入](runs-first/prepare-filled-md/feedback.md)、[计划](runs-first/prepare-filled-md/plan.json)、[RESULT](runs-first/prepare-filled-md/output/RESULT.json)、[MATERIALS](runs-first/prepare-filled-md/output/MATERIALS.json)、[COMMAND](runs-first/prepare-filled-md/COMMAND.json)：exit0 |
| 正常CSV reviewer非空对照 | exit2 | [输入](runs-first/prepare-filled-csv/feedback.csv)、[RESULT](runs-first/prepare-filled-csv/output/RESULT.json)、[COMMAND](runs-first/prepare-filled-csv/COMMAND.json)：正确硬拒 |

## 本轮验证

独立程序使用标准库，实际 **31次工具CLI：29次符合预先定义的结果，2次实际假通过**。不得计为31项通过。每个label记录真实argv/PID/时间/耗时/exit、stdout/stderr和四guard；模型/网络/app import/.env读取/数据库打开尝试全部0，各子进程已结束、日志关闭。见 [RESULT](RESULT.json) 及 [探针源码](probe_tools.py)。

已实际覆盖合法四例scope、attempt=1→2时SHA改变与maximumCalls4→8；字符串/重复/未知caseIds、bool计数、对象profile、bool/float尝试、bool费用、float token、缺预算、给null限制同时存在另一有效限制、秘密字段、空model、NaN/Infinity/1e999、重复JSON键与根数组均正确拒绝。合法preflight只给人工形状审查，不提供授权/模型存在/执行器/预算保证。

完整15与显式14材料准备正确完成，未选C15单列 `unrunCaseIds`；仍指定15却删C15 summary正确硬拒。错误artifact SHA、路径 `../`、bool版本、未知计划字段也正确拒绝。复用既有output被拒且首次MATERIALS原SHA保留。这些行为支持旧G4集合与strict scope修复保持。

另一份独立检查直接核作者当前包，未借生产blank_feedback下结论：273条引用路径与实际SHA相同且唯一；原CSV严格20列×15行、所有人工列空；原Markdown15案例、CaseHash与CSV对应，所有人工字段仍为占位；四行native的人工身份/版本/页数/结论全空；历史PDF参考按1/8/2/2严格13行。RESULT/MATERIALS/plan及三准备文件SHA相符。见 [CURRENT-PACKAGE.json](CURRENT-PACKAGE.json) 与 [独立检查源码](check_current_package.py)。

开工/收尾全部工具源码与原冻结1056材料SHA完全相同，见 [BASELINE](BASELINE.json) 及 RESULT的 `toolSourceDrift=[]`、`originalArtifactDrift=[]`。新复制样本及首败全部保留，不清理TEMP。

实际命令（仓库根PowerShell）：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
python -B docs/qa/TEACHING-LOOP-G4-B7A-REVIEW-20261005/tools/probe_tools.py

$env:REVIEW_GUARD_OUTPUT='H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-G4-B7A-REVIEW-20261005\tools\current-package-guard.json'
python -B docs/qa/TEACHING-LOOP-G4-B7A-REVIEW-20261005/tools/guard_cli.py docs/qa/TEACHING-LOOP-G4-B7A-REVIEW-20261005/tools/check_current_package.py
```

本轮未重跑作者整套unit、历史59/46验收、check/API/E2E、浏览器或旧导出：未改产品，新CLI直接覆盖本审查问题与旧工具边界。没有新渲染/看图、Word/WPS控制、真实模型/教师评分或物理SQLite/Blob检查；这些待验不是bug。当前物理源仍 `not_run_source_temp_unavailable`，原B6/B7整体、RAG-REL与原跨批观察保持未关闭。

下一批先最小修复此反馈校验并独立关闭两条反例，保持现有273材料与正常准备包原件；之后直接收教师实际反馈与原生Word/WPS逐页证据，不重复离线准备。真实模型试评仍须新的完整模型/精确案例/attempt/可执行总预算与执行授权，合法scope和已有连接不构成真实调用授权。
