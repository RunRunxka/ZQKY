# B3-FIX-SCORE v2 实现者结果卡

日期：2026-10-02。状态：**ready_for_review（实现者自检完成，待独立验收）**。

任务 v1 为成绩后端 B3-R03/R04/R05/R06/R07；总控在同批授权内追加 v2：权威承认范围、原件/校正/有效四态预览、可选总分/出勤列、明确刷新施测上下文与旧快照保护。未实施 B4。

## 文件归属

本实现者修改：

- `apps/api/app/services/scores/imports.py`
- `apps/api/app/services/scores/service.py`
- `apps/api/tests/test_b3_review_score_fixes.py`（新增，32 个正确行为用例）
- 本结果卡及 `logs/score-*.txt`

总控同步修改的共享依赖不计为本实现者文件：Python/TS 成绩与施测 DTO、公共 `tabular.py` 严格解码、成绩刷新 HTTP 路由、显式出勤校正及返回原始两视图的仓储。没有修改迁移、锁文件、`main.py`、权威进度文档、旧审查证据；没有 Git 写操作或启动端口。

## 逐项正确行为

| 范围 | 实现与正确行为证据 |
| --- | --- |
| B3-R03 | 物理列在分析、PATCH 校验、读取和持久化统一为去首尾空白后的大写身份；`C/c` 计分列重复、计分/身份列大小写占用及两个身份列占用均 422 `SCORE_MAPPING_INVALID`，含规范物理列定位，导入锁保持不变且没有正式修订。单独合法小写列映射保存为大写，确认原分数仍为 100/200/300。 |
| B3-R04 | 同工作表任意映射变化（包括表头、身份、计分、总分、出勤列）从受管原件重提取有效行；两级表头改 `headerRow=2` 后只剩物理行 3/4，确认两生原分数不变。身份列更换能排除旧备注行、加入此前未提取行，同时保留仍存在物理行的明确人次和坐标校正。 |
| B3-R05 | 自动检测没有任何身份列时，独立于已识别计分列数量返回 `mapping=None` 的可校对批次。未知、重复身份表头均 201，可读取原表单元格证据（没有伪造有效状态），手动指定身份/小题列后确认真实矩阵成功。 |
| B3-R06 | 公共严格 UTF-8-BOM/GB18030 解码由总控落地；真 API 验证两编码的中文姓名、缺考、免考原文和上传原件 SHA-256。不可解码字节 422 `TABLE_PARSE_FAILED` 且没有导入批次。没有本模块第二套 CSV 解析器。 |
| B3-R07 | `recorded` 修正同时要求解析成功、状态为 recorded、units 非空；空串/空白/缺考/免考均 422 `SCORE_CELL_INVALID` + `scoreText` 定位，原 active、旧矩阵、修订数量与审计数量不变。数值 0 仍成功并产生新完整版本及审计。 |
| 权威承认与有效四态 | `requiredAcknowledgements` 与确认闸门共用同一 PreviewMatrix 的 absent-by-class / missing-person / missing-cell 统计；文件缺考和免考整人次覆盖空白，0 保持 recorded，真正 missing 独立列举。行 DTO 的有效状态/units 取最终矩阵；metadata 格不伪造小题状态。已确认或过期预览使用 summary 内冻结范围。 |
| 可选总分 | 自动识别总分/合计等明确表头，可手动映射/坐标校正；列占用校验覆盖大小写。只有所有小题 recorded 时精确按 Decimal×100 比较；不符以真实行/列的 `SCORE_TOTAL_MISMATCH` 保存可校对预览并在确认时 422。非法类型 422 `SCORE_CELL_INVALID`；空可选总分不阻断；含 missing/absent/exempt 时显示不能核对提示，不反推小题、不补 0。验证 0.1+0.2+0.3=0.60、原表 9/11 对小题 6 的不符和校正后的真实确认。 |
| 可选出勤 | 自动识别明确出勤表头；仅接受规定的 present/出勤/正常、absent/缺考、exempt/免考或空白。不明文本及与小题标记冲突阻断；显式出勤列与施测冻结出勤不符以物理位置 `SCORE_ATTENDANCE_MISMATCH` 阻断，不覆盖施测快照。原小题缺考/免考覆盖语义兼容保留。 |
| 明确刷新与版本 | `refresh_import` 保留受管原件、映射、人工定位和单元格修正；读阶段与提交短事务分别校验 import/assessment/base。成功只增加 revision/previewVersion 各 1、明确冻结当前参测/出勤预览。GET 过期时保留原统计/承认范围并明确提示；单独传新施测版本不能绕过刷新确认。active/base 变化必须新建导入，不能悄悄换 base。确认批次不可刷新。 |
| 新人次/历史保护 | 补考新增人次后旧预览仍展示原范围；刷新才产生新 missing 集合，手动定位/0 分校正保留，新矩阵完整覆盖两人次；旧正式修订仍只含自己的 1 人次、原值不变、固定 paperRevisionId 可读。确定性交错在预览计算后校正出勤，提交重核返回 409，导入锁/预览锁零变化。 |

## 首败、修复及真实验证

所有 pytest 运行都在导入 `app.main` 前显式设置新临时 `ZQKY_DATA_DIR`，夹具另注入 `tmp_path` 四库与内存凭证；模块级默认 app 没有进入 lifespan。没有读取真实 `.env` 或操作正式 `.local-data`。TestClient 只在进程内模拟 `127.0.0.1:8001`，没有监听端口，也没有模型/Qdrant 请求。

| 命令（`apps/api` 工作目录） | 结果 | 日志 |
| --- | --- | --- |
| `uv run --no-sync python -m pytest tests/test_b3_review_score_fixes.py -q --tb=short` | exit 1；共享 DTO 的 requiredAcknowledgements 已先落地，服务尚未接入，15 失败/1 通过。此轮只记集成首败，不当作 R03–R07 原始缺陷诊断。 | `logs/score-first-fail.txt` |
| `uv run --no-sync python -m pytest tests/test_b3_review_score_fixes.py -q --tb=short --show-capture=no`（仅接入权威 DTO 后、R03/R04/R05/R07 修复前） | exit 1；14 失败/2 通过。复现大小写列占用、表头/身份重提取、未知/重复身份 500 与 recorded 非数值 500。2 个 CSV 失败为测试假设矩阵按学生排序，已改为按实际身份排序再断言。 | `logs/score-baseline-correct-behavior.txt` |
| 同上（v2 产品修复后，29 用例） | exit 1；28 通过/1 失败。失败为同场景两导入测试夹具重用同一 submissionId 导致合法 409 `SUBMISSION_CONFLICT`；改成每 import 独立标识，没有放宽幂等。 | `logs/score-fixes-first-run.txt` |
| `uv run --no-sync python -m pytest tests/test_b3_review_score_fixes.py tests/test_scores_imports.py tests/test_scores_confirm.py tests/test_scores_corrections.py tests/test_scores_scale.py -q --tb=short --show-capture=no` | exit 0；62 通过/1 skipped/1 warning。 | `logs/score-bounded-regression.txt` |
| 上述五文件命令，加 `-o addopts= -q`（新回归增加 3 个刷新版本/交错用例、总分越满分仍作不符核对） | exit 0；**65 passed、1 skipped、1 warning，18.85s**。 | `logs/score-bounded-final.txt` |
| `uv run --no-sync python -m pytest tests/test_b3_review_score_fixes.py -o addopts= -q --tb=short --show-capture=no`（最后补齐 mapping=None 原表格预览后） | exit 0；**32 passed、1 warning，9.25s**。 | `logs/score-final-correct-behavior.txt` |
| `git diff --check -- apps/api/app/services/scores/imports.py apps/api/app/services/scores/service.py apps/api/tests/test_b3_review_score_fixes.py` | exit 0；仅有现有 Windows LF→CRLF 提示。 | 本结果卡记录 |

PowerShell 每轮均保存/恢复原 `ZQKY_DATA_DIR`；有 UTF-8 输出的运行保存/恢复 `PYTHONIOENCODING=utf-8`，真实退出码从 `$LASTEXITCODE` 保存并以 `exit $scoreExit` 返回。保留首败日志，未重写原审查目录断言缺陷的探针。

唯一 warning 为依赖中 `anyio.abc.BlockingPortal` 的既有弃用提示；唯一 skipped 为需要 `ZQKY_RUN_SCALE_BASELINE=1` 的 200 人×100 叶规模基线。默认 20 人×100 叶链已运行，不能据此宣称重新完成 200 人基线。

## not_run

- 全量 `npm.cmd run test:api`：未执行，总控分工要求实现者只跑成绩有界回归；留集成验收阶段。
- `npm.cmd run check`、全量 E2E、浏览器故障注入：未执行，属于总控与前端/独立验收范围。
- 200 人×100 叶显式基线：未启用，本轮只跑默认规模链。
- 正式数据迁移、真实模型、Word/WPS、Qdrant：未执行；当前成绩流程不调用模型评分。

本卡仅支持上述隔离自检行为，不替代独立验收、全量检查、真实浏览器结果或新冻结清单。提交 **ready_for_review** 后本实现者停止写上述成绩文件。
