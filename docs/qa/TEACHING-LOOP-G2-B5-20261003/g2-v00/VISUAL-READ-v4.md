# G2-V00 独立原图审阅 v4

2026-10-03，北京时间。状态 ACTUAL_SCREENSHOT_REVIEW_COMPLETE_WITH_STATED_LIMITS。按正式卡逐张 tools.view_image(detail=original) 实际读取14/14原PNG，包括相同SHA的重复图；不是只判JSON。前后SHA全部相同，完整值与每张实际观察在VISUAL-READ-v4.json。未改图片、产品/QA、旧报告或权威文档，未跑浏览器/API/单测/服务/Git。

390×844、1024×768、1440×900的三个弹窗标题、正文和四按钮全部位于画面内，标签完整，没有可见裁切或重叠；390为2×2按钮，1024/1440为3+1。三个取消图无弹窗/遮罩，当前练习仍选中，发起切换的第二练习按钮有清楚焦点外圈。图7直接显示计分叶输入3、已发送草稿成功且后续编辑未保存notice、服务端审阅满分2；图8直接显示列表备注A、textarea新B与保留notice。

前6张恢复图和三个cancel图没有拍到编辑字段，不能用静图断言本地5/1.75、题号、题量或脏字段恢复。图2/3/4相同SHA，图5/6相同SHA，已分别读取；相同画面不能证明不同路由/pageclose/Back生命周期，这些依赖原动态场景与trace。

| 图 | 实际可见观察 | 明确限度 |
| --- | --- | --- |
| [1 · cancel-and-discard](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/g2-v00/run-browser-r4-first/attachments/case-01-attachment-01.png>) | 1440×900页面上半部：当前闭环练习行蓝色选中，来源报告链条、v1已审核只读/v2草稿历史及固定练习概要清楚；概要显示后端总分1.25分。可见区无弹窗或文字重叠。 | 只拍到选题与计分结构标题前后，编辑满分、节点、题量在画面外；不能静图证明取消保留或明确放弃的动作与值。 |
| [2 · history-route-refresh-recovery](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/g2-v00/run-browser-r4-first/attachments/case-03-attachment-02.png>) | 1440×900页面上半部回到当前闭环练习，链条/固定历史/概要清楚，后端总分1.50分；可见区正常。 | 未显示恢复后的输入5或节点/约束；路由、reload、恢复动作需已过功能用例与trace。 |
| [3 · closed-page-recovery](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/g2-v00/run-browser-r4-first/attachments/case-03-attachment-03.png>) | 实际读取此原图；显示当前闭环练习、固定历史、后端总分1.50分，版面与上一张一致。 | 此图与上一张SHA相同；不能从相同静态画面推断page close/newPage生命周期或输入恢复。 |
| [4 · native-back-keep-restored](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/g2-v00/run-browser-r4-first/attachments/case-04-attachment-01.png>) | 实际读取native-back-keep图；当前闭环练习仍选中，固定历史与后端总分1.50分显示完整，可见区无弹窗。 | 与history/reopened图SHA相同；输入1.75/1(Back)在画面外，不能用静图验证Back或保留稿恢复。 |
| [5 · native-back-save-restored](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/g2-v00/run-browser-r4-first/attachments/case-05-attachment-02.png>) | 当前闭环练习、来源链条与固定修订历史仍完整，概要后端总分显示1.75分，未见可见区覆盖或混入第二练习概要。 | 可见1.75是后端概要；编辑字段未进入画面，Back/save顺序与恢复题号仍依赖功能证据。 |
| [6 · rapid-destinations-original-action-only](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/g2-v00/run-browser-r4-first/attachments/case-06-attachment-01.png>) | 实际读取rapid-destinations图；当前闭环练习选中，无第二练习概要或弹窗，后端总分1.75分。 | 与native-save图SHA相同；截图不证明两次trusted click、一次leave action或本地5仍保留。 |
| [7 · post-replay-new-score](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/g2-v00/run-browser-r4-first/attachments/case-07-attachment-02.png>) | 滚动到结构编辑区域：计分叶满分输入为3，题号1(Back)可读；成功notice说明发送草稿已保存、后续编辑仍保留未保存；保存按钮蓝色、审核按钮浅色禁用外观。下方服务端完整题目审阅显示该计分叶满分2分。 | 整题满分输入在画面上方未包含；静图显示本地3/服务端2及notice状态，不能单独证明真实200、abort、同包或收据次数。 |
| [8 · post-replay-new-note](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/g2-v00/run-browser-r4-first/attachments/case-08-attachment-02.png>) | 教师备注页当前列表显示原初始备注与已发送备注A；textarea保留请求后新备注B；notice说明原备注已追加、之后新备注仍保留尚未追加，追加按钮可见。可见表单无遮挡。 | 只能说明本页可见A/B状态；一次追加/数据库A1 B0/POST201与原包重放由HTTP或DB证据支持。 |
| [9 · dialog](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/visual-inspection-r4/visual-case-01-attachment-01.png>) | 390×844弹窗完整位于窄视口内；标题、未保存提示、恢复稿/固定历史只读/明确放弃说明完整换行，四个操作按钮按2×2显示，标签均完整且不重叠；背景有遮罩，移动页头完整。 | 静图不能证明focus trap、滚动锁、按钮动作与脏字段值；背景正文/历史部分在视口外。 |
| [10 · keyboard-cancel-preserves-input](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/visual-inspection-r4/visual-case-01-attachment-02.png>) | 390×844取消后画面无弹窗/遮罩；当前闭环练习仍蓝色选中，第二练习按钮出现清楚的蓝色焦点外圈。列表和链条长ID换行，可见布局未被横向撑出。 | 编辑字段在画面外；不能从图片确认Escape键、焦点返回过程或输入未丢失，仅观察取消后的可见状态。 |
| [11 · dialog](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/visual-inspection-r4/visual-case-02-attachment-01.png>) | 1024×768弹窗完整居中，标题/说明/四按钮均在视口内；前三操作同一行、明确放弃位于下一行，文字自然换行且没有裁掉。背景遮罩清楚，按钮不重叠。 | 静图不证明键盘遍历/焦点锁与交互；有正常垂直页面内容在下方视口外。 |
| [12 · keyboard-cancel-preserves-input](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/visual-inspection-r4/visual-case-02-attachment-02.png>) | 1024×768取消后无弹窗/遮罩；当前闭环练习蓝色选中，第二练习按钮蓝色焦点外圈完整。来源链条换行显示，固定历史可见，无可见重叠。 | 不能静图确认按键路径或dirty值；完整编辑区在画面外。 |
| [13 · dialog](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/visual-inspection-r4/visual-case-03-attachment-01.png>) | 1440×900弹窗完整居中，宽度留有充足边距；标题、说明和3+1排列的四操作全部可读，未见按钮/文本超边界或互相遮挡；遮罩与背景层次清楚。 | 截图不替代focus trap、点击/离开处理及全部页面视觉审查。 |
| [14 · keyboard-cancel-preserves-input](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/visual-inspection-r4/visual-case-03-attachment-02.png>) | 1440×900取消后无弹窗/遮罩；当前闭环练习蓝色选中、第二练习按钮焦点外圈清楚；链条/固定历史/概要显示正常，概要后端总分2分。 | 编辑字段未包含；不能由此静图证明键盘Escape或未保存值5恢复，需动态用例/trace。 |

静图不证明点击/按键/Back、hydration、focus trap、丢响应或收据次数，不代表全部页面/全部状态视觉质量通过。root只读TCP/四库/收据及11traceCRC保持原证据，本卡未重跑。未见这14张所列区域的阻断性弹窗显示问题，限于可见状态。两次报告辅助尝试的路径读异常与JS变量异常发生在新报告创建前，实际图片读取均成功且现场文件存在；原工具错误记入JSON，不当业务或视觉首败。新报告按独占范围创建，源图/旧报告不变。V00停写，关闭阶段由CTRL合并全部适用门禁判断。

