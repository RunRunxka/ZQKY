# B4 r21 后续代码审查

日期：2026-10-03，北京时间。用户请求为“review一下，再输出下阶段提示词”。本批只读审查产品、运行隔离探针和相关窄回归、编写后续提示词与现行文档说明；**没有修复产品或启动 B5**。

## 结论

本轮确认 **3 项 P2**：练习未保存输入的离开保护、未知原包的编辑代次、练习 PATCH 的原包恢复。建议下一批先以 **G2** 修复并独立关闭三项，再实施 **T90/F30 学情驱动教案增量**。B4 原独立验收与关闭仍是原批历史事实，本次发现的是原门禁未覆盖的编辑边界，不追改旧结论或冻结件。

学情 T70 的固定成绩、自身人次/叶快照、四态与 any_loss_v1、分母、证据分页、幂等与 owner 隔离在本次范围未见新增可复现缺陷。T80 现有审核/固定题/导出/转换/成绩回流相关回归通过。**65 项既有窄回归通过**，不能代替新边界正确行为：前端三个探针和实际 HTTP 重放探针仍失败。

## B4F-R01 · P2 · 切换练习会静默丢失未保存草稿

位置：[PracticeEditor.tsx:39](../../../apps/web/src/features/practices/PracticeEditor.tsx:39)、[PracticesWorkspace.tsx:49](../../../apps/web/src/features/practices/PracticesWorkspace.tsx:49)（历史切换在59行，身份重新挂载在62行）。

编辑器仅把 pending/unknown 上报为锁，dirty 没有离开处理。列表直接换 practiceSetId，历史直接换 fixedId，导致携带本地 state 的编辑器被卸载。

独立组件复现：原满分1，未保存改为5；切第二份练习，再返回第一份，满分变回1。全程零 PATCH，未出现保存或明确放弃交互。期望保留5的正确行为断言失败。证据：[组件探针](frontend/practice-boundaries.test.tsx)、[最终首轮日志](frontend/probes-final-v2.log)。这是实际工作区组件的切换行为，本次没有声称已跑浏览器路由导航。

应增加按练习身份隔离的恢复稿或统一的保存/取消/明确放弃策略，覆盖列表、历史、补题往返与公共导航；失败/冲突/未知结果必须保留当前输入。仅把 dirty 永久当忙碌锁禁掉切换，且不给用户处理出口，不能关闭此项。

## B4F-R02 · P2 · 未知重试重新捕获编辑代次，旧 ACK 覆盖后续输入

位置：[PracticeEditor.tsx:69](../../../apps/web/src/features/practices/PracticeEditor.tsx:69)（69～77行）、[LearningAnalysisWorkspace.tsx:213](../../../apps/web/src/features/learning-analysis/LearningAnalysisWorkspace.tsx:213)（213～216行，TeacherNotes）。

首次提交冻结了原包，但未知响应重试的外层函数重新读取当前 editGeneration。此时 payload 仍是旧输入，generation 却是新输入；ACK 比较误认为“用户没有继续编辑”。

- 练习：发送满分2，等待期间改3；首次响应未知，重试仍发送原包2；成功回执把输入覆盖回2、清除 dirty。期望保留3的断言失败。
- 备注：发送A，等待期间写B；未知后重试原A，成功回执将B清空。期望保留B的断言失败。

两次请求均断言完整深等。本组使用受控服务回执，证明实际组件的操作/输入边界；练习后台成功重放缺陷另列 R03。首次请求未被服务端接受、第二次才接受原包也是合法触发条件，R03存在不能否定本项。

证据：[三个前端探针日志](frontend/probes-final-v2.log)、[前端详细报告](frontend/RESULT.md)。应把 context、submissionId、payload、**首次 editGeneration** 一同冻结并跨重试保留。回执只确认原操作，后续输入继续 dirty；不能改用重试按钮点击时的代次。

## B4F-R03 · P2 · 练习保存已成功，原包重放撞上自己的 CAS

位置：[PracticeDraftPatch](../../../apps/api/app/contracts/b4.py:189)、[PracticeService.save_draft](../../../apps/api/app/services/practices/service.py:237)、[前端调用](../../../apps/web/src/features/practices/PracticeEditor.tsx:71)。

PracticeDraftPatch 没有 submissionId，save_draft 先核 expectedRevision，成功后递增版本，没有提交登记/返回原结果能力。前端却使用冻结提交并提供“重试原草稿保存”。CAS按现有契约工作，问题在于前后端对未知结果的恢复协议不一致。

真实 FastAPI 四库 TestClient 链：审核版复制草稿，把整题/叶满分1.25改1.00，expectedRevision3 首次 PATCH **200 → revision4，totalScoreUnits100**。将此回执视为浏览器未收到，完全相同请求再次发送：**409 REVISION_CONFLICT，currentRevision4**，服务器新值确实仍是1.00。不是其他编辑者导致的冲突。

证据：[完整收据](practices/changed-patch-replay.json)、[正确恢复断言首败](practices/changed-patch-first.log)、[详细报告](practices/RESULT.md)。本次使用真实业务 HTTP 装配，无伪造产品成功返回；未启动网络监听或实际浏览器丢包。

建议给保存加入稳定提交身份并复用同库 command_submissions，成功重放先于当前 CAS 校验，业务与收据同事务。也可设计明确读取核对恢复协议，但不能盲用新CAS再写一次或把所有409当第一次未提交。需保留真正多客户端CAS冲突，并验证期间另有保存后重放仍返回原收据而不回退新稿。

## 观察项，未定为阻塞缺陷

1. **XLSX文字题号投影。** 自定义合法题号 `=16` 的表头与固定映射被 openpyxl 编码为公式型f。实测T60回导仍正确，没有证实成绩错误/丢失；未用Excel/WPS求值。建议明确文字字段类型或前置拒绝格式。实际包及回导见 [formula-header.json](practices/formula-header.json)。
2. **多共同材料的可见归属。** combine将去重后的全部材料前置，题组标题没有自动标明材料编号。题干只写“根据上述材料”时可能不够明确。仅静态观察，符合当前共同材料统一前置形式；本次无真实Word反例，不判数据错配。后续教学/排版验收应覆盖多份不同材料的题组。
3. 保留原R-14间歇、聊天静帧观察、RAG-REL等既有台账；这次窄审没有关闭这些问题，也不把所有已有观察派作B5必修。

## 本轮验证与证据

| 检查 | 本轮实际结果 | 原件 |
| --- | --- | --- |
| T70新增独立探针 | 4 passed，exit0；含216个状态组合、同进程并发幂等、owner与真实ASGI分页/备注 | [分析结果](analysis/RESULT.md)、[日志](analysis/probes-first.log) |
| T70既有五文件窄回归 | 20 passed，exit0 | [日志](analysis/regression-first.log) |
| 前端既有四文件窄回归 | 27 passed，exit0 | [日志](frontend/regression.log) |
| T80既有窄回归 | 18 passed，exit0 | [日志](practices/regression-first.log) |
| 前端新增正确行为 | 3 failed，exit1；对应R01与R02两条路径 | [最终日志](frontend/probes-final-v2.log) |
| 草稿真正改分后的恢复正确行为 | 1 failed，exit1；对应R03 | [首败](practices/changed-patch-first.log) |
| 候选与保全 | 开工五分组879/53/5/2007/191均0漂移；另捕捉两旧B4目录2916个文件，收尾结果见独立JSON | [BASELINE](BASELINE.json)、[FINAL-VERIFICATION](FINAL-VERIFICATION.json) |

前端首轮有一条测试选择器未考虑无障碍名称空格，修正后保留新日志，最终三条失败均为产品输入保留断言。T80首次边界命令另有模板文字投影诊断失败，仅列观察，不能机械地把所有失败计作产品缺陷。各轮不合并、不覆盖。运行命令与隔离根分别见三个 RESULT 与 TEMP-ROOT；Python在app.main导入前设置新临时 ZQKY_DATA_DIR/ZQKY_ENV，Settings.credentials_file=None；Node使用必要flag。

**未执行**：本轮全量check/API/build/E2E、浏览器与像素、真实模型/教学质量、Word/WPS、Qdrant、正式迁移、200×100再跑及超基线压力。原因是本次只读针对性复查，现有问题已由隔离组件/真实装配HTTP证明。用户所报153/14/2保留为 [原B4报告](../TEACHING-LOOP-B4-RESUME-20261003/REPORT.md) 的历史运行，不算本轮重跑。

## 下阶段落点

[B5总控提示词](../../design/teaching-loop-v1/B5_总控启动提示词_20261003.md) 已精确到接口/事务/编辑会话伪代码和验收。顺序为 **G2三项关闭 → T90后台教案与AI建议 → F30现有教案工作台增量 → 本批独立与工程验收**。当前只编写，未开始执行。

已有教案规则填充、本地schemaVersion1和旧键、撤销重做、串行保存、JSON、模板Word及打印继续保留。新接口当前尚未实现，lesson_generation仅为预留kind；不能宣称已有真实教案后端。模型使用匿名固定班级统计与真实固定教材/题库依据，建议由教师逐字段接受，同库原子追加不可变教案版本，不修改固定学情。具体数据库与公共契约由下一批CTRL追加冻结。

收尾没有产品/既有测试源/构建/next-env改动，无本轮服务/浏览器/端口残留。旧QA及冻结件不改；仅新增本批证据/提示词，并更新 CURRENT_STATUS、接手及文档索引以免后续使用过期入口。权威文档的后续更新不回填r21。[运行与文档检查入口](EVIDENCE-COMMANDS.md)汇总本轮证据。
