# R14-QA v1.1 · 作者准备结果（2026-10-03）

两执行源ready并停写。仅修改原spec目标双书case及新增helper；没有book生产源码、其它QA或服务生命周期改动。独立审查／真实两分支／原全量153／聊天14均未执行，等待正式卡，不称验收通过。

helper SHA cb6407c8045c35dc0ae54915c9854b0ab9275b17f9654ef3aa9dbfedfee0a072；spec SHA b36e6b41fa441a0972d172b632464b085561e0afdb6546d0b88475e8ceae27f9。已精确绑定r18两源（完整候选4ea85c1190c35daa201ea289734b142c2d1e4b437bf73ee127ced4c9c2c08832）；本作者报告没有新跑全量清单审计。

新单轮strict noEmit TypeScript＋AST：PID5324／exit0／720.9081ms，diagnostics空；限定两文件ESLint：PID1184／exit0／1019.6367ms，stdout/stderr真实0字节。完整argv、stdin、起止、原始双流和SHA保留在两个v11-first-command.json及对应stdout/stderr.log，不复用v1自检冒充本版。

源边界证明：原6标题一致；其它5个完整case字节相同，module在删除唯一新import、移除目标case后前后两段字节相同；原top functions全文相同。49个原expect全文全部保留，当前52只新增两真实ready与成功主体后的资源正向检查；目标9→12。两30000、两120000和总180000保持；原await second.close文本/调用保留。完整diff、每个case SHA与AST输出见JSON。

同步startBookInterruptedRecovery(page,{bookId,pageId,expectedNote,deadline})返回result/cleanup。deadline是Date.now绝对毫秒，共享原窗口。result仅在真实stored status ready且strip0后resolve，提供normal/recovered、实际browser Continue click计数、note与完成时刻。精准compiling/interrupted/唯一可见enabled Continue且准确保存note后，至多一次Playwright UI click；paused、book error、缺书/损坏、恢复拒绝、再次中断拒绝。正常中间提交边界仅等，不伪造ready；没有sleep/reload/retry/直接写库。

浏览器只读MutationObserver、storage、zqky:books、click capture与有界deadline timer。cleanup幂等、停止监听并await在途动作/结果、dispose JSHandle；正常ctx给准确0/1，若ctx先销毁读不到最后计数明确null而不补造0。清理详情和失败依据由附件保留。

v1已先封存两源before、PREP-v1与两个原静态收据。CTRL指出v1 finally资源assert可能覆盖主体首败，本版只修此边界：捕获原primary对象；finally完整allSettled观察器清理、原second.close及附件；原主体失败时优先原样throw，secondary写入附件而不替换；资源正向assert仅在主体全部原断言成功后执行。helper与v1逐字同。未以静态成功证明实际恢复有效，也未关闭跨批R14。

完整scope结果pass：True。日志文件已正常关闭，两个自有静态子进程均自然exit0；无服务、浏览器、DB连接或其它活跃资源持有。新source/QA一律停止写入，之后仅可补MD/JSON结果。
