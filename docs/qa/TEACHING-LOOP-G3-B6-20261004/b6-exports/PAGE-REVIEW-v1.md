# B6 四例实际 PDF 逐页核对与 Word/WPS 待验清单

记录日期：2026-10-04。候选产品 B6-base-v1，构建 `q84e_pxQoZ2_nwnws9QiI`。本表只签收 `samples-r3` 的完整四例；r1/r2 首败不改，前三例历史成功不拼入本轮。

本轮通过现有公开 Word 导出、现有冻结打印 `printSnapshot` 和现有 print CSS 生成真实文件。`window.print` 仅捕捉产品冻结快照，随后 Chromium `page.pdf` 保存真实 PDF；没有声称操控原生打印窗口。PDF 共 13 页，由 bundled Poppler 全页转 PNG，以下每页均实际调用 `view_image` 查看。另实际查看四张冻结打印预览截图；长例整张预览因自动缩小仅作整体次序检查，文字与截断判断以 8 张独立 PDF 页图及实际 PDF 表格完整重建为准。

| 样本/页 | 实际 PNG | 实际阅读观察 | 结论 |
| --- | --- | --- | --- |
| 短课 1/1 | [页1](samples-r3/short/pdf-pages/page-1.png) | 课题、课时、课型、五正文域及两环节/二次备课完整；核查区域与当前固定 v2 页脚在页内 | actualpass |
| 长文 1/8 | [页1](samples-r3/long/pdf-pages/page-1.png) | 基础资料与目标/重难点后进入“长正文开始”；教学设计跨页，表格未压住页脚 | actualpass |
| 长文 2/8 | [页2](samples-r3/long/pdf-pages/page-2.png) | 接上页标题、教学设计续段、固定来源及页码完整；段末正常续排 | actualpass |
| 长文 3/8 | [页3](samples-r3/long/pdf-pages/page-3.png) | 教学设计续段到“长正文结束”；页内余白，没有文字被遮住 | actualpass |
| 长文 4/8 | [页4](samples-r3/long/pdf-pages/page-4.png) | 导入完整长设计到“长环节结束”；右栏从“长二次甲开始”继续，未越出表格 | actualpass |
| 长文 5/8 | [页5](samples-r3/long/pdf-pages/page-5.png) | “导入（续）”与二次甲续文；设计已结束所以中栏空白，右栏正常续排 | actualpass，保留窄栏分页观察 |
| 长文 6/8 | [页6](samples-r3/long/pdf-pages/page-6.png) | 二次甲续到“长二次甲结束”；无丢尾、重叠或底部截断 | actualpass |
| 长文 7/8 | [页7](samples-r3/long/pdf-pages/page-7.png) | 检测活动与“长二次乙开始”；较长右栏正常跨页 | actualpass |
| 长文 8/8 | [页8](samples-r3/long/pdf-pages/page-8.png) | 二次乙结束、课堂练习及反思、核查区全部在页内；当前固定来源与8/8存在 | actualpass |
| 六环节 1/2 | [页1](samples-r3/multi/pdf-pages/page-1.png) | 导入/自主尝试/同伴比较三环节及各自二次记录，次序正确 | actualpass |
| 六环节 2/2 | [页2](samples-r3/multi/pdf-pages/page-2.png) | 方法梳理/课堂检测/反思迁移、三二次记录及最终字段完整 | actualpass |
| 特殊字符 1/2 | [页1](samples-r3/symbols/pdf-pages/page-1.png) | 中文括号引号、`<>&`、斜线/反斜线、α²/≤/≥/±/×/÷、三环节与各二次记录均可见，未变成 XML 标签或乱码 | actualpass |
| 特殊字符 2/2 | [页2](samples-r3/symbols/pdf-pages/page-2.png) | 课堂练习和反思完整特殊字符串、核查区与当前固定来源完整 | actualpass |

PDF 实际表格提取另外重建每个完整正文域、全部环节设计与全部 secondary，并逐页核对完整当前 revision ID、后台固定 v2 与 A4 页尺寸。没有仅用“长正文开始/结束”代替全文校验。完整提取和 PNG SHA 见每例 `offline-structure-and-pdf.json`，真实调用 PID/持续时间见 [offline 收据](offline-r1-command.json)。

保留现有版式观察：二次备课窄栏的长文会产生多页续排和设计栏空白；浅色固定来源页脚在实际图中可见，全文提取包含完整 ID，但未开展纸张实印可读性测试。原 Word 页面约 209.9×302.7mm，PDF 为 A4，不能要求两种格式页数相同。

## Word/WPS 人工核对待办

状态 `not_run`：bundled-only `render_docx.py` 依赖检查实际得到 `LibreOffice soffice.exe was not found on PATH`；没有 bundled LibreOffice 可调用，本卡禁止借用用户桌面 WPS/LibreOffice。DOCX 的 ZIP/XML/字体/合并/可增长行高通过，不等于 Word/WPS 页面排版通过。

教师使用下列可打开原样本另存副本核对；不要覆盖证据文件。页数以实际 Word/WPS 打开后为准，本表不虚构其页码。

| DOCX | Word/WPS 每一实际页必须核对 | 页码/应用版本/意见（教师填） |
| --- | --- | --- |
| [短课](samples-r3/short/short.docx) | 基础资料、全部正文、两设计与两 secondary、课型复选框、合并单元格、核查区；确认下载名称与 manifest 的当前 v2 来源映射 | 待填 |
| [长正文与长二次](samples-r3/long/long.docx) | 教学设计完整连续、长环节和长 secondary 所有续页无截断；行高可增长、跨页表格边框/文字不重叠，首尾及中间逐段对照全文 | 待填 |
| [六环节](samples-r3/multi/multi.docx) | 第一表前两环节、第二表其余四环节、每个 secondary 携带对应环节名；完整次序与末段 | 待填 |
| [中文特殊字符](samples-r3/symbols/symbols.docx) | 中文/引号/数学符号与 `<>&` 字面保留，全部五正文域及三设计/secondary；无转义残留或缺字 | 待填 |

Word 来源当前通过公开下载文件名及完整 manifest 映射；现有 Word 正文没有新增源标签，本批未修改模板插入来源。PDF 来源在每页页脚。教师核对时同时保留下载名称、document/revision ID 和 manifest，不能只看被本包整理为 `short.docx` 等简称的文件名。
