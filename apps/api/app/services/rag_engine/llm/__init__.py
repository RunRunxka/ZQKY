"""P7 本地讲解生成层：运行时、提示词、生成缓存（docs/SCHEMA.md §十）。

模块：
  - local_generator   LocalOllamaGenerator（Ollama 回环 /api/chat）+ MockGenerator
  - prompts           PROMPT_VERSION / OUTPUT_SCHEMA / build_messages / build_evidence_pack
  - generation_cache  GenerationCache（键含模型身份，mock 与真实命名空间物理隔离）
"""
