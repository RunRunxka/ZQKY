# G2 公共契约 v1

冻结：2026-10-03，负责人CTRL。本文件是本批实施协议，尚不等于业务已验收。开工来源及差异见[基线](ctrl/BASELINE.json)。

## 练习保存

PATCH /api/v1/practice-sets/{id}/draft 必须提供 submissionId（1～128字符）、expectedRevision≥0、items 与 constraints；Python snake_case、HTTP/TS camelCase。返回现有 PracticeSetView 和 replayed。operation 为 practice.draft:{practiceSetId}，身份另含owner；同原包查询成功receipt先于当前CAS/state/外部事实预检，同身份异包409 SUBMISSION_CONFLICT；新的操作旧CAS409 REVISION_CONFLICT/details.currentRevision。PublicationCoordinator内再查，业务及receipt同teaching事务，不新增库或表。

兼容决策：本批不支持无submissionId的旧保存请求，缺字段明确422。不存在短期无ID分支或延期；已有CAS仍约束新的逻辑操作，不能用新CAS重写来冒充原包恢复。现行业务测试种子显式添加每次逻辑操作的新ID；冻结历史QA不改、旧结果不套新契约。内部审核采用纯items内容验证，不构造假提交命令。

## 前端操作与回执

共享 FrozenSubmission 保留 submissionId/payloadKey/payload，兼容新增 metadata={contextKey,originalEditGeneration,loadGeneration}。submitWithReceipt(payload,run,metadata) 返回 {result,operation,current} 或null；metadata及深复制payload仅首次冻结，unknown重试复用全部原值。current仅指hook当前挂载/观察代次；调用者另核对象与load身份、单调服务器revision和固定revisionId。旧submit仍仅返回当前有效结果，现有调用保持兼容。

recoverFrozen(operation) 用于从模块严格校验的恢复缓存恢复unknown原操作，不能自动发送。HTTP调用前模块同步保存恢复包；缓存失败用明确错误阻止发送。服务器基线只能前进；相同revision不同固定身份也不得hydrate或清dirty。新输入/撤销重做只确认原编辑代次，未保存新输入保持dirty。

## 离开与恢复

CTRL提供 NavigationGuardProvider/useNavigationGuard：register(contextKey, async()=>boolean)返回注销函数；requestNavigation(action)先审全部已注册会话，false/错误不执行action，同一时刻只处理一次导航。WorkspaceShell侧栏/品牌及模块GuardedLink用同接口；模块内部对象/历史切换也处理自己的会话。兼容无Provider的独立旧模块调用。

练习按practiceSetId独立缓存，当前草稿和固定历史身份分开。提供取消、保存成功后离开、成功写恢复缓存后保留稿离开、明确放弃；pending/unknown不得当作已保存或直接放弃。保存失败/409/422/unknown留原上下文。浏览器Back/刷新/关闭有恢复保护，坏缓存/读取失败暂停覆盖。只使用隔离上下文，不读真实草稿；缓存metadata保留首次loadGeneration，重新挂载不冒充首次ACK。
