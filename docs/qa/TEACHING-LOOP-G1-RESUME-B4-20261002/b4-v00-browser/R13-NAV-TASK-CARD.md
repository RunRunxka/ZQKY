# B4-F-R13-NAV v1 — 独立红测准备卡

负责人 `/root/g1_v00_fe`，CTRL登记独立验收。当前仅准备，不执行；全量153 E2E仍属CTRL/P原执行身份。原产品、原E2E、旧QA及旧证据只读。

本卡可写仅新增 `b4-v00-browser/r13-navigation.test.tsx`、`vitest.r13.config.ts` 和本任务新MD/JSON/日志，不写原任何文件。两个新的正确行为组件场景使用真实薄server page→QuestionBankWorkspace→QuestionLibrary；next/navigation与分类/列表数据、非目标面板及补题内容为显式组件替身，不作真实服务或四库通过。

场景1：保留同一次workspace挂载，将晚到重复fragment与显式tab=library查询分别受控交付，library必须选中；returnPracticeSetId完整编码保留；教师手动导入/已入库切换仍正确并同步tab查询；旧#library仍可直接打开。场景2：已有实际library挂载时显式tab=generation必须打开其实际generationOpen状态；保留return context、手动tabs和旧#generation。第二例不把只变initialGenerationOpen props却未更新真实内部状态当通过。

冻结前全停写并向CTRL提交SHA。红测只允许在CTRL另行冻结并明确授权后单轮执行，原正确预期不因失败放宽。预/后完整核候选；保留首次完整输出、exit、耗时、样本与资源收据。发生QA启动/类型错误如实登记，不当产品红测。

红测命令模板（候选路径由CTRL正式通知后替换，当前未执行）：

```powershell
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-root/run_check.py' --label r13-nav-red-first --candidate '<CTRL正式冻结候选相对路径>' -- 'C:/Program Files/nodejs/node.exe' 'node_modules/vitest/vitest.mjs' run --config 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-v00-browser/vitest.r13.config.ts'
exit $LASTEXITCODE
```

root既有runner注入 `NODE_OPTIONS=--no-experimental-webstorage`、测试新根、16333/9/empty教材、保留样本；配置使用POSIX路径精确收集同一新文件与既有tests/setup.ts。不给它启动服务/重跑全量check权限。根runner自身读Git身份，不执行Git变更。
