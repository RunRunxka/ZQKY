# G1-SCORE v1 实现者结果

2026-10-02，负责人 `/root/g1_score`。起点 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec` 加已有未提交 B3-FIX r7。状态：**ready_for_review**；本实现者停止写入，等待 CTRL 冻结与独立验收。尚未实施 B4，不将实现者自检称作独立关闭。

## 文件归属与实际改动

- 新增 `apps/api/tests/test_g1_score_text_boundaries.py`，41 条正确行为回归。
- 新增本目录内结果、首败/最终日志与 XML、HTTP 探针/收据、原表 `sources/`、SHA 与资源记录。
- 分配的 `scores/imports.py`、`scores/service.py`、`repositories/teaching/scores.py` **无需改动**，与本批 BASELINE 磁盘 SHA 相同，见 [scope-hashes.json](scope-hashes.json)。不为满足任务名额添加冗余服务检查。
- 共享 `tabular.py` 的修复由 CTRL 实施，本实现者只提交协议建议并测试集成；未修改 contracts、main、迁移、依赖锁、权威进度或旧证据。

成绩专用读取保持 20,000 字符支持上限，完整转换后拒绝超限，不先截断再验证。超限为 422 `TABLE_TOO_LARGE`，`details={sheet,row,column,address,view,actualLength,maxLength}`；公式/缓存/CSV 分别标记视图。名单/知识点的通用读取策略不变。CSV parser 的 `csv.Error` 被 CTRL 封装为 422 `TABLE_PARSE_FAILED`，包含工作表及 parser 实际行号，不伪造无法确定的列。

## R04 正确行为

| 范围 | 实际断言 |
| --- | --- |
| XLSX 与 UTF-8-BOM CSV 五类列 | 学号、姓名、小题、总分、出勤每列 20,001 字符，真实上传均定位原表第 2 行/A、B、C、F、G 列 422。原漏洞文本 `1.` + 19,998 个零 + `1` 不得删尾后变成 1 分。 |
| 公式与缓存两视图 | 五类列分别注入超长公式文本、`t="str"` 超长公式缓存；两视图均在解析前使用同一长度边界。不是只用 numeric float cache 代替字符串缓存。 |
| 支持范围精度 | XLSX/CSV 原值、两视图、持久化/预览证据、受管 blob 逐项相等；20,000 字符合法尾零保留并确认成精确 100 单位。0、长尾零 0、1.23 长尾零均精确确认。缓存视图边界同样确认成功。 |
| 非零尾数 | 支持范围内 20,000 字符的末尾非零精度不合法，完整原值进入数值验证并返回 `SCORE_CELL_INVALID`，C2 定位正确且零导入/正式矩阵。超过读取上限的合法尾零数也明确拒绝，不能绕过文件支持上限。 |
| 身份与元数据缓存 | 学号前导零 `0001`、姓名、总分、出勤与小题各自合法字符串缓存能确认，原公式和缓存完整存入 `raw_cells_json`。映射后公共 row API 按既有契约投影计分/总分/出勤，身份以原表存储和最终人次快照核验。 |
| 四态与总分 | 4 人×3 叶完整确认：recorded(0) 不丢、missing 不补 0、absent/exempt 保留；仅完全 recorded 人次有 totalUnits，其他为 null。 |
| 拒绝零写与原件保护 | 超长上传前后五张成绩表、file_assets、command_submissions 数量及施测详情不变，无导入、修订、矩阵、审计或成功提交；预存受管原件及上传源文件字节不变，无新增 blob。 |
| O1 CSV 观察 | 131,073 字符备注触发真实 parser 上限，现为 JSON 422 `TABLE_PARSE_FAILED`、row=2、无未知 column，零导入和资产写；这条只覆盖本次触及的错误封装。 |

畸形 XLSX dimension（O2）保持原观察范围，本任务未修复、未重新执行、不提升为第九个 G1 门槛，不宣称所有畸形文件均已覆盖。

## 首败与执行记录

所有命令工作目录为 `H:\备份xuexi\智启课源\apps\api`；每条解释器命令前设置 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、`ZQKY_ENV=test` 和全新 `ZQKY_DATA_DIR`，随后才启动 pytest/探针。运行根绝对路径分别记录在 `first-temp-root.txt`、`final-temp-root.txt`、`probe-import-temp-root.txt`。探针内部另在导入 app.main 前设置自己的新根。

HTTP 测试台显式 `Settings(..., env="test", data_dir=tmp_path/"data", credentials_file=None)`；四库与真实服务装配，班级/学生/施测/成绩走进程内 TestClient，原卷种子在临时教学库经真实确认触发器建立。没有监听 8001、调用模型或连接 Qdrant。模块级默认 app 未进入 lifespan，不读取正式 `.env`。

| 实际命令 | 单次结果 | 证据 |
| --- | --- | --- |
| `.\.venv\Scripts\python.exe -m pytest tests/test_g1_score_text_boundaries.py -o addopts= -q --tb=short --junitxml=../../docs/qa/TEACHING-LOOP-G1-B4-20261002/g1-score/first.xml` | **36 passed / 2 failed / 1 warning / 10.70s，exit 1** | [first.log](first.log)、[first.xml](first.xml)、first.exit.txt |
| `.\.venv\Scripts\python.exe -m pytest tests/test_g1_score_text_boundaries.py tests/test_b3_review_score_fixes.py tests/test_score_precision_exact.py tests/test_score_preview_boundaries.py tests/test_participant_attendance.py tests/test_scores_imports.py tests/test_scores_confirm.py tests/test_scores_corrections.py tests/test_scores_scale.py tests/test_assessments_api.py tests/test_assessment_held_on.py tests/test_tabular.py -o addopts= -q --tb=short --junitxml=../../docs/qa/TEACHING-LOOP-G1-B4-20261002/g1-score/final.xml`（另置 `ZQKY_RUN_SCALE_BASELINE=1`） | **169 passed / 0 failed / 0 skipped / 1 warning / 45.05s，exit 0**，其中本次 41 条；20×100 与 200×100 均实际执行 | [final.log](final.log)、[final.xml](final.xml)、final.exit.txt |
| `.\.venv\Scripts\python.exe ../../docs/qa/TEACHING-LOOP-G1-B4-20261002/g1-score/probe_score_text_receipts.py` | 4 个代表场景，exit 0；3 个长值拒绝＋1 个精确确认 | [HTTP 收据](http-receipts.json)、[stdout](http-receipts.log)、http-receipts.exit.txt、[原件](sources/) |
| `git diff --check -- apps/api/app/services/scores/imports.py apps/api/app/services/scores/service.py apps/api/app/repositories/teaching/scores.py apps/api/tests/test_g1_score_text_boundaries.py`（仓库根目录） | exit 0，仅已有 LF→CRLF 提示 | [diff-check.log](diff-check.log)、diff-check.exit.txt |

首次两失败是新测试误把 A/B 身份列当作映射后 row API 的公开计分格，`StopIteration` 出现在证据查找，上传均为 201，非产品拒绝/写入错误。定位既有 `_row_view` 投影后，改为核持久化 `raw_cells_json` 与最终人次快照，仍保留原公式/缓存完整性断言；没有放宽长度、精度、零写和确认要求。首败原日志/XML保持原样。随后添加 3 个缓存边界/合法超长拒绝用例；各次计数不相加。

唯一 warning 为既有 Starlette/AnyIO BlockingPortal 弃用提示。XML枚举本次新用例 41、最终总数169；代表收据保存实际完整错误信封、源 SHA、XML SHA、写入前后数量及矩阵，不把 probe 的 exit 0 当作独立验收。

## 未执行与资源

全量 test:api、check/build/E2E、实际浏览器、独立 V00：未执行，属于 CTRL 集成门禁与停写后独立验收。真实供应商/教学质量、Word/WPS、Qdrant、正式迁移、超200×100与多进程发布协调：未执行，不属成绩文本边界实现者范围。

无常驻服务、浏览器或监听端口；所有 TestClient 上下文与 CLI 已退出，本次新临时根保留登记见 [resources.json](resources.json)。没有清理共享 pytest 保留目录、未知数据或旧六个 policy 拒绝删除目录；没有 Git 写操作、提交、推送或部署。
