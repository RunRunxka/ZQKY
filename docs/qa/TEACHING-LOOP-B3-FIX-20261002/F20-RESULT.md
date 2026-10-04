# B3-FIX-F20 / PAPERS / PARTICIPANT-ADD 结果卡

- task_id/version：B3-FIX-F20 v1，原卷/参测增量按总控追加授权。
- owner：assessments_frontend。
- actual_base：`main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`。
- status：**ready_for_review，产品停止写入**。此卡是实现者自检，不冒称独立验收。

## 精确产品范围

`apps/web/src/features/assessments/` 下：

- 修改 `AssessmentsPanel.tsx`、`ScoreImportReview.tsx`、`ScorePanel.tsx`、`PapersPanel.tsx`、`labels.ts`、`labels.test.ts`、`hooks.test.tsx`。
- 新增 `AssessmentsPanel.test.tsx`、`ScoreImportReview.test.tsx`、`ScorePanel.test.tsx`、`ParticipantAttendanceEditor.tsx/.test.tsx`、`ParticipantAddPanel.tsx/.test.tsx`、`PaperImportReview.tsx/.test.tsx`。
- 未修改共享 contracts/services/导航/routes/styles、Git、用户 next-env.d.ts 或审查原件。公共字段、客户端、RichContentRenderer/useObservedJob 由总控提供；名单表导入属于其他实现者。

## 正常与失败路径

| 范围 | 正确行为与证据 |
| --- | --- |
| B3-R02 | 直接使用服务端 `requiredAcknowledgements`，删除 raw blanks 推导；缺考+剩余原件空白可提交 `missing=null`，免考不会产生伪缺口，有效0/真正missing组合只传真实范围。权威范围缺失明确阻断；预览版本变化重新承认。ScoreImportReview 6例、labels 13例。 |
| B3-R08 | create callback只返回结果，hook有效返回后才改变父级。StrictMode正常仅一次选择；卸载迟到成功/失败、切班/换卷、同班同卷改选既有施测均零旧选择副作用。创建422表单与参测编辑保留。AssessmentsPanel 7例。 |
| 单格证据 | 服务端 effectiveStatus/scoreUnits优先，另列原件值/公式缓存/已保存校正，未保存草稿另标；空白不把整行有效缺考误显示成missing，有效0保持0。 |
| 出勤校正 | 显式attendance/reason、施测CAS与幂等标识；409保留编辑及当前版本，结果未知锁编辑并重放同标识/原包，切人次迟到成功/失败零父级副作用。成功提示明确刷新成绩预览，旧成绩不变。ParticipantAttendanceEditor 5例。 |
| 补录/补考 | 选择既有学生id，明确人次/出勤；新增人次不发送姓名快照。CAS409保留输入；历史班级422定位后必须填写依据再显式确认，新的逻辑请求使用新标识。响应丢失重放原包，切施测迟到成功/失败零副作用。ParticipantAddPanel 6例。 |
| 成绩映射/刷新 | 原有出勤/总分列读回及PATCH完整保留，原表物理列大写规范化；422展示原表行/列/field且保留映射编辑。明确刷新使用导入/施测/base三个独立字段；未保存行校对和映射编辑均保留，CAS失败显示当前版本；切批次迟到刷新成功/失败不污染新上下文，卸载迟到上传不通知父级。ScorePanel 7例。 |
| 原卷完整校对 | DOCX上传入口使用真实客户端，学科来自真实taxonomy；完整源块20/页、题目10/页，共用公式/合并表格/受管图片/共同材料renderer。题号/父子/叶子满分/正式知识点可编辑，手建题并将真实原块加入题面或共同材料；原有rich内容不随元数据修改丢失。 |
| 原卷问题处置 | structured supplement_text/supplement_asset/exclude，内容损失不提供排除选项；有理由排除与真实补录分别发明确结构，422保留输入/field定位，409保留标题，刷新对照不清本地编辑。 |
| 原卷确认与AI | 确认冻结标识/版本，未知重放原包，服务端失败不假成功；确认后读取自己的固定修订标题再选用，读取失败不改选择。AI复用公共queued@0→succeeded@1观察，明确模型、六态/取消/重试、候选逐题显式选正式知识点后应用或拒绝，不自动发布。PaperImportReview 11例。 |

## 实际命令与退出码

全部Node窄测使用 `NODE_OPTIONS=--no-experimental-webstorage`；只 stub fetch，使用真实组件/hooks/客户端。API响应替身不冒称真实FastAPI业务验收。

- `npm.cmd run test:unit -- <自有8个 .test 文件>`：**68 passed / 8 files / exit 0**，`logs/f20-own-final-unit.txt`。随后新增两个有意义场景：父子容器结构、总分/出勤422物理定位。
- `npm.cmd run test:unit -- apps/web/src/features/assessments/PaperImportReview.test.tsx`：**11 passed / exit 0**，`logs/f20-paper-final.txt`。
- `npm.cmd run test:unit -- apps/web/src/features/assessments/ScorePanel.test.tsx`：**7 passed / exit 0**，`logs/f20-mapping-final.txt`。
- 最终候选自有独立用例共 **70**；这是68例集成窄跑后两个单文件增量自检的并集，不能冒称最终一次70例合跑。
- `node node_modules/eslint/bin/eslint.js <自有精确16文件> --max-warnings=0`：**exit 0**，`logs/f20-own-final-eslint.txt`；后续原卷/补录及映射增量各窄lint **exit 0**，`logs/f20-last-eslint.txt`、`logs/f20-mapping-eslint.txt`。
- `git diff --check -- <自有产品文件>`：**exit 0**；只读检查，没有Git写操作。
- 期间全目录窄测包含其他实现者的 RosterImportPanel 17例；不计入本实现者自有70例，也不冒称其实现归属。

首败与修正依据见 `logs/f20-first-failure-summary.md` 及其中指向的原始日志，未以重试抹去首败。

## not_run 与交接

- not_run：全局typecheck/npm check/build、全量后端/全量E2E、真实FastAPI浏览器链、三视口/键盘/reduced-motion人工视觉；由总控资源负责人串行组织。本实现者未启动端口。
- not_run：真实模型、Word/WPS、Qdrant、正式数据迁移、超基线压力；本模块任务未获得正式数据操作范围。
- 独立复验必须用当前服务端权威范围和真实隔离原卷/施测/成绩链。旧审查导出推导helper的诊断探针保留原件，但不作为新候选回归。
- 稳定控件：原卷DOCX文件、原卷学科、上传原卷并校对、原卷修订标题；题 1 满分/题 1 知识点（multiple）；保存原卷草稿/确认原卷入库；源块 `paper-source-<blockId>`；结果 `paper-confirm-result`；成绩 metadata `总分列`/`出勤列`；`明确刷新成绩预览`；`补录学生`/`补录人次序号`/`补录出勤`/`新增参测人次`。
