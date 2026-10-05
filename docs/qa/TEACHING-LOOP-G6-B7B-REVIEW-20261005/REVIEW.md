# G6 / B7-B 后续代码审查

2026-10-05。本轮产品只读，独立隔离窄探针与下一批提示词已完成；**没有实施修复或启动 B7-C**。

新增两项 P2，尚未修复。G6 的正常 ACK/cleanup 原修复保持，B7-B 预算账本窄审无新确认缺陷；离线技术收据继续按原范围成立。这两项是后续新增反例，不改写原收据为未执行，也不据本次窄审签全项目完成。

## 1. R-G6-WRITE-OWNER-01 / P2：写入另一标签页的未知原包

位置：[useLessonOperation.ts:65](../../../apps/web/src/features/lesson-plan/model/useLessonOperation.ts#L65)、[write retry:93–95](../../../apps/web/src/features/lesson-plan/model/useLessonOperation.ts#L93)。DocumentsPanel 的 create/import 分别使用同源共享恢复键。

两个页面先加载空键。B 正常发送后收到 status=0，结果未知且合法完整恢复包已经持久化；A 随后首次正常操作直接写入 A 包，并发送 A。另一入口是 A 首次 quota 写失败且 HTTP0，B 合法发送后结果未知，A 点击公开缓存写重试；它仅验证旧包形状/context，然后覆盖 B 并返回 true 解锁。两个入口都没有核完整包归属，create/import 四个正确行为反例全部失败。

影响是 B 持久恢复身份被替换，刷新时无法从该键恢复 B 原包。B 当前内存和 unknown 状态仍保持，**未证实正文丢失、服务端重复创建或自动重复 HTTP**。正常入口本次实测 A send=1，重试入口 send=0；二者都实测 B 原字节被替换。

最小修复：正常发送前与公开 write retry 共用 owned-write 闸门。先读取并验证现有包，只有空或完整相同包允许写；foreign、坏包、不可读保持原字节并阻止本次 HTTP。闸门位于 prepare 之前，并在 prepare 后/write 前再核活会话，写后读回，恢复只解锁不自动发送。既有 ACK/cleanup 判据保持；localStorage 读写不是原子 CAS，不把此次确定性顺序修复扩为全部竞态已解。

证据：[cache/REVIEW.md](cache/REVIEW.md)、[最终完整轮 JSON](cache/write-owner-final.json)。窄回归 9 文件 **127/127，exit0**；新完整 12 场景 **8 pass / 4 fail，exit1**。四项失败是正确行为反例失败，不是预期硬拒通过。首轮/第二轮/最终轮分别保留，未拼轮计绿。

## 2. R-B7B-NATIVE-01 / P2：截断图片获得原生页证据完整性通过

位置：[trial_result_check.py:516–517](../../../scripts/teaching-quality/trial_result_check.py#L516)。native_return 核路径/SHA/扩展名后，仅检查 PNG/JPEG/WebP 文件头。

正确 SHA 的 **8 字节 PNG、3 字节 JPEG、12 字节 RIFF+WEBP** 文件头，没有像素且不可解码，三例仍 exit0、native_return_integrity_pass。这样的逐页证据无法查看，完整性门禁应拒绝。顶层 native_pending 和 createsNativeApproval=false 保持；**不称工具冒充了实际 Word/WPS 打开或人工排版通过**。

最小修复：用真实图像解码器核允许格式、与扩展名匹配、正尺寸、完整容器及实际像素解码，设置合理明确的资源范围；坏 CRC/截断/解码异常不能被魔数或正确 SHA 替代。必要依赖由 CTRL 唯一登记，保持 fixture 小图正常对照与真人/原生 pending 边界。

证据：[results/REVIEW.md](results/REVIEW.md)、[SUMMARY.json](results/SUMMARY.json)、[PNG 反例](results/runs/25-native-header-only-png/checked/RESULT.json)、[JPEG 反例](results/runs/26-native-header-only-jpeg/checked/RESULT.json)、[WebP 反例](results/runs/27-native-header-only-webp/checked/RESULT.json)。完整单轮 **28 CLI = 6 正常 + 19 正确硬拒 + 3 假通过**，总入口 exit1。三协议、合法不同分钟、来源/usage/字段保持、教师 hardFailure、PDF 拒绝等符合预期；四 guard 尝试计数全 0。实际 Popen PID 与 checker PID 一致，出生时间未采已如实注明。

## 3. 预算执行器复核

[budget/RESULT.md](budget/RESULT.md)：独立首轮 **19/19 unittest 方法，0 fail/error/skip，exit0**；9 条真实生产服务 fixture 场景，8 fixture wire sends，真实调用 0。三协议成功结算、坏 JSON/length 计 attempt 与已知 usage、未知/越界/HTTP 失败保留预留并停、预算差1拒绝、换label累计/重启/坏账本/排他锁/live拒绝均符合范围内判据。五禁止 guard 计数全 0，main 未导入。

当前 live CLI 明确硬拒，缺具体模型 proof registry 和可信 host/凭证绑定；费用模式和额外 usage 维度未支持，HTTPS 非回环限制也已声明。它们不是本次新缺陷。**补一份 scope 不代表可直接调用任意模型**。下一真实阶段应只支持一个人类指定模型，证明完整上界与 usage 语义后在精确授权子集执行，复用现有账本/结果工具；不重复制作离线材料包。

## 4. 候选、证据与本次未执行

[BASELINE.json](BASELINE.json)开工逐项核对：main@b7f99ab09826c68724e281d01e15215e660c1ce0，CANDIDATE-B7B-offline-r1 SHA 08e71f7d386e4005406209718317220506829bf9816d9d9e4bce1b934dc61988；972 source / 3771 executableQA / 33 contract / 970 build 全部一致。build wsH0-uD7VDC2ACYsbiRfS，next-env SHA 0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc。

[SEAL-VERIFICATION.json](SEAL-VERIFICATION.json)：原最终封印 11,525 项引用逐文件 SHA 全部一致，未导入应用或用网络/数据库。[FINAL-AUDIT.json](FINAL-AUDIT.json)与[DELIVERY-VERIFICATION.json](DELIVERY-VERIFICATION.json)是本轮收尾保全/新增文档验证入口：原产品、原执行 QA、契约、构建、开工旧 QA 58,503 个文件和受保护原件保持；五现行状态/索引文件仅增加本次审查块，旧字节保留，原 v2 任务及伪代码未修改。

本次未重跑完整 check/API/E2E、真实浏览器、聊天或书籍恢复；没有产品修改，不需要把交付历史 check/211/16/174 冒称本轮重跑。真实模型、教师评价、Word/WPS、RAG/Qdrant、正式迁移与压力未执行；无必要输入/授权，本次也仅审查范围。旧被拒额外 HTTP probe 未重试。原 B6/B7 整体、RAG-REL 与其他现行待验台账保持。

未提交、推送、切分支或部署；本轮未启动常驻服务/浏览器，探针命令已退出，TEMP/首败保留。不因本次修复建议自动开工。

新增文档首检在本报告发现三处源码相对路径多上一级，另两处为检查器尚未写出的自身输出引用；均已修正，首检收据保存在 [DELIVERY-VERIFICATION-first-fail.json](DELIVERY-VERIFICATION-first-fail.json)。此为本轮文档/检查器问题，不计产品 finding 或窄测试失败。

## 5. 下一批

[G7 → B7-C 总控提示词](../../design/teaching-loop-v1/B7C_总控启动提示词_20261005.md)已写至伪代码、文件归属与验收标准。先最小修复两项 P2，再按一个明确模型的可信 host/proof 接入及实际授权范围试评。没有模型/案例/attempt/累计预算授权则 G7 关闭后 STOP，真实调用 0，不再另起泛化离线准备批。

提示词已由[缓存专项](cache/PROMPT-REVIEW.md)、[预算专项](budget/PROMPT-REVIEW.md)、[结果专项](results/PROMPT-REVIEW.md)核读；采纳 prepare 后活会话复核、源码旧测试与旧 QA 归属、图像实际格式/CRC 反证及公共 proof/registry 单写者建议。最终版本 SHA 由新增交付校验绑定。用户下发后才执行。
