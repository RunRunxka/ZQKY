# B6 集成／导出原件独立审查 v2

责任人：`g3_boundary_review`。日期：2026-10-04。状态：**限定技术原件审查通过，STOP**；真人教学质量、真实模型和原生 Word/WPS 排版继续待验。本卡只读现有稳定原件，未执行业务 QA、HTTP 请求、服务启停、产品导入、产品修改或 Git 操作；只新增本 lane 报告。

完整机器记录：[integration-export-independent-v2.json](integration-export-independent-v2.json)，SHA `e519fba0865a5c0de84a53a32b6d2fb4d6d03267eab8554353e6572ae57152dd`。只读原件解析 PID `17852`，`514.490ms`；521 份固定输入逐文件 SHA 前后零漂移，含 API 源393份和既有导出消费者源码。这里的解析不是再次运行产品测试。

## 候选和范围

沿用 B6-base-v1 SHA `c04c01bdd0dbedf85e7f0aba81d4ed92c8cad50ec5fea7d232ef896081e19ca1`，实际原运行构建 `q84e_pxQoZ2_nwnws9QiI`。集成 endpoint-r4 的941份源在原运行前后均精确等于该 base；393份 API 源及 `services/export.ts`、`styles/print.css` 在本次只读审查仍同源。后续 B6-R01 SourcePanel 新候选及新构建由 ROOT 单独绑定与验收，本报告不冒称在新构建上重跑。

导出作者已 STOP 的 RESULT-v1.md/json SHA 分别为 `14a948991535e8811a256601472e8a400751c3ae6d73d5b4a5979870adcf3735` / `445b925723b1965df5b455019780b2c6005fb2cbfe23625722d65a4ac4e4b3b7`，原104项 evidenceInventory 逐项 SHA 无变化。

## 集成固定事实

原 endpoint-r4 收据：runner PID `24552`，launcher PID `10948`，实际 workload PID `23952`；命令时长 `3179.899ms`、业务段 `1983.997ms`、exit0。隔离环境在标准 `app.main` 导入之前建立，`env=test`、`PYTHONUTF8=1`、新 OS TEMP、`credentials_file=None`；无 TCP 监听。使用真实标准 `create_app` / TestClient 和公开业务端点，仅 Provider.complete 的 HTTP transport 沿用原隔离替身，生成文本是手写技术哨兵，不能据此判教学质量通过。

独立读取实际 endpoint-calls、chain、手写 oracle、完整前后 JSON／SQL，而非只采信作者 PASS：

- 单班、明确单 KP 的固定成绩报告进入后台教案；五整字段应用后完整11字段等于手写预期，教师六字段逐值保持，四环节预算11＋11＋11＋10＝43分钟。
- 正式 reviewed 练习为独立业务对象，不将教案 exercises 字符串当作题库或正式练习。其固定 revision 转成新 paper／assessment，再下载实际成绩模板、填入1.25分并通过公开导入／确认／分析端点产生新 score／run；新报告引用新 paper／score，且回指原 practiceRevisionId／practiceItemId。
- 实际新证据为 recorded125/125；单班单 KP 分母1、needs0、fullCredit1、ratio0。旧报告 needs1 保留；历史 className 仍 null＋“该成绩未记录班名”，没有从后来班名补事实。
- 题库新 revision、班名、名单显示名和 KP 归档后，17份完整旧／新固定业务 JSON 前后深等。SQL以全部列、原始 JSON 字符串和行多重集合核对56个固定历史表；120条旧行无删改，after123条只增加1条 question_revision 和2条 question_knowledge_links。当前可变实体本来被主动修改，不将该事实误写为整库所有可变行未变。
- 归档后明确新生成请求实际409 / KNOWLEDGE_ARCHIVED，Provider调用1→1，增量0；原生成 submission 重放与原 receipt 全字段一致（replayed=true），原 apply 同样完整重放，无新模型调用。

本卡确认该端点链和固定事实的技术记录成立，不判实际浏览器的新候选 UI 或真实模型语义质量。endpoint-r1～r3历史首败未拼入本轮结果。

## 四例导出原件

原浏览器完整 r3：PID `25336`，`5610.820ms`，四例单轮、exit0、0retry、trace on；离线原结构／PDF／Poppler收据 PID `11044`，`1922.684ms`、exit0。这里只取 r3 四例完整单轮；r1/r2原件保留，未拼绿。

对 short／long／multi／symbols 四例，独立读取 create/save 的原 `{status,payload}`、当前v2、初始v1、完整历史和 context；导出前后全部深等，browser PATCH0，公开下载文件名含相同固定v2来源。每份 DOCX 实际 ZIP全成员 CRC、全部 XML／rels 解析、内部关系目标、11字段、每个 process设计及secondary完整匹配；字体／styles和表、行、单元格、section属性继承现有模板，每例11个gridSpan、4个vMerge，未出现exact固定行高。实际原模板与公开派生模板 SHA 均核对；不设计另一套导出。

四份实际 PDF 另用原文件表格单元格重建全部五正文域和所有 process设计／secondary，去掉排版换行空白后逐字一致；环节次序一致，13页逐页含完整当前 revision ID、后台固定v2、A4尺寸。DOCX来源由公开文件名与manifest映射；现有 Word正文未新增来源标签，不声称已内嵌标签。

| 样本 | 当前v2 revision | 页数 | 独立结论 |
| --- | --- | --- | --- |
| short | eb059afddca342dc8abcb528b2c9f197 | 1 | 固定正文／来源、DOCX结构、实际PDF通过 |
| long | 5a21e390d6934004a66eb067483fd0bf | 8 | 完整长正文与两长secondary通过，保留窄栏续页表现 |
| multi | 6f4b5b45c19b4523b250f539b57042d4 | 2 | 六环节与六secondary次序／全文通过 |
| symbols | 6af492ff2bf04b72adfb6b1afa7783cf | 2 | 中文、引号、XML特殊字符和数学字符完整 |

## 实际逐页观看

以下13页均由本独立审查者实际调用 `tools.view_image` 查看原 Poppler PNG，不以存在路径或作者清单代替观看。每页 PNG SHA、实际PDF文本SHA均记录在 JSON。

| 页 | 实际观察 |
| --- | --- |
| short1 | 完整基础资料／课型、五正文域、两环节和二次备课、核查区；边框和文字无叠压，页脚在页内 |
| long1 | 基础字段后“长正文开始”进入教学设计长段；表格靠近页底但没有盖住来源页脚 |
| long2 | 接上页与教学设计续段正常；表格结束后余白，来源／2/8页码保留 |
| long3 | 连续长教学设计到“长正文结束”；末句未丢失，无截断 |
| long4 | 导入长设计到“长环节结束”；二次甲起段沿右窄栏续排，未越出表格 |
| long5 | 导入（续），主设计已经结束所以中栏为空；右栏二次甲连续，属于现有窄栏分页表现 |
| long6 | 二次甲继续到“长二次甲结束”；主栏余白保留，没有右栏丢尾 |
| long7 | 检测短设计和“长二次乙开始”；右窄栏继续，页底正文未碰页脚 |
| long8 | 二次乙到结尾，课堂练习、教学反思和核查区完整，来源／8/8页码保留 |
| multi1 | 导入、自主尝试、同伴比较前三环节与三二次记录对应；边框与正文无叠压 |
| multi2 | 方法梳理、课堂检测、反思迁移后三环节与各secondary完整，末两正文域和核查区保留 |
| symbols1 | 中文《》【】、引号、<>&、斜线／反斜线、α²／≤／≥／±／×／÷可见，三个环节／secondary无乱码 |
| symbols2 | 练习和反思完整特殊串、核查区、固定来源完整；无截断或叠压 |

长secondary窄栏产生8页及设计栏空白，是已保留版式观察；来源页脚较浅但在图中可见，原PDF提取含完整ID。没有纸张实印可读性或原生打印窗口验收。

## 保留的首次读取失败和待验边界

首版只读解析结果 [integration-export-independent-v1.json](integration-export-independent-v1.json) SHA `19d52d37dd38baa117551a57918ef0aa5a87aa0d12b44a452d821d8331b1a531` 原样保留。PID19480／174.272ms时，集成事实已核对，导出段因读取层误把 `{status,payload}` 外壳当裸业务 JSON 停止；这不是产品缺陷或新业务测试失败。v2从原 payload 核对，dataSHA尊重原 JSON 字段顺序，521份原输入与v1一致，未改原件／产品／业务断言。

Word/WPS/LibreOffice页面排版 `not_run`：作者bundled-only实测缺少soffice，本卡未借用用户桌面Office，未将XML结构通过写成原生DOCX页面通过。真实模型和教师评分待输入／待评，`RAG-REL OPEN`；合法切片与替身完成不能证明教材语义相关性或真实拒答质量。

质量lane原 RESULT-v1保持；调用计数应同时引用 [RESULT-CORRIGENDUM-v1.md](RESULT-CORRIGENDUM-v1.md)：15例各1次、合计15次Provider transport fixture调用，真实模型／外网0。B6整阶段、B7及全站验收没有因此关闭。ROOT继续负责新候选 UI 和适用总门禁。

**独立审查 STOP：仅新增本报告及JSON，不改变其他 lane／权威文档／产品。**
