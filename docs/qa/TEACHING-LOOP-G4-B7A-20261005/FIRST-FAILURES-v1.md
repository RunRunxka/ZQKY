# 本批首败与候选边界

所有轮次分别保留完整命令、退出码、日志和原件；新整轮不会合并早期通过项。旧 G3/B6/UI 证据不改。

| 范围 / 完整轮 | 实际结果 | 归因与最小处理 | 复验边界 |
| --- | --- | --- | --- |
| Q 作者 r1 / r2 / r3 | 见 quality/ 原收据；r1 缺旧物理 TEMP 数据库，后续冻结来源证明补验 | 不迁移或重建旧 TEMP；显式 frozen-source-binding 与 readonly-catalogs 两模式，物理源缺失独立记未执行 | Q 作者最终 r4 52/52，V00 完整第二轮 59/59；仅结构材料通过 |
| Q 独立 first | 45 项范围反证完成，全集汇总因独立 QA 三个前缀错误缺 SHA 失败 | 只修独立 QA 前缀，原脚本与失败汇总保留 | second 单轮 59/59，非拼接 |
| 产品组件 first | exit 1、0 测试 | Windows 绝对反斜杠 glob 未收集；只改独立 config 一行相对正斜杠 | 原 config 保留在 first/ |
| 产品组件 second | 35/38，3 项失败 | 独立 oracle 在已明确成功 ACK 后错误要求 frozen 仍存在；原契约成功应释放。仅改 ACK 后 pending=null 与 succeeded，发送前同包/零 HTTP/读回断言保持 | second 原源码保留，third 单轮 38/38；只适用于 G4 原产品候选 |
| 新浏览器 first | exit 1、未收集业务测试 | ESM 中使用 __dirname，配置路径解析错误 | 原 first config/log 保留 |
| 新浏览器 second | exit 1、2 worker 启动失败、9 未执行；业务均未进入 | worker 重载 config 后 output 已被主进程创建；只把拒覆写检查移至 ROOT 启动前运行器 | 原 second config/log/trace 保留；实际共 11 项 |
| 新浏览器 third | 9/11，exit 1；0 retry | pre-send 保存故障后 running ref 清除未通知，实际 busy 快照使公开恢复按钮禁用；属于产品缺口。另一坏缓存场景在旧页 pagehide 前注入，按正常规则被可信内存覆盖；属于 QA 故障注入阶段错位 | 最小产品补修 finally 对当前同 promise/同会话通知；坏 cache 改新页 initScript 注入。第三轮原测试已保存，旧构建不再代签新产品 |

第三轮真实浏览器通过项包括四视口键盘焦点/完整缓存恢复、持续失败零 HTTP/正文备份、未知实际提交同包重放且历史不重复、较高 CAS 人工冲突、两个持有实际来源响应后清除及仅新意图生成。后续仍须重新完整相关独立和浏览器轮次、check/build、适用 174 全量 E2E；本文件不关闭 G4。

live = not_run_user_offline_scope；教师 = pending；Word/WPS = not_run；旧物理源核验 = not_run_source_temp_unavailable。原 B6/B7 整体与 RAG-REL 保持开放边界。
