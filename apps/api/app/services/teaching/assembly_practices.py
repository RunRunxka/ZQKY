"""练习域（practices，需求 8）装配：练习服务 + 导出任务执行器 + 路由。

由 ``app.main`` 的 ``_DOMAIN_ASSEMBLIES`` 调用（``assemble(app, settings)``）；
main.py 不感知本域内部结构。装配内容（沿归档 main.py 的练习段迁移到分域装配）：

1. **依赖只读复用，不重建**：``app.state.teaching``（教学库，R5 已装配）、
   ``analysis_service``（R6 学情分析，练习的来源报告读取方）、``question_bank`` /
   ``question_bank_service``（R4 题库，固定题与题目资产来源）、``knowledge``（R3
   知识点库）、``asset_store`` / ``file_assets``（R5）、``assessment_service``（R5）、
   ``publication_coordinator``（核心）、``job_engine``（R5 登记 teaching JobStore 后
   重建）——任一缺失时本域整体不装配（键留 None），路由按 503 处理，不假成功；
2. ``PracticeService`` → ``app.state.practice_service``（归档键名不变）；固定题读取
   复用 ``FixedQuestionReader``（R7-BE 装配的 ``app.state.fixed_question_reader``，
   缺失时本域自建只读实例——同一类、无状态，不产生第二套语义）；题目资产读取经
   ``app.services.question_bank.rich.read_asset``（受管 blobs + 题库兼容 SHA）；
3. 执行器注册：``(teaching, export)`` 执行器工厂注册进 ``app.state.job_executors``
   （R5 已建 registry 与 ``(teaching, paper_mapping)``；R6 追加 ``(teaching,
   analysis)``；R7 追加 ``lesson_generation``；本域追加 ``export``，不覆盖）——
   练习导出是**任务**（异步产物），与 R6 分析报告的同步产物不同；
4. 路由注册：practices + ``/workflow-jobs`` 幂等守卫（try-import；文件缺失就跳过）。

挂 app.state 键名（沿用归档）：``practice_service``。
``ExportArtifactsService``（产物读取/下载）已由 R6 装配；练习产物走其练习链分派
（``export_artifacts`` 表命中），不需要第二套读取入口。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

from app.core.config import Settings

logger = logging.getLogger("zhiqikeyuan.api.practices")


def assemble(app: FastAPI, settings: Settings) -> None:
    """R8-BE 域装配入口（main.py 逐批调用；失败由 main 按域降级记录）。"""
    # 0) 键位预置：None = 未装配，路由据此 503/501（不假成功）
    if not hasattr(app.state, "practice_service"):
        app.state.practice_service = None

    # 1) 前置依赖（R3/R4/R5/R6/核心装配）：缺失时本域整体不装配，不重建他人键
    catalog = getattr(app.state, "teaching", None)
    asset_store = getattr(app.state, "asset_store", None)
    file_assets = getattr(app.state, "file_assets", None)
    assessment_service = getattr(app.state, "assessment_service", None)
    analysis_service = getattr(app.state, "analysis_service", None)
    knowledge_catalog = getattr(app.state, "knowledge", None)
    question_bank = getattr(app.state, "question_bank", None)
    question_bank_service = getattr(app.state, "question_bank_service", None)
    coordinator = getattr(app.state, "publication_coordinator", None)
    job_engine = getattr(app.state, "job_engine", None)
    missing = [
        name
        for name, value in (
            ("teaching", catalog),
            ("asset_store", asset_store),
            ("file_assets", file_assets),
            ("assessment_service", assessment_service),
            ("analysis_service", analysis_service),
            ("knowledge", knowledge_catalog),
            ("question_bank", question_bank),
            ("question_bank_service", question_bank_service),
            ("publication_coordinator", coordinator),
            ("job_engine", job_engine),
        )
        if value is None
    ]
    if missing:
        logger.warning(
            "练习域未装配（缺少前置服务：%s）；相关路由按 503 处理。", "、".join(missing)
        )
        return

    # 2) 固定题读取：R7-BE 已装配（同类只读、无状态）时复用；缺失时自建只读实例
    from app.services.question_bank.fixed import FixedQuestionReader

    fixed_question_reader = getattr(app.state, "fixed_question_reader", None)
    if not isinstance(fixed_question_reader, FixedQuestionReader):
        fixed_question_reader = FixedQuestionReader(question_bank)
        app.state.fixed_question_reader = fixed_question_reader

    # 3) 练习服务（依赖注入沿归档 main.py 练习段；owner 语义：教学/练习单教师 local）
    from app.services.practices import PracticeService
    from app.services.question_bank.rich import read_asset as read_question_asset

    app.state.practice_service = PracticeService(
        catalog,
        analysis_reader=analysis_service,
        fixed_question_reader=fixed_question_reader,
        knowledge_catalog=knowledge_catalog,
        coordinator=coordinator,
        assets=asset_store,
        question_asset_reader=lambda asset_id: read_question_asset(
            asset_id, assets=asset_store, blobs=question_bank_service.blobs
        ),
        job_engine=job_engine,
        file_assets=file_assets,
        assessment_service=assessment_service,
        question_owner_id=question_bank_service.owner_id,
    )

    # 4) 执行器注册：(teaching, export) —— 练习导出是任务；注册进公共 registry（不覆盖）
    registry = getattr(app.state, "job_executors", None)
    register = getattr(app.state.practice_service, "register_job_executors", None)
    if callable(register) and registry is not None:
        register(registry)

    # 5) 路由：practices 本卡；/workflow-jobs 归 R3-BE（try-import 幂等注册）。
    from app.api.v1 import practices as practices_route

    _include_router_once(app, practices_route.router)
    try:
        from app.api.v1 import workflow_jobs as workflow_jobs_route

        _include_router_once(app, workflow_jobs_route.router)
    except ImportError:  # pragma: no cover - R3-BE 未落盘时
        logger.info("workflow_jobs 路由未注册（模块缺失，归 R3-BE 批次）")

    logger.info("练习域（练习集/选拔/导出/回流）装配完成")


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
