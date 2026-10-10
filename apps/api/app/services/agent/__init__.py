"""Agent 编排服务：LangChain + LangGraph 内嵌于 FastAPI。

本包是教学闭环的对话式编排层：Agent 复用既有业务服务（名单/原卷/施测/成绩/学情/练习/教案）
作为工具，所有写操作经教师确认后才落库（AI 只进候选红线不变）。

- ``model``：把既有模型配置（连接 + profile + SecretStore 凭证）显式构造为 LangChain 官方
  chat model，**绝不读进程环境变量**（凭证红线 D9 的 Agent 侧落地）。
"""
