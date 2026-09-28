# model-settings 模块约定（模型与连接）

先读根 `AGENTS.md`。在 `/settings` 的「模型与连接」面板中提供真实连接/模型管理；
学习问答顶栏的模型选择器复用本模块目录。**凭证只存后端，前端只见状态。**

## 结构与职责

- `ModelSettingsPanel.tsx`：设置页主面板（连接卡片 → 详情 → 模型目录/参数）。
- `ConnectionForm.tsx` / `NewConnectionForm.tsx` / `ConnectionDetail.tsx`：连接编辑与详情。
- `ProviderCard.tsx` / `ProviderPicker.tsx` / `ProviderMark.tsx` / `ModelBrandIcon.tsx` / `provider-icons.ts`：供应商卡片与图标。
- `ModelSelector.tsx` / `ModelListPicker.tsx`：聊天顶栏模型选择与列表。
- `AuthPanel.tsx` / `ProfileForm.tsx` / `TestResult.tsx`：认证、模型 profile、连接测试。
- 数据：`useModelCatalog.ts` / `useProviderDirectory.ts` → `services/model-settings-api.ts` → 后端 `apps/api`。
- 类型：`contracts/model-settings.ts`。

## 关键不变量

- **契约分层**：供应商身份、认证方式、API 格式、模型参数分层；`providerId` 落库，旧连接缺字段按原 protocol 映射
  custom，不猜供应商/不改 URL/ID/默认引用。不新增 `isCustomProvider` 布尔混合类型与 URL 编辑状态。
- **凭证边界**：API Key 只经服务端 secret store；前端不持久化、不进 Git/日志/截图。OAuth/本机认证有专门
  服务端生命周期，不当普通 API Key 下拉。
- **发现与推理**：发现返回 upstream/catalog/manual 来源；认证/网络失败不吞成空列表或回退静态候选。
  reasoningEnabled 三态与 reasoningEffort 独立；reasoningStyle 只读派生、不写入、不落库。
- **真实验收分开**：连接/模型配置 CRUD 与真实供应商流式验收分开记录；除 DeepSeek 指定场景外，
  多数注册项无独立真实通过证据（见 `docs/CURRENT_STATUS.md` R-13 台账）。

## 修改后必测

`typecheck`/`lint`/`test:unit`（ModelSettingsPanel 单测）；e2e 跑 `model-settings.spec.ts`、
`model-settings-nesting.spec.ts`、`replica-settings.spec.ts`；改动契约另跑 `test:api`。
