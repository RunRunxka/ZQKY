"""Isolated real FastAPI for teaching-loop browser tests; never loads user credentials.

Run from apps/api:
  uv run uvicorn teaching_loop_backend:app --app-dir ../../tests/fixtures --port 8001

ZQKY_DATA_DIR must be an absolute path beneath the OS temporary directory and
ZQKY_ENV must be test. ZQKY_TEST_GENERATION=1 enables a controlled model Provider;
all business routes, four catalogs, jobs, review and confirmation remain real.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any


def require_isolated_data_dir() -> Path:
    """Refuse unsafe configuration before importing app.main's default assembly."""
    raw = os.environ.get("ZQKY_DATA_DIR", "")
    if not raw or os.environ.get("ZQKY_ENV") != "test":
        raise RuntimeError("Browser fixture requires explicit ZQKY_DATA_DIR and ZQKY_ENV=test")
    candidate = Path(raw)
    if not candidate.is_absolute():
        raise RuntimeError("Browser fixture data root must be absolute")
    resolved = candidate.resolve()
    temporary = Path(tempfile.gettempdir()).resolve()
    repository = Path(__file__).resolve().parents[2]
    if (
        resolved == temporary
        or not resolved.is_relative_to(temporary)
        or ".local-data" in (part.lower() for part in resolved.parts)
        or resolved.is_relative_to(repository)
    ):
        raise RuntimeError("Browser fixture refuses non-temporary or production data root")
    return resolved


# This check must precede every import that can transitively import app.main.
require_isolated_data_dir()
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

from fastapi import FastAPI  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.core.secrets import SecretStore  # noqa: E402
from app.main import _build_executor_registry, create_app  # noqa: E402
from app.providers.llm.base import FINISH_STOP, LLMConfig, LLMResponse  # noqa: E402
from app.repositories.knowledge.points import (  # noqa: E402
    KnowledgePointRepository,
    SubjectRepository,
)
from app.schemas.model_config import (  # noqa: E402
    ApiFormat,
    ModelConnection,
    ModelProfile,
    ModelProtocol,
    now_utc,
)
from app.services.model_runtime import ChatModelHandle  # noqa: E402
from app.services.question_bank.service import build_question_bank_service  # noqa: E402

PROFILE_ID = "teaching-browser-profile"
CONNECTION_ID = "teaching-browser-connection"
POINT_CODE = "F10-RATIONAL"
GENERATED_STEM = "计算有理数 (-2) + 5 的结果。"


class ControlledGenerationProvider:
    """Records actual model calls and waits for an explicit test release."""

    def __init__(self, point_id: str) -> None:
        self.point_id = point_id
        self.calls: list[dict[str, Any]] = []
        self.gate: asyncio.Event | None = None
        self.released = False
        self.failures_remaining = 0

    async def complete(self, config: LLMConfig, request: Any, *, transport: Any = None) -> LLMResponse:
        self.calls.append({"profileId": config.modelProfileId, "modelId": config.modelId})
        self.gate = asyncio.Event()
        if self.released:
            self.gate.set()
        await self.gate.wait()
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise AppError('受控模型首轮故障；请通过公共任务接口显式重试。',
                           code='CONTROLLED_PROVIDER_FAILURE', status_code=502)
        return LLMResponse(
            text=json.dumps({"questions": [{
                "type": "short_answer",
                "stemMarkdown": GENERATED_STEM,
                "options": [],
                "answer": {"choiceKeys": [], "accepted": None, "textMarkdown": "3"},
                "explanationMarkdown": "从 -2 向正方向移动 5 个单位，得到 3。",
                "knowledgePointIds": [self.point_id],
                "evidenceIds": [],
                "assetIds": [],
            }]}, ensure_ascii=False),
            finishReason=FINISH_STOP,
        )

    def release(self) -> None:
        self.released = True
        if self.gate is not None:
            self.gate.set()


def create_fixture_app(*, enable_question_generation: bool | None = None) -> FastAPI:
    require_isolated_data_dir()
    settings = replace(
        Settings.from_env(),
        credentials_file=None,
        textbook_source_dir=Path(os.environ["ZQKY_DATA_DIR"]) / "no-textbooks",
        qdrant_url="http://127.0.0.1:16333",
        embedding_base_url="http://127.0.0.1:9",
    )
    secret_store = SecretStore()
    application = create_app(settings, secret_store=secret_store)
    enabled = (
        os.environ.get("ZQKY_TEST_GENERATION") == "1"
        if enable_question_generation is None
        else enable_question_generation
    )
    if not enabled:
        return application

    timestamp = now_utc()
    repository = application.state.model_config_repo
    repository.create_connection(ModelConnection(
        id=CONNECTION_ID,
        displayName="隔离浏览器模型（受控替身）",
        protocol=ModelProtocol.openai_chat,
        # 2026-10-08：题库 AI（整理/补题）云端限定落地后，受控替身必须按**云端**档案装配，
        # 否则前端闸门与后端 422 QUESTION_MODEL_NOT_CLOUD 会把补题入口整个禁掉；
        # 真实调用仍由注入的受控 Provider 处理，地址不会被访问。
        providerId="openai",
        apiFormat=ApiFormat.openai_chat,
        baseUrl="https://fixture.invalid/v1",
        createdAt=timestamp,
        updatedAt=timestamp,
    ))
    # 云端供应商按"已保存凭证"判定可调用（model_readiness.callable_state）；
    # 夹具在内存存储里放一把明显是替身的 Key，不触网。
    secret_store.put(CONNECTION_ID, "fixture-key-not-a-secret")
    repository.create_profile(ModelProfile(
        id=PROFILE_ID,
        connectionId=CONNECTION_ID,
        displayName="隔离补题模型",
        modelId="teaching-browser-model",
        purpose="chat",
        maxOutputTokens=2048,
        createdAt=timestamp,
        updatedAt=timestamp,
    ))
    repository.mutate(lambda document: setattr(document, "defaultChatProfileId", PROFILE_ID))

    with application.state.knowledge.write_transaction() as connection:
        SubjectRepository().ensure_subject(connection, subject_id="math", name="数学")
        point = KnowledgePointRepository().create_point(
            connection, subject_id="math", code=POINT_CODE, name="有理数",
        )
    provider = ControlledGenerationProvider(point.point_id)
    handle = ChatModelHandle(
        profile_id=PROFILE_ID,
        model_id="teaching-browser-model",
        provider=provider,
        config=LLMConfig(
            protocol=ModelProtocol.openai_chat,
            baseUrl="https://fixture.invalid/v1",
            modelId="teaching-browser-model",
            apiFormat=ApiFormat.openai_chat.value,
            # 与连接同口径：云端供应商，后端闸门才会放行（不是本机档案）
            providerId="openai",
            connectionId=CONNECTION_ID,
            modelProfileId=PROFILE_ID,
        ),
    )

    def resolver(profile_id: str) -> ChatModelHandle:
        if profile_id != PROFILE_ID:
            raise RuntimeError("Unexpected model profile in browser fixture")
        return handle

    # Only the model port is replaced. Keep the real domain catalog/coordinator,
    # shared engine and its original-lease publishing and confirmation behavior.
    service = build_question_bank_service(
        application.state.question_bank,
        settings,
        model_resolver=resolver,
        knowledge_catalog=application.state.knowledge,
        coordinator=application.state.publication_coordinator,
        job_engine=application.state.job_engine,
    )
    application.state.question_bank_service = service
    _build_executor_registry(application)

    @application.get("/__test/generation", include_in_schema=False)
    async def generation_stats() -> dict[str, Any]:
        return {
            "pointId": point.point_id,
            "pointCode": POINT_CODE,
            "profileId": PROFILE_ID,
            "providerCalls": len(provider.calls),
            "calls": provider.calls,
            "released": provider.released,
            "failuresRemaining": provider.failures_remaining,
        }

    @application.post("/__test/generation/release", include_in_schema=False)
    async def release_generation() -> dict[str, bool]:
        provider.release()
        return {"released": True}

    @application.post("/__test/generation/fail-next", include_in_schema=False)
    async def fail_next_generation() -> dict[str, int]:
        provider.failures_remaining = 1
        return {"failuresRemaining": 1}

    return application


app = create_fixture_app()
