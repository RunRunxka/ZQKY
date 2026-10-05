# G2-V00 v1 · 独立验收准备

日期：2026-10-03，北京时间。负责人 g2_oracle。**当前仅准备源码，全部检查 not_run**；没有执行 pytest/Vitest/Playwright/类型检查/lint/build，也未导入或装配 app.main、启动/停止服务或访问正式数据。实现者仍在编写，不能以本目录存在宣称独立通过。

起点 main@6aeb57280f6a7e0d7391cad4d150745479ea58ec；旧 B4 r21 及原审查仅为历史输入，实际执行必须绑定 CTRL 新冻结候选、构建与保全清单。原三条组件正确行为首败、真实草稿原包反例及历次日志均保持。

## 准备源与手写 oracle

| 来源 | 准备范围 |
| --- | --- |
| unit/edit-ack.test.tsx | 练习2→3及备注A→B的原 unknown、首次200；更高服务端版本后旧receipt；相同revision不同固定身份；重复点击；切练习/报告后迟到ACK |
| unit/frozen-metadata.test.tsx | 原payload/首次metadata深等重放；重复点击一调用；recoverFrozen不自动发送；卸载迟到回执current=false |
| unit/leave-recovery.test.tsx | 原切换反例改为取消/明确保留/明确放弃；分值、节点题号、KP选定与约束全保持；固定历史分离；409保存失败留原上下文；坏缓存原字节保留 |
| api/test_draft_receipts.py | 11个显式真实HTTP例：S1/CAS3→revision4/100；并发同包/异包；S2→revision5/200后S1仍旧receipt4/100；原包冲突/真正旧CAS/无ID422/practice域/owner；审核+题归档后重放；receipt登记失败全事务回滚 |
| browser/correct-behavior.spec.ts | 5个真实浏览器例：全部字段取消/明确放弃；真实422保存失败及成功后才切换；历史/来源报告/补题/公共侧栏/Back/刷新/关页恢复；真实PATCH200丢回执、unknown刷新后原包重试仍保留3；真实备注A丢响应重放保持B |
| browser/seed_runtime.py | 接受 CTRL 已隔离的 app，真实四库原成绩→报告→练习/导出初始种子，再建立两份草稿；不创建app或监听 |

预期值均手写；没有调用生产 merge/ACK/canonical_hash/session validator 来生成预期。static fixture 仅提供原反例的输入形状。并发指同 app 的两 HTTP 请求，不声称已验证多进程 PublicationCoordinator。

真实丢响应通过 route.fetch 实际保存取得200/201后 route.abort；重试 route.continue，深等原HTTP包及submissionId。没有伪造成功响应。截图/trace只由未来实际执行生成；不存在预造截图。

## 环境与执行依赖

CTRL先停写并冻结产品/公共契约/本目录源码，运行记录应包含候选SHA、命令/env、PID/创建时间、exit、单轮计数、重试/跳过及用时。当前尚未生成执行结果；以下只是入口。

- Python收集前新建系统TEMP `zqky-g2-*` 根，建立data目录并设置 `ZQKY_DATA_DIR`、`ZQKY_ENV=test`、`PYTHONUTF8=1`；代码顶部在任何直接/间接app.main导入前拒绝缺失/非TEMP隔离。pytest `--basetemp` 置于本次新根，`G2_V00_OUTPUT` 指向新label的输出目录。Settings显式credentials_file=None、空教材目录、Qdrant16333、embedding9；不用正式env、模型或6333。
- API每例独立四库，TestClient不监听端口；HTTP完整JSON与四库integrity/FK结果按独立文件写入，采用exclusive-create，不能覆盖上一轮。
- Node使用仓库依赖与 `NODE_OPTIONS=--no-experimental-webstorage`。unit/vitest.config.ts retry0、5000ms测试预算；原全量工程门禁另由CTRL执行，不将此窄测冒称全量。
- 浏览器前由CTRL核实真实8001服务、拥有的临时根、实际新build/8001代理及5174监听身份。不得结束现有用户前端；具体审批拒绝不换Agent/工具/端口绕过。
- seed_for_browser(app, manifestPath) 由CTRL显式调用，不能在正式app调用。设置 `G2_V00_SEED_JSON` 指向生成的新manifest，包含schemaVersion1/apiOrigin/runId/practiceA/practiceB/fixedRevisionA/targetKnowledgePointIds/initialNote/questionId/questionRevisionId/catalogPaths。practiceA初始revision3，B为独立草稿；全部资料是合成种子。
- external.config.ts `webServer=undefined`、workers1/retry0，继承原45s单例/10s expect预算，不自动起停前端或扩大预算；`G2_V00_RUN` 必须是新的label，已有输出目录拒绝复用。trace=on保留完整独立断言链。

首败完整保留；实现修复要新候选。框架/选择器错误与产品失败分别登记，适配合法接口不删除原case、不降低正确行为、不拼接多轮绿色。

## 未执行与准备期诊断

本轮尚未执行所有产品/工程/浏览器检查、真实模型/Word/WPS/Qdrant/正式迁移；原因是 CTRL 只授权准备源，候选尚未停写。没有自有进程或连接需要释放，没有读取正式草稿。

只读准备曾误猜 submissions.py（实际services/submissions/service.py），误猜teaching_b4迁移通配（实际core/migrations/b4.py）；已用rg读取真实文件。编写期间自行发现并修正browser配置相对导入层级、节点题号标签和ApiError参数位置。这些均为执行前准备修正，没有业务首轮结果或隐藏重跑。
