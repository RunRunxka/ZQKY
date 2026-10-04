# G1-V00-SCORE-QB v1 独立验收结果

负责人 `/root/g1_v00_score_qb`，2026-10-02。候选 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec` + G1 冻结文件。状态 **pass，待 CTRL 集成确认**。独立于本批实现者，只写 `v00-score-qb/**`；产品、直接产品测试、共享文档和旧证据均只读，未开始 B4。

最终单次 **53 passed / 0 failed / 0 skipped / 1 warning，16.15 秒，exit 0**：R04 33 个场景、R07 20 个场景，见 [accepted-v2.log](accepted-v2.log)、[accepted-v2.xml](accepted-v2.xml)、[EVIDENCE.json](EVIDENCE.json)。不累计中间运行次数作为通过数。

## 冻结与证据保护

- 初检 r1 全部 825 项：仅 `next-env.d.ts` 在 CTRL typegen/build 窗口短暂改变，保存 [sha-before.json](sha-before.json) 后暂停产品验收。收到恢复通知后重新完整核对 **825 项 0 差异**，才开始执行，见 [sha-before-restored.json](sha-before-restored.json)。
- 验后 r1 **825 项 0 差异**；CTRL 将安全 `.env.example` 补进配置覆盖形成 r2，原 r1 文件不变。验后 r2 **826 项 0 差异**，见 [sha-after-r1.json](sha-after-r1.json)、[sha-after-r2.json](sha-after-r2.json)。r1→r2 仅扩展覆盖，无产品改动，无需重复不受影响的行为测试。
- 旧 B2/B3/FIX/REVIEW **629 个证据文件逐字节 0 差异**，见 [old-evidence-check.json](old-evidence-check.json)。未覆盖旧日志、原诊断或首败；本目录独立夹具及收据与旧实现测试分离。

## R04 正确行为

自建新临时应用，用真实 `create_app` + `TestClient`；每场景均检查教材、题库、知识点、教学 **四个 SQLite 库**实际存在。班级、学生、施测、上传、确认、矩阵均走真实 HTTP API，无业务服务/仓储替身。前置两叶原卷 Q1=2/Q2=3 仅在临时教学库通过真实迁移约束及 `draft→confirmed` 触发器种子建立；成绩预期单位和四态矩阵为测试手写常量，不调用生产分数解析来生成期望。

- 五类原值：学号、姓名、小题、总分、出勤；CSV/XLSX 原值、XLSX 公式文本和字符串缓存共 **20 场景**。20,001 字符非法非零尾文本及超长公式均返回 422 `TABLE_TOO_LARGE`，逐字段精确校验 `sheet、row=4、column、address、view、actualLength=20001、maxLength=20000`。独立原表有两个空前导行，防止把逻辑行误当原表物理行。
- 每次拒绝前后七张成绩/资产/提交表计数、施测完整详情和全部受管 blob SHA 相同；零新增导入、成绩修订、正式格子、审计、受管文件和成功提交。预存原卷 blob 和上传源文件逐字节保留。
- **6 场景**证明 20,000 字符合法尾零 `1.000…`、`0.000…`，在 CSV、XLSX 原值、公式字符串缓存完整保存于 `raw_cells_json`，受管上传原件与源字节相同，最终确认分别为 100/0 单位，前导零学号 `0007` 不丢，正式矩阵与总分精确相符。
- **2 场景**：20,000 字符末尾非零非法精度返回定位 C4 的 `SCORE_CELL_INVALID`，不舍入、不截断、零导入/正式矩阵/资产写入。另 **2 场景**：数值上完全合法的 20,001 字符尾零也明确拒绝，不绕过文件支持上限。
- **2 场景**：真实确认四人×两叶的 8 格完整矩阵；有效 0=`recorded(0)`、空白=`missing`、缺考=`absent`、免考=`exempt`，后 3 类有信息缺失/非记录状态的人次总分均 null，仅全 recorded 人次有总分。
- CSV parser 的 131,073 字符备注触发本次触及的错误路径，返回 JSON 422 `TABLE_PARSE_FAILED`、CSV/真实第 4 行、无伪造未知 column，零上传写入。畸形 XLSX dimension 未执行，保持观察项，不提升为第九项 G1 阻塞。

## R07 正确行为

所有题库操作走真实 HTTP，不导入或调用生产 fingerprint/identity 函数作为期望值 oracle。独立富内容夹具直接给出共同材料、段落、两个选项、LaTeX/OMML、表格及真实 PNG 字节；夹具只自行构造现行 Markdown 投影，重复/不同题的期望完全来自手写场景。

- 相同题干/选项、材料 `1 mol/L` 与 `2 mol/L` 分别在默认和 `edit_as_new` 两条路径均成为两道正式题，预览不判重；同一个确认包内材料不同的两题也均入库，正式修订固定材料不混淆。
- 独立改变题干、选项、OMML（保持 LaTeX/旧文本相同）、LaTeX、表格合并跨度（保持表格投影相同）、表格内容、真实图片字节，预览与确认均区分新题。不同图片只位于共同材料，旧题干文本完全相同；同一实际 PNG 在受管键与题庫旧 bare SHA 存储别名之间仍判为真重复。
- 真重复忽略随机块/材料 ID、原始来源定位、答案和解析的变化；冲突答案明确显示“答案不同”。默认跳过；`link_existing` 明确关联原题并追加新来源，17 个其他详情字段/内容/答案/固定修订全部相同，旧来源保留；`edit_as_new` 返回 `DUPLICATE_UNRESOLVED`，不生成第二题或覆盖原答案。冲突草稿保留给教师处理。
- 新题同时保存 `derived-v1` 与 `question-surface-v1`。模拟旧 plain/旧 rich 修订只有旧算法行时，预览及默认重复确认只读比较，旧修订整行及旧指纹行完整不变，未趁查询回填新算法。plain 与等价的只有段落的 rich 也兼容判重。
- 同包两个真重复默认只发布一个；显式 `edit_as_new` 无有效题面改动整包 `DUPLICATE_UNRESOLVED`，正式题和 submission 都零写。
- 成功提交后仅在隔离临时根破坏当前图片字节，再重放原冻结确认包，返回完全相同成功结果且不重新校验当前图片；同键改 expectedDraftRevision 仍返回 409 `IDEMPOTENCY_CONFLICT`。测试 finally 恢复图片原字节。

完整 HTTP 信封、确认包、矩阵、源 SHA 与多次执行记录保留在 [http-receipts.jsonl](http-receipts.jsonl)，147 个独立原表源文件 SHA/大小见 EVIDENCE.json 与 `sources/`。

## 首败说明（全部保留）

四次中间失败均在独立 QA 夹具/断言前置，没有候选产品变更；已逐次通知 CTRL。它们不作为产品回归失败关闭，不隐藏为全绿：

1. `first`：20 passed / 1 failed，7.04s，exit 1。首行说明文字被现行自动表头规则选中，确认返回 `SCORE_MAPPING_INVALID`。独立夹具改为两个空前导行，仍保持同样物理第 4 行、长度/精度/正式矩阵断言。
2. `recheck`：31 passed / 1 failed，9.50s，exit 1。QB fixture key=`first` 只有 5 字符，违反现行 submissionId 最少 8 字符；加固定 `v00-independent-` 前缀，不改变业务预期。
3. `final`：41 passed / 1 failed，13.40s，exit 1。错误把 `link_existing` 收据的 `linkedQuestionIds` 期望写成 `skippedDraftIds`；改为明确原题关联、无新题/无跳过，原 HTTP 正确收据保留。
4. `accepted`：41 passed / 1 failed，13.38s，exit 1。过严要求 link_existing 后包含可追加 `sources` 的整份详情完全不变；改成除了来源外 17 字段完整相同、原来源保留、仅该操作追加来源。内容/答案/固定修订不可变要求未放宽。

最终 `accepted-v2` 单次 53 条全部执行通过。每次日志/XML/退出码均以原文件保留；唯一 warning 是既有 Starlette 对 AnyIO BlockingPortal 的弃用提示。

## 未执行与资源

本 Agent **未执行** root 的 check/API 全量/build/E2E、实际浏览器/Word/WPS/Qdrant、真实供应商教学质量、G1 前端/任务领域、B4 分析/练习/迁移/导出、压力与多进程协调，因为它们不属于 R04/R07 独立任务。不能据此结果宣称 G1 全部关闭或 B4 已验收。

所有解释器在任何间接 app.main 导入前设置新系统临时根、`ZQKY_ENV=test` 和 UTF8；每个 Settings 明确 `credentials_file=None`。未读 `.env`、正式业务库、真实草稿、只读原始教材、旧六个 policy 拒绝删除目录；没有外部网络/模型调用、常驻监听端口、浏览器上下文、构建、Git 写操作、消息外发或部署。

五个 bootstrap 根及 190 个每场景临时根保留在 [resources.json](resources.json)，每次 TestClient 正常退出，所有运行进程已结束。未删除未知数据和任何旧六个目录；本 Agent 不擅自清理总控可能仍需复查的临时库。独立测试/验收写入现已停止。
