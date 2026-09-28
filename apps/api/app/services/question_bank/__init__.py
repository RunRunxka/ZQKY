"""题库服务（RAG-REBUILD v1.0 · B3）：拆题、校对、AI 建议与幂等确认入库。

AI 整理的模型语义（v1.2 唯一化）：**只用本机 Ollama 的本地模型，绝不调用云端聊天模型**。
``OrganizeRequest.modelProfileId`` 是可选的本地模型名覆盖（省略/空串 → 服务端默认整理模型，
``DEFAULT_ORGANIZE_MODEL``）；调用前用本机 ``/api/tags`` 校验在场，不在场 422
``ORGANIZER_MODEL_MISSING``；profile 标识（UUID）永远不会被当作模型名发给上游。

装配（总控在 ``main.py`` 里执行）::

    from app.repositories.question_bank.catalog import QuestionBankCatalog
    from app.services.question_bank import QuestionBankService

    app.state.question_bank = QuestionBankCatalog(
        settings.question_bank_root / "question-bank.sqlite3"
    )
    app.state.question_bank.migrate()
    app.state.question_bank_service = QuestionBankService(
        app.state.question_bank, settings
    )

未装配服务时题库路由返回 503 ``SERVICE_UNAVAILABLE``，不返回空列表或假成功。
"""

from app.services.question_bank.organizer import (
    DEFAULT_ORGANIZE_MODEL,
    LOCAL_MODEL_POLICY,
    Batch,
    LocalModelCatalog,
    OllamaModelCatalog,
    OllamaOrganizerModel,
    OrganizerCall,
    OrganizerModel,
    match_installed_model,
)
from app.services.question_bank.service import (
    QuestionBankService,
    build_question_bank_service,
)

__all__ = [
    "Batch",
    "DEFAULT_ORGANIZE_MODEL",
    "LOCAL_MODEL_POLICY",
    "LocalModelCatalog",
    "OllamaModelCatalog",
    "OllamaOrganizerModel",
    "OrganizerCall",
    "OrganizerModel",
    "QuestionBankService",
    "build_question_bank_service",
    "match_installed_model",
]
