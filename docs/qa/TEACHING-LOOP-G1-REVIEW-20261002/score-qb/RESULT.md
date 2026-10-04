# G1 成绩原值与题库查重后续审查

2026-10-02，`/root/g1_scores_questions_review`。范围为 G1 的 B3F-R04、B3F-R07。结论：**本次范围未发现新增可行动的产品缺陷**。原两项修复的实现与独立验收记录相符；这不等于关闭整体 G1，也不替代浏览器/E2E。

## 代码核查

- [tabular.py:179](../../../../apps/api/app/services/tabular.py:179)：成绩单元格使用完整字符串转换，超 20,000 字符返回定位的 422，而不是先截断。XLSX 原值/公式视图与缓存视图分别经过相同限制；CSV 严格 UTF-8/GB18030 解码，字段解析异常转为错误信封。读取阶段没有资产或成绩库写入。
- [fingerprint.py:148](../../../../apps/api/app/services/question_bank/fingerprint.py:148)：新增 `question-surface-v1` 只计算有序共同材料、题干、选项及其真实结构；随机块 ID、来源、答案/解析不造新题。旧 `content_fingerprint` 和 `derived-v1` 不修改。结构字段兼容 snake_case/camelCase，图片使用冻结声明或内容寻址散列，公式/表格结构参与身份。
- [service.py:813](../../../../apps/api/app/services/question_bank/service.py:813) 与 [catalog.py:1422](../../../../apps/api/app/repositories/question_bank/catalog.py:1422)：预览和确认共享同一题面口径，只比较本 owner 的 confirmed 当前修订；缺少新算法行的旧题从冻结内容只读重算，不查询回填旧修订。
- [service.py:1514](../../../../apps/api/app/services/question_bank/service.py:1514)：原提交重放优先于新资产预检；新发布资产核验在 SQL 写事务外，域内复核草稿版本。正式改题同事务追加新修订和两种派生算法；原修订内容及指纹保留。

先阅读根/后端 AGENTS、本批 REPORT、G1-CLOSE-MATRIX 与 v00-score-qb 独立结果（53 项）。已有独立验收覆盖超限零写、真实四态矩阵、旧/新算法、图片别名、真重复答案冲突、同包处置及原包优先重放；本次没有重新运行这 53 项或全量门禁，也没有把历史次数并入本次计数。

## 本次新增窄探针

[probe.py](probe.py) 的最终单次 **5 项通过，exit 0**，见 [probe-final.log](probe-final.log)、[退出码](probe-final.exit.txt)、[机器结果](probe-results.json)。期望为手写业务事实，不调用生产指纹函数生成期望值。

1. GB18030 CSV 中 20,000 字符尾零原文、姓名与前导零学号完整保留。
2. CSV 长度 20,001 的分数明确拒绝，地址为原表 B3、view=csv，不截断成可接受分数。
3. 无法按允许编码解码的字节明确返回 422 `TABLE_PARSE_FAILED`。
4. 真实 ASGI HTTP 正式改题将材料 1 mol/L 改为 2 mol/L 后，2 mol/L 候选只关联当前修订；1 mol/L 可作为新题入库。旧修订整行及两种旧指纹保持字节值不变，新修订同时登记两个算法。
5. 只在解析中增加真实 PNG 的候选仍判为原题重复，默认跳过，既有题内容/答案不被覆盖。

第 1–3 项为纯读取边界；第 4–5 项用现有测试输入构建器和 `TestClient`，真实四库服务/仓储，没有业务成功响应替身。复用了题库输入与 reviewed 前置构建器，**不将其称为完全独立的前置 oracle**；查重、正式修改、确认、历史保留的期望均直接断言 HTTP/数据库事实。

## 首败、边界与资源

首轮 [probe-first.log](probe-first.log) / [exit 1](probe-first.exit.txt) 为本审查夹具错误：误调用不存在的 `catalog.read_transaction()`；修正为现有只读 `_read()` 后重跑。没有修改产品或放宽业务断言；首败原文保留。首轮完成前三项读取断言，正式修改前置因该夹具错误中止，不能计为产品失败。

两个本次创建的系统临时根保留（首轮 `zqky-g1-review-score-qb-vqgyr9qq`；最终 `zqky-g1-review-score-qb-dkx3y3rq`），最终地址见机器结果；每个进程均在任何 app.main 导入之前设置临时 `ZQKY_DATA_DIR` 与 UTF-8，每个测试应用显式 `credentials_file=None`。TestClient 进入/退出的是进程内 lifespan，日志中的 8001 启动行不是监听服务。无常驻服务、5174、实际浏览器、正式数据/.env、外部模型调用、Qdrant、Git 操作或旧证据写入。

畸形 XLSX dimension 仍沿用已登记观察项。本次不扩大为全格式损坏/解压安全、实际 Excel/WPS 数值精度、超基线压力或完整成绩确认链验收；第 1–3 项没有实际 HTTP 入库。本次全部写入仅在新的 `score-qb/` 证据目录及自建临时根内。
