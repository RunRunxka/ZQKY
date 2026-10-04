# B4-F-BROWSER v1 — r6 real-second 首败

真实第二轮 **单次1例失败，exit1/8697ms，PID23668已退出**。原 `real-browser.spec.ts:168` 在点击打开候选后立即同步读 `page.url()`，import路径匹配null。原首败 [command](browser-real-second-command.json)/[results](browser-results-real-second.json)、stdout3737字节/stderr328字节、失败PNG/error-context与完整trace均保留，没有重试或与第一轮合并计数。

主要首败是 **QA缺少异步路由完成同步**：trace候选打开click后，目标 `/question-bank/imports/29696d7d83354ce4b04ad4de3d2b3d02?returnPracticeSetId=e28bc59f073f4f4e93d3181780c722ab` 的RSC导航GET在mono7420.118开始并200；同步null断言mono7424.611已失败，最终error-context与后续API请求Referer已在该正确审阅路径。生成组件的既有onOpenImport→router.push没有同步完成保证。

**另有未销掉的HTTP500事实**：其后mono7478.802、UTC `2026-10-02T13:34:04.126Z` 的 `/api/v1/question-imports/<id>` GET 返回500，原body为21字节 `Internal Server Error`，error-context显示SERVICE_UNAVAILABLE。请求发生首断言失败后、context关闭完成前；不能先认定是teardown/后端停止，更不能声称无业务错误。完整真实snapshot/body见 [late-GET500.json](browser-real-second-late-GET500.json)，已交CTRL核相同后端日志，本Agent未发新HTTP重试。

本轮已真实执行并通过前段：初种子27来源块及真实GET图片200/74字节/SHA/media核对；history固定链接→同学生人次显式互斥→真实报告字面事实；12条证据/12个实际loaded图片/12公式/12表格；初始富报告1440/1920/390布局与PNG均产出且实际view。文档宽度分别等于视口、交互控件无横溢，390标签区域实际横向滚动；查看画面图文正常、长ID换行，截图记录当前内层滚动位置，不当成其它尚未经过阶段的视觉通过。Tab可见焦点solid2px；实际正常150ms running/reduced1e-05s无running，实际RGB改变3371/3367像素。

备注已真实追加、练习已创建、正式题真缺口1/2显示且无自动补题；ControlledProvider真实生成1题成功，实际请求只含正式KP/题型/难度/约束，4个合成学生的姓名/学号/studentId及5个participantId全不包含。两次trace读取重复同模型request资源，不计成2次模型调用。原始实际请求与核对见 [completed-evidence.json](browser-real-second-completed-evidence.json)。

尚未执行人工编辑/审核/确认/查看入库/返回练习、练习晚响应/未知原包审核、双DOCX/真实名单模板下载及ZIP检查、转换/T60新分数/T70新报告/完整逐叶映射、旧版本最终相等与四库oracle，均不计通过。整体B4未关闭。

完整r6前审exit0/206ms、后审exit0/207ms，877产品/36QA/5契约0漂移，next-env一致。构建仍`v3NL9Nd4Zve30UcCepg0R`，产品与r5成功check/build身份绑定由CTRL独立记录。216条trace ZIP全CRC通过，SHA `01531f1e4865d1384c726a3e3a244bd071f8348a8c2bac7f827e16b32e8c0c70`；Closecontext `pw:api@233` complete/end7821.091/noerror，AfterHooks/context/worker-browser fixture均结束。仅库正常收尾自身浏览器，未启动/停止服务，`jjraqnst`临时根保留，旧六目录未触碰。

首败后CTRL单独授权QA-R08只加一行精确导航wait，所有原115matcher及原路径/数字/timeout/API/PII断言全文保留，原r6-byte副本保留；准备未执行，另冻后新样本才能复验。见 [QA-R08-PREP.md](QA-R08-PREP.md)。

