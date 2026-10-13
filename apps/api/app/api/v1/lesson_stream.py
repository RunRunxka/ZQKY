"""教案流式逐模块生成（C3-3）：POST /lesson-plans/generation-stream（SSE）。

事件：module.start / module.delta / module.error / module.done / message.end / error。
流开始前失败（模型缺失/学情未就绪）用 HTTP 错误，流开始后用 error 事件——与 /chat、/rag 一致。

R7 适配：
- 模型解析经 ``resolve_agent_chat_model``（LangChain 官方包、显式凭证、env 断言），
  在有界线程执行（构造可能读配置/SecretStore，不阻塞事件循环）；
- ``sourceAssetRef``（R7 前端追加字段）：上传学情文件来源。**2026-10-13 起本域真正消费**：
  经 ``lesson_source_service``（须为教师本人的受管资产）读回材料文本，作为固定数据注入
  每个模块的提示；读不到/为空如实报 HTTP 错误，不再静默忽略该来源。
"""

from __future__ import annotations

import functools
import json

import anyio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.exceptions import AppError
from app.schemas.lesson_stream import LessonStreamRequest
from app.services.lesson_streaming.service import DEFAULT_MODULES, stream_modules

router = APIRouter(tags=["lesson-plans"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
}


def _sse(event: str, payload: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


@router.post("/lesson-plans/generation-stream")
async def lesson_generation_stream(request: Request, body: LessonStreamRequest) -> StreamingResponse:
    # 流开始前的准备工作（模型解析/学情读取/知识点查询）在这里完成，失败即 HTTP 错误。
    repo = getattr(request.app.state, "model_config_repo", None)
    secrets = getattr(request.app.state, "secret_store", None)
    if repo is None or secrets is None:
        raise AppError("模型配置未装配，无法生成教案。", code="SERVICE_UNAVAILABLE", status_code=503, retryable=True)

    def _resolve():
        from app.services.agent.model import resolve_agent_chat_model

        return resolve_agent_chat_model(repo, secrets, body.modelProfileId)

    handle = await anyio.to_thread.run_sync(_resolve)

    report: dict | None = None
    if body.analysisRunId:
        analysis = getattr(request.app.state, "analysis_service", None)
        if analysis is None:
            raise AppError("学情分析服务未装配。", code="SERVICE_UNAVAILABLE", status_code=503, retryable=True)
        try:
            report = await anyio.to_thread.run_sync(
                functools.partial(analysis.read_ready_report, body.analysisRunId)
            )
        except AppError as exc:
            raise AppError(
                f"学情报告读取失败：{exc}", code=exc.code, status_code=exc.status_code, retryable=exc.retryable
            ) from exc

    source_material = None
    if body.sourceAssetRef:
        sources = getattr(request.app.state, "lesson_source_service", None)
        if sources is None:
            raise AppError(
                "学情材料服务未装配，无法读取上传的学情文件。", code="SERVICE_UNAVAILABLE", status_code=503, retryable=True
            )
        source_material = await anyio.to_thread.run_sync(
            functools.partial(sources.read_material, body.sourceAssetRef)
        )

    knowledge_names: list[str] = []
    if body.selectedKnowledgePointIds:
        knowledge = getattr(request.app.state, "knowledge_service", None)
        if knowledge is None:
            raise AppError("知识点服务未装配。", code="SERVICE_UNAVAILABLE", status_code=503, retryable=True)
        for point_id in body.selectedKnowledgePointIds:
            point = await anyio.to_thread.run_sync(functools.partial(knowledge.get_point, point_id))
            knowledge_names.append(point.name)

    modules = body.modules or list(DEFAULT_MODULES)
    request_id = body.requestId

    async def event_stream():
        yield _sse("message.start", {"requestId": request_id, "modules": modules})
        async for event in stream_modules(
            handle,
            report=report,
            knowledge_names=knowledge_names,
            course_name=body.courseName,
            requirements=body.requirements,
            modules=modules,
            source_material=source_material,
        ):
            kind = event.get("type")
            if kind == "module-start":
                yield _sse("module.start", {"module": event["module"], "label": event["label"]})
            elif kind == "module-delta":
                yield _sse("module.delta", {"module": event["module"], "text": event["text"]})
            elif kind == "module-error":
                yield _sse("module.error", {"module": event["module"], "message": event["message"]})
            elif kind == "module-done":
                yield _sse("module.done", {"module": event["module"]})
            elif kind == "end":
                yield _sse("message.end", {"finishReason": "stop"})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)
