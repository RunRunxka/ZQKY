# B4-F v1 · 作者结果

负责人 `/root/g1_resume_browser`。起止 HEAD 均 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`。状态 **ready / 全部停写，待独立验收**。本结果是实现者自检，不是 B4 已验收或关闭。

## 实现范围

新增13个源码/测试文件，仅 `apps/web/src/features/learning-analysis/**` 与 `features/practices/**`；精确文件、字节数和 SHA256 见 `RESULT.json`。本批准备、完整命令日志、JSON及专属noEmit配置仅写 `b4-frontend/**`。公共契约/客户端/导航/薄路由/F20/题库返回入口由CTRL写，本作者只读核查，不修改它们或旧 G1 证据。

- 学情：固定历史成绩来源核对、显式唯一学生人次/补考、创建/同原包重放、公共六态job观察、固定报告历史、班级/学生/全部证据服务端分页、后端观察/独立信息不全/分母与ratio直接显示、历史班名缺失、有效0分和其余三态、共同材料/题干/选项/教师答案解析/受管图片、完整源定位和真实practice lineage、追加备注、目标KP创建真实练习。
- 练习：ready来源与约束、正式固定候选/覆盖/gaps、不自动放宽或调用模型、教师显式采用或已知正式修订加入、顺序/父子/计分叶/Decimal满分/正式KP/sourceBlockIds编辑、CAS保存、独立审核、固定历史只读、新草稿复制、服务端已保存完整题面审阅。
- 导出/回流：固定审核版两DOCX、实际转换后指定assessment的XLSX模板、真实Blob下载（不保存字节数不符的半文件）、完整exportId/jobId/revision/variant/assessment/result artifactId绑定、成功产物历史、显式日期/多班人次/出勤/补考/历史归属确认、转换未知原包重放、只用服务端返回assessmentId链接现有F20，后续新成绩历史进入新报告。
- 竞态与保护：复用现有useAsyncResource/useFrozenSubmission/useObservedJob，编辑generation防保存/备注晚响应清新输入；unknown锁原内容/身份/版本；source/history切换禁止丢未明确包；不同owner/key清旧视图；建议迟到不采用，约束变更不显示旧缺口；导出旧任务与旧产物不冒充当前身份。shared renderer未复制。
- 界面：保留蓝色/token/space语言与公共壳，宽事实表内部滚动、字段/长ID/来源换行、390单列、换序提供键盘按钮。无新动画、AI教案动作或掌握率计算。已只读核查CTRL的Next16薄页await searchParams及固定IDs key。

## 实际自检

Node `v26.2.0`，`C:/Program Files/nodejs/node.exe`；Vitest设置 `NODE_OPTIONS=--no-experimental-webstorage`。仅使用jsdom脱敏固定样本/API注入和任务观察替身，不接真实FastAPI，不读取正式.env/凭证/业务库/浏览器草稿。

| 轮次 | 实际结果 | 完整证据 |
| --- | --- | --- |
| unit-first | exit0，2文件10通过，1.76s | unit-first.log / unit-first.json |
| lint-first 首败 | exit1，0错误、1 exhaustive-deps警告，未作业务fail；随后增加任务身份去重并补全effect依赖 | lint-first.log |
| unit-second | exit0，2文件10通过，1.92s；晚响应与导出守卫变动后复跑 | unit-second.log / unit-second.json |
| lint-second / types-first | exit0，0警告；专属noEmit exit0 | lint-second.log / types-first.log |
| unit-final | exit0，2文件14通过，0失败/跳过，1.95s；增加未知审核/导出及两种旧exportId反例 | unit-final.log / unit-final.json |
| lint-final | exit0，0错误0警告 | lint-final.log |
| types-final | exit0，专属noEmit检查，incremental=false，无构建输出 | types-final.log / tsconfig.json |

最终命令（仓库根目录；stdout/stderr重定向到上述同名log）：

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
node.exe node_modules/vitest/vitest.mjs run apps/web/src/features/learning-analysis/LearningAnalysisWorkspace.test.tsx apps/web/src/features/practices/PracticesWorkspace.test.tsx --reporter=default --reporter=json --outputFile=docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-frontend/unit-final.json
node.exe node_modules/eslint/bin/eslint.js apps/web/src/features/learning-analysis apps/web/src/features/practices --max-warnings=0
node.exe node_modules/typescript/bin/tsc -p docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-frontend/tsconfig.json
```

14项行为包括：历史不换active/同学生明确补考互斥；后端ratio原样与0分完整富证据；读取损坏不是empty/旧筛选迟到；备注后编辑保留/unknown原包页签锁；在途分叶继续编辑/零审核；409422保输入/unknown保存原包；正式候选gaps不隐式写草稿；未知审核同CAS与submission；学生预览无教师块/202无下载/模板须实际施测；旧revision产物晚到；unknown导出variant与名单原包；job.result旧exportId拒绝；artifact metadata旧exportId拒绝；转换显式免考/补考人次的未知重放及F20定位。

## 资源与待验

没有启动/停止服务、打开浏览器、build或Git写入；没有后端临时库/新端口。自检node/worker均自然结束，终读CIM未发现vitest/eslint/tsc残留node进程。用户持有5174未操作；旧policy拒删目录未触碰。

以下 **not_run**：真实FastAPI全回流、实际202轮询/取消/重试/租约、真实DOCX/XLSX下载与像素/重解析、三视口人工画面/键盘/实际reduce动画、200×100浏览器首屏/翻页、check/test:api/build后E2E、迁移/四库新增表资产离线备份恢复。原因：正式作者卡限定专属jsdom自检；需全部作者停写、CTRL新候选冻结/构建及另一作者独立执行。Provider/Services替身只证明技术行为，不证明真实模型质量。

准备与作者结果完成后全部停写，等待CTRL集成和独立验收；如出现反例，由CTRL登记明确修复范围再改，不在冻结验收中自行变更源码。
