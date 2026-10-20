"""Thin asynchronous T70 HTTP routes; SQL/IO execute in bounded threads."""
import functools
import anyio
from fastapi import APIRouter, Query, Request
from pydantic import Field
from app.contracts.b4 import (AnalysisCreateRequest, AnalysisReceipt, AnalysisRunDeleteReceipt, AnalysisRunView,
                              ClassReportRow, EvidenceRow, Frozen, ItemStatView, NoteRequest, NoteView, Page,
                              StudentReportRow)
from app.contracts.learning_analysis import (
    AnalysisReportReceipt,
    DistributionResponse,
    KnowledgeStatsResponse,
    StudentKnowledgeResponse,
)
from app.core.exceptions import AppError

router = APIRouter(tags=["analysis"])


def service(request):
    value = getattr(request.app.state, "analysis_service", None)
    if value is None:
        raise AppError("学情分析服务未装配。", code="SERVICE_UNAVAILABLE", status_code=503, retryable=True)
    return value


async def run(fn, *args, **kwargs):
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


@router.post("/assessments/{assessment_id}/analysis-runs", response_model=AnalysisReceipt, status_code=202)
async def create_run(request: Request, assessment_id: str, body: AnalysisCreateRequest):
    return await service(request).create_run(assessment_id, body)


@router.get("/analysis-runs", response_model=Page[AnalysisRunView])
async def list_runs(request: Request, assessmentId: str | None = None, scoreRevisionId: str | None = None,
                    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    """报告列表：归档/恢复端点已移除（删除即删除）；列表返回全部正常数据。

    ``archivedAt`` 字段在视图里保留（旧库残留行的只读时间戳），归一化脚本会把
    残留行的 ``archived_at`` 清空。
    """
    return await run(service(request).list_runs, assessment_id=assessmentId, score_revision_id=scoreRevisionId,
                     offset=offset, limit=limit)


@router.get("/analysis-runs/{run_id}", response_model=AnalysisRunView)
async def get_run(request: Request, run_id: str):
    return await run(service(request).get_run, run_id)


@router.post("/analysis-runs/{run_id}/archive", include_in_schema=False)
@router.post("/analysis-runs/{run_id}/restore", include_in_schema=False)
async def run_archive_removed(run_id: str):
    """归档/恢复端点已移除（B3，2026-10-20 用户裁定「删除即删除」）：显式 404。"""
    raise AppError(
        f"学情报告 {run_id} 的归档/恢复端点已移除；删除请用 DELETE /analysis-runs/{{id}}。",
        code="ARCHIVE_ENDPOINT_REMOVED",
        status_code=404,
    )


@router.delete("/analysis-runs/{run_id}", response_model=AnalysisRunDeleteReceipt)
async def delete_run(request: Request, run_id: str):
    """删除报告（R10-BE 拆开交叉引用）：可拆引用级联/置空后才物理删除。

    - 由本报告派生的练习集**级联删除**（连带 reviewed 修订/导出/转换/工件）；
    - 教案修订的 ``analysis_run_id`` 来源指针**置空**（教案本体保留）；
    - 教案冻结生成血缘（``lesson_generation_inputs`` / ``lesson_ai_proposals``，
      NOT NULL 且行不可变）存在时 → 409 ``ANALYSIS_RUN_IN_USE``，逐项列出计数；
    - 不存在 → 404；以上全部在同一写事务内完成，任一步失败整体回滚。
    """
    return await run(service(request).delete_run, run_id)


def report_endpoint(kind):
    async def endpoint(request: Request, run_id: str, classId: str | None = None,
                       participantId: str | None = None, knowledgePointId: str | None = None,
                       offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
        return await run(service(request).list_report_rows, run_id, kind, class_id=classId,
                         participant_id=participantId, knowledge_point_id=knowledgePointId, offset=offset, limit=limit)
    endpoint.__name__ = f"list_{kind}"
    return endpoint


for _kind, _model in (("classes", ClassReportRow), ("students", StudentReportRow), ("evidence", EvidenceRow)):
    router.add_api_route(f"/analysis-runs/{{run_id}}/{_kind}", report_endpoint(_kind), methods=["GET"], response_model=Page[_model])


@router.post("/analysis-runs/{run_id}/notes", response_model=NoteView, status_code=201)
async def add_note(request: Request, run_id: str, body: NoteRequest):
    return await run(service(request).add_note, run_id, body)


@router.get("/analysis-runs/{run_id}/notes", response_model=Page[NoteView])
async def list_notes(request: Request, run_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    return await run(service(request).list_notes, run_id, offset=offset, limit=limit)


@router.get("/analysis-runs/{run_id}/item-stats", response_model=list[ItemStatView])
async def get_item_stats(request: Request, run_id: str):
    """图表聚合（C2）：按题号的全班得分率（匿名聚合；趋势图与热力图共用）。"""
    return await run(service(request).item_stats, run_id)


class AiCommentaryRequest(Frozen):
    """AI 学情评价请求（C2-3）：即席生成不落库；model_profile_id 指定评价用模型。"""

    model_profile_id: str = Field(alias="modelProfileId", min_length=1, max_length=128)


class AnalysisCommentaryResponse(Frozen):
    """AI 学情评价响应（R6）：候选 Markdown + degraded 标注。

    ``degraded=False``：模型成功返回的候选文本（不落库）；``degraded=True``：模型
    未返回内容（空文本/传输失败/超时），``commentary`` 为空串——如实标注降级原因，
    不伪造评价文本。报告未就绪（409 ``REPORT_NOT_READY``）仍按错误返回。
    """

    commentary: str
    degraded: bool
    reason: str | None = None


@router.post("/analysis-runs/{run_id}/ai-commentary", response_model=AnalysisCommentaryResponse)
async def ai_commentary(request: Request, run_id: str, body: AiCommentaryRequest):
    """AI 学情评价：读已就绪报告的匿名聚合（学生以代称进模型），经 LangChain 生成 Markdown 评价。

    候选文本不落库；教师可在界面上「存为教师备注」（走既有 notes 追加）。
    模型解析经 ``resolve_agent_chat_model``（LangChain 官方包、显式凭证、env 断言）；
    生成失败**不抛服务端错误**：返回 ``degraded=true`` + 空文本 + 原因。
    """
    import anyio as _anyio

    from app.services.agent.model import AgentModelHandle, resolve_agent_chat_model
    from app.services.analysis.commentary import generate_commentary

    analysis = service(request)
    repo = getattr(request.app.state, "model_config_repo", None)
    secrets = getattr(request.app.state, "secret_store", None)
    if repo is None or secrets is None:
        raise AppError("模型配置未装配，无法生成 AI 评价。", code="SERVICE_UNAVAILABLE", status_code=503, retryable=True)

    def _resolve() -> AgentModelHandle:
        return resolve_agent_chat_model(repo, secrets, body.model_profile_id)

    try:
        handle = await _anyio.to_thread.run_sync(_resolve)
        text = await generate_commentary(analysis, run_id, handle)
    except AppError as exc:
        if exc.status_code == 409 and exc.code == "REPORT_NOT_READY":
            raise
        return AnalysisCommentaryResponse(commentary="", degraded=True, reason=exc.code)
    return AnalysisCommentaryResponse(commentary=text, degraded=False)


@router.get("/analysis-runs/{run_id}/knowledge-stats", response_model=KnowledgeStatsResponse)
async def get_knowledge_stats(request: Request, run_id: str):
    """知识点得分率（冻结形状）：按小题得分率聚合到知识点，``scoreRate`` 降序。

    口径：对每个计分小题按 item_stats 同口径（missing/absent/exempt 不进分母）算
    全班得分率，再按小题满分加权平均到其**primary 知识点**（``paper_item_knowledge``
    冻结进报告事实的链接；同小题多个 primary 不可能——确认闸门允许，但权重各计一次）。
    未挂任何 primary 知识点的小题不计入聚合（口径注明于服务层 docstring）。
    """
    return await run(service(request).knowledge_stats, run_id)


@router.get("/analysis-runs/{run_id}/student-knowledge", response_model=StudentKnowledgeResponse)
async def get_student_knowledge(request: Request, run_id: str):
    """学生 × 知识点矩阵（冻结形状）：``label`` 由后端给出（脱敏代称，不是学生姓名）。

    口径：学生行按参测人次的**脱敏代称**（学生A/学生B…，与 AI 评价同源）展示；
    单元得分率 = 该生在该知识点 primary 链接小题上的 recorded 得分合计 / 满分合计，
    无任何 recorded 依据（全 missing/absent/exempt）时 ``scoreRate`` 为 null（不补 0）。
    """
    return await run(service(request).student_knowledge, run_id)


@router.get("/analysis-runs/{run_id}/distribution", response_model=DistributionResponse)
async def get_distribution(request: Request, run_id: str):
    """得分率分数段分布（冻结形状）：学生级该次考试得分率分档。

    口径：学生级得分率 = 该生**全部计分小题**的 recorded 得分合计 / 满分合计
    （该生没有任何 recorded 依据 → 不进任何分档）；分档 低 <60% / 中 60–85% /
    高 ≥85%，``count`` 为学生（人次去重到学生）数。
    """
    return await run(service(request).distribution, run_id)


@router.post("/analysis-runs/{run_id}/report", response_model=AnalysisReportReceipt, status_code=201)
async def create_analysis_report(request: Request, run_id: str):
    """生成学情分析报告导出产物（201）：渲染 docx → 落 ``export_artifacts`` + 受管 blob。

    - 重复导出**生成新产物**（不覆盖旧产物）；
    - 渲染/登记失败如实报错，不留半成品（登记与 blob 写入由服务层保证原子性）；
    - 下载走既有受管产物端点 ``GET /export-artifacts/{artifactId}/download``。
    """
    return await run(service(request).export_report, run_id, file_assets=getattr(request.app.state, "file_assets", None))
