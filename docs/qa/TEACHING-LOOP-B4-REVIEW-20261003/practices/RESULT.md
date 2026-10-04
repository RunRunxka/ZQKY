# B4 T80 只读代码复查

日期：2026-10-03，北京时间。产品、正式库、旧证据与权威文档没有修改；未启动监听服务/浏览器、未读取正式凭证，未提交或推送。本目录只保存新增复查脚本与证据。

本范围确认一项跨前后端 P2，根报告编号 **B4F-R03**；两项另列观察。既有窄回归通过不能覆盖本次新反例。PATCH 的现有 CAS 本身按契约工作，问题是前端把这个未幂等的保存接口当作可冻结原包重放的提交操作。

## B4F-R03：已提交但回执未知的草稿保存，原包重放永久撞自己的 CAS

代码：[`PracticeDraftPatch`](../../../../apps/api/app/contracts/b4.py:189) 没有 submissionId；[`PracticeService.save_draft`](../../../../apps/api/app/services/practices/service.py:237) 先核 expectedRevision，成功后无条件将 practice_sets.revision 加一；没有原包提交登记或恢复原结果的路径。前端 [`saveDraft`](../../../../apps/web/src/features/practices/PracticeEditor.tsx:69) 却使用 useFrozenSubmission，并在未知响应时重发原 expectedRevision/载荷。

真实装配 TestClient HTTP 实测：从审核版复制一个新草稿，编辑整题和计分叶满分从 `1.25` 为 `1.00`；PATCH `expectedRevision=3` 首次返回 200，服务器已保存 `totalScoreUnits=100`、新版本 4。设此响应没有送到浏览器，重发完全相同原包：409 `REVISION_CONFLICT`、`details.currentRevision=4`；服务器保存的新满分仍为 `1.00`。这不是并发编辑者造成的冲突，是自己的成功请求导致的冲突。

证据：[`changed-patch-replay.json`](changed-patch-replay.json)、[`changed-patch-first.log`](changed-patch-first.log)、[`XML`](changed-patch-first.xml)，正确恢复断言 **1 failed，exit 1，2.11s**。另保留首次无内容变化保存的独立边界复现 [`patch-replay.json`](patch-replay.json)，同为 200→409。TestClient 运行真实 create_app/lifespan、真实四库、JobEngine 与所有练习相关 HTTP 操作；未使用浏览器或为产品 API 伪造响应。所有种子和成绩/报告/练习/导出均仅在隔离临时根。

影响：丢回执后的“重试原草稿保存”无法完成页面的保存确认与 CAS 更新；关联的后续审核等流程可能停在过期版本。具体组件上的错误/恢复表现由前端复查目录另证，本目录不冒称已跑浏览器。修复可给保存引入同库提交身份及原包重放，或实现明确的读取核对恢复协议；不能仅将 expectedRevision 改为当前值再盲写，也不能把所有 409 当作首次请求未提交。

关闭标准：真实业务首写已成功且回执丢失，完全相同保存原包能够确定原保存结果/固定身份，且不再创建额外版本、不覆盖期间发生的其他编辑；另一人的真正 CAS 冲突继续保留本地输入并显示差异。需要对应实际页面链，受控 fetch 单测成功不足以证明真实 PATCH 支持重放。

## 观察项

**O-P1：公式样貌题号在 XLSX 中被编码成公式。** 服务接受完整自定义题号 `=16`，保存、审核、转换、导出都成功。[`exports.template`](../../../../apps/api/app/services/practices/exports.py:82) 对学号/姓名设了文字类型，却没有对题号表头与固定映射的题号列做同样处理：`成绩!E1`、`固定映射!C6` 的 `data_type` 均为 `f`。[`formula-header.json`](formula-header.json) 保存实际包读取及回导结果。本次填 0 后回传 T60 仍正确匹配 E 列、无 issues/missing，**没有证实成绩丢失或错误封存**；未用真实 Excel/WPS 求值/保存，不推断应用的最终显示或动态计算风险。建议将所有文字身份字段明确导出为文字，或将不允许的题号格式前置拒绝；目前作为观察，不纳入阻塞缺陷。

**O-P2：多份不同共同材料全部前置，题组没有自动显示材料归属。** 静态核查 [`combine`](../../../../apps/api/app/services/practices/exports.py:35) 按内容身份去重后把所有材料放入一个 sharedMaterials 数组，题组标题只显示序号与分值，没有材料标号/引用；公共 T10 renderer 会统一先输出材料、再输出题干。两个题组各自的题干只称“根据上述材料”而没有明确名称时，读者可能难以判断归属。本行为符合当前 v1“全份共同材料只输出一次”的组合形式；未新增真实 DOCX/Word反例，不定为数据错配 bug。后续可以保留去重同时增添可见材料编号及题组引用，人工排版/教学质量验收应包含这种场景。

首次边界命令 [`probes-first.log`](probes-first.log) **2 failed，exit 1，4.60s**：一项为原包恢复正确行为，一项为文字题号投影的理想行为。后者是上述观察的诊断断言，不将“断言失败”机械地算成产品阻塞。新增真实改分反例是另一条单独命令，首日志全部保留；没有重复运行拼接成全绿。

## 既有窄回归

[`regression-first.log`](regression-first.log)、[`XML`](regression-first.xml)：**18 passed，exit 0**，覆盖 ready/owner/固定旧题、排原题/答案无关、覆盖缺口、审核修订及三类子表封存、教师专用图片全ZIP排除、锁外预检期间归档再核、实际名单与模板冻结、多叶完整题号/顺序/分值、转换同事务与幂等回放、实际 T60→新T70 来源键、映射插入失败全回滚。

运行用显式临时 `ZQKY_DATA_DIR` + `ZQKY_ENV=test` + `PYTHONUTF8=1`，create_app 显式 `credentials_file=None`；pytest 配置也使用隔离数据。[`TEMP-ROOT.txt`](TEMP-ROOT.txt) 与各 JSON 中的 sample dataRoot 保存临时根，均保留。所跑测试只使用受控初始题/卷种子和真实本地业务，不访问真实模型、Qdrant 或正式教材。无服务/端口需要释放。

未执行：全量 API/check/build/E2E、真实浏览器与三视口、Word/WPS、模型质量、Qdrant、正式库迁移、超基线压力；理由为本次只读窄复查，现有问题用本地实际 HTTP 与隔离数据已经可复现，不将旧批次检查冒充本轮重新执行。
