# TEACHING-LOOP B3 总控交付报告（已完成）

2026-10-02，总控 `/root`。用户授权的B3实施、独立验收与适用全量门禁均完成，无遗留本批阻塞fail。全量API1523项、单测1069项及check/build、全量E2E153项均通过；完整真实链、规模与三视口独立复核通过。已停止本批工作，没有启动B4，没有提交/推送/部署。

## 实际起点、文件归属与候选

实际分支/HEAD为 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`，与旧提示0f4b8cb不同。B2/B3已经在该HEAD中；仅next-env.d.ts为既有用户改动。全部旧冻结指纹逐一对照HEAD与CRLF，B2 47/84、B3 157/163匹配，差异为本轮前已有实现/文档/测试，不回退。证据BASELINE.json。

最多3位实现者并行：scores_backend负责成绩服务和后续富内容后端；assessments_frontend负责成绩/原卷/施测/补考组件；question_frontend负责题库观察与名单/草稿保护。精确文件/版本/验收条件列TASK-CARD及各RESULT卡；root独占共享DTO、API客户端、公共任务/模型守卫、共用富内容renderer、集成、浏览器、权威文档、迁移/锁/Git。实现者ready后停止写，独立V00只写自建探针与报告；独立新发现均由root修复，不由验收者边验边修。

当前候选r7 **168项磁盘SHA-256**，包括产品、契约、迁移、测试、配置及锁文件，不代表168个修改文件。r1/r2/r3/r4/r5/r6各原件保留：r3独立产品验收前后165项0漂移；r4仅3个Python测试（两项扩展进清单）；r5仅2个真实browser spec；r6仅重放文案正确断言与代理注释；r7新增模块CSS宽度修复及三视口测量spec。r4成绩验收跟进期间root并行修改两browser spec，独立r4后验如实记录该两项漂移；随后r5重冻结且167项前后零漂移。r7独立前端与G0后验168项零漂移。root权威文档在产品候选之外，后验单独登记。next-env在最终构建后恢复用户原字节，不纳入产品候选。

## 本批结果

- **G0**：RV01–11与三域发布回滚复验关闭；公共retry真实执行、初次queued0/重试queuedN窗口、原lease/CAS、取消与模型漂移零调用、发布锁跨域提交、固定修订标题和已填旧库迁移均通过。原G0已有实现经本轮真实反例复核；新发现正式题PATCH发布锁空隙和过期heartbeat复活已修复。逐项见G0-CLOSE-MATRIX。
- **T60**：严格编码、物理列/行、人工身份/人次消歧、四态与服务端承认、总分/出勤列、定位422、三版本CAS、显式出勤校正/刷新、提交重放、并发仅一赢家、故障零写、完整修正/历史不变可用。独立新增Decimal极端数、过期PATCH/提交交错与重复物理行三类阻塞全部关闭。
- **F20-I**：真实名单映射/link/create/ignore、批次恢复/转班历史；DOCX全原文/共同材料/OMML/图片/合并表格、人工建题/满分/KP/结构化问题处理；固定卷施测、补考既有人次+1、出勤校正；成绩五步与历史修正。未知响应冻结原包/ID，回读新版本不能偷换请求；迟到200/409/422不覆盖新对象。390修正下拉框长ID溢出已修。
- **F10-QB**：正式知识点分类/筛选/增删关联、人工指定KP补题、真实六态/取消/公共retry、AI草稿先保存再审核再入库；200+failures整批未登记不假称成功。原导入/拆合/整理与旧题读取保留。题库/原卷共用一个安全富内容renderer；富内容权威、显式null转换、受管字节/owner/引用限制与派生指纹同步。

原件管理与四库边界保持，FastAPI为唯一业务后端；模型替身不计算成绩、不识别学生答案或评分点。资料原件/凭证/用户草稿/正式数据根不进入本批测试。依赖锁及迁移SQL/登记散列不变。

## 迁移与完整性

现场已经有 `0001_teaching_baseline`、`0002_teaching_business_tables`、`0003_teaching_paper_tables`、`0004_teaching_assessment_tables`、`0005_teaching_paper_revision_titles`、`0006_teaching_score_tables`、`0007_teaching_assessment_active_score_fk`，无需重复新建。独立逐项与HEAD登记SHA核对7/7；本批没有更改上述迁移或增加未来表。

0006存原件/映射/原格坐标、参测/计分叶快照和修正审计；四表关系约束同施测/同题/同人次，百分整数、四态/范围、完整性封存和confirmed不可变触发器生效。scoreRevision通过不可变施测关系公开固定paperRevisionId。0007恢复active到同施测已确认scoreRevision的DEFERRABLE复合FK，draft/cross-assessment被实际数据库拒绝。source_practice_revision_id仍只能空。

SQLite3.53.1隔离实证。专属启动连接、事务外FK调整、事务内显式copy/drop/rename/index/trigger、读全部foreign_key_check和integrity_check结果、逐行对账、登记commit与finally FK ON；遵循[官方完整重建步骤](https://www.sqlite.org/lang_altertable.html#making_other_kinds_of_table_schema_changes)。独立真实0004已填旧库（2班/3学生/2施测/4人次含补考）升级；copy/rename/trigger/registry在SQL实际执行后抛错，另真实FK孤儿、integrity首行ok后错误与verification错。全部schema/表行/登记完整回滚、FK恢复ON、可重跑；既有确认卷与固定卷触发器保留。新库、B0/B1路径在全量API既有迁移回归中执行。正式数据迁移未执行。

## 实跑门禁与独立验收

| 门禁 | 最新实际结果 | 证据 |
| --- | --- | --- |
| 全量API，r4后端产品与r7相同 | **1523 passed，exit0，207.40s**，仅既有Starlette/AnyIO弃用warning1 | logs/root-api-final-r4.txt，root-api-final-r4.xml |
| 全量check，r7 | **typecheck/lint零警告/1069单测（108文件）/build通过，exit0**；单测81.28s | logs/root-check-final-r7.txt |
| 真实六项浏览器，r7 | **6 passed，exit0，24.6s**，无跳过 | logs/root-browser-final-r7.txt，browser-final-r7/results.json |
| 全量E2E，r7 | **153 passed，exit0，361.327s（6.0m）**，0unexpected/0flaky/0skip | logs/root-e2e-full-r7.txt，browser-full-r7/results.json，FULL-E2E-SUMMARY.json |
| 独立G0/迁移 | **60 passed，exit0，11.99s** | V00-G0-REPORT，logs/v00-g0-final-r3.txt |
| 独立成绩/富内容后端 | **71 passed，exit0，21.36s**（47+24） | V00-SCORES-REPORT，logs/v00-scores-final-r3.txt |
| 独立前端 | **105 passed，exit0，5文件**，原6条反例及3条编辑竞态通过 | V00-FRONTEND-REPORT，logs/v00-frontend-r3-final.log |
| 独立R19任务钟复核 | **2 passed，exit0，1.64s**，50ms与70ms过期边界 | logs/v00-g0-clock-audit.txt |

上述计数分别来自各自一次完整命令，不合并重复测试。独立r3结果后续通过只读差异核查继承；r7唯一新增产品CSS由独立前端看实际失败/修复图片与真实测量复验，不把jsdom当布局验收。完整命令/首败/退出码见EVIDENCE-COMMANDS和三V00报告。

最终两位只读验收者再次逐层枚举全量153项及本批6条真实链，均为首次passed，无失败/重试通过/跳过。前端后验168项零漂移；G0最终文档核查consistent、blockingFindings为空，核对原next-env、端口与六临时目录保留边界，并指出CURRENT_STATUS一处旧“当前运行”已由root修正后独立重读。证据V00-FRONTEND-probes/browser-reviewed-r7.json及logs/v00-g0-final-doc-audit.json；该后验不增加测试计数。

全量API首轮1517pass/6fail保留：Windows父子CLI编码、过期预览旧测试、双lease假时钟同步、R19真实jieba冷启动越过50ms。PYTHONUTF8统一编码；3测试由独立验收者只读审口径后调整，保留原业务TTL/CAS/lease断言，不改产品绕过失败。全部旧首败日志和XML保留。浏览器初轮选择器/名单dataNo、转发磁盘File、省略先保存、build rewrite固化、重放文案、窄屏413px分别定位，最终通过同一完整链。首败索引ROOT-FIRST-FAILURES。

## 真实链、规模与人工视觉

8001真实临时FastAPI/四库，5174正式构建，模型只有受控Provider。固定样本Q1=2、Q2=3、Q3=5：甲(2,2,5)、乙(2,3,空白)、丙缺考、丁(0,3,5)。浏览器实际CSV名单→DOCX富原卷校对/KP确认→固定卷施测→CSV成绩→权威absences/missing承认→HTTP200已提交后丢响应→原包深等重放同submissionId/revisionId且replayed=true→教师甲Q1修正1.5生成v2；v1详情与全矩阵逐项不变。甲v2合计8.5，丁8，乙/丙不展示总分。结果JSON与三视口/原卷图片保全browser-final-r7。

补题真实创建202 queued0→终态attempt1、Provider调用1、候选1、人工保存needs_review→单独审核reviewed→正式入库→KP筛选只读回新题。另替身Provider先明确失败，公开workflow retry收queued1→succeeded2，冻结输入不变，Provider共2调用、候选1。所有业务请求都实际进入FastAPI，不以route mock返回伪成功。

200人次×100叶完整后端矩阵20000格；HTTP准备学生/施测/上传/映射/确认累计3718ms，其中上传处理约605ms、映射约496ms、确认约620ms。浏览器只读矩阵50人次/页（5000格），首屏336ms、翻页339ms，根1440无溢出，100叶内部横向滚动。全量E2E再次执行同规模通过：HTTP全准备3660ms、首屏537ms、翻页569ms，missing=0/resolved=200/confirm HTTP200，根仍1440。原始stdout及scale注释保存在FULL-E2E-SUMMARY.json。时间是本机两次基线，不是性能承诺；超限定位拒绝，无截断，两次结果不相加为测试数。

总控实际IAB人工操作真实历史矩阵，1440×900、1920×1080、390×844逐一看像素，键盘Tab焦点与读回；manual-history三个JPG保全。随后实际看r7新完整链三视口/原卷与题库图片，390下拉框约束正常、0/空白/缺考视觉区分、公式/蓝色PNG/合并表头/共同材料可见。原人工历史样本曾有旧校正值，不将其数值混作新固定样本；新链以API收据和新截图为准。reduced-motion由实际浏览器自动断言，未声称原生IAB支持手工emulateMedia。

## 未执行与交接

未执行真实模型教学质量/正式供应商、Word/WPS、Qdrant、正式库迁移、超200×100规模、跨进程PublicationCoordinator。此批不以构建通过宣称这些质量通过。RAG相关性拒答RAG-REL、真实模型预算R13、书籍双标签跨批R14、embedding加载R18仍保留；R19只关闭测试时钟冷启动耦合，自动janitor扫描时序未测。

固定 `scoreRevisionId`、`paperRevisionId`、全矩阵与 `participantSnapshot` 已就绪，可供后续any_loss_v1读取不可变版本。T70/T80、学情展示、AI教案、正式练习/练习导出及转换外键尚未实施；本批结束停止，后续请求才决定B4。

最终产品168项SHA零漂移、main/HEAD未变、旧B2/B3证据未改；用户next-env原字节已恢复（SHA 0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc）。权威文档后验见POST-ACCEPTANCE-DOCS.json，精确变动清单见DELIVERY-FILES.json，最终核验见FINAL-VERIFICATION.json。

8001/5174/16333均无监听，本批IAB页关闭且viewport reset，未停止用户/未知进程。删除六个有记录的root临时数据目录的命令被工具自动审批拒绝，仅返回blocked by policy；未请求重复批准或改用其他删除方式，六目录保留，绝对路径见RESOURCE-CLEANUP.json。浏览器临时API由fixture正常退出并清理；测试资源释放与临时文件保留分开记录。没有提交、推送、部署或切换分支。
