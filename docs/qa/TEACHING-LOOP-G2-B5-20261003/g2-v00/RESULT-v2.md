# G2-V00 独立窄复验结果 v2

2026-10-03，北京时间。状态 FAILED_NARROW_REVERIFY；G2 保持打开，浏览器及后续门禁停止。绑定 G2-r2 SHA aaa4868a51ff9d9ce12f45bc08bd3084832029a4ca7f2bab5ca789b78b7c9fa8，构建 Y6c5E7notWcBElEjX1GF_，本轮可执行 QA 为已冻结 v4。r1/RESULT-v1 与所有首败文件保持原样。

## 实际结果

| 检查 | 真实结果 | PID / exit / 耗时 |
| --- | --- | --- |
| 4 文件 / 23 unit | 22 passed、1 failed、0 skipped；3 文件通过、1 文件失败 | 7628 / 1 / 2508.342ms；Vitest 2.04s |
| 11 API | 10 passed、1 failed、0 errors、0 skipped、1 warning | 7716 / 1 / 12846.815ms；pytest 12.54s；JUnit 12.473s |
| 四库完整性 | 11 例共 44 个 integrity_check=ok / FK 空，并显式关闭连接 | 独立各案例新 TEMP；完整输出在 run-api-fixed |
| 8 browser | 未执行 | 窄复验失败，未发运行卡 |

两个门禁均失败，不把 22/23 或 10/11 拼成 G2 通过。只各启动一次，原预算内并行运行，retries 0；首败在工具返回后立即报告 CTRL，没有新增检查或重跑。已启动 API 单轮的最终收据仅做收集。

## 首败归因

unit 的 explicit-discard 场景 line74 仅等待满分 '1'；A/B 都有该值，不能证明新 A 已加载。随后 line75 取题量时 DOM 只剩列表。静态证据提示 QA 的等待身份缺口，尚未确认新断言运行结果；首败及原断言留存。后续修正须等真实当前 A 身份和完整 editor 字段后检查全部恢复值，不能删断言、放宽预期或拓预算。

API 并发同 S1、同 body 是实际产品行为失败，CTRL 已确认：两请求均来自 copy.deepcopy 同一原包，实回包一条 200/replayed false、一条 409/REVISION_CONFLICT。正确预期保持双 200、一 false 一 true、相同业务结果、一个原 S1 收据和一次 CAS 编辑。该案例在 status 断言首败，后面的 replay pair/once-write 未执行，不冒称这些原断言已通过。

本轮完成后只读查看该案例自身、经 TEMP 路径验证的 teaching.sqlite3，精确原 operation+S1 收据数为 1，当前 revision4。诊断与真实失败回包完整存 API-FAILURE-DIAG-v2.json；原包从已捕获 copy-201 响应及冻结 fixture 字面变换重建，并非网络 request body 抓包，记录明确这一限度。该诊断不能把 409 的失败 oracle 改判为通过。

## 绑定与保留

unit runner 自动候选绑定 source 886 / QA287 的 before/after，changedSources/changedQA 均空；API runner source886 前后 sourceDrift 空，独立 qa-before-v2/qa-after-v2 另核 QA287 前后无差。全部 before 与候选 SHA 表一致。完整 command/env/PID/ms、runner logsClosed、unit childClosed、log SHA 见 RESULT-v2.json 和 CTRL 原 command receipts。两个 run 各独占新系统 TEMP，API 凭证 None、无 TCP server、教材为空、Qdrant16333/embedding9。没有访问正式 env/data/草稿。

9 份 r2 可执行 QA 原字节已保留于 run-api-fixed/source-snapshot（验证等于 v4 frozen hashes，供后续修正前保留）；unit完整 JSON、logs，API全部11份HTTP journal、11份四库 integrity、XML、TEMP 数据保留。源码、QA、权威文档、服务和 Git 均未修改或起停。待 BE 修复和另行授权 QA等待修正、新稳定候选后再跑新 label。
