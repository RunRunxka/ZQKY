# B6 导出与教师试用材料结果 v1

更新：2026-10-04T14:22:24.446502+08:00。责任人 g3_v00；导出作者 STOP。完整四例本轮通过，实际 PDF 共13页且全部逐页查看；Word/WPS页面排版仍 not_run。没有产品或模板改动，不将教学内容质量列为通过。

## 身份和运行

产品 base SHA `c04c01bdd0dbedf85e7f0aba81d4ed92c8cad50ec5fea7d232ef896081e19ca1`；实际运行构建 `q84e_pxQoZ2_nwnws9QiI`，对应 G3 candidate SHA `1ef1756283abc1fda103c2263c3a49034c5d3ffec4f06669c0735488134efcbb`。此为 q84e 上新实际导出，后续 SourcePanel 修复的新 build 只能由 ROOT 另列同源绑定，不能把本结果冒称新 build 新跑。

ROOT 所有 API4056/Next21544；隔离数据根 `C:\Users\96022\AppData\Local\Temp\zqky-b5-runtime-b6-shared-r1-1u2lhqlp\data`，seed SHA `77697783a8f8790416f91a509cc2666529f94bc7377024a2e29fc72bc728cfcf`。所有 browser/request context 已闭合；本 lane 无启停服务，不触用户 WPS/正式草稿/凭证，TEMP 保留。原五分组中 source/QA/contract/build 守卫均0差异。

| 命令收据 | PID | 时长 ms | 结果 |
| --- | --- | --- | --- |
| [完整四例实际浏览器](browser-r3-command.json) | 25336 | 5610.820 | 4/4 actualpass，trace on，0retry |
| [离线结构/PDF/Poppler](offline-r1-command.json) | 11044 | 1922.684 | 4/4 actualpass，13全页PNG |

DOCX marker PID25060/60.349ms、PDF marker PID11096/67.909ms 均首次 r1 exit0，每格式只执行一次；r2/r3仅引用原收据。marker本身不是导出通过证据。

## 四例完整结果

| 样本 | 当前固定版本 | 实际PDF页数 | DOCX结构 | 实际PDF全文/视觉 | Word/WPS排版 |
| --- | --- | --- | --- | --- | --- |
| short | 2 · eb059afddca342dc8abcb528b2c9f197 | 1 | actualpass | actualpass | not_run |
| long | 2 · 5a21e390d6934004a66eb067483fd0bf | 8 | actualpass | actualpass | not_run |
| multi | 2 · 6f4b5b45c19b4523b250f539b57042d4 | 2 | actualpass | actualpass | not_run |
| symbols | 2 · 6af492ff2bf04b72adfb6b1afa7783cf | 2 | actualpass | actualpass | not_run |

每例 `samples-r3/<case>/manifest.json` 保留完整11字段、当前/初始/所有历史完整业务 JSON、context、固定source label/data/source/file/template SHA、公开下载名称、打印快照和trace。导出前后深等、浏览器 PATCH0。每例 `offline-structure-and-pdf.json` 实际解析全部 ZIP成员CRC/XML/relations、整字段、每个process/secondary、字体/表格合并及继承页设置；PDF实际表格重建所有正文和process/secondary，页页核完整当前revision ID。

沿用原模板 SHA `f51bae6b1cae0cce1072650a7ffdef07fb12708c5502eb36b70910c4276fa164` 与原副本同值；实际公开派生模板 SHA `62104c96436f4d6d30498dc5a040674a10986dbf8327252324de73ee9a050588`。字体继承宋体/Times New Roman；每例11个gridSpan、4个vMerge，表/单元格/行/section属性与派生模板一致，长行无exact固定高度。此为真实结构结果，不声称WPS分页。

[逐页清单](PAGE-REVIEW-v1.md) 和 [实际视觉签收](VISUAL-REVIEW-v1.json) 覆盖全部13PDF PNG与4冻结预览；没有仅检查路径存在。长secondary窄栏产生8页、主栏部分空白的现有布局保留。Word正文来源仍按公开文件名与manifest映射，PDF每页有源标签；本批没有插入另一套来源/导出系统。

## 首败与QA调整

- r1 `Paper retains teachingDesign` 失败，原因是合法分页标题/页脚打断 whole-innerText 连续匹配；完整1832字符在实际DOM中保留。原源/原trace（SHA a9c10a…）/日志/收据保留于 `qa-first-source-r1`，修订说明 [QA pagination delta](QA-PAGINATION-DELTA-r2.json)。
- r2 第四创建POST实际422，82 UTF16 的otherTypeText超过既有80上限；首轮原响应正文没有记录，原因由冻结fixture和现有契约推断，未冒称读到错误原包。原源/inputs/log/receipt保留于 `qa-first-source-r2`；[QA boundary delta](QA-BOUNDARY-DELTA-r3.json) 仅该短字段合法化，正文/process完整特殊串不变，新增错误response保存与按轮trace名。
- 本结论只取新r3四例完整单轮，不与r1短例、r2三例拼绿。所有原断言目标 retained，全文校验升级为实际域与二次栏重建，没有去掉截断验证。

## 未执行及教师材料

bundled-only `render_docx.py` resolver实测失败：`LibreOffice soffice.exe was not found on PATH`。Word/WPS排版 not_run；禁止借用用户桌面Office，未动其PID。原生打印窗口/物理纸张、真实Provider教学质量、教师评分、正式迁移/Qdrant/压力及本lane重复工程全量未执行，原因逐项见 [完整结果JSON](RESULT-v1.json)。

[教师试用说明](TEACHER-TRIAL-v1.md) 已覆盖名单/原卷/小题分→固定单班KP报告→五整字段与教师六字段→reviewed练习/两版导出→新施测/新分数/新报告，四态、重叠与零分母、unknown原包、CAS人工对照、本地/后台身份和离线四库资产备份。链接质量 lane 的真实feedback入口，不自评教师质量。

OBS-LP-MODE-LABEL、CV01～03/R14/RAG-REL保持，后台模式以固定身份和保存ACK判定。此卡交付是导出技术验收和试用准备，live_run待输入、teacher_review_pending；不代表整个B6/B7或全站视觉/教学质量已完成。

全部证据路径、文件SHA、markers、首败和未执行边界见 RESULT-v1.json 的静态交付inventory；后续 `review-source`/`review-quality` 是另卡新证据，不能回写本轮运行事实。
