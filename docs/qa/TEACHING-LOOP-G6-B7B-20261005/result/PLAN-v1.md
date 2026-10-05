# B7B-R v1 计划与边界

负责人 B7B-R。起点 `main@b7f99ab09826c68724e281d01e15215e660c1ce0`；ROOT 开工保全 `676831c8b441388108c80d1ffaecc15c239c66b0155ed40b021843ac2f3c738f` 后释放实现。本卡仅写新 `trial_result_*.py`、专属 `test_trial_result_*.py`、`README-trial-result-v1.md` 和本 result 目录。

1. 只读消费 X 所属 `trial-result.json` v1 与其 SCHEMA，按显式文件散列关联固定案例、新输出、wire、usage、attempt、生产 JobView、候选和可选应用/导出。共享字段不由 R 改写。
2. 使用生产 `normalize_model_output` / `validate_for_apply` 和最终 wire 隐私检查。按原 15 手写案例的固定统计事实核输入；四阶段与整数总分钟执行生产约束，绝不要求旧 fixture 的 `stageMinutes` 数组或逐字答案。
3. 应用证据存在时核教师六字段与全部未选字段保持；缺 applied/DOCX 明确 not_run。选中但停止未运行与未选集合分列，fixture/live 分列。
4. 提供独立教师返回、Word/WPS 原生返回入口：完整身份/hash、真人声明/时间、八维、硬失败、原文位置和理由；原生需实际应用/版本、页码总数、逐页证据与 secondary/中文/合并/跨页/裁剪理由。自动化只核一致/完整，原样保留人工结论，不造 PASS。无返回 pending。
5. 作者全轮使用手写 synthetic 输入，正确行为 oracle 预先记录。每个实际 CLI 子进程记录 argv/PID/起止/elapsed/exit/sourceQA SHA/网络、main、env、DB guard；首败原件保留。完整自检后停止写入，独立 V00 由 ROOT 另行释放。

未给明确 live 模型/案例/attempt/预算，真实模型 0。原 common/prepare/aggregate/preflight、273 引用/15案例/四历史导出/旧 QA/正式应用/权威文档/模板/锁文件只读。合成返回不是真人反馈或原生开页；13 旧 PDF 不替代 native。RAG-REL OPEN，原 B6/B7 整体不关闭。
