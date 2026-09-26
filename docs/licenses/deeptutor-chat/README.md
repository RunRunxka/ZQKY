# 学习问答参考资源与本地改动

本批由用户指定 `C:\Users\96022\Documents\Codex\2026-09-09\wo\outputs\deeptutor-page` 为学习问答视觉参考，读取于 2026-09-09。参考包的 `REFERENCE.md` 标明 DeepTutor v1.6.5 / `42fab3cf429a1fbf36b257ab8d116a3814964202`，本批不修改参考目录。

固定输入 SHA256：

- `src/main.tsx`：`ADEDFC3631C2A875A4739A4D5D95E46B67D333F930C221EE14E7B8D2D02050FA`
- `src/style.css`：`17CD75A0F12102CB85F9D33B513D93391B35F9F41056AB377BE83EBE02D13ACF`

## 使用的资源

| 资源 | 项目内位置 | 来源与许可 |
| --- | --- | --- |
| Thinking-orbs React/Canvas 实现 | `apps/web/src/features/chat/vendor/thinking-orbs/` | 从参考包 vendored 目录复制；MIT；原提交 `3862ffa345217443b63696a8c331a0664eea4b04`，保留目录内 LICENSE 与原作者注释 |
| Geist、Lora 拉丁字体 | `apps/web/public/fonts/chat/` | 参考包随附字体；保留 Geist-OFL.txt、Lora-OFL.txt；仅应用于学习问答，中文使用系统字体回退 |
| 模型品牌 SVG | `apps/web/public/provider-icons/` | 参考包品牌图标目录；识别实际模型 ID，未知使用中性 CPU 图标，不推断代理连接供应商 |
| 页面结构、CSS 与 Lucide 对应关系 | `chat-home.css`、WorkspaceShell、模型选择与消息组件 | 按参考样式重建并适配项目 React/Next 组件；保留 Apache-2.0 原件 `UPSTREAM-LICENSE`；沿用项目已锁定的 Lucide 依赖 |

`THIRD_PARTY_NOTICES.md` 为参考包的原始声明，包含该包其他资源的声明，不表示目标复制了所有品牌或业务实现。智启课源保持自己的名称、蓝色与导航能力，没有复制参考包的 DeepTutor 标志或演示问答存储。

## 目标修改标记

- Thinking-orbs 的原有主题/currentColor/supersampling 改动随源代码保留。
- `theme.ts`：增加对 `html[data-motion="reduced"]` 的监听，与系统减少动画取并集；Canvas 单帧静止，取消监听与帧循环。
- `engine/core.ts`：给兼容上游调用签名的未用参数加单行 Lint 说明，绘制算法不变。
- vendored TypeScript 按目标仓库 Prettier 格式规范化，没有引入新的动画或绘图库。
- 原布局色值改用目标蓝色；目标业务仍使用原 ChatService、模型目录、Zustand 会话与 IndexedDB。未复制参考包的演示 adapter。

进度与验收只维护在 [STATUS](../../STATUS.md)，逐项映射在三矩阵。

> 玻璃主题（`glass.css`、流体背景层）的来源与许可另见
> [玻璃主题来源与许可](../glass-theme/README.md)：那里的 AGPL-3.0 流体文件已整份移除并替换为自研实现，
> 与本文件的参考包资源互不相干。
