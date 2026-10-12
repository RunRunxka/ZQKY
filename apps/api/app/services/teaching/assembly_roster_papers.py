"""施测与成绩第一批（R5-BE）装配：班级/名单 + 试卷（原卷）域。

由 ``app.main`` 的 ``_DOMAIN_ASSEMBLIES`` 调用（``assemble(app, settings)``）；
main.py 不感知本域内部结构。装配内容（沿归档 main.py 的教学段拆分迁移）：

1. 既有教学库体检（损坏/缺表/迁移漂移拒绝启动，不按空库重建）→
   ``TeachingCatalog.migrate()``（幂等；新库按冻结迁移建表）→ ``app.state.teaching``；
2. ``AssetStore``（受管 blobs，沿用核心 ``settings.assets_root``）与
   ``FileAssetsRepository``（教学库 ``file_assets`` 唯一入口）→
   ``app.state.asset_store`` / ``app.state.file_assets``（归档键名不变）；
3. roster / papers / assessments 三服务 + ``confirmed_paper_reader``；
4. teaching 域 JobStore 经 ``register_job_store`` 登记（引擎按当前全集重建），
   执行器工厂注册进 ``app.state.job_executors``（本域现注册 ``teaching:paper_mapping``）；
5. 路由注册（roster / papers / assessments；``/workflow-jobs`` 归 R3-BE 所有，
   这里只 try-import 幂等注册，文件缺失就跳过——不新建、不改写）。

缺依赖时对应键留 None 并记录原因：路由返回 503/501，不假成功。
知识点库（``app.state.knowledge``）归 R3-BE 装配；本模块只读复用（原卷知识点
校验/建议允许集合），其缺失时原卷确认/建议的跨库复核按 503 处理（服务自身语义）。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

from app.core.config import Settings

logger = logging.getLogger("zhiqikeyuan.api")

#: 任务白名单的教学域取值（沿归档 ``JOB_KINDS["teaching"]``；种类是契约的一部分）
TEACHING_JOB_KINDS = frozenset(
    {"paper_import", "paper_mapping", "analysis", "lesson_generation", "export"}
)


def assemble(app: FastAPI, settings: Settings) -> None:
    """R5-BE 域装配入口（main.py 逐批调用；失败由 main 按域降级记录）。"""
    # 0) 键位预置：None = 未装配，路由据此 503/501（不假成功）
    for key in (
        "teaching",
        "file_assets",
        "roster_service",
        "paper_service",
        "confirmed_paper_reader",
        "assessment_service",
    ):
        if not hasattr(app.state, key):
            setattr(app.state, key, None)

    # 1) 既有库体检（损坏/缺表/迁移漂移拒绝装配；新库不存在时由 migrate 创建）
    from app.core.database_gate import DatabaseExpectation, verify_existing_databases
    from app.repositories.teaching.schema import REQUIRED_TABLES as TEACHING_TABLES

    verify_existing_databases(
        [
            DatabaseExpectation(
                settings.teaching_root / "teaching.sqlite3", "teaching", TEACHING_TABLES
            )
        ]
    )

    # 2) 教学库目录（唯一权威）+ 受管资产
    from app.repositories.teaching.catalog import TeachingCatalog

    catalog = TeachingCatalog(settings.teaching_root / "teaching.sqlite3")
    catalog.migrate()
    app.state.teaching = catalog

    from app.repositories.assets.file_assets import FileAssetsRepository
    from app.services.assets.store import AssetStore

    asset_store = AssetStore(settings.assets_root)
    file_assets = FileAssetsRepository(catalog)
    app.state.asset_store = asset_store
    app.state.file_assets = file_assets

    # 3) 教学域 JobStore（引擎按当前全集重建）+ 执行器注册表
    from app.repositories.jobs.repository import JobStore
    from app.services.jobs.assembly import register_job_store
    from app.services.jobs.registry import JobExecutorRegistry

    store = JobStore(catalog, domain="teaching", table="workflow_jobs", kinds=TEACHING_JOB_KINDS)
    register_job_store(app, "teaching", store)
    registry = getattr(app.state, "job_executors", None)
    if not isinstance(registry, JobExecutorRegistry):
        registry = JobExecutorRegistry()
        app.state.job_executors = registry

    # 4) 名单服务（班级/学生/归属历史与名单导入）
    from app.services.roster.service import build_roster_service

    app.state.roster_service = build_roster_service(
        catalog,
        asset_store=asset_store,
        file_assets=file_assets,
        job_engine=getattr(app.state, "job_engine", None),
    )

    # 5) 原卷服务（导入拆题/草稿校对/确认入库/AI 知识点建议/已确认读取）；
    #    知识点库只读复用（R3-BE 装配），缺失时对应跨库复核按服务自身 503 语义。
    from app.services.papers.service import build_paper_service

    paper_service = build_paper_service(
        catalog,
        asset_store=asset_store,
        file_assets=file_assets,
        knowledge_catalog=getattr(app.state, "knowledge", None),
        coordinator=getattr(app.state, "publication_coordinator", None),
        model_resolver=None,
        job_engine=getattr(app.state, "job_engine", None),
        model_config_repo=app.state.model_config_repo,
        secret_store=app.state.secret_store,
        model_auth_service=app.state.model_auth_service,
    )
    app.state.paper_service = paper_service
    app.state.confirmed_paper_reader = paper_service.confirmed_reader()
    register = getattr(paper_service, "register_job_executors", None)
    if callable(register):
        register(registry)

    # 6) 施测服务（只用已确认原卷的固定修订）
    from app.services.assessments.service import build_assessment_service

    app.state.assessment_service = build_assessment_service(
        catalog, reader=paper_service.confirmed_reader()
    )

    # 7) 路由：roster / papers / assessments 本卡；/workflow-jobs 归 R3-BE
    #    （try-import 幂等注册；文件缺失就跳过，不新建/不改写）。
    from app.api.v1 import assessments as assessments_route
    from app.api.v1 import papers as papers_route
    from app.api.v1 import roster as roster_route

    _include_router_once(app, papers_route.router)
    _include_router_once(app, roster_route.router)
    _include_router_once(app, assessments_route.router)
    try:  # 并行批次（R3-BE）可能尚未落盘：缺失即跳过
        from app.api.v1 import workflow_jobs as workflow_jobs_route

        _include_router_once(app, workflow_jobs_route.router)
    except ImportError:  # pragma: no cover - R3-BE 未落盘时
        logger.info("workflow_jobs 路由未注册（模块缺失，归 R3-BE 批次）")

    logger.info("施测与成绩第一批（班级/名单 + 试卷）装配完成")


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
