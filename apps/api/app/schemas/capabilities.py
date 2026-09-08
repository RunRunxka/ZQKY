"""能力状态模型与响应结构。"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel


class CapabilityStatus(str, Enum):
    # planned：业务未实现；ready：业务已实现；unconfigured：已实现但未配置；unavailable：已实现但当前不可用
    planned = "planned"
    ready = "ready"
    unconfigured = "unconfigured"
    unavailable = "unavailable"


class Capability(BaseModel):
    feature: str
    label: str
    status: CapabilityStatus
    detail: str


class CapabilitiesResponse(BaseModel):
    service: str
    apiVersion: str
    generatedAt: datetime
    capabilities: list[Capability]


def now_utc() -> datetime:
    return datetime.now(UTC)
