# G3-BOUNDARY-v1 第三人边界审核

2026-10-04：审核准备完成，尚未执行候选验收。

- [审核条件](AUDIT-CONDITIONS-v1.md)：正文/缓存/服务端写入、可信基线、历史复制与只读 B6 剩余映射。
- [手写全字段探针](session-boundary.test.tsx)：5 个独立行为场景，针对真实服务端 persistence hook 和本地 writer；预期不使用生产合并逻辑。
- [独立配置](vitest.config.ts)：隔离 jsdom，执行必须带 `NODE_OPTIONS=--no-experimental-webstorage`。

执行状态：`not_run`。原因：产品实现尚在写入，等待 CTRL 稳定候选与停写通知，不在实现边写时验收。新业务、服务、浏览器、旧额外 HTTP 身份检查、真实 Provider、正式数据库、Git 均未启动。

待执行命令（不是已执行证据）：

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
npm.cmd run test:unit -- --config docs/qa/TEACHING-LOOP-G3-B6-20261004/boundary/vitest.config.ts --reporter=verbose
```

后续仅新增本目录结果与候选绑定收据；旧首败、旧通过原件和 B5-r8 保持。
