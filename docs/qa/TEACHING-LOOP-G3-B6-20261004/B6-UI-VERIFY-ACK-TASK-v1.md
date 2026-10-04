# B6-UI-VERIFY-ACK v1

2026-10-04，ROOT，负责人g3_impl、独立g3_v00。依赖browser-r8完整首败与真实trace的只读分类；产品530005e…/LkFgY8qsEnCOUbC11Dm1T保持STOP。

r8收集严格1条，元数据真实迟交→ready报告与单KP→模型/分类/loading恢复已到达，但整例90s失败，等待生成POST未收到，不能计通过。初步迹象是点击“核验教材切片”后马上读取固定题，取消尚未完成的核验。只有原trace与UI确证该正常ownership顺序后才适配；不同原因或产品缺陷先报告。

可写范围仅own `b6-integration/five-fields.spec.ts`，在点击核验后等待既有UI实际成功状态，按现有真实文案/role等待；不伪造业务响应或证据，不加任意sleep、skip、retry、全局timeout，不改产品，不减弱完整来源/字段/分钟/历史/六字段断言。先保存r8原spec/SHA、完整错误原件/trace/图及真实请求序列，单列核验200与前端adoption/取消、生成POST0边界。QA STOP后新r9完整单轮1条，不能把r8元数据半链与r9拼绿。自有CLI/浏览器按本人生命周期关闭、全部TEMP保留。
