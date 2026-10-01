# B3 成绩只读审查实证（2026-10-01）

本审查未改产品、现有测试、B3 定版清单或正式数据。探针在导入任何 `app.main` 之前设置临时 `ZQKY_DATA_DIR`，用真实 `create_app`、真实 FastAPI 路由、迁移后的临时 SQLite 和受管文件服务；已确认原卷前置复用现有 `ScoresHarness` 的固定种子，不替换成绩服务或仓储。所有临时数据在运行结束后释放，无监听端口。

复现程序：`scores_review_probe.py`；最终结果：`scores_review_probe_output.jsonl`。最终运行退出码 0，包含下述 5 类诊断场景（第 3 类含 3 次独立输入）。这是诊断程序完成，非产品无缺陷或原验收失败的宣称。

命令（仓库根目录，PowerShell）：

```powershell
$env:PYTHONIOENCODING='utf-8'
& apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/scores_review_probe.py
```

## S01 [P2] 修改同工作表的表头行不重建数据行，真正表头持续被当成学生行

位置：`H:/备份xuexi/智启课源/apps/api/app/services/scores/service.py:763`（763–776；793–795 继续复用旧行）。

`rebuild` 只在工作表变化或原来无映射时为 true。已存在映射时改 `headerRow`、身份列等影响 `extract_rows()` 行筛选的条件只通过校验，行集合仍为旧结果。

实证：XLSX 第 1 行是分组头 `学号/姓名/小题得分`，第 2 行是真正 `学号/姓名/Q1/Q2/Q3` 表头，第 3、4 行是学生。上传成功。教师 PATCH `headerRow=2` 并指定 C/D/E 计分叶映射返回 200；预览仍保留 `[2,3,4]`，确认返回 422 `SCORE_ROW_UNRESOLVED`（第 2 行表头被当作待定位学生行）。正常操作不能通过修正表头排除该行。前端 `ScorePanel.tsx:421` 确有可编辑“表头行（0 = 无表头）”输入。

建议：影响提取行集合的映射变更从原件重建，同时按物理坐标保留仍适用的人工定位与校正值；增加两级表头及同表身份列变更回归。

## S02 [P2] 列字母大小写可绕过同一物理列只能对应一个叶子的约束

位置：`H:/备份xuexi/智启课源/apps/api/app/services/scores/imports.py:647`（同一问题也在 627 的身份列比较）。

列合法性通过 `column_index()` 的大写归一化检查，实际解析、读格均用大写；但 `seen_columns`、身份列占用比较仍使用原始 `entry.column`。`C` 和 `c` 实际指向同一物理列，校验却认为不同列。

实证：原行三个分数为 1/2/3。映射 Q1→C、Q2→c、Q3→E 后 PATCH 200，确认 200，无问题清单。正式矩阵变为 100/100/300 单位，总分 500，而原始数据总分应是 600；D 列的 2 分被丢弃。接口契约允许普通字符串，`c` 是当前实现明确接受的列字母，并非绕过类型验证。

建议：先将所有身份/计分列归一为唯一物理列身份，再做重复、占用和范围校验；不要只在读格阶段归一。

## S03 [P2] recorded 修正中的空白/缺考/免考文本被当作有效解析，最终返回非契约 500

位置：`H:/备份xuexi/智启课源/apps/api/app/services/scores/service.py:1646`（1641–1660）。

`parse_score_text()` 的空白/缺考/免考是合法四态解析结果，`is_error=False`，但并不是 `recorded`。修正服务只检查 `is_error`，随后把 `units=None` 与请求 `status='recorded'` 写入矩阵，触发数据库 recorded 必须有分数的 CHECK。

实证：从一个已确认的正常矩阵修正 Q1，请求 `status='recorded'`，`scoreText` 分别为 `''`、`缺考`、`免考`。三次均 HTTP 500，纯文本 `Internal Server Error`，无法提供字段定位。事务回滚后修订数仍为 1，无部分写入。

建议：该分支须核实解析后的 `status=='recorded'` 且 units 非空，否则返回 422 `SCORE_CELL_INVALID` / `SCORE_CORRECTION_INVALID` + `scoreText` 定位；保留四态严格区分。

## S04 [P2] 成绩 CSV 使用替换解码导致 GB18030 原始证据乱码

位置：`H:/备份xuexi/智启课源/apps/api/app/services/tabular.py:267`。

成绩专用 CSV 读取仅 `decode('utf-8-sig', errors='replace')`，与同模块 `read_csv()` 的 UTF-8/GB18030 支持及 API AGENTS 的表格约定不一致。中文姓名、表头、缺考/免考文字被不可逆替换，后续人工映射无法恢复原始权威值。

实证：同一 GB18030 字节流，公共 `read_csv()` 正确读出 `学号/姓名/Q1/Q2/Q3`；`read_score_sheet()` 表头变为 `ѧ��/����/Q1/Q2/Q3`。上传该合法 CSV 实际 HTTP 500（同时触发 S05 的身份列缺失错误），源头乱码独立于 S05。即便修复 S05，人工映射后的中文状态值仍会错误。

建议：与既有 CSV 读取共用严格解码策略；任何支持编码均解码失败时明确 422，而不是替换原始字节。

## S05 [P2] 可识别计分列但身份表头未知的合法文件不能进入人工映射

位置：`H:/备份xuexi/智启课源/apps/api/app/services/scores/imports.py:488`（488–490）。

`AutoMapping.mapping` 的约定是身份列不识别时返回 None 等待人工指定。当前条件额外要求 `not item_columns`，导致已有 Q1 等计分列、没有识别到身份列时继续构造要求至少一个身份列的 `ScoreColumnMapping`，抛未处理 ValidationError。

实证：独立 UTF-8 CSV 表头 `身份代号,学生称呼,Q1,Q2,Q3`，数据正常且分数在范围内。上传 HTTP 500 纯文本，不能得到批次和 PATCH 入口。该场景不涉及编码不支持；表头别名超出自动识别字典是正常人工映射场景。

建议：任何无识别身份列的情况均返回待映射批次，保留计分候选为提示；不要将自动映射不完整当作服务异常。

## 未追加为新缺陷的已披露边界

- 导入 API 不直接返回 missing/absent 人次详情，由前端推导并经确认 422 闸门校验：用户报告已披露，本审查未重复计数。
- 没有出勤校正端点、修正/确认故障注入 E2E 未执行、真实模型/Word/Qdrant 未执行：不作为新增产品 bug。
- 本次未重跑全量测试；定向诊断已确认上述结果。
