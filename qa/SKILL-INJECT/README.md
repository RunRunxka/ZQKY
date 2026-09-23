# SKILL-INJECT v1 批次证据

批次：**SKILL-INJECT v1（Skill 注入通道与三个内置教学技能）**，2026-09-23。
起因：用户提问"设置里有 Skill 和 MCP 服务，但是没有任何内容，哪种是必须的"，并要求按评估结论开始实施。

## 1. 起点事实（本批依据，均可从源码复核）

| 位置 | 起点状态 |
| --- | --- |
| `apps/web/src/services/extension-catalog.ts` | 目录条目只有 `{id, kind, name, description, content, enabled}`，存 localStorage `zqky.replica.extensions.v1` |
| `apps/api/app/api/v1/capabilities.py` | `mcp` 与 `skills` 均为 `planned` |
| `apps/web/src/features/chat/model/extensions-snapshot.test.ts:351` | 断言"真实服务不把 extensions 转发给底层 SSE 客户端"——即技能完全不进模型上下文 |
| `apps/api/app/schemas/chat.py` | `ChatStreamRequest` 无 tools/skills 字段 |
| `apps/web/src/features/chat/ChatWorkspace.tsx:649` | `store.send(text, selection)` 只传两个参数，从不构造扩展快照 |

结论：技能注入通道此前不存在，设置里的 Skill 是纯标签。

## 2. 本批做了什么

- 契约与目录：`TurnExtensionSnapshot.skills` 增加可选 `content`（旧快照按原样读取）；新增 3 个内置教学技能预置与 `seedBuiltinSkills()` / `buildTurnExtensionSnapshot()` / `skillTakesEffect()`。
- 注入通道：前端把"已启用 + 正文非空"的技能转成 `skills` 下发；后端 `app/services/skill_context.py` 拼装为**一条前置 system 消息**，唯一收口在 `apps/api/app/api/v1/chat.py`。
- 发送接线：`ChatWorkspace.submit` 发送即从目录冻结技能快照，重试沿用原快照。
- 口径校正：`capabilities` 中 `skills` 由 `planned` 改为 `ready`（仅提示词级）；`mcp` 保持 `planned` 并写明"不连接、不检测、不执行"；设置页 Skill/MCP 分区文案分别改为真实生效 / 未实现。

## 3. 工程检查（实跑）

| 检查 | 结果 |
| --- | --- |
| `npm run typecheck` | 通过 |
| `npm run lint`（`--max-warnings=0`） | 通过，0 警告 |
| `npm run test:unit` | **47 文件 / 367 例通过**（基线 46/353，净增 14） |
| `npm run build` | 通过，`BUILD_ID = cnodHanXs1xNpzQww6yCO` |
| `apps/api` pytest（`.venv/bin/python -m pytest`） | **191 例通过**（基线 181，净增 10） |
| e2e `settings.spec.ts` + `replica-settings.spec.ts` | **2 passed**（首轮 1 failed：`保存模拟配置` 按钮文案断言，按本批文案变更同步并加注；另新增内置技能载入的浏览器断言） |
| e2e 聊天组（`chat` / `chat-composer` / `chat-composer-boundaries` / `chat-home` / `chat-deeplink` / `chat-message-locate` / `chat-source-links` / `sidebar-chat-fixes`） | **44 passed**（本批改了 `ChatWorkspace.submit` 的发送路径，用既有断言证明无扩展时请求形态与交互不变） |
| 全量 e2e（168） | **未执行**（只跑与本批改动相关的 9 个 spec，共 46 例通过） |

## 4. 真实服务验证（DeepSeek Flash，本机 127.0.0.1:8000）

脚本 `real-service-verify.py`，完整输出 `real-service-output.txt`。同一模型档案、同一提问，只差是否携带 `skills`：

- **A 决定性探针**——探针技能要求"第一行必须原样输出「【技能已生效】」"：
  - `A1-无技能`：正文无标记（判定 True）；
  - `A2-带技能`：首行出现该标记（判定 True）。
- **B 产品级对比**——内置「教案规范」技能 vs 不启用，提问为《荷塘月色》第 1 课时教案骨架：
  - `B1-无技能`：模型自拟栏目，缺少 `核心素养目标 / 教学设计 / 练习与作业`；
  - `B2-启用教案规范`：`课题 / 总课时 / 课型 / 核心素养目标 / 教学重、难点 / 教学设计 / 教学过程 / 练习与作业 / 教学反思` **栏目齐备**；且遵循了技能里的"环节名称 · 时长""时长合计与总课时一致"（合计 40 分钟）与"教学反思待授课后补充"。

**已验证**：技能说明确实进入模型上下文并改变输出结构。
**同一批的边缘观察（记录备查，非本批缺陷）**：首次以 `maxOutputTokens=3000` 请求 B 时命中既有 R-13 现象——推理内容耗尽预算、零正文并返回 `EMPTY_RESPONSE`；提高到 16000 后正常。R-13 仍是未关闭项。

## 5. 本批明确未做（不得据此声称已实现）

- MCP 连接、检测与工具调用：不做，后端无 tool 循环，`capabilities.mcp` 保持 `planned`。
- DeepTutor 式逐轮扩展选择器：`features/chat/ExtensionPicker` 仍未挂载到输入区；本批为"已启用技能对所有问答自动生效"。
- `ExtensionEntry` 结构扩展（学科标注 / MCP transport 等）：不做预留字段。
- 内置技能质量未经教研评审：三条技能内容为产品口径初稿（教案栏目对齐 `assets/templates/source/teacher-standard.docx`），需要老师试用后再迭代。
- 未跑全量 e2e（168）与动画矩阵；未在移动真机验证。
