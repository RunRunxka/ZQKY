# 教案模块约定

先读根和前端AGENTS.md，并读 `docs/modules/lesson-plan/README.md`。

- 入口 `/lesson-plans`；`LessonPlanWorkspace` 组合配置、表单、要求填充、预览和导出，`LessonPlanProvider`提供实例状态与服务。
- 保持 `LessonPlanData`、`DraftEnvelope.schemaVersion=1` 和本地键 `zhiqikeyuan:lesson-plan:v1` 的兼容性。改变数据结构时必须设计迁移；不能默默丢弃旧草稿。
- 填充统一经 `FillProvider` 返回建议，再展示警告并确认合并；失败不能自动换成示例或静默覆盖。默认是本地规则，不是真实AI。
- 存储经 `DraftRepository`；600ms防抖，离开路由/卸载前刷新。异步写入串行，失败保留待写版本；坏草稿暂停覆盖。修改后测试快速导航、失败重试和刷新恢复。
- 原始模板在 `assets/templates/source/teacher-standard.docx`，来源为根Word原件。修改源文件不是常规开发步骤；派生模板由根脚本生成。
- Word保留原模板的表格属性、合并、可增长行高和非标准A4页面。前两个环节映射第一表，其余映射第二表；二次备课保留环节名称。
- PDF使用网页打印、标准A4及命名页面 `lesson-plan`，与Word分页不保证相同。勿把“打开打印窗口”称为“PDF已保存”。
- 导出改动检查中文、全部字段、长正文、长二次备课、特殊字符和原模板校验。结构相同不能替代Word/WPS人工排版验收。
- 现有基准包括桌面1440×900、平板1024×768、手机390×844、2页示例和大字号长文。截图和测试数据必须来自隔离会话。
- 不新增账号、多教案列表、AI生成或任意模板上传，除非本次用户任务明确包含这些能力。
