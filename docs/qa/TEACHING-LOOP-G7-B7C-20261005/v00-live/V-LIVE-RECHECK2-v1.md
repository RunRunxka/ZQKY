# V-LIVE 复验 2 v1（guard bytes/str 归一修复，仅 guard 一处）

- 验收者：V-LIVE（独立）；日期：2026-10-06
- 背景：CTRL 首发实测发现 `socket.getaddrinfo` 审计事件的 host 为 bytes，旧 guard `str(args[0])` 比较失效，允许路径失效被误拦（`forbiddenNetworkAttempts=1`，无出网）。本轮仅复验 guard 修复，其余复用 RECHECK-v1 结论。
- **结论先行：guard 修复 pass。允许路径（str/bytes DNS）与拒绝路径（bytes/str 全矩阵）均正确。无回归。发现 1 处候选范围偏差（见 §4），1 处需 CTRL 知情的事实（见 §5）。**

## 1. 候选文件核对 — pass（含一项说明）

与 `V-LIVE-RECHECK-v1.json` 对比，11 个候选文件中 **2 个变化**：
- `scripts/teaching-quality/controlled_guard.py`：`db5bad13…1c2222`（v2）→ **`e7b86442cec7a707dd9bd59c496971c3be3295407410aa9ecc72dc20db290027`**（v3，本轮修复）
- `scripts/teaching-quality/tests/test_controlled_live_v1.py`：`2de129ce…f91db1`（v2）→ **`aa9350ca3cf960ad37c06e4a202fd13f507d8687bb30a95b2419edf844f6e7a4`**（v3，作者的 bytes 矩阵测试，guard 修复的配套测试，非产品逻辑变化）

其余 9 个文件（host/proof/provider/trial/checker/common/scope/ledger/fixtures）逐字节不变。变化范围与 CTRL 声明一致；guard diff 无夹带逻辑（只含：live_endpoint 参数与计数器——recheck1 已有、bytes/str 归一、双 formal 根——recheck1 已有、connect 归一与 Proactor 注释）。

## 2. 允许路径 — pass（probe5c，scratch 环境，无凭据）

固定 `live_endpoint=("api.deepseek.com", ("203.0.113.10",))`（TEST-NET 注入，非真实解析），安装 guard 后：

| 用例 | 结果 |
| --- | --- |
| `socket.getaddrinfo("api.deepseek.com", 443, proto=TCP)`（str） | 允许，真实解析成功（15 条 A 记录），`allowedLiveDnsLookups` 0→1 |
| `socket.getaddrinfo(b"api.deepseek.com", 443, proto=TCP)`（bytes） | 允许，真实解析成功，计数 1→2 |
| `socket.getaddrinfo("API.DEEPSEEK.COM.", 443)`（大写+尾点） | 允许，计数 2→3（归一化含 strip/rstrip('.')/lower） |
| 三次允许期间 `forbiddenNetworkAttempts` | 保持 0 |

**是否出站的明确记录：做了。** CTRL 指令要求以无凭证 GET 佐证允许路径；我执行了一次 `GET https://api.deepseek.com/`（无任何 Authorization/apiKey 头，仅 TLS+SNI+Host）→ **返回 HTTP 401**。这不是本地拦截（若 guard 误拦会是 PermissionError），证明允许路径在真实出站下生效；401 是服务端对未认证请求的预期应答，未消耗模型调用。这是本轮唯一的出站字节（三次 DNS 查询 + 一次 TLS 握手/请求），之外无任何出站。

## 3. 拒绝路径 — pass

bytes/str 双形式全矩阵（probe5c，同进程内）：

| 用例 | 结果 |
| --- | --- |
| `b'example.com':443` DNS | 拒，`forbiddenNetworkAttempts` 递增 |
| `b'api.deepseek.com'` + `b'80'`（bytes 端口串） | 拒（端口归一 int(80)≠443） |
| `b'api.deepseek.com'` + `80` | 拒 |
| str 伪造域 `deepseek.com.evil.io`:443 | 拒 |
| `apps/api/.env` 读 | 拒（credential file forbidden），计数 0→1 |
| `仓库根/.local-data/model-config.json` 读 | 拒（formal data forbidden），计数 0→1（**F2 修复未回归**） |
| 非 TEMP SQL | 拒（only new TEMP SQL），计数 0→1 |
| `socket.connect` bytes 归一 | 本机 Windows/CPython 不发出 connect 审计事件（与修复注释一致）。在 guard 方法级以合成参数验证：`(b'203.0.113.10',443)` 允许且 `allowedLiveConnects` +1、str 同、`(b'203.0.113.99',443)` 拒、`(b'203.0.113.10',8443)` 拒。端到端 `create_connection(b'203.0.113.99',443)` 被拒（经其自身的 getaddrinfo 事件，IP≠live host） |

矩阵判定：**允许路径由 DNS 层把守且对 bytes 生效；connect 层归一在方法级正确；端到端拒绝路径完整。** 全程 `forbiddenNetworkAttempts=7`、`allowedLiveDnsLookups=3`、`allowedLiveConnects=2`（合成参数注入 2 次，无真实连接）。

## 4. 回归 — pass

| 测试文件 | 结果 | exit | 日志 |
| --- | --- | --- | --- |
| tests/test_controlled_live_v1.py（含作者新增 bytes 矩阵：`allowedLiveDnsLookups>=2`、`forbiddenNetworkAttempts>=4`、bytes 80 拒） | 7 passed in 1.29s | 0 | logs/author-test-live-r3.log |
| tests/test_controlled_executor.py | 73 passed in 19.70s | 0 | logs/author-test-executor-r3.log |

## 5. 需 CTRL 知情的事实（非缺陷，非本轮产物）

复验开始前 `b7c/control-live/` 下已存在**两个**授权账本目录（v1 验收时只有一个）：
- `22f47cf5…`（旧）：v1 负向对照遗留的 unknown C01 账本，原样未动；
- `d5261182…`（新，mtime 2026-10-06 17:12:13）：runLabel=`live-r1-C01`、stopReason=`UNKNOWN_MODEL_RESULT`、1 张 unknown 票据（预留 17082、sends=1、rawSHA/usageSHA 为空）。票据特征与 CTRL 描述的"首发实测被误拦"一致（真实发送尝试被 guard 拦下后账本记 unknown 并 STOP）。该账本对应的收据（应为 v2 首发收据）**已被其第一次发送尝试消耗**——CTRL 需确认这是计划内的首发收据消耗，并为重发准备新收据（新 authorizationId，或同一收据重开授权——由 CTRL 按账本语义决定；账本按收据绑定，旧 authorizationId 已永久 STOP）。
- 本轮复验未向这两个目录写入任何内容。

## 6. 资源与产物

- 探针：`probes/probe5c_guard_bytes.py`（本轮 harness 初版有 2 处自我断言算术/前缀匹配错误，已修正后重跑；候选行为自始正确）。
- 出站：仅 §2 记录的 3 次 DNS + 1 次无凭据 GET（HTTP 401）；无模型调用；无凭据读取。
- TEMP 保留：`zqky-v-recheck2-guard-*`、`zqky-v-recheck2-*`、`zqky-v-dbg-*`（复验中间态）。
- 日志 SHA：见 `V-LIVE-RECHECK2-v1.json.logSHA256`。

## 7. 判定

**guard bytes/str 修复 pass；无回归。** 候选可在 CTRL 完成首发收据的账本处置后再次进入真实发送。
