"""题库服务：拆题、校对、AI 建议与幂等确认入库。

模型语义（RAG-QUALITY v1.1，唯一一套）：题库「AI 整理」使用**点击时的当前聊天模型，
本地或云端一视同仁**；``OrganizeRequest.modelProfileId`` 是聊天模型 profile id，
解析委托注入的 ``model_resolver``（共享实现 ``services.model_runtime.resolve_chat_model``），
本包不解释 profile id、不列本机模型、没有默认模型回退。

装配（总控在 ``main.py`` 里执行）::

    from app.repositories.question_bank.catalog import QuestionBankCatalog
    from app.services.question_bank import build_question_bank_service

    app.state.question_bank = QuestionBankCatalog(
        settings.question_bank_root / "question-bank.sqlite3"
    )
    app.state.question_bank.migrate()
    app.state.question_bank_service = build_question_bank_service(
        app.state.question_bank,
        settings,
        model_resolver=_build_model_handle_resolver(app),  # (profileId) -> ChatModelHandle
    )

未装配 ``model_resolver`` 时 ``organize`` 返回 503 ``SERVICE_UNAVAILABLE``（可重试），
不建任务、不发上游；未装配服务时题库路由同样 503，不返回空列表或假成功。
"""

from app.services.question_bank.organizer import (
    MAX_BATCH_INPUT_CHARS,
    MAX_OUTPUT_TOKENS,
    Batch,
    ChatModelResolver,
    pack_batches,
)
from app.services.question_bank.service import (
    QuestionBankService,
    build_question_bank_service,
)

__all__ = [
    "Batch",
    "ChatModelResolver",
    "MAX_BATCH_INPUT_CHARS",
    "MAX_OUTPUT_TOKENS",
    "QuestionBankService",
    "build_question_bank_service",
    "pack_batches",
]
