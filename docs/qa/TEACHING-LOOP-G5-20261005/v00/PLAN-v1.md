# G5-V00 v1 独立验收准备

2026-10-05，独立验收者 g4_v00_product。当前为准备；ROOT 明确释放稳定 STOP 候选前，不执行产品、CLI、浏览器或服务。唯一可写本批 v00，原产品、作者测试、权威文档和历史证据只读。

R-G4-RECOVERY-01：公共 DocumentsPanel、DocumentGateway、LeaveProtection 组合测试。create/import 各 14 条：连续成功取消后第二 422、409；首失败/首成功清理；第二成功当前回执并保留或取消新编辑；发送前失败零 HTTP、结果未知精确重放；重复恢复；跨文档与卸载迟到；坏读取、损坏包、持续清理失败。完整正文十一项、二次备课、context/source/selection、当前文档身份和旧本地信封均逐项保留。失败恢复不得导航旧回执或追加 HTTP；成功仅导航当前回执。新 28 条、原 stale-ack 1 条及 cleanup-controls 2 条、原恢复 37 条、原来源/历史 60 条、原独立公共恢复 14 条及操作恢复 10 条分别统计，合计 152 条，不将历史次数算作本轮。

R-B7A-QUALITY-01：新 label 隔离复制冻结合成材料，手写 CSV/MD 结构与空槽判据，所有改动显式重锚 artifact manifest SHA。原 full15、明确14/C15未跑必须接受，反馈仍是完整冻结15例。原273引用和正常空 CSV/MD保留。CSV额外格、短行、缺/重/未知头、case完整顺序、固定哈希、人审非空；MD逐人审槽、附加正文、错误/缺/重/未知case和标题/哈希；合法 BOM/换行与引号空模板不误拒。原集合、路径/缺件/错SHA/覆盖/冻结来源绑定的适用硬拒保留。所有 CLI 在网络、app import、.env/正式数据访问、SQLite 四项 guard 下单次运行，记录真实 PID/argv/时间/elapsed/exit/rawlog/首败，任何 guard 非零即失败。源/QA/契约/构建/原273及原材料前后精确 SHA。

ROOT 负责真实浏览器和服务。独立审核公共页面连续 create/import：四视口 390×844、1024×768、1440×900、1920×1080，先成功等待期间编辑、取消离开、第二422缓存删除失败、公开恢复后正文和选择不变、恰两次 create/import；第二成功只打开第二回执，新编辑仍可取消。恢复按钮键盘焦点和恢复后状态各四张原始截图；受控 HTTP/Storage 标明替身，真实模型0。新 build 后完整 check、新业务浏览器、原完整174 E2E分别成轮。API源码未改则只引用同源后端旧收据并标本批未执行。

旧 G4/B7-A关闭仅其历史技术/离线范围，本批新问题不倒改旧收据。模型、教师、原生 Word/WPS、physical源缺件、RAG_REL、B6/B7整体、59真引用+1missing、旧43中12drift、R14保持原限定。G5授权止于修复关闭；不执行B7-B、不代填人审、不以13历史PDF页冒称原生排版。

原正确行为来源与SHA见 ORACLE-v1.json；根开工 OPENING-v1 c8449d9a8ff5ba144f0ba460e213228e3d64e6c79af03f2bd7b6dcd162a251b4。原反例和两正常/失败控制只读复验，不重写旧 first-failure。
