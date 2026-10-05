# 来源恢复与新教师意图补充准备

2026-10-04。新增 `source-intent-recovery-boundary.test.tsx`，1 个实际组件行为场景；原 5 个全字段探针和首败原 case 均不改，总共 7 个 boundary 场景待稳定 r2 单轮执行。

场景先保留教师要求及 47 分钟，启动旧 report A 迟到读取、全正文 A 后 discard；记录完成放弃后的 run 显示、KP 勾选、完整生成 inputs、context，再释放旧返回，要求这些状态不被旧操作改变、保存 0。其后教师重新选择 A、明确勾选 A 知识点，必须正常保存 BASE 正文+新 A 上下文；再明确编辑完整 B，必须正常使用新 CAS 保存 B，同时 run/KP 和教师要求/分钟仍保留。

此补充不是放宽原断言：首败原文件 SHA 仍 `bfc96c302b1ccb2581c11b6a6c9101389821d0d3de9844ff8e18c14f1420099d`，须原字节重跑。新场景手写完整正文与新上下文 oracle；业务受控 API、真实 React 组件，不称浏览器/FastAPI 验收。

准备状态 `PREPARED_NOT_RUN`，产品仍由作者 r2 修改，本审查者停写，ROOT 稳定候选后运行全部 boundary。原 v1 证据/首败不追改，新的执行 QA 由 CTRL 单列候选增量。
