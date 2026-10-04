# B4 shared foundation v1.2 · 收口规则

此补录仍属于实现阶段，独立验收以最终冻结清单为准；原 v1/v1.1 与首败日志保留。

1. 原卷未记录题型时，T70 `originalQuestionContents` 保留缺失/null，不填 `other`。T80 仅在原题排除比较阶段把该条未知题型展开为正式六种合法题型，或用候选的实际题型计算现有 `question-surface-v1`；已知题型严格比较。此规则不回写原题事实，富题面、共同材料、选项仍完整参与指纹。
2. Practice 树节点新增 SQLite 递归祖先环检查；报告备注的目标知识点须出现在该 run 的固定结果中。备注保持独立追加，不能改 ready 报告。
3. `Settings.from_env()` 在 `ZQKY_ENV=test` 时直接令 `credentials_file=None`，确保间接导入 `app.main` 前的隔离配置也不保留正式凭证路径。此前迁移自检只导入配置/装配，没有进入正式凭证读取的 lifespan；本次修正后 foundation/config 单轮 13 项通过，首轮记录不改写。
4. 导出产物下载除资产归属/字节/hash 核验，还要求关联的同 owner 任务处于 succeeded；未完成任务不能暴露成功下载元数据。

共享迁移 0008/0009 的最终 SQL/hash 在候选冻结时登记。原 0001～0007 声明与散列保持。
