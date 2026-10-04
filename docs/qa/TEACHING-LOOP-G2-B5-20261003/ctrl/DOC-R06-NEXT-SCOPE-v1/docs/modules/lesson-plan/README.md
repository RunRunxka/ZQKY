# 正式教案模块

更新：2026-10-03。本文件说明已有教案的使用和维护边界，当前任务与验收限制见 [CURRENT_STATUS](../../CURRENT_STATUS.md)。

入口 `/lesson-plans`，源码 `apps/web/src/features/lesson-plan`。本目录说明正式Next.js版本；原目录中的Vite文档仅适用于冻结旧版。

## 当前功能

三栏配置、逐字段填写、实时预览；教学环节增删及上下移动；撤销重做；本机草稿保存与恢复；JSON导入备份；要求解析、警告、确认与追加/替换；Word下载和PDF打印；缩放、字号及手机编辑/预览切换。

初始《荷塘月色》是演示内容，未经过课程审定。默认本地模式继续规则填充；B5增量后台模式见下文，账号与云端服务未建立。自由描述只识别明确的课题、课时及部分课型，推荐使用：

```text
课题：荷塘月色
总课时：2
本节课：1
核心素养：品味语言，理解景物描写与情感关系。
教学过程：
情境导入 | 展示画面并交流 | 关注初读感受
品读赏析 | 分组讨论修辞 | 联系原文指导
作业：完成150字写景片段。
```

## 状态、组件与服务

`LessonPlanProvider`创建独立编辑实例，`EditorContext`协调交互，`useDraftPersistence`恢复和订阅数据，`createDraftWriter`串行保存。UI拆分为OutlinePanel、FormPanel、NlFillPanel、PreviewPane、ExportMenu、EditorOverlays和移动切换组件。

保留旧版草稿键与schemaVersion=1。读取失败暂停自动覆盖，写入失败保留待保存版本。路由切换先flush，刷新/页面离开也尝试写入。当前仍只支持单份本地草稿，不处理跨标签页冲突。

## 模板与导出

正式源模板副本在assets/templates/source，manifest记录原根文件名与SHA256。派生模板在前端public/templates，结构schema随模块保存；根脚本无需引用冻结目录即可重新构建。

原Word页面约209.9×302.7mm，并非标准A4；顶部/底部840、左右940 twips。Word保留原表格网格、合并、可增长行高、页面设置，前两个环节在第一表，其余在第二表。二次备课携带对应环节名称。

PDF使用标准A4、网页预览的紧凑布局和字号；长文本保守分片，连续教学过程标签合并，续页重复标题。导出需在浏览器打印窗口选择“另存为PDF”并关闭浏览器页眉页脚。不能保证Word与PDF逐页相同。

## B5 增量后台模式

既有工作台增量接入FastAPI后台教案列表/创建/保存/固定历史和显式旧稿导入，正文与DraftEnvelope仍v1。固定ready学情报告入口只带analysisRunId，进入后由教师选择单一班级和目标知识点；教材依据经生产RagV2核验，课堂题是confirmed固定题修订，练习是已reviewed固定修订。生成沿用公共六态任务，候选对照五个完整字段，教师选择应用后形成新修订，不自动改正文或审核。

旧键保留原字节；后台缓存按document ID独立，600ms串行保存区分editRevision/server CAS，unknown保存原操作可重放，409保留稿并人工看差异。历史只读，教师明确复制为新编辑后才能另存；撤销/重做仍是当前编辑操作。Word与打印继续旧模板和源快照，B5独立业务、恢复与浏览器验收结果只看CURRENT_STATUS，不能据本说明或源码存在认定完成。

## 保留的建设边界

账号、多人协作、任意模板上传、图片/公式富文本编辑器、独立服务端PDF渲染不属于B5。保留当前本地教案功能和旧草稿兼容。升级设计见 [教学闭环设计](../../design/teaching-loop-v1/README.md)，排期与授权只看 CURRENT_STATUS。Word/WPS实际打开后的长文分页和细节排版仍需人工验收。

当前进度、审查问题与最近验证只看 [CURRENT_STATUS](../../CURRENT_STATUS.md)。旧复刻矩阵与 `docs/QA_REPORT.md` 只作历史追溯；后者已合入 [项目历史 source-5](../../archive/History.md#source-5)，不能作为当前 Next.js 或未来 AI 教案升级的验收结论。
