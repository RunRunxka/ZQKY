"""原卷（试卷）服务包：导入拆题、草稿校对、确认入库、AI 知识点建议与已确认读取。

对外入口只有两处：

- ``build_paper_service(...)``（CTRL 装配到 ``app.state.paper_service``）；
- ``PaperService`` 的公开方法（HTTP 路由 ``app/api/v1/papers.py`` 调用）。

内部模块分工：``imports`` 规则拆题（纯函数）、``proposals`` 提示词/解析/执行器、
``reader`` 已确认原卷读取适配器、``service`` SQL 与事务编排。
"""

from app.services.papers.reader import (
    ConfirmedPaperItem,
    ConfirmedPaperReaderAdapter,
    ConfirmedPaperSnapshot,
)
from app.services.papers.service import PaperService, build_paper_service

__all__ = [
    "ConfirmedPaperItem",
    "ConfirmedPaperReaderAdapter",
    "ConfirmedPaperSnapshot",
    "PaperService",
    "build_paper_service",
]
