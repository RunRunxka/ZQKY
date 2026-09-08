"""真实健康检查：只报告服务可用性，不返回任何配置内容。"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.config import API_VERSION, SERVICE_NAME

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "apiVersion": API_VERSION,
        "time": datetime.now(UTC).isoformat(),
    }
