# G0 与 B3 审查关闭矩阵

2026-10-02。总控 `/root`；独立验收者没有参与实现。旧 B2/B3 报告、冻结件及诊断探针保持原文。正确行为断言与首败路径见三份 V00 报告；诊断脚本 exit0 不作为修复通过。

| 原审查 | 修复后的正确行为 | 独立证据/状态 |
| --- | --- | --- |
| B2-RV01 | 公共注册执行器 retry 后真实终态；queued N→claim N+1；重复点击单次执行；调度故障可明确重试；重启不自动模型重放；N+2拒绝 | V00-G0 真实注册引擎、V00-FRONTEND 三hook观察，pass |
| B2-RV02 | 结构化补录/排除必须真实内容或依据；空计分题/必要材料缺失不能确认；原卷不要求答案解析 | V00-G0 空题确认零写、补录固定修订，pass |
| B2-RV03 | 无题号/未归属段落、原始OMML、图片/合并表格完整可读，受管资产限制当前引用/owner | V00-G0 自建DOCX四类块及PNG，pass |
| B2-RV04 | 等名额后临调用核真实模型指纹，漂移或取消Provider0、候选0 | V00-G0 generation/knowledge/paper，pass |
| B2-RV05 | 中间批及失败checkpoint用原lease同事务CAS；cancel/expired/wrong token/旧attempt/终态均零写 | V00-G0身份矩阵与实际整理交错，pass；N02过期心跳复活已关闭 |
| B2-RV06 | 同一PublicationCoordinator跨有效关联复核到域短事务；IO预检锁外，历史关联可读 | V00-G0 paper/question确认与正式PATCH归档竞态，pass；N01锁空隙已关闭 |
| B2-RV07 | 改学科校验完整显式/继承集合；跨学科拒绝或显式清空；历史旧修订不变 | V00-G0与V00-SCORES，pass |
| B2-RV08 | 改日期复核原人次归属；明确重确认原attempt依据后可改；姓名/学号/旧归属不变 | V00-G0 真实HTTP日期交错，pass |
| B2-RV09/10 | StrictMode单次终态回调；cancel/retry的迟到200/409在reset/switch/unmount后零副作用 | V00-FRONTEND 三hook自建反例，pass；F06知识点首次queued0已关闭 |
| B2-RV11 | 固定修订与reader读各自标题；旧回填明示可变标题来源；已填旧库升级失败完整回滚 | V00-G0真实0004旧库8故障场景，pass |
| public publish rollback | question/knowledge/teaching三域AppError/内部异常；回滚后只用最初lease收敛failed，cancel优先/newholder零覆盖；资源释放 | V00-G0 18实际域内sentinel故障，pass |
| B3-R01 | 首次补题queued0正确观察attempt1终态/候选，失败可见，公共retry达到attempt2 | V00-FRONTEND及V00-G0，pass |
| B3-R02 | 缺考/免考扩展到有效全矩阵；承认范围由服务端生成并绑定previewVersion，无伪missing | V00-SCORES 5×3矩阵、V00-FRONTEND实际组件，pass |
| B3-R03 | C/c物理列身份归一；计分/身份/总分/出勤不能占同列 | V00-SCORES，pass |
| B3-R04 | 同sheet重设header/identity重建行集合，保留仍适用校正与真坐标 | V00-SCORES，pass |
| B3-R05 | 未识别身份上传可进入人工映射，不500、不按姓名自动合并或猜补考 | V00-SCORES，pass |
| B3-R06 | UTF8sig/UTF8/GB18030严格解码，无replacement损坏原证据 | V00-SCORES，pass |
| B3-R07 | recorded空白/缺考/免考修正定位422；Decimal精确百分整数，不舍入/溢出 | V00-SCORES，pass；S01极端Decimal已关闭 |
| B3-R08 | 创建/修正/原卷/名单/补考卸载与对象切换后迟到响应零选择/父回调 | V00-FRONTEND，pass |
| B3-R09 | 整理失败checkpoint捕获原attempt/token，同事务CAS不覆盖新轮 | V00-G0真实Provider失败与新holder交错，pass |
| B3-R10 | 名额等待取消后不调用模型、不产候选且释放资源 | V00-G0，pass |

独立新增成绩边界 S02：过期PATCH与预计算后施测变动均409、批次行/锁零修改；S03：两个物理行映射同一人次必须双方定位阻断，不静默丢第二行。二者原反例均通过。

独立新增前端边界 F01–F05：成绩确认/施测创建/成绩修正/题库确认结果未知时冻结完整原请求及submissionId；读回新版本不换包，编辑控件锁定，重放旧原包；题库不假称零入库。已知200+failures整批未登记允许改稿后复用原submissionId。五条原反例及DraftEditor立即编辑/effect交错3条均通过。

一次独立实跑：G0 **60 passed**（11.99s）、成绩/富内容 **71 passed**（21.36s）、前端 **105 passed**（5文件）。另独立R19时钟探针 **2 passed**（1.64s），保留50ms TTL和真实jieba冷初始化，精确50ms及原70ms过期；不并入先前60计数。终轮r3前后165散列0漂移；后续r4仅三Python测试、r5仅两浏览器spec、r6仅成绩browser断言/注释、r7新增成绩模块CSS宽度修复与测量spec（168项），各版本原件保留。r3→r7后端产品/迁移与前端JS均未变；r7 CSS另由独立前端实际像素与浏览器测量核验，不隐去产品差异。

迁移0001–0007及登记散列未改；已有0006成绩全矩阵与0007 active同施测DEFERRABLE复合外键保持。专属启动连接事务外调整FK；copy→drop→rename→重建trigger/index→读全部FK/integrity→逐行对账→登记→commit；全部故障回滚后FK ON、可重跑。confirmed/完整矩阵/固定卷触发器仍生效；source_practice_revision_id仍只能空。

总控全量API/check/build/真实浏览器/视觉结果另见最终REPORT，不用此矩阵替代整体门禁。真实供应商质量、Word/WPS、Qdrant和正式库迁移未执行；B4/T70/T80未实施。
