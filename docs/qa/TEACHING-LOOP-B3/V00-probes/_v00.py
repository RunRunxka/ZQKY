"""V00-G0 探针公共支撑（只读候选；自建，供 V00-probes 各探针复用）。

硬边界：
- 任何 `app.*` 导入前把 ``ZQKY_DATA_DIR`` 指向本次进程的临时目录（不读写正式
  ``.local-data``/``.env``）；模型全部为受控替身；不联网；不占端口。
- 仅写入本目录（``V00-probes/**``）。
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

#: 每个探针进程独立的临时数据根（先设再导入 app.main）
PROBE_TMP = Path(tempfile.mkdtemp(prefix="zqky-v00-b3-"))
os.environ["ZQKY_DATA_DIR"] = str(PROBE_TMP / "default-data")
os.environ.pop("ZQKY_CREDENTIALS_FILE", None)

from app.core.config import Settings  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.providers.llm.base import (  # noqa: E402
    FINISH_STOP,
    LLMConfig,
    LLMResponse,
    LLMUsage,
)
from app.services.model_runtime import (  # noqa: E402
    ChatModelHandle,
    fingerprint_of_handle,
    model_fingerprint,
)

ALLOWED_ORIGINS = frozenset({"http://127.0.0.1:5173", "http://127.0.0.1:5174"})
LOCAL_PROFILE = "chat-model-local"
FAKE_API_KEY = "sk-v00-should-never-be-persisted"

EVIDENCE_DIR = Path(__file__).resolve().parent


def make_settings(data_dir: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8001,
        allowed_origins=ALLOWED_ORIGINS,
        env="test",
        data_dir=data_dir,
    )


class FakeProvider:
    """受控聊天模型替身：固定回复队列、记录调用、可选门闸阻塞。"""

    def __init__(self, replies: list[str] | None = None) -> None:
        self.replies = list(replies or ["{}"])
        self.calls: list[dict[str, Any]] = []
        #: 线程门闸（threading.Event）：置位后每次调用前等待；可从测试线程安全置位
        self.gate: threading.Event | None = None
        #: asyncio 门闸（同事件循环场景）
        self.async_gate: asyncio.Event | None = None
        #: 进入上游前的回调（用于在阻塞前登记"已开始调用"）
        self.before_call: Any = None
        #: 已开始的上游调用（在门闸之前登记；用于"零调用"计数）
        self.starts: list[dict[str, Any]] = []

    async def complete(self, config: LLMConfig, request: Any) -> LLMResponse:
        self.starts.append({"modelId": config.modelId})
        if self.before_call is not None:
            self.before_call()
        if self.async_gate is not None:
            await self.async_gate.wait()
        if self.gate is not None:
            await asyncio.to_thread(self.gate.wait)
        messages = getattr(request, "messages", [])
        self.calls.append(
            {
                "modelId": config.modelId,
                "baseUrl": config.baseUrl,
                "messages": len(messages),
                "profileId": getattr(config, "modelProfileId", None),
            }
        )
        text = self.replies.pop(0) if self.replies else "{}"
        return LLMResponse(text=text, finishReason=FINISH_STOP, usage=LLMUsage())

    async def stream(self, *args: Any, **kwargs: Any):  # pragma: no cover - 不用于本批
        raise NotImplementedError

    def bind_oauth(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None

    def bind_secrets(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        return None


def make_handle(
    profile_id: str = LOCAL_PROFILE,
    *,
    model_id: str = "model-A",
    provider: Any = None,
    base_url: str = "http://127.0.0.1:11434/v1",
    protocol: str = "openai_chat",
    api_format: str = "openai_chat",
) -> ChatModelHandle:
    config = LLMConfig(
        protocol=protocol,
        baseUrl=base_url,
        modelId=model_id,
        apiKey=FAKE_API_KEY,
        apiFormat=api_format,
        connectionId="conn-v00",
        modelProfileId=profile_id,
    )
    return ChatModelHandle(
        profile_id=profile_id,
        model_id=model_id,
        provider=provider if provider is not None else FakeProvider(),
        config=config,
    )


class FakeResolver:
    """``(profileId) -> ChatModelHandle`` 替身；可切换 default、记录调用。"""

    def __init__(self, default: ChatModelHandle | None = None) -> None:
        self.default = default
        self.calls: list[str] = []

    def __call__(self, profile_id: str) -> ChatModelHandle:
        self.calls.append(profile_id)
        if self.default is None:
            raise AppError("模型配置不存在。", code="MODEL_PROFILE_NOT_FOUND", status_code=404)
        return self.default


def emit(name: str, payload: dict[str, Any]) -> Path:
    """把探针观察写入 ``V00-probes/<name>.json`` 并返回路径。"""
    out = EVIDENCE_DIR / f"{name}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def cleanup() -> None:
    shutil.rmtree(PROBE_TMP, ignore_errors=True)


__all__ = [
    "ALLOWED_ORIGINS",
    "API_ROOT",
    "AppError",
    "ChatModelHandle",
    "EVIDENCE_DIR",
    "FAKE_API_KEY",
    "FakeProvider",
    "FakeResolver",
    "LOCAL_PROFILE",
    "PROBE_TMP",
    "REPO_ROOT",
    "cleanup",
    "emit",
    "fingerprint_of_handle",
    "make_handle",
    "make_settings",
    "model_fingerprint",
]
