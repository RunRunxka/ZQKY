# V00-Q v1 独立验收（STOP）

2026-10-05，g4_s。对已 STOP 的 G4-Q 三工具只读独立复验通过。**采用 second 完整新单轮 59/59 预期行为**：45 条严格范围预检、14 条材料汇总；5 条合法范围仅通过离线形状审查，2 条合法汇总，52 条负例按预期非零。没有从第一轮拼接通过片段。

手写预期始终来自运行前 PLAN 与固定 case-specs SHA353e56…，完整集合明确 C01～C15，显式子集 C01～C14；原候选 f79ac9… 固定每个材料的原 SHA。完整材料分别实核15/15和14/14技术结构与DOCX结构，14子集明确 C15 unrun。逐例核固定输入／匿名wire／候选／应用完整11字段与教师6字段／context／process secondary／导出／原full canonical来源记录及身份，未重新生成15例。

原删 C15 反例、将计数改14但未授权、重复／额外未知ID、缺DOCX记录／文件、缺结果、SHA错误、canonical不符、固定来源身份错误全部失败且不发布通过计数。坏 ZIP 反例在新的隔离复制件一致绑定 DOCX/manifest/export SHA，再实际到达ZIP校验，返回 BAD_ZIP；不能以仅SHA失败冒称结构反证。

严格范围包含原七项非法输入，空白／对象模型、case数组／已知唯一身份、非bool正整数样本数与尝试数、预算 bool／非正／null／非有限值、非JSON／重复键／数组根／凭证及未知字段、模型描述错配等；错误非零且定位字段。scope hash按独立canonical计算并包含maxAttempts，合法输出仍modelVerified=false、createsHumanAuthorization=false、budgetEnforced=false。没有真实模型调用或新授权。

**来源模式分列**：frozen-source-binding逐例及全局均为完整冻结原件SHA/canonical/source identity通过；当前物理四库和Blob均 not_run_source_temp_unavailable。旧TEMP目录仍在但SQLite缺失，未猜原因／重建／迁移；readonly-catalogs 对同一缺库实际exit2硬失败。这个限定来源绑定检查不能称本轮实查四库成功。15 DOCX为技术结构检查，Word/WPS原生排版仍未运行。15行原教师评分/理由均空，teacher_review_pending；RAG-REL仍OPEN。

first 首败原件保留：45范围行为符合预期后，首个全集汇总正确拒绝不存在的 seed SHA键（MISSING_HASH）。原因是我的三CLI prefix只给b6-quality相对路径，原candidate键为仓库相对docs/qa/...。经ROOT允许，保留原脚本SHA244168…，仅修三prefix为原manifest真实键，当前QA SHA28d986…；PLAN/手写ID/oracle/负例/阻断器不变。这是独立QA路径定位，不是产品修复。

所有59条命令/PID/UTC时间/退出码/日志/完整源SHA与原结果保存在run-second，各子进程和日志关闭；独立socket/import/open阻断器全部0网络尝试/应用导入/正式env读取。旧质量材料324文件零漂移，两个新TEMP与首败保留；没有服务、浏览器、Git或后台应用操作。outer runner PID未采集，逐条子命令真实PID已完整记录，不补造。

三个接受源SHA：common.py `69a79aec5e5fac015935e4875738f20462ade650bf8b1544d516f49fe7902f69`；aggregate_review.py `20048c5d1509074a43a3b87c2c5e62b4591151168235a8afa407e2dd1c3f96a7`；scope_preflight.py `8745398c023361c4dbb7ae16d9e0ad31ee1718a1ec9a80a15e7696d85308918f`。RESULT-v1.json记录全部证据SHA、命令与模式边界。此签收只覆盖G4-Q两个技术工具问题；整个G4/原B6/B7、来源浏览器、真实模型、真人质量及WPS由ROOT按剩余门禁判断。
