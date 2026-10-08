"""知识点服务（TEACHING-LOOP B1 / T20；任务①②③ 扩展）。

- ``service``：门面（CRUD/父树/别名/归档/教材依据/表格导入/AI 候选/彻底删除/
  范围过滤/教材提取）与装配工厂；
- ``evidence``：教材证据读取（冻结标题、区间核验、失败 503 不当"没有依据"）；
- ``imports``：表头映射、行规范化、父树校验与确认计划（纯规则 + 只读 SQL）；
- ``suggestions``：AI 候选提示词与回复解析（不被凭证污染的冻结输入）；
- ``references``：跨库引用计数（删除守卫的唯一真实实现）；
- ``textbook_scope``：任教范围解析（scope=taught / gradeId 过滤的唯一真实实现）。
"""

from app.services.knowledge.service import KnowledgeService, build_knowledge_service

__all__ = ["KnowledgeService", "build_knowledge_service"]
