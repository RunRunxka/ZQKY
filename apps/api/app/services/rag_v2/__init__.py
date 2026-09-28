"""RAG v2：严格范围检索、原文证据重建、本地知识点首答与所选模型详解。

模块分工（子模块之间只做单向 import，避免环）：

- ``scope``       范围解析 / 使用前核验 / 允许集合过滤（SQLite 权威）
- ``retrieval``   稠密（Qdrant，带 filter 下推）+ BM25（SQLite 允许块）+ RRF 融合
- ``source_text`` 不可变规范化文本读取与来源定位（只读复用 B1 能力）
- ``evidence``    邻块扩展、证据重建与预算取舍
- ``summary``     本地 Ollama 知识点首答（结构化 JSON，只概括已核验原文）
- ``explain``     所选聊天模型详解（上游文本增量，普通聊天 SSE 语义）
- ``requests``    v2 HTTP 请求模型（未知字段 422）
- ``presenter``   把结构化结果渲染成人类可读正文
- ``service``     有界、可恢复的会话服务（事件编号、续传、显式取消）

不变量：范围先于排序；原文不可变；失败不伪装成功（服务不可用绝不变成"没有匹配"）；
聊天题目与详解历史不在后端落盘或记录日志。
"""

from app.services.rag_v2.service import RagV2Service

__all__ = ["RagV2Service"]
