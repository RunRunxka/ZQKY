# G3 最终源码影响核查 v1

时间：2026-10-04T13:46:25.906123+08:00。负责人：`/root/g3_impl`。任务 `G3-FINAL-SOURCE-v1`；产品保持 STOP。本次仅只读散列/范围核查，没有重跑测试、起服务或改权威文档。

实际分支/HEAD为`main@6cb6a40db890390f0261d547213e319040f64785`。以 [开工基线](../BASELINE-v1.json) 和 [r2-qa5](../CANDIDATE-G3-r2-qa5.json) 为依据，独立逐文件核现行941源码：候选漂移0；相对开工938源码仅3产品变化、3作者测试新增、删除0。不能据Git未跟踪标记把既有B0～B5文件当作本批新增。

## 三份产品与作者 r2 结果精确一致

| 文件 | 当前 SHA256 | r2 一致 |
| --- | --- | --- |
| `apps/web/src/features/lesson-plan/model/useServerPersistence.ts` | `4cb06c213e8a07091a510d5697e3207d373d657704274e81d9d5b943c2d1d961` | 是 |
| `apps/web/src/features/lesson-plan/components/DocumentsPanel.tsx` | `d766b73ff2852432cdd3883f236935959fd7ddd3c779b11aee388985d2e99e45` | 是 |
| `apps/web/src/features/lesson-plan/components/SourcePanel.tsx` | `1452e19a77d12e843c1064283ec12d72e7ec573996b18f5d0a6a6deb0d0d2e95` | 是 |

参见 [作者 RESULT-v2](RESULT-v2.json) 与本记录 [JSON](G3-FINAL-IMPACT-v1.json)。三处修复只影响教案保存/放弃、历史复制和来源异步所有权；HTTP载荷、后台协议、迁移与导出实现未变化。

## 门禁适用性

- **14 聊天：本批未执行，按最终变更范围无需追加重跑。** 公共 navigation-guard、布局/WorkspaceShell、chat及其传输/协议均逐字节未变；本批改变的教案离开行为由新增真实延迟导航与重构建后的原完整153门禁验证。原14属于历史结果，不能算本批新跑。若共享代码后改，须重新评估。CV01～03继续保留，不据此宣称全站视觉通过。
- **后台：410文件与原成功运行精确同源绑定足够支持不机械重复完整API。** 本次重新逐文件核410后台/依赖/脚本/模板漂移0，33冻结契约漂移0；源码范围中的API/DDL/导出也无变化。原1918通过/1既有重型规模skip和独立42按 [原绑定](../ctrl/G3-API-UNCHANGED-BINDING-v1.json) 引用，不冒称本批重跑。新影响仍需真实FastAPI保存/读取/历史浏览器验收，不能用同源绑定替代。
- **必需新门禁仍由ROOT与独立验收者收口。** 本卡不以源码散列或原后台绿宣称G3关闭。完整153新运行已由ROOT记录，本作者本次未重跑；此前首败、间歇台账、QA各版保留。正式Qdrant/迁移/超基线压力、真实模型与教师内容质量不由本核查推断通过。

## 资源与停止

本卡没有监听PID、浏览器或SQLite句柄；只写上述新JSON/Markdown证据，产品、旧QA、契约、next-env与Git未写。完成后 STOP，等待CTRL独立签核和后续B6任务卡。
