"""R7 教案工作台测试现场：真实固定目录事实 + 假 LangChain 模型（BE author scene）。

Provider 传输与模型输出是显式隔离替身；业务路由/服务/修订/外键/回执全部真实；
不起监听、不触网。与归档差异：``scene.ai.practice_scene.knowledge`` 收敛为
``scene.ai.knowledge``（练习域未回归，知识点目录由 GenerationScene 直建）。
"""
import copy
from contextlib import contextmanager

from app.contracts import lesson_plans as lp
from app.services.lesson_plans import LessonPlanService
from tests.analysis_support import ManualEngine
from tests.lesson_generation_support import GenerationScene, data


class LessonScene:
    @classmethod
    async def create(cls, root, protocol="openai_chat"):
        self = cls()
        self.ai = await GenerationScene.create(root)
        self.catalog = self.ai.catalog
        self.engine = ManualEngine(self.ai.store)
        from app.services.assets.store import AssetStore
        from app.repositories.assets.file_assets import FileAssetsRepository

        self.be = LessonPlanService(self.catalog, analysis_reader=self.ai.analysis.service,
            knowledge_catalog=self.ai.knowledge, coordinator=self.ai.analysis.coordinator
            if hasattr(self.ai.analysis, "coordinator") else _CoordinatorOf(self.ai),
            job_engine=self.engine, generation_service=self.ai.service, evidence_reader=self.ai.rag,
            asset_store=AssetStore(root / "export-assets"), file_assets=FileAssetsRepository(self.catalog))
        self.body = self.ai.body
        return self

    def create_request(self, *, submission="create", context=None, source="manual", content=None, **changes):
        return lp.LessonCreateRequest(submissionId=submission, subjectId="math", classId="class", data=content or data(),
                                      context=context, source=source, **changes)

    def save_request(self, lesson, *, submission="save", content=None, context=None, source="manual", revision=None):
        return lp.LessonSaveRequest(submissionId=submission, expectedRevision=revision or lesson["revision"],
            data=content or lesson["currentRevision"]["data"], context=context, source=source)

    def context(self, points=("k1", "k2")):
        return dict(analysisRunId=self.body.analysis_run_id, selectedKnowledgePointIds=list(points))

    def count(self, table):
        assert table in {"lesson_plans", "lesson_plan_revisions", "lesson_revision_reviews", "lesson_generation_inputs",
                         "lesson_ai_proposals", "lesson_proposal_decisions", "command_submissions", "workflow_jobs"}
        with self.catalog.read_connection() as conn:
            return conn.execute("SELECT count(*) FROM " + table).fetchone()[0]

    def generate_request(self, lesson=None, *, submission="generate", **changes):
        value = self.body.model_dump(by_alias=True, mode="json")
        value.update(submissionId=submission, **changes)
        if lesson is not None:
            value.update(baseRevisionId=lesson["currentRevisionId"], baseServerRevision=lesson["revision"], classId=lesson["classId"])
        return lp.LessonGenerateRequest.model_validate(value)

    async def proposal(self, lesson=None, *, submission="generate", **changes):
        lesson = lesson or self.be.get_lesson("lesson")
        receipt = await self.be.generate_proposal(lesson["lessonPlanId"], self.generate_request(lesson, submission=submission, **changes))
        record = self.ai.store.get(receipt["job"]["jobId"])
        job = await self.engine.run_job("teaching", record.job_id, self.ai.service.executor_for(record), uses_model=True)
        assert job.state == "succeeded", job.error
        return self.be.get_proposal(lesson["lessonPlanId"], job.result["proposalId"]), receipt

    def apply_request(self, proposal, fields=("process",), submission="apply"):
        return lp.LessonApplyRequest(submissionId=submission, expectedRevision=proposal["baseServerRevision"],
            baseRevisionId=proposal["baseRevisionId"], selectedFields=list(fields))

    @contextmanager
    def client(self):
        # 归档口径：标准 create_app + 显式注册教案路由（隔离装配；不触真实 .env）。
        from app.main import create_app
        from app.api.v1.lesson_plans import router as lesson_plans_router
        from app.api.v1.lesson_sources import router as lesson_sources_router
        from app.core.config import Settings
        from app.core.secrets import SecretStore
        from fastapi.testclient import TestClient

        source = self.ai.root / "empty-textbooks"
        source.mkdir(exist_ok=True)
        settings = Settings(host="127.0.0.1", port=8001, allowed_origins=frozenset({"http://127.0.0.1:5174"}),
            env="test", data_dir=self.ai.root / "http-data", credentials_file=None,
            textbook_source_dir=source, qdrant_url="http://127.0.0.1:16333", embedding_base_url="http://127.0.0.1:9")
        app = create_app(settings, bootstrap_textbooks=False, secret_store=SecretStore())
        for router in (lesson_plans_router, lesson_sources_router):
            if not any(getattr(route, "path", None) == "/api/v1/lesson-plans" and router is lesson_plans_router
                       for route in app.routes):
                app.include_router(router, prefix="/api/v1")
        app.state.lesson_plan_service = self.be
        app.state.analysis_service = self.ai.analysis.service
        app.state.fixed_question_reader = None
        with TestClient(app, base_url="http://127.0.0.1:8001") as client:
            yield client, app

    async def close(self):
        await self.engine.shutdown()
        await self.ai.close()


class _CoordinatorOf:
    """AnalysisScene 没有公开 coordinator 时的最小发布协调器（与归档场景一致）。"""

    def __init__(self, ai) -> None:
        from app.services.publication import PublicationCoordinator

        self._coordinator = PublicationCoordinator()

    def publication(self, *, operation: str):
        return self._coordinator.publication(operation=operation)


def changed(content, **changes):
    return {**copy.deepcopy(content), **changes}
