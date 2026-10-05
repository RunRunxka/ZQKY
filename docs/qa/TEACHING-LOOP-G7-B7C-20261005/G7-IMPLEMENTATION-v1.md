# G7 实现记录 v1（CTRL/E/R 作者侧）

2026-10-05。候选停止写入时的实现与自检记录。`before` 为开工原字节（`opening-bytes/` 与 `OPENING-v1.json`），`after` 为当前冻结源码。

## G7-A：单一写入归属闸门

| 文件 | before SHA256 | after SHA256 | 变更 |
| --- | --- | --- | --- |
| `apps/web/src/features/lesson-plan/model/useLessonOperation.ts` | `16f38d8348b4dfd57b64b3e0f3374d6770ee936388d128ab4bc1ee1bfdc550b4` | `efaedb3faaf71b2e083f42254102eef51ae6bbc868ad47b76b01e02320e3318b` | 新增 `exactFrozenOperationKey` + `writeOwnedPackage`；正常 `run` 写前调用闸门（失败→HTTP 0、保持原包、阻断并显示原因）；`retryRecoveryWrite` 的 write 分支改为同一闸门 |
| `apps/web/src/features/lesson-plan/g6-cache-owner.test.tsx` | `aeb56be7c3cf58f6ed0c48a82a30e0f97ab151f5695a1d2ac81c1497750a97be` | `8a19239247df5b182f1c0c57ebd74d27800642996295613afe8a8ec356e06b3b` | 两个模板（共 8 例）按 CTRL 登记做最小前置调整：foreign 包隔离构造；B 先在键→A 被阻断 HTTP 0→B 显式重放结束→A 仅完成存储清理 |
| `apps/web/src/features/lesson-plan/g7-write-owner.test.tsx`（新增） | — | `643d0854b1c3abf0f553ed687c20184b662970f46b3e1e2ca15e5d5cdc44dd30` | 新模块行为测试 20 例：create/import × 正常写入/quota 重试/foreign 阻断/自身包重放/坏包/不可读/verify 失败/跨 context/prepare 异常/卸载 |

闸门语义（与伪代码一致）：活会话 → 校验本次操作 → **读取现有包（读失败/坏包不当空）** → foreign 完整包则原字节保持并拒绝 → 活会话 → `prepare`（在确认 foreign 之后才允许改变旁路恢复身份）→ 活会话 → 写 → 读回逐字段核验 → 活会话。cleanup 路径（`clearAcknowledgedPackage`）保持原完整归属判据不变；localStorage 仍非原子 CAS，本批只修确定性顺序写入。

## G7-B：原生页图严格解码

| 文件 | before SHA256 | after SHA256 | 变更 |
| --- | --- | --- | --- |
| `scripts/teaching-quality/trial_result_check.py` | `1367ed17beb2b5d1bc214c297f26c8a70b4f04c25399b0dbe16fd57776972b25` | `8a2d582c1b7b28ac8be6724da56ff1d29fdb41d999091218078fa07abbe795d2` | 新增 `native_page_image`：路径/精确 SHA → 允许扩展名与字节/像素/单边/帧数上界 → 真实解码器 `Image.open`（格式∈PNG/JPEG/WEBP、与扩展名匹配、正尺寸）→ `verify()` → 重开 `load()` 全部帧像素；截断/坏 CRC/伪装/超资源显式拒绝；`LOAD_TRUNCATED_IMAGES=False` |
| `scripts/teaching-quality/tests/test_trial_result_v1.py` | `d42523b5eeebc6675f51d94cff9cdeec12b369f789da242103fe2020724bd610` | `37382026de6a45f81871dfad7ee6c7bca8016b5ac828135f5b94ca80fb4ffd0e` | 专属测试：合法 PNG/JPEG(.jpg/.jpeg)/WebP 正例与多页路径；零字节/8 字节 PNG 头/3 字节 JPEG 头/12 字节 WEBP 头/截断/坏 CRC/扩展名错配/PDF 伪装/超资源全部硬拒且 `field=page.evidence`；1 像素对照改为可解码合成图 |
| `apps/api/pyproject.toml` | `3be6f4248fdfe9b3d8997ca593201ad0f930686eff066f34170fc1ecfade1d7d` | `9d03ac17357a1d2d908301497b18ee202cf78bd46ae9a6bbb4c689c5e97ce8f2` | 新增固定 `pillow==12.3.0`（CTRL 唯一登记，见 `dependency/REGISTER-pillow-v1.md`） |
| `apps/api/uv.lock` | `9bf4f971c66f6d29eca8a986202ac4cccaabcf32387e0076ff33b2405a768688` | `0c0872eb9a76fe46a72717d70380b223020542c357a2c2664aef3ead0177bf3a` | 仅新增 Pillow 12.3.0 条目（+73 行，0 修改/删除；无其他包升级） |

## 作者自检（非独立验收）

- 组件：`g7-write-owner.test.tsx` 20/20；`g6-cache-owner.test.tsx` 83/83；审查者探针 12/12（四项反例转绿）；全量单测 128 文件/1483 通过。
- 旧 QA 回归（G6 审查配置）：131 通过 / 8 失败，8 项全部为已登记前置改变（`REGISTER-affected-G6-fixtures-v1.md` §3），首败原件在 `first-failures/`。
- 页图：专属测试 11 方法全过（含新反例）；`dependency/DEPENDENCY-SELFCHECK-v1.json` 逐项匹配；venv 由 `uv sync` 保持（Python 3.12.14 / PIL 12.3.0），`uv lock --check` 一致。
- 工具/环境：`B7B_R_RUN_DIR` 均指向新 TEMP，正式库/凭据/网络未触碰。

## 边界

页图解码只证“允许格式的完整可解码图像”，不签 Word/WPS 实际打开、内容真实性或排版；顶层 native 仍 pending、`createsNativeApproval=false`。写入闸门仍不宣称排除全部极窄并发竞态。独立验收（非作者）见 `v00/` 下 V-G7-A/B 收据；最终关闭以 `CTRL-CLOSE-v1.json` 为准。
