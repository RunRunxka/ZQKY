# B4-R09/R10-STATIC v1 独立只读补审

结论：**PASS（静态范围）**。候选 `CANDIDATE-b4-r9-owner-fixed.json` SHA256 `ba5f0470d7ee7503e384cb68a39a9fdbf47a83745f54e9a9e96aa70feab739ba`；首次完整核验 878 产品、40 可执行 QA、5 共享契约均 0 漂移。当前报告不代替真实 HTTP、浏览器或回归验收。

## owner 桥接与三个单题闸门

修前五份字节均匹配 `b4-root/R09-R10-BEFORE.json` 的 SHA。r5 至 r9 产品仅五旧文件改动、新增一个 `test_question_owner_boundary.py`，无删除。main 第 341 行将实际 `question_bank_service.owner_id` 显式注入 Practice；三处固定题读取第 160/205/265 行统一采用 `question_owner_id`，分别为候选查询、固定版本准备、提交时活动引用复核。未加入无 owner 的 fallback 查询或多 owner 遍历。

教学 owner 仍默认 `local`，题库 owner 仍默认 `local-user`；已有直接构造器在不提供 question owner 时保留原 teaching owner 行为。main 的 `_build_b4_runtime` AST 去除新增 Practice keyword 后与修前完全一致，AnalysisService 装配不变。题库 get/patch/delete 分别在第 1729/1781/1839 行统一检查 `record is None or record.owner_id != self.owner_id`，在详情/关联读取、题面资产验证/写入、归档事务之前返回既有 `QUESTION_NOT_FOUND` 404。

`FixedQuestionReader` 与所有候选收录迁移文件精确同于 r5。固定版本 SQL 继续带 `q.owner_id=?`。未新增旧 row owner 更新或迁移重写；本审阅没有读取实际数据库，因此不宣称核验历史 row 的实际内容。

## 自检与种子不减弱断言

`practices_support.py` 只将造新题的 owner 改为实际服务 owner，原 11 个 Python assert 全部保留。`test_practices_api.py` 原 15 个 assert 全部保留，新增 3 个 assert（新 GET 查询、200、实际题库 owner、教学 owner 的四条语句）。新增单题边界测试参数化 GET/PATCH/DELETE，以真实新确认题、另一个 owner 服务执行 HTTP，请求预期为字面值 404 / QUESTION_NOT_FOUND，并要求 requestId、retryable false、目录 row 完全不变；恢复原 owner 后 GET 与原完整 detail 相等。测试仅读取，未执行。

browser seed 的 r09-before SHA `4f50256da7bc41bd7c09b6be3364969eae8f7a66999fd811b19ee4509970d044`，当前 SHA `f84e424d40dcbc6ed4d03f08116374175072d3b84278fe2a14d6ec713d654ada`。逐字节仅 `owner_id="local"` 改为 `owner_id=application.state.question_bank_service.owner_id`；6 个 assert 全部原形保留，137 个调用总量不变。R07 完整 blocks/item 映射、真实 HTTP 资产 byte/hash/mime 检查、emptyB4Counts 和固定 T30/T60 HTTP oracle 均保留，未预造 B4 记录。

R08 spec 当前仍为 SHA `66e1c563fa46c83102a84d6761c362bb0a901bcf68e73d0fc91c292f8d436156`。删除唯一新增精确 `toHaveURL` 等待可逐字节还原 r6-before；原 115 个直接 expect matcher 和 2 个 expect.poll 未减弱，只多一个导航 matcher。等待绑定固定 localhost/5174、实际 import 非空 ID、相同 practiceSetId 和 URL 末尾，不更改业务断言、超时或 mock。独立晚 GET500 的原 JSON 及 SHA 继续保留，不以此静态审阅宣称已解决。

## 可绑定的原验收身份

r5 前端全部 **451 文件**与当前候选和实际源码精确同 SHA；根级非 apps/tests 输入 **32 项**同源，含 package/lock、ESLint、Vitest、Playwright、启动/模板脚本等。前端配置与样式已包含于 451 项。r5 构建清单 **2007 文件**当前逐一 0 漂移，BUILD_ID 仍为 `v3NL9Nd4Zve30UcCepg0R`，next-env 原字节 SHA 与构建身份一致，清单中的 API rewrite 仍为 8001。没有重建或操作用户前端。

T70 作者清单的 **14 项**（6 业务源、7 自检源、1 QA 执行脚本）逐项与作者 v1.3、r2 独立 A 候选、r5、r9 及实际文件完全同 SHA；独立 A 可执行 QA 也与 r2 同源。固定成绩/原卷/名单 facts、教学 owner 与固定回流 lineage 查询均未改，聚合仍为纯整数函数、T70 不访问 FixedQuestionReader。因此可将先前 A 的 8 场景证据按同源绑定保留；本轮没有重新执行 8 场景或规模测量，也不把同源结论扩为新的 owner 业务实测。

## 执行与后续限制

仅读取代码、清单、修前字节并使用 Python stdlib AST/散列；只写本 MD/JSON。未导入 app.main，未测试/收集，未启动或停止服务，未检查端口，未读取正式或临时数据，未改产品/可执行 QA，未执行 Git。CTRL 在首轮静态捕获后另授权 P 的 Scene.question 和 F 的 stdout/stderr UTF8 两处 QA 适配；最终本地 QA 相对 r9 的差异在 JSON 原样列出，需新候选另行补审。不能将后续差异写成 r9 当前全 QA 零漂移。

准备过程的两个窄问题已记录：最初 Python 路径选错，退出后用已有 apps/api/.venv 重读；最初广义等待选择器匹配到已有行，最终用仅新增字节行证明还原。均未执行或改动业务。
