# B6 完整五字段 UI QA 准备 v2

状态：产品及作者测试 STOP；新 UI QA 也 STOP_NOT_RUN，等待 ROOT 新构建和绑定 seed。旧 q84e 的 browser-r1 至 r6、首败、错误上下文与 trace 原样保留。没有启动服务或浏览器。

新 runner 的浏览器运行必须显式提供 B6_CANDIDATE 与 B6_SEED，不再默认旧构建或旧 seed。先验证 ROOT-built candidate、seed 的精确 candidate SHA 与 buildId 一致，再冻结本次 942 来源、旧 QA 和 own QA 的 before/after；新 label 目录不可覆盖旧轮。

公开工作台先以本地教师稿明确选班级和单个知识点，再公开创建后台教案。新后台 SourcePanel 打开期间只延迟 actual model-profiles 业务响应：route.fetch 访问真实隔离后端，保存返回 status/body SHA，原返回保持，不伪造 payload/200。在释放前实际读 ready 报告并选择单个 KP；释放后要求模型、年级、版本完整、加载提示消失及教师固定来源不被改回。随后真实核验教材、选择 confirmed 题与 reviewed 练习、生成并应用五个完整字段、保留六项教师哨兵，核完整正文及 contextSnapshot、固定历史 JSON。Provider 仅既有 HTTP Transport 替身，教学质量仍 teacher_review_pending。

成功 trace 使用 on，失败也保留 trace；新报告不得拼接旧 browser-r6 前段或旧 endpoint 绿段。实际执行还未进行。静态 TypeScript transpile 仅检查新 spec/config 语法：两项 parseErrors=0，未运行浏览器业务。

冻结文件 SHA：

- run_lane.py：4161541ed69216f51dc3920f611559421bbce65e8e762b77cd7a0692dde43c37
- five-fields.spec.ts：d550fa9b23a0961a1efa3d4bac8f4dd1fbd3833b5e1d2abca13dc58900b54374
- browser.config.ts：525a225cd89c13b726b660ec5fbc97f6c84b9a5a20d9bb0d657242de1ae87b89
