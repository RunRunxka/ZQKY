# 正式教案模块

入口 `/lesson-plans`，源码 `apps/web/src/features/lesson-plan`。本目录说明正式Next.js版本；原目录中的Vite文档仅适用于冻结旧版。

## 当前功能

三栏配置、逐字段填写、实时预览；教学环节增删及上下移动；撤销重做；本机草稿保存与恢复；JSON导入备份；要求解析、警告、确认与追加/替换；Word下载和PDF打印；缩放、字号及手机编辑/预览切换。

初始《荷塘月色》是演示内容，未经过课程审定。默认没有真实AI、账号或云端服务。自由描述只识别明确的课题、课时及部分课型，推荐使用：

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

## 尚未实施

真实AI、多教案列表、云端存储、账号、协同冲突、任意模板上传、图片/公式富文本、服务端一键PDF下载均未实现。Word/WPS实际打开后的长文分页和细节排版仍需人工验收。

当前进度与最近验证只看 [STATUS](../../STATUS.md)，逐页功能和视觉状态看 [页面矩阵](../../replica/PAGE_MATRIX.md)。旧 `docs/QA_REPORT.md` 已合入 [项目历史 source-5](../../archive/PROJECT_HISTORY.md#source-5)，只作迁移前追溯，不作为当前 Next.js 验收证据。
