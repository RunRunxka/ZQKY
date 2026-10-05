# 下一批提示词缓存核心只读复核

2026-10-05。对象：[B7C 总控启动提示词](../../../design/teaching-loop-v1/B7C_总控启动提示词_20261005.md)。本复核只核 G7 缓存伪代码、文件归属、会话与 foreign 保护、旧夹具调整条款；未修改提示词/产品，没有新增执行或重复测试。

初读 SHA256 `3c99a5865494ef958600b0ef0098ebb39bf9f91afcefde64471da5d6123f29ea`；二次读取时 native finding 标识已由总控修订，当前 SHA256 `7b28de578a0e2352f5bbd648761642d5a40cd02e7bb99c56c77af36e4403cf08`。两个字节版本中的本缓存核心判据相同。以下为该实际版本的复核意见，不预先覆盖以后修订。

## 可执行部分

- normal/write-retry 共用写入闸门，缓存先读，空或完整 identical 自有包才写；正文/metadata/submission 等完整比较，同 context 不代替归属。
- foreign、损坏、不可读禁止本次写入和 HTTP，保留自己的冻结身份与另一原件；仅缓存恢复不自动 HTTP、不打开历史 result。
- G6 ACK/cleanup 独立 oracle 保留；新增 write 闸门改变旧双 in-flight 前置时允许有依据地修构造，不删除核心断言。
- 同一全新 BrowserContext 两 Page 使用真实同源 Storage，明确不是两隔离 Context。
- 不增加锁库/迁移/业务 API；现有 localStorage 非原子边界如实保持，未把原子 CAS 提为新要求。

## 两处应明确

1. `writeOwnedPackage` 中 `prepare` 是注入回调，可在当前实现中抛错，在独立会话边界探针中也可能触发卸载/context 切换。现伪代码只在 `prepare` 前检查会话，接着无条件 `write`，直到写后才检查；应在 `adapter.prepare?.(operation)` 后、`adapter.write(operation)` 前再检查当前会话。retry 的 `isCurrent` 还应包含捕获的失败记录身份与未 busy，前后 guard 使用同一闭包，不只在 verify await 后检查。
2. §1 旧 QA 全只读，§2 E 只列新模块行为测试，§3末又允许修改受影响“原文件/断言”，容易使执行者为旧双 in-flight 夹具写入范围再停下来询问。建议明确：`apps/web` 现有相关测试由 CTRL 登记后由 E 最小调整前置；旧 QA 测试保持原件，只复制到本批新 QA 后改构造，登记原文件 SHA、复制件和差异。ACK foreign 保护判据保持。独立验收者拥有新 QA，原实现者不能改验收 oracle。

上述是提示词可执行性修订建议，不是新增产品 finding，不影响原 G6 ACK 限定关闭。实际产品 finding 仍仅 R-G6-WRITE-OWNER-01，两写入入口同项归因。native/proof/host 交由其他复核者，本复核未签这些部分。

## 最终提示词复核

总控完成两处建议后的实际提示词 SHA256 为 `a97e15bb7d91a249c9020b89a8ca313d51e68ddcf16010a7944cfb317d52a8f0`，本复核只读再次检查：

- `prepare` 后、`write` 前明确再次 `requireSameLiveSession`；原 foreign/完整同包判断与写后校验保持。
- 明确 `apps/web` 现有受影响测试经 CTRL 登记由 E 最小调整前置；旧 QA 全只读，复制到新 QA 后建立新探针，保留旧 SHA 和差异；ACK foreign 不删除的独立 oracle 保持。
- normal/write-retry 共用写入规则、确定性 foreign 不写不 HTTP、完整身份不变、同源两页、非原子 CAS 边界与停止条件没有被削弱。

**缓存核心与旧夹具归属条款：通过可执行性复核。** 保留上方初读记录，最终签核仅覆盖上述实际 SHA 与缓存核心，不转签 native/live 模型能力或产品验收。本次没有重测，也没有修改提示词或产品。
