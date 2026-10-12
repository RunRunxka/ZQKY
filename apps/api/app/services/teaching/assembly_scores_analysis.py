"""成绩与学情第二批（R6-BE）装配：成绩导入/确认 + 学情分析 + 报告导出。

由 ``app.main`` 的 ``_DOMAIN_ASSEMBLIES`` 调用（``assemble(app, settings)``）；
main.py 不感知本域内部结构。装配内容（沿归档 main.py 的成绩/学情段迁移）：

1. ``ScoreService``（成绩导入/校对/确认/修正/只读矩阵）→ ``app.state.score_service``
   （归档键名不变；依赖 R5 已装配的 ``teaching`` / ``asset_store`` / ``file_assets`` /
   ``assessment_service`` / ``confirmed_paper_reader`` / ``publication_coordinator``，
   不重建这些键，缺依赖时本域 503 不假成功）；
2. ``AnalysisService``（固定成绩学情分析 + R6 三个图表端点 + 报告导出）→
   ``app.state.analysis_service``；``file_assets`` 与知识点库（R3 ``app.state.knowledge``，
   只读复用——知识点目录路径实时读取）经构造注入；
3. ``ExportArtifactsService``（受管产物读取/下载，含 R6 分析报告产物分派）→
   ``app.state.export_artifacts_service``；
4. 执行器注册：``(teaching, analysis)`` 执行器工厂注册进 ``app.state.job_executors``
   （R5 已建 registry 与 ``(teaching, paper_mapping)``；本域追加，不覆盖）；
   ``export`` 类型本卡不产生任务行（报告导出是同步产物），不注册执行器；
5. 路由注册：scores / analysis / export_artifacts + ``/workflow-jobs`` 幂等守卫
   （R3-BE 的文件先落盘就注册，缺失跳过——与 R5 装配同一约定）。

缺依赖时对应键留 None 并记录原因：路由返回 503/501，不假成功。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

from app.core.config import Settings

logger = logging.getLogger("zhiqikeyuan.api")


def assemble(app: FastAPI, settings: Settings) -> None:
    """R6-BE 域装配入口（main.py 逐批调用；失败由 main 按域降级记录）。"""
    # 0) 键位预置：None = 未装配，路由据此 503/501（不假成功）
    for key in ("score_service", "analysis_service", "export_artifacts_service"):
        if not hasattr(app.state, key):
            setattr(app.state, key, None)

    # 1) 前置依赖（R5/核心装配）：缺失时本域整体不装配，不重建他人键
    catalog = getattr(app.state, "teaching", None)
    asset_store = getattr(app.state, "asset_store", None)
    file_assets = getattr(app.state, "file_assets", None)
    assessment_service = getattr(app.state, "assessment_service", None)
    paper_reader = getattr(app.state, "confirmed_paper_reader", None)
    coordinator = getattr(app.state, "publication_coordinator", None)
    job_engine = getattr(app.state, "job_engine", None)
    missing = [
        name
        for name, value in (
            ("teaching", catalog),
            ("asset_store", asset_store),
            ("file_assets", file_assets),
            ("assessment_service", assessment_service),
            ("confirmed_paper_reader", paper_reader),
            ("publication_coordinator", coordinator),
            ("job_engine", job_engine),
        )
        if value is None
    ]
    if missing:
        logger.warning(
            "成绩与学情域未装配（缺少前置服务：%s）；相关路由按 503 处理。", "、".join(missing)
        )
        return

    # 2) 成绩服务（导入/校对/确认/修正/只读矩阵）
    from app.services.scores import build_score_service

    app.state.score_service = build_score_service(
        catalog,
        asset_store=asset_store,
        file_assets=file_assets,
        assessment_service=assessment_service,
        paper_reader=paper_reader,
        publication_coordinator=coordinator,
    )

    # 3) 学情分析服务（含 R6 图表端点与报告导出）；知识点库只读复用（R3 装配，
    #    缺失时 knowledge-stats 的 path 落 null，不阻断本域）
    from app.services.analysis.service import AnalysisService

    app.state.analysis_service = AnalysisService(
        catalog,
        job_engine=job_engine,
        asset_store=asset_store,
        file_assets=file_assets,
        knowledge_catalog=getattr(app.state, "knowledge", None),
    )
    register = getattr(app.state.analysis_service, "register_job_executors", None)
    registry = getattr(app.state, "job_executors", None)
    if callable(register) and registry is not None:
        register(registry)

    # 4) 导出产物读取/下载（练习产物 + R6 分析报告产物同一入口）
    from app.services.export_artifacts import ExportArtifactsService

    app.state.export_artifacts_service = ExportArtifactsService(
        catalog, assets=asset_store, file_assets=file_assets
    )

    # 5) 路由：scores / analysis / export_artifacts 本卡；/workflow-jobs 归 R3-BE
    #    （try-import 幂等注册；文件缺失就跳过，不新建/不改写）。
    from app.api.v1 import analysis as analysis_route
    from app.api.v1 import export_artifacts as export_artifacts_route
    from app.api.v1 import scores as scores_route

    _include_router_once(app, scores_route.router)
    _include_router_once(app, analysis_route.router)
    _include_router_once(app, export_artifacts_route.router)
    try:  # 并行批次（R3-BE）可能尚未落盘：缺失即跳过
        from app.api.v1 import workflow_jobs as workflow_jobs_route

        _include_router_once(app, workflow_jobs_route.router)
    except ImportError:  # pragma: no cover - R3-BE 未落盘时
        logger.info("workflow_jobs 路由未注册（模块缺失，归 R3-BE 批次）")

    logger.info("成绩与学情第二批（成绩导入/确认 + 学情分析 + 报告导出）装配完成")


def _include_router_once(app: FastAPI, router: Any) -> None:
    """幂等注册（重复装配/测试重复挂载不产生重复路由）；通配 501 占位留在最后。"""
    existing = {getattr(route, "path", None) for route in app.router.routes}
    if any(
        getattr(route, "path", None) in existing
        for route in router.routes
    ):
        return
    app.include_router(router, prefix="/api/v1")
    routes = list(app.router.routes)
    catch = [route for route in routes if getattr(route, "name", "") == "feature_not_implemented"]
    if catch:
        app.router.routes[:] = [route for route in routes if route not in catch] + catch


__all__ = ["assemble"]
