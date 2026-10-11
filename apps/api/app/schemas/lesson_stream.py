"""教案流式生成请求模型（C3-3）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LessonStreamRequest(BaseModel):
    """逐模块生成教案候选文本（不落库；教师保存才写入编辑草稿）。

    - ``analysisRunId`` 可选：提供时读取该学情报告的匿名聚合作为固定数据；
    - ``selectedKnowledgePointIds`` 可选（≤50）：按知识点名补充上下文；
    - ``modules`` 可选：默认全部七模块。
    """

    requestId: str = Field(min_length=1, max_length=128)
    modelProfileId: str = Field(min_length=1, max_length=128)
    courseName: str = Field(default="", max_length=200)
    requirements: str = Field(default="", max_length=4000)
    analysisRunId: str | None = Field(default=None, max_length=128)
    selectedKnowledgePointIds: list[str] = Field(default_factory=list, max_length=50)
    modules: list[str] = Field(default_factory=list, max_length=8)


__all__ = ["LessonStreamRequest"]
