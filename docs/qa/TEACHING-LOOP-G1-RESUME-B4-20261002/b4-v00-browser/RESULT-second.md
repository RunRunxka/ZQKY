# B4-V00-F 二轮／v1.2配置准备

f2候选 SHA `d296dd68ece4ce180f816c05f088a24c2ca7799a7e4a867bab2136a210cfeaa0`，877产品＋26QA＋4共享契约。前审201ms／后审189ms均exit0、全部零漂移、next-env同。

类型 second **exit0／1414ms**，PID1756已退出，实际stdout/stderr均0字节。FE second **exit1／425ms**，PID22888已退出，stdout176字节／stderr358字节，全部流和命令收据实物保留。Vitest报告0 suites／0 cases、success:false，首败 `No test files found`，不是18pass或业务反例。原因是冻结include绝对Windows反斜杠被作为glob，未匹配同一独立文件。

CTRL另授v1.2：仅将 vitest.config.ts 中同一精确 include路径追加 backslash→POSIX slash规范化；其他环境、setup、alias、fileParallelism、FE源码／18计划场景及全部断言不变。原配置逐字复制 vitest.config.f2-source.txt，原SHA `8c461b16dcd3e34f9da815cbfd4675c00a67780316d8ca3c3941efce43d42d38`。新config SHA `a2ba3fbb94d690fd6663abccece4067b1f611401765cec35050f9b1730ef7a80`，当前对f2完整hash只有此1授权QA改变，877产品／4契约／其余25QA零变化。可执行源已停写，**未重试未冻结FE**，等待F3。

类型/FE二轮新根均保留：
`C:\Users\96022\AppData\Local\Temp\zqky-b4-v00-hfjs_jp7`、
`C:\Users\96022\AppData\Local\Temp\zqky-b4-v00-650zrqob`。
仅读观察均存在、只含empty-textbooks。自己的两个子进程已正常结束；无服务/浏览器/连接需要终止。旧六目录与首轮原件均未触碰。CTRL已重申用户要求临时根保留，此后不再尝试删除。

自动审批拒绝了精确 `Remove-Item -LiteralPath $resolved -Recurse -Force` 清理动作，目标为上述两个绝对新根；仅返回 `blocked by policy`，未给具体原因。整条命令未执行、两个目录未删除；不换命令／工具绕过。完整独立资源记录见 resources-second.json。

seed/browser/ZIP/像素/四库验证均未执行，不因此宣称B4门禁关闭。
