# G1R 独立浏览器第二轮结果

**第二轮真实浏览器通过：正式退出 0，2 passed / 0 failed / 0 skipped / 0 flaky，7.471 秒。** 第一轮 0 pass / 2 timeout 的完整原件和 RESULT.md 保留，未覆盖或改作成功。

实际执行候选 g1-resume-r2，manifest SHA256 `952a6e2fd8a3cca002c4ff89f5dba145d9f7c4c55835e20092b6c02c154dcca5`。前后核其已登记 826 源、22 执行 QA、815 旧证据均 0 漂移，first 的 33 个原文件额外逐 SHA 验证不变。启动之后 ROOT 通知另外两份未执行的独立 audit oracle 新增未纳入 r2，因此**不宣称 r2 全 QA 零新增**；hash-after-second.json 精确登记。r3 只扩覆盖这两文件，共同 826 源及 22 执行源与实际执行时字节相同，见 second-common-binding-r3.json；独立 oracle 计数范围修正和 r4 冻结由 ROOT 另行处理，不冒称那两个文件已通过。

本轮仅使用现有 bundled Node v24.19.0（binary SHA256 `3602f2bb1a10f2cbab4c36886218a33c1ab3db87290e73b033c46c77147d0237`）调用同安装 Playwright CLI。用户 5174 的 Node26/构建未改，未升级包或锁；原 trace on、180 秒 timeout、配置和所有业务断言保持。唯一脚本适配仍是经 CTRL v1.2 授权的起始三步顺序，51 个原业务 expect 全保留。first trace 收尾 Node26 问题由 CTRL 分派的独立诊断保留，不删失败、不关 trace、不延长 timeout。

第一用例 3345ms，通过实际名单新增/导入/转班后合法 checkbox、出勤 exempt、人次3保留，移出学生撤销提示；映射 F 真实 PATCH 200 延迟期间新 G 编辑保持 dirty/不可承认；校对未保存时 zero confirm；保存读回后重新承认；真实确认提交后丢响应、完全相同冻结包重放；唯一正式成绩修订及历史矩阵。第二次只读收据审计另以原 CSV 和甲 Q1 改1的字面表验证完整 9 格：甲=(100,200,500) / total800，丙=(200,300,500) / total1000，丁=(0,300,500) / total800，全部 recorded。正式 revisionId `c6a00d5b321544e5b97381ecb5e3795f`，两次实际 confirm 200 返回同 revision，第二 replayed=true。

第二 R08 用例 2484ms，通过真实 DOCX 上传→校对保存→正式确认，固定卷 `totalScoreUnits=1000`（10 分）、三叶 200/300/500。默认 `|` / 显式 `,` / 显式 `|` 保留 x/y 两参数，各视口验证文字、操作符和顺序、正宽高/实际坐标并截图。1440/1920/390 文档 scrollWidth 分别等于自身宽度。Tab/Enter 检查实际 :focus-visible 的 2px 轮廓；普通 hover 存在 running150ms transition，reduce 后 transition=1e-05s、animations=[]、相邻帧背景已稳定改变。第二轮三个390公式局部像素及390历史整页已查看，公式参数/分隔符完整，历史面板收敛且矩阵在自身容器滚动；剩余整页最终视觉结论由 CTRL 核查。

两份完整 trace.zip 均用现有 Playwright yauzl 全条目读取，检查每条目长度、CRC32 并记录 SHA256：业务 trace 242 条 / 5418717 字节；R08 trace95条 /1564818字节，均有 EOCD。见 second-trace-validation.json，未把不完整 first ZIP 替换掉。

完整命令/环境/退出见 browser-second-command.json，stdout 见 browser-second.log，正式计数见 browser-results-second.json；完整业务/实际公式/动画/三视口收据见 second-business-audit.json 和 second artifacts 各原始 JSON。测试 runner 正常退出、无残余 worker 子进程或 Playwright Edge profile；未启动/停止任何监听。ROOT 在正式 exit0 后自行核归属并停止自有 8001，用户 5174 PID6836保留，见 second-resources.json。此报告只关闭本 Agent 的剩余真实浏览器项；整体 G1、适用全量 E2E 与是否进入 B4 由 CTRL 根据全部门禁决定。
