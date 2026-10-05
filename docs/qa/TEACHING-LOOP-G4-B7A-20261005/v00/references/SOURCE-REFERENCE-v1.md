# G4-REF v1 独立历史引用核查（STOP）

2026-10-05，g4_s。只读当前稳定候选 `CANDIDATE-G4-built-r3-qa.json`，构建 `cIUfoiJQX6Dhw7umsfyyW`；956源码、33契约及970构建文件逐SHA before/after均零漂移。本卡没有执行历史测试、恢复、导出、渲染、看图或真实模型，仅验证适用引用的原文件和限定源码域。完整路径／SHA／当前漂移见 [SOURCE-REFERENCE-v1.json](SOURCE-REFERENCE-v1.json)，实际只读运行PID18504／683.122ms。

| 引用域 | 独立核对结果 | 本批是否新跑与限制 |
| --- | --- | --- |
| 后台／原全量API | 原 `ctrl/B6-MATERIALS-SAME-SOURCE-v1.json` 的410文件全部当前精确相同；原两个运行 sourceBefore/sourceAfter的410子映射也逐文件相同。原 `b5-api-full-prebuild-v1-command.json`（PID21200／392504.479ms）和原JUnit实际1919项：1918pass、1既有重型skip、0fail/error | 本批未重跑1918+1。没有backend/provider/DDL/recovery产品变化，原重型skip保留为not_run压力；新质量工具窄验收另列 |
| 原独立后台42 | 原 `b5-v00-prebuild-v1-api-first-command.json`（PID20076／40948.122ms）与原JUnit实际42/42，源码同一410子映射，证据SHA均与冻结记录/开工历史QA锚一致 | 本批未重跑42，不冒称新业务／新工具通过来自旧42 |
| 原备份／恢复 | `B6-RECOVERY-REFERENCE-v2.md`、精确JSON、原全量API中恢复case及复制的proof载荷均原SHA绑定；早期schema gate曾有1差异，保留“早期5仅4同源”，当前最终410同源恢复case可引用 | **不是本批新恢复**。当前原保留proof及旧TEMP的SQLite已经缺失；存在性附证见 [RECOVERY-TEMP-EXISTENCE-v1.json](RECOVERY-TEMP-EXISTENCE-v1.json)。未打开SQL/Blob、重建原库或猜清理原因。原SQLite/Blob为隔离实际恢复；Qdrant为Transport替身，正式6333／迁移／新压力均not_run |
| 最新chat专项与共享壳 | 从最新 UI-UNIFY `source-r11.json` SHA505cff…、`final-integrity.json`、`chat-r13.json` SHA17165f…逐SHA绑定；chat/共享壳/控件/样式/客户端/契约/相关运行源码域186项当前零漂移。原聊天JSON实际14次passed attempt、retry0、0skip/flaky/reporter errors，独立构建 `8poFqRffbOe-w2FM8T0jy` | 本批chat14未重跑。引用最新UI统一后的14，不能使用B6旧蓝图的103项粗略等同；当前来源/恢复仅改教案域。整个UI472项有10个本批教案改动，不称整个472同源；完整适用174 E2E和G4新浏览器由ROOT另验 |
| 原Word模板与导出核心 | 原根Word、teacher-standard副本、manifest及派生模板逐SHA保持；既有11项导出service／print.css／模板核心同源 | **旧export/styles43清单有12项漂移**（外部UI统一及本批教案恢复接线），具体路径／前后SHA在JSON。尤其全局styles不同于旧B6；不使用“43全同源”宣称新build排版或渲染等价 |
| 原15案例／rubric／空feedback | 原B6候选 f79ac9… 的1056三路材料全部逐SHA保持，包含原case-specs、15 inputs/wire/source全列绑定/candidate/application/DOCX、量规、反馈、两类独立审查与关闭材料。原SUMMARY实际15唯一案例；15行教师字段全部为空 | 当前仅引用旧offline-third固定输出和原冻结源证据，没有新生成15例或重新调用Provider。旧案例及四导出TEMP目录仍在，SQLite均缺失；当前物理来源not_run_source_temp_unavailable。当前G4-Q新独立工具反证另见v00/quality，结构PASS不代表真人教学评价 |
| 原四DOCX／13PDF页 | short/long/multi/symbols四manifest、4DOCX、4真实PDF及1/8/2/2共13页原PNG，逐SHA与原B6候选保持。原逐页签收、完整字段提取、来源及全history记录均引用原件 | 原导出实际使用 `q84e_pxQoZ2_nwnws9QiI`，不能称本批 `cIUfoi…` 新导出或新排版签收。本卡不重渲染／看图，不以原13PDF页替代Word/WPS原生验收；native仍not_run |

原B6 `ctrl/B6-MATERIALS-SAME-SOURCE-v1.json` 是当时事实，未改旧报告或关闭记录。此处新增当前域归因及限制：backend410可精确引用；chat/shared-shell使用最新UI候选；Word/PDF只引用原冻结文件与限定未变导出核心，当前样式/教案接线差异明确单列。

物理源、冻结绑定、技术结构、native排版、live与human各自分栏：当前物理源未查；冻结原材料SHA通过；历史结构与13PDF页签收按原件引用；Word/WPS未验；真实模型0；教师评分／理由空，teacher_review_pending。C10～C13原材料不是RAG真实检索质量试验，RAG-REL保持OPEN。CV01～03、R14、OBS-LP-MODE-LABEL、原ERR_NO_BUFFER_SPACE等首败/观察保留，不以一次全绿关闭间歇台账。

所有60条核心引用精确路径和SHA以及1056材料清单在JSON中；当前物理proof不存在时单列缺证据，依据冻结proof载荷与原命令/JUnit引用其历史验收，未伪造当前proof重查。本卡SQL连接/网络/应用导入/正式env读取/服务/Git均0。ROOT的新适用保存／来源／离开场景及必要门禁不得由这份历史引用替代。
