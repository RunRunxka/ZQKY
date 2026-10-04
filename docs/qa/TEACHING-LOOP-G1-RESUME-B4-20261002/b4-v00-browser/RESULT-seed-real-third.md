# B4-F-SEED real-third v1

单轮新种子通过，exit0，1561ms，子 PID25548 自然退出。仅种子一次，不包含浏览器或监听服务验收。

新样本：`C:\Users\96022\AppData\Local\Temp\zqky-b4-v00-a58xyb5t\browser-seed.json`，SHA256 `a4a5fbcac0688746c364d360fa520549814701cf96a7d45ffe697079b1419a36`；四库与受管字节保留在同根 data。旧 real-second 样本未读写修改，所有临时目录保留。

绑定稳定 CANDIDATE-b4-r9-owner-fixed.json：`ba5f0470d7ee7503e384cb68a39a9fdbf47a83745f54e9a9e96aa70feab739ba`。前/后 audit 分别192/195ms，各 exit0，878产品、40可执行QA、5契约均零漂移，next-env原字节匹配。完整审计命令及stdout/stderr分别见 audit-seed-real-third-before/after-command.json 和对应日志。

真实入库的正式题 status=confirmed、owner=local-user。种子直接读取运行时 application.state.question_bank_service.owner_id 插入，因此该owner为运行时题库服务值；PracticeService 的同值注入由冻结 main.py 第341行 `question_owner_id=app.state.question_bank_service.owner_id` 及构造器赋值证明。本轮没有退出后再次启动应用或运行第二次owner探针。

五类B4表实际各0；paper_source_blocks实际27。初种子真实HTTP固定卷图片GET200，完整PNG74字节、SHA `868959b7a3619404d2e010a19cf7a723691dd12f1d5b20a46c805ae9b388ce5b`、image/png全部原assert通过。四库只读 integrity_check均ok、foreign_key_check均0，所有只读连接关闭。

seed-real-third-command.json 保留真实子命令、环境、UTC开始/结束、PID、1561ms/exit0和临时根，原stdout/stderr不覆盖；同名RESULT JSON另存外层完整命令与原始工具输出。全部源继续停写。浏览器未执行，等待CTRL自有8001启动及明确放行；没有启动/停止服务、删除、Git或构建操作。

