# B6-CHECK-QA v1：原local flush测试同步

2026-10-04 14:48，ROOT授权最小测试适配。负责人 g3_impl；独立审查 g3_boundary_review；ROOT集成与最终门禁。可写范围仅 `apps/web/src/features/lesson-plan/lesson-workspace.test.tsx` 中 `a failed local flush protects original input until explicit %s` 的打开/关闭等待，以及自己 `b6-integration/check-qa/` 新证据。产品、旧断言、API和其他测试禁止写入。

完整check首轮1285/1：discard在错误文本出现后同步查找可访问按钮失败；第二轮1285/1：retry导航调用可见后同步检查dialog已关闭失败。原整文件96/96诊断通过不替代完整check。独立只读核实dialog始终在DOM、错误文本不代表已showModal，open/close由React useEffect写入；真实首败没有dialog.open时点，不能宣称环境根因已证实。

修改前保存原test完整字节/SHA到own新叶；只在原错误文本等待后增加实际可访问dialog等待，末尾原 `queryByRole(...).not.toBeInTheDocument()` 原断言置入 `await waitFor`。保留所有title/rawcache/save调用次数/replaybody/router/no-loss/decision四分支断言；不加skip/retry、不延长全局超时、不改实现、不变更假时钟。旧首败日志保持。

自检原整文件96例新单轮，记录源及QA前后SHA、PID/时长/结果/TEMP保留，并保存最小diff证明没有删除断言；测试STOP后报ROOT。ROOT适配新冻结清单，重新完整check/build及新实际UI、旧独立组和原153；只有完整门禁通过才能关闭限定B6。
