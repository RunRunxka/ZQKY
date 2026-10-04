# G3-V00：r2 单轮组件结果独立核查

2026-10-04。本报告是 V00 对 ROOT 实际运行原件的独立读取与判定，没有重新运行或拼接旧结果。所有执行 QA 和产品保持停止写入；真实浏览器仍在另行执行，本文不关闭 G3。

绑定候选：`CANDIDATE-G3-r2.json`，SHA `80bc5a40d08c81a0b6cb5d62e19d4267ccf3c56e0c1d2c776fe89ce839860d22`。四份命令收据均为 source/QA 漂移空数组、原 next-env SHA `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`，子进程及日志已关闭；实际日志 SHA 与收据逐份一致。

| 本批新运行 | 实际结果 | PID / elapsed | ROOT 原命令及日志 |
| --- | --- | --- | --- |
| V00 完整独立组件 | 15/15 pass，0 skip/retry | 16652 / 5644.926ms | `../ctrl/g3-v00-unit-r2-command.json`、`../ctrl/g3-v00-unit-r2.log` |
| 原两个 required behavior | 2/2 pass；4 原错误行为诊断按模式过滤 | 14024 / 4064.218ms | `../ctrl/g3-original-required-r2-command.json`、`../ctrl/g3-original-required-r2.log` |
| 原 B5 独立组件 | 6文件27/27 pass | 21000 / 7154.447ms | `../ctrl/g3-prior27-r2-command.json`、`../ctrl/g3-prior27-r2.log` |
| 第三方完整边界 | 4文件8/8 pass | 25060 / 4353.012ms | `../ctrl/g3-boundary-eight-r2-command.json`、`../ctrl/g3-boundary-eight-r2.log` |

原两个 required 行要求的断言保持：明确放弃后跨 600ms 不保存/不重建恢复键；历史复制等待期间新的输入和缓存保持、复制 intent 保留。4 个过滤诊断用于证明旧错误，过滤不是当前产品豁免。

V00 的完整15项覆盖：后台旧子树多周期的自动入口撤权；立即卸载对照；留页新 B 可再保存；恢复键删除失败保唯一稿并停自动发送；已发 HTTP/unknown/exclusive/auxiliary 拒绝放弃；本地完整基线恢复与新编辑；历史复制中长正文和过程编辑的全文/缓存/intent；正常复制与Undo/Redo；双击仅一次；读取失败重试；真实 CAS 判断；不同教案迟到响应。预期全文由独立手写样本构造，没有调用生产 merge 自造 oracle。

第三方的 actual SourcePanel 迟到读取和实际完整 Workspace+ServerControls 源恢复链也已通过：可信正文、固定上下文、显示来源及新操作保存分别核对。瞬态生成资格可在成功放弃后撤销；真实固定上下文和教师输入不能被旧读取覆盖。该结论来自实际测试结果与公开组件链，并不将简化 Controls 缺少 ServerControls 效果认定为产品缺陷。

## 首败与 QA 差异保留

最初 V00 完整15为13pass/2fail：本地夹具每渲染创建新 notice 回调，触发持久化 effect 清理 flush；跨文档夹具只 fireEvent.click(summary) 未产生 details.open/native toggle，列表未读取。首日志、整个 unit 四文件原字节和 SHA 在 `unit-first-source-r1/` 保留，只修稳定 callback 和真实 toggle 并增加列表调用断言，场景和 oracle 未删除/放宽。

修夹具后 ROOT 的完整15单轮通过，以及本次 r2 的完整15单轮通过分别独立记录，不拿初轮13项拼接为通过。新 SourcePanel 产品反例与修复由 ROOT/第三方另存首败，旧批审查编号保持。

浏览器路径首轮在收集前失败，0行为案例；原3文件字节/SHA及仅 import 层数修正在 `browser-path-first-source-r2/`、`BROWSER-PATH-QA-DELTA-r4.json`。一次 `--list` 收集14项不是行为通过。新的完整14浏览器场景另见本批运行原件，本文未将运行中结果写成已通过。

## 当前边界

本报告仅确认以上本批组件运行。真实延迟 Next/业务 GET、四尺寸截图/实际焦点/reduced-motion、完整浏览器 JSON/trace、适用工程/API/E2E/聊天门禁仍须各自实际证据。真实付费模型、教师教学质量、Word/WPS人工排版/实际PDF保存、正式6333、正式迁移、超范围压力均未在本 V00 组件核查执行。旧政策拒绝额外 HTTP 身份复核未重试；不提交、推送、部署或提前启动 B6。
