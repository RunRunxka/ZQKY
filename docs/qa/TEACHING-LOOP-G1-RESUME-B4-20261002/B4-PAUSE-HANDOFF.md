# B4 暂停交接

更新：2026-10-03。用户明确要求「先暂停，记录好情况写好文档后续接着做」。**当前暂停，等待用户恢复；G1 已关闭，B4 最终门禁未关闭。** 本文记录暂停现场，唯一当前进度入口仍为 [CURRENT_STATUS](../../CURRENT_STATUS.md)。

## 现场

- 工作区 `H:\备份xuexi\智启课源`；`main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`。全部未提交改动保留，不提交／推送／切分支／部署。
- [r17-nav-final](CANDIDATE-b4-r17-nav-final.json)：878 产品／45 可执行 QA／5 契约，SHA `7ee8b05c5bdacd17c3410c08f6a31b026fbcf26a895f227c9e2cb877d8b792b1`。
- 构建 `Ji-Jz8X9yY2R_79JOPivD`，2007 文件，实际 proxy 8001；[身份](BUILD-IDENTITY-b4-r17.json) SHA `29252444df2d9fb4160c3f26b9d28baaf3b93271014a49f696883feb51ae8b93`。现场 next-env 原 SHA `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc` 已恢复。
- 用户前端 PID 5172，创建于 `2026-10-02T23:46:46.5737930+08:00`，`node scripts/run-web.mjs start 5174`，暂停时仍监听 5174。Agent 不结束／重启；启动曾被 policy 拒绝，禁止 Agent 重试、换工具／端口／Agent 绕过。
- root stream PID 23268 优雅退出 0、原 fixture finally 实际返回，8001／8002 释放。原聊天 14 场景未执行；服务曾启动不能算业务测试通过或失败。
- 新样本、首败、旧六拒删根全部保留。[资源](B4-RESOURCES.md)、[审计](b4-root/PAUSE-AUDIT.json) 与独立文档复核只证明其实际时点，不保证未来 PID／端口仍相同。

## 已完成，不重复实施

T70／T80、双 DOCX／成绩模板、四库迁移／备份恢复、转换→T60→新 T70、owner／归属边界已有独立通过证据。完整 check 为 1110 单测＋类型／零警告 lint／build 通过；全 API 单轮 1698 通过／1 规模门控 skip，当前后端同源绑定；T70 8 场景与 T80 64 场景分别计数。

R11 ready 同步、R12 手机可读性和 B4-R13 query 导航已修复；r17 独立导航 2 通过、第六完整实际浏览器 1 通过／24925 ms、新手机 8 补屏通过。最新 E2E 题库两例及全部后续断言通过。旧批提示词不是重新实施已交付阶段的指令。

## 未完成

1. 最新原 E2E 为 **152 通过／1 失败，exit 1**；原 24 spec／153 case，153 attempt，retry 0，原断言不改。唯一失败是 `books-commit-safety.spec.ts:267`：第二书 strip 在原 120000 ms 后仍为 1。A 完成及完成前两笔记保存通过；B DOM 显示明确 interrupted＋继续生成。恢复操作及后续最终跨标签笔记／双 ID／无锁断言未执行，根因、lease／write-lock 因果和恢复结果未证实。
2. 原聊天两 spec／14 场景 **未执行**。external 配置、隔离 retained stream wrapper 和任务卡已准备，但此次启动已结束；旧 stream receipt／日志／stopfile 不覆盖，不重复使用其样本当新执行。
3. 上述必要门禁完成后还须最终来源／构建／保护／资源／文档审计；当前暂停收口不是 B4 关闭。

首败：[最新全量](b4-v00-practices/FULL-E2E-REAL-FIXED-FIRST-RESULT.md)、[独立 R-14 调查](b4-v00-browser/R14-STATIC-FIRST-FAILURE.md)、[首败记录](B4-ROOT-FIRST-FAILURES.md)。旧 r13 的题库导航 152／1 首败也保留，不拼成一次全绿。

## 用户恢复后接续

1. 重读根／拟改模块 AGENTS、CURRENT_STATUS、PROJECT_GUIDE，核现场 HEAD／分支、r17 源／QA／契约／构建／原 next-env。先只读核端口／PID 身份，保护用户前端和真实会话；进程若已改变，不按本表旧 PID 操作。
2. 先评估 R-14 只读报告。报告的「合法 interrupted 后仅一次显式继续」是未实施、未验收的 QA 契约建议。须另行声明单一写入者、精准范围、旧字节／断言保留、新候选和独立验证；原两 strip count 0、完成后笔记、双 ID、held／pending 0、旧锁键 null 及原超时均保留。实际恢复若失败或数据／锁异常，应报告具体产品问题，不能继续借中断语义解释。
3. 回归使用全新系统根、新标签／输出／日志／候选收据，不试跑、重试或过滤掩盖失败。QA-only 变化需核构建输入同源再明示绑定 r17；前端产品变化则先形成可审查修复，请用户手动停止 5174，再完整 check／build／恢复 next-env，请用户手动启动新构建，Agent 不触发被拒生命周期。
4. 原聊天用既有 Node 24、项目 Playwright、`b4-chat.external.config.ts` 执行完整两 spec／14 场景，无 grep／shard／retry／改超时。main 导入前为全新 stream 根设置 test／DATA_DIR／空教材／16333／embedding9、确认 credentials_file=None；只有其它后端确已退出且 8001／8002 空时启动。不要运行会重建或启动 5174 的默认 `test:chat`。原断言／三个替身协议不改，结束后优雅退出自有服务并保留样本。
5. 所有必要验收与适用门禁实际通过、独立复核及保护／资源／文档收口后才关闭 B4。授权止 B4，B5／T90、提交／推送／切分支／部署不执行。

暂停期间不自动执行上述步骤，不创建定时任务，等用户指示。
