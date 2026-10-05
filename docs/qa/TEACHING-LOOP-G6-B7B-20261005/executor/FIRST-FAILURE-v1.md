# 首完整作者轮

self-check-first：真实 PID 6132，3801.87ms，exit1，30 passed、20 setup error。SHA 前后零漂移，原 stdout/stderr/COMMAND/guard 保留，不能与后轮合并。

20 errors 是 offline guard 拒绝 Windows stdlib socket._fallback_socketpair 为 asyncio 创建 self-pipe 的回环内部连接；尚未进入生产固定来源/SQL，禁止正式.env/库与未隔离 main 均0。网络 guard 原拒绝次数20保留，不追改为0。

修订只允许调用栈确认为 socket._fallback_socketpair 且直接来自 asyncio._make_self_pipe 的内部对，并单独计数；其余 Provider/TCP/DNS仍拒绝。新完整轮独立记录，不拼旧30。
