"""题库仓储（RAG-REBUILD v1.0 · B3）：独立 SQLite 权威层与只读记录类型。

``QuestionBankService`` 定义在服务层（``app.services.question_bank``），这里按
任务卡要求一并导出：用模块级 ``__getattr__`` 延迟导入，避免仓储包与服务包互相
导入形成循环。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.repositories.question_bank.catalog import QuestionBankCatalog
from app.repositories.question_bank.records import (
    DraftInput,
    DraftRecord,
    ImportRecord,
    JobRecord,
    QuestionRecord,
    SourceBlockInput,
    SourceBlockRecord,
    SubmissionRecord,
    SuggestionInput,
    SuggestionRecord,
)

if TYPE_CHECKING:  # pragma: no cover - 仅供类型检查
    from app.services.question_bank.service import QuestionBankService

__all__ = [
    "DraftInput",
    "DraftRecord",
    "ImportRecord",
    "JobRecord",
    "QuestionBankCatalog",
    "QuestionBankService",
    "QuestionRecord",
    "SourceBlockInput",
    "SourceBlockRecord",
    "SubmissionRecord",
    "SuggestionInput",
    "SuggestionRecord",
]


def __getattr__(name: str):
    if name == "QuestionBankService":
        from app.services.question_bank.service import QuestionBankService

        return QuestionBankService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
