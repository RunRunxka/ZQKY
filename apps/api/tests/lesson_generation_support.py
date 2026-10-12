"""R7 教案测试现场：真实四目录读取器 + 假 LangChain 模型（不触网）。

与归档 ``lesson_generation_support`` 的差异（R7 LangChain 改造适配）：

- 模型替身是**假 LangChain chat model**（``with_structured_output`` 返回冻结的
  ``{"patch","budget"}`` 字典），不再起 HTTP transport / 三协议 provider；
- 练习域（practices）随推倒重做尚未回归：``practice_reader`` 落 None 替身
  （练习引用路径由 ``test_lesson_generation_sources`` 的练习用例覆盖，本现场
  只覆盖报告/教材/题目来源；练习重建后按归档口径补回）；
- 教材证据用**真实教材目录**（``tests.test_textbook_ingest.Harness``）+
  ``LessonEvidenceAdapter``（装配层的真实适配器），不是证据替身；
- 知识点/固定题目录与练习服务由真实 ``PracticesScene``（R6-PH 回归）提供。
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.messages import AIMessage

from app.contracts.lesson_plans import LessonGenerateRequest, LessonView
from app.core.sqlite import now_iso
from app.services.lesson_generation import LessonGenerationService
from tests.analysis_support import AnalysisScene
from tests.test_textbook_ingest import Harness, sample_text


def reply() -> dict:
    ids = ["new:N1", "new:N2", "new:N3", "new:N4"]
    return dict(patch=dict(coreCompetencies="依据固定班级计数安排学习活动", keyPoints="两项知识点复习",
        teachingDesign="通过固定教材开展探究", exercises="请使用已确认课堂题", process=[
            dict(id=key, stage="环节" + str(i), design="对照教材讨论", secondary="") for i, key in enumerate(ids)]),
        budget=dict(durationMinutes=40, stages=[dict(processId=key, phase=phase, minutes=10,
            knowledgeAliases=["K1", "K2"], activity="比较固定题目", check="课堂口头检测", evidenceAliases=["E1"])
            for key, phase in zip(ids, ("introduction", "exploration", "practice", "conclusion"))]))


def data() -> dict:
    return dict(title="教师原题", totalLessons="2", currentLessonNo="1", lessonTypes=["review", "new"],
        otherTypeText="教师课型", coreCompetencies="原素养", keyPoints="原要点", teachingDesign="原设计",
        process=[dict(id="old-safe", stage="原过程", design="原过程设计", secondary="原二次备课")],
        exercises="原练习", reflection="教师反思")


class _StructuredRunnable:
    """假 LangChain ``with_structured_output`` 的 runnable（include_raw=True 形状）。

    返回的 ``parsed`` 按 runner 的契约校验为 schema 实例（与真实
    ``with_structured_output(include_raw=True)`` 一致）；校验失败按
    ``parsing_error`` 返回（不抛异常，让 runner 走重试/降级路径）。
    ``delay``>0 时先睡眠（供在途取消/租约测试制造竞态窗口）。
    """

    def __init__(self, model: "FakeStructuredChatModel") -> None:
        self._model = model

    async def ainvoke(self, messages: list, config=None) -> dict:  # noqa: ANN001
        self._model.calls.append(list(messages))
        if self._model.started is not None:
            self._model.started.set()
        if self._model.delay:
            await asyncio.sleep(self._model.delay)
        reply_value = self._model.results.pop(0) if self._model.results else self._model.default_reply
        if isinstance(reply_value, BaseException):
            raise reply_value
        raw = json.dumps(reply_value, ensure_ascii=False) if isinstance(reply_value, dict) else str(reply_value)
        try:
            parsed = self._model.schema.model_validate(reply_value)
        except Exception as exc:  # noqa: BLE001 - 与真实解析失败同形
            return {"raw": AIMessage(content=raw), "parsed": None, "parsing_error": exc}
        return {"raw": AIMessage(content=raw), "parsed": parsed, "parsing_error": None}


class FakeStructuredChatModel:
    """假 LangChain 模型：``with_structured_output`` 逐次返回冻结结果（不触网）。

    ``delay``：每次调用前的睡眠秒数（0=即时）；``started``：首次调用置位的
    ``asyncio.Event``（供测试等待"模型已被调用"）。
    """

    def __init__(self, default_reply: dict | None = None) -> None:
        self.default_reply = default_reply if default_reply is not None else reply()
        self.results: list[Any] = []
        self.calls: list[list] = []
        self.schema: Any = None
        self.delay: float = 0
        self.started: asyncio.Event | None = None

    def with_structured_output(self, schema, *, include_raw=False, **kwargs):  # noqa: ANN001, ANN202
        self.schema = schema
        self.structured_kwargs = {"schema": schema, "include_raw": include_raw, **kwargs}
        return _StructuredRunnable(self)

    async def astream(self, messages: list):  # 流式替身（lesson_stream 测试用）
        for text in self.stream_texts:
            yield AIMessage(content=text)


class FakeAgentHandle:
    """``resolve_agent_chat_model`` 句柄的最小替身（chat_model + fingerprint）。"""

    def __init__(self, chat_model: FakeStructuredChatModel, *, profile_id: str = "isolated-profile") -> None:
        self.profile_id = profile_id
        self.model_id = "isolated-model"
        self.chat_model = chat_model
        # 输出预算在冻结上限（16384）内：build_request 的预算核对按归档语义放行
        self.max_output_tokens = 16000
        self.fingerprint = "fixture-fingerprint"


class GenerationScene:
    """教案生成 AI 现场：真实目录读取器 + 假模型；不触网、不起监听。"""

    @classmethod
    async def create(cls, root) -> "GenerationScene":
        self = cls()
        self.root = root
        self.analysis = AnalysisScene(root)
        receipt = await self.analysis.ready()
        self.catalog = self.analysis.catalog
        # 练习域现场（R6-PH 已回归）：真实 PracticesScene 提供知识点目录 + 固定题库
        # + 练习服务（种子口径与归档一致：math + k1/k2 活跃修订 + class 成员）。
        from tests.practices_support import PracticesScene

        self.practice_scene = PracticesScene(self.analysis)
        self.practice_scene.run_id = receipt.run_id
        self.knowledge = self.practice_scene.knowledge
        self.questions = self.practice_scene.questions
        from app.services.question_bank.fixed import FixedQuestionReader

        self.fixed_question_reader = FixedQuestionReader(self.questions)
        # 教材证据（真实目录 + 真实适配器）
        self.textbook_harness = Harness(root / "textbooks")
        job = self.textbook_harness.commit_and_run(
            self.textbook_harness.import_with_metadata(sample_text(sentences=8))
        )
        assert job.state == "succeeded", job.error
        from app.services.knowledge.evidence import TextbookEvidenceReader
        from app.services.rag_v2.source_text import ImmutableSource
        from app.services.lesson_plans.assembly import LessonEvidenceAdapter

        self.rag = LessonEvidenceAdapter(TextbookEvidenceReader(
            self.textbook_harness.catalog, source=ImmutableSource(catalog=self.textbook_harness.catalog)
        ))
        doc_ids = self.textbook_harness.catalog.library_document_ids(self.textbook_harness.library.library_id)
        doc = self.textbook_harness.catalog.get_document(doc_ids[0])
        revision = self.textbook_harness.catalog.get_revision(doc.current_revision_id)
        text = self.rag._require_source().read_normalized_text(revision)
        from app.schemas.textbook import TextbookSelection

        selection = TextbookSelection(gradeId="senior-1", subjectId="math", editionId="renjiao-a",
                                      documentIds=[doc.document_id])
        # 证据区间取真实正文块（region='body' 的首个 chunk 范围 ∩ 文本长度），
        # 不猜偏移——习题区/页眉行由分块已剔除，引用重建的正文区核验才能通过。
        from app.core.exceptions import AppError
        chunk_set_id = self.textbook_harness.catalog.allowed_chunks(
            self.textbook_harness.catalog.catalog_state().active_generation_id, [revision.revision_id]
        ).chunk_set_ids[0]
        body_chunks = [c for c in self.textbook_harness.catalog.list_chunks(chunk_set_id) if c.region == "body"]
        first = body_chunks[0]
        try:
            self.verified = self.rag.prepare_selected_evidence(selection, [dict(
                documentRevisionId=revision.revision_id, charStart=first.char_start, charEnd=min(first.char_end, len(text)))])
        except AppError as exc:
            # 单块仍超预算（>16000 合计不可能；>6000 单段才可能）：截半重试
            mid = (first.char_start + min(first.char_end, len(text))) // 2
            self.verified = self.rag.prepare_selected_evidence(selection, [dict(
                documentRevisionId=revision.revision_id, charStart=first.char_start, charEnd=mid)])
        # 假 LangChain 模型 + 句柄
        self.model = FakeStructuredChatModel()
        self.handle = FakeAgentHandle(self.model)
        self.calls = 0
        original_ainvoke = self.model.with_structured_output

        def counting(schema, **kwargs):  # noqa: ANN001, ANN202
            self.calls += 1
            return original_ainvoke(schema, **kwargs)

        self.model.with_structured_output = counting
        self.reply = reply()
        self.model.default_reply = self.reply
        # 生成服务（fixed/practice reader 复用练习域真实读取器/服务）
        self.service = LessonGenerationService(
            self.catalog, analysis_reader=self.analysis.service, knowledge_catalog=self.knowledge,
            evidence_reader=self.rag, fixed_question_reader=self.fixed_question_reader,
            practice_reader=self.practice_scene.service, model_resolver=lambda _: self.handle,
            frozen_model_resolver=lambda _: self.handle, question_owner_id="local-user",
        )
        from app.repositories.jobs.repository import JobStore

        self.store = JobStore(self.catalog, domain="teaching", table="workflow_jobs",
                              kinds=frozenset({"analysis", "lesson_generation"}))
        # 种子教案（归档口径）
        self._seed_lesson()
        context = dict(subjectId="math", classId="class", classNameAtSave="当前班名", analysis=None)
        self.lesson = LessonView.model_validate(dict(lessonPlanId="lesson", subjectId="math", classId="class", revision=1,
            currentRevisionId="lesson-r", currentRevision=dict(lessonPlanId="lesson", revisionId="lesson-r", version=1,
                data=data(), contentHash="seed", source="manual", contextSnapshot=context, analysisRunId=None,
                acceptedProposalId=None, importEnvelope=None, selectedFields=[], processMetadata=[],
                reviewState="unreviewed", createdAt=self._now)))
        self.body = LessonGenerateRequest(submissionId="generate", baseRevisionId="lesson-r", baseServerRevision=1,
            analysisRunId=receipt.run_id, classId="class", selectedKnowledgePointIds=["k1", "k2"],
            requirements="按固定班级统计设计复习", durationMinutes=40, modelProfileId="isolated-profile",
            scopeSnapshot=self.verified.scope_snapshot, evidenceRefs=self.verified.evidence_refs,
            questionRevisionIds=[], practiceRevisionIds=[])
        return self

    def _seed_lesson(self) -> None:
        self._now = now_iso()
        context = dict(subjectId="math", classId="class", classNameAtSave="当前班名", analysis=None)
        with self.catalog.write_transaction() as conn:
            conn.execute("INSERT INTO lesson_plans VALUES('lesson','local','math','class','lesson-r',1,NULL,?,?)",
                         (self._now, self._now))
            conn.execute(
                "INSERT INTO lesson_plan_revisions VALUES('lesson-r','lesson','local',1,?,'seed','manual',?,NULL,NULL,NULL,'{}','[]','[]',?)",
                (json.dumps(data(), ensure_ascii=False), json.dumps(context, ensure_ascii=False), self._now))
            conn.execute("INSERT INTO lesson_revision_reviews VALUES('lesson-r','lesson','local','unreviewed',NULL,?)",
                         (self._now,))

    def prepare(self, body=None, lesson=None):
        return self.service.prepare(body or self.body, lesson=lesson or self.lesson, owner_id="local")

    @property
    def engine(self):
        """按需真实引擎（run_job 直跑）；需要捕获调度的测试自行替换为 ManualEngine。"""
        if getattr(self, "_engine", None) is None:
            from app.services.jobs.engine import JobEngine

            self._engine = JobEngine({"teaching": self.store})
        return self._engine

    @engine.setter
    def engine(self, value) -> None:
        self._engine = value

    def job(self, prepared=None):
        prepared = prepared or self.prepare()
        with self.catalog.write_transaction() as conn:
            job = self.store.create_in(conn, kind="lesson_generation", frozen_input=prepared.frozen_input,
                model_snapshot=prepared.model_snapshot, owner_id="local")
            self.service.insert_input_in(conn, job=job, prepared=prepared, owner_id="local")
        return job

    async def run(self, job=None):
        job = job or self.job()
        return await self.engine.run_job("teaching", job.job_id, self.service.executor_for(job), uses_model=True)

    def question(self, text="固定课堂问题", owner="local-user", subject="math"):
        """种一道固定题（归档 PracticesScene 口径：同 subject、挂 k1/k2 链接）。"""
        from app.contracts.teaching_loop import canonical_hash

        content = dict(type="short_answer", stemMarkdown=text, options=[], answer=None,
                       explanationMarkdown=None, assetIds=[], richContent=None)
        links = [dict(knowledgePointId=kp, knowledgeRevisionId=kp + "-r", subjectIdSnapshot=subject,
                      knowledgeNameSnapshot="固定" + kp, role="primary") for kp in ("k1", "k2")]
        with self.questions.write_transaction() as conn:
            return self.questions.insert_question_in(conn, owner_id=owner, content=content,
                metadata={"subjectId": subject, "difficulty": "easy"}, answer_state="not_provided",
                content_fingerprint=canonical_hash(content), source_spans=[], import_id=None, knowledge_links=links)

    def count(self, table: str) -> int:
        assert table in {"lesson_ai_proposals", "lesson_generation_inputs", "lesson_plan_revisions"}
        with self.catalog.read_connection() as conn:
            return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    async def close(self) -> None:
        self.textbook_harness.catalog.close()
        for catalog in (self.catalog, self.knowledge, self.questions):
            catalog.close()


#: 归档测试以 ``Scene`` 命名引用生成现场；R7 改造后同一个类（假 LangChain 模型）。
Scene = GenerationScene
