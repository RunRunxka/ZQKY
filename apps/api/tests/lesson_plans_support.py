"""BE author scene: actual fixed four-catalog facts, providers and JobEngine.

Provider transport and embeddings are the AI scene's explicit isolated doubles.
Business routes/services/revisions/FKs/receipts are real; no socket is started.
"""
import copy
import json
from contextlib import contextmanager
from dataclasses import dataclass

from app.contracts import lesson_plans as lp
from app.services.lesson_plans import LessonPlanService
from tests.analysis_support import ManualEngine
from tests.lesson_generation_support import Scene, data


class LessonScene:
    @classmethod
    async def create(cls, root, protocol="openai_chat"):
        self = cls()
        self.ai = await Scene.create(root, protocol)
        self.catalog = self.ai.catalog
        self.engine = ManualEngine(self.ai.store)
        self.be = LessonPlanService(self.catalog, analysis_reader=self.ai.analysis.service,
            knowledge_catalog=self.ai.practice_scene.knowledge, coordinator=self.ai.practice_scene.coordinator,
            job_engine=self.engine, generation_service=self.ai.service, evidence_reader=self.ai.rag)
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
            return conn.execute("SELECT count(*) FROM "+table).fetchone()[0]

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
        # The pre-import environment and Settings defaults are established by the
        # outer runner. This uses standard create_app/error middleware; until CTRL
        # integrates main, only the new router is explicitly registered here.
        from app.main import create_app
        from app.api.v1.lesson_plans import router
        from app.core.config import Settings
        from app.core.secrets import SecretStore
        from fastapi.testclient import TestClient
        source = self.ai.root / "empty-textbooks"
        source.mkdir(exist_ok=True)
        settings = Settings(host="127.0.0.1", port=8001, allowed_origins=frozenset({"http://127.0.0.1:5174"}),
            env="test", data_dir=self.ai.root/"http-data", credentials_file=None,
            textbook_source_dir=source, qdrant_url="http://127.0.0.1:16333", embedding_base_url="http://127.0.0.1:9")
        app = create_app(settings, bootstrap_textbooks=False, secret_store=SecretStore())
        if not any(getattr(route, "path", None) == "/api/v1/lesson-plans" for route in app.routes):
            app.include_router(router, prefix="/api/v1")
        app.state.lesson_plan_service = self.be
        with TestClient(app, base_url="http://127.0.0.1:8001") as client:
            yield client, app

    async def close(self):
        await self.engine.shutdown()
        await self.ai.close()


def changed(content, **changes):
    return {**copy.deepcopy(content), **changes}
