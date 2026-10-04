# B4-V00-F 首轮与 v1.1 准备结果

f1 前审／类型失败后的后审均 exit0：877产品、24执行QA、4共享契约零漂移，next-env一致。候选 SHA `d38366cc323fa20c86aa2d5c76ac4abdfd1e8f964644ec2696f6debdbc6e6845`。冻结审计不代表行为通过。

类型检查 first **child exit2／1462ms**，PID7864已退出。外层 exec 返回1，实际 tsc 子退出码以 types-first-command.json 为准。完整实际 stdout12018字节／stderr0字节均保存，未伪造空日志。首败是新 QA 的 ByRoleOptions 不支持 exact、jest-dom 类型未纳编译范围、ErrorIssue 缺 code、Class/Student/Assessment fixture DTO不完整。没有执行 FE；计划18不可写成18pass。

首败源码已逐字节复制 independent-fe.f1-source.txt／tsconfig.f1-source.txt，SHA与 f1 原件一致；首轮命令、日志、临时根全部保留。前审第一次 exec 的控制台 Unicode 存在替换解码，只保留其真实 combined decoded delivery，不冒称分别原始stdout/stderr；audit-f1-before.json 原始 UTF-8 结构收据完整。后审两实际重定向流已落盘。

CTRL 另授 v1.1，仅收口 independent-fe.test.tsx／tsconfig.json 类型。保留所有精确 string name、用例、断言、场景和延迟。existing jest-dom/vitest 导入；compiler include既有 tests/setup.ts；runtime config原来已用同setup未变。ErrorIssue追加code；补完整 Class/Student及分页／membership、完整Assessment DTO。两个原 ancillary updatedAt 字段仍保留在结构类型匹配的 named fixtures，没有 as any 或删除断言／用例。

静态 TypeScript parser exit0，parse diagnostics0，13测试定义标题原样（计划参数展开18）；122个expect相关AST call节点在仅正规化 role exact 后全部原样相同。**这只是获授权静态解析，未跑第二轮类型检查／FE。** 相对f1当前仅两授权 QA 源变化，877产品／4契约／其余冻结QA零变化。

新 FE SHA `283928976d1f3dbcfeb4e17d19dfdbed5a6f7f3b00cdec1694d0e29c5e607b44`；tsconfig SHA `135bc8b0b789bc6b72d6c33ccf0f4751e0c9c90cd4c40cd94abfc12c283ee7fc`。其余 browser/seed/配置／helper身份不变。全部可执行源已再次停写，等待CTRL重冻／执行指令。

保留新临时根 `C:\Users\96022\AppData\Local\Temp\zqky-b4-v00-6u5_y_yd`，只有类型runner隔离目录，无业务库／监听。seed、浏览器、导出／DB oracle均未执行；没有操作5174/8001、构建、Git、产品或旧QA。首败是QA类型准备故障，不计作产品业务失败或通过。
