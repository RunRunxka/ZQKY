"""B5 AI: real four catalogs/readers and three real provider serializers.

Only HTTP transport/model replies and embedding vectors are substituted. This
module never imports app.main; outer runner establishes a fresh OS TEMP first.
"""
import asyncio
import copy
import json
from dataclasses import replace

import httpx2 as httpx
from app.contracts.lesson_plans import LessonGenerateRequest, LessonView
from app.contracts.teaching_loop import canonical_hash
from app.core.sqlite import now_iso
from app.providers.llm.base import LLMConfig
from app.providers.llm.openai_chat import OpenAIChatProvider
from app.providers.llm.openai_responses import OpenAIResponsesProvider
from app.providers.llm.anthropic_messages import AnthropicMessagesProvider
from app.schemas.model_config import ModelProtocol
from app.repositories.jobs.repository import JobStore
from app.services.jobs.engine import JobEngine
from app.services.model_runtime import ChatModelHandle, fingerprint_of_handle
from app.services.lesson_generation import LessonGenerationService
from app.services.question_bank.fixed import FixedQuestionReader
from tests.analysis_support import AnalysisScene
from tests.practices_support import PracticesScene
from tests.test_rag_v2_support import RagEnv, sample_text


def reply():
    ids = ["new:N1", "new:N2", "new:N3", "new:N4"]
    return dict(patch=dict(coreCompetencies="依据固定班级计数安排学习活动", keyPoints="两项知识点复习",
        teachingDesign="通过固定教材开展探究", exercises="请使用已确认课堂题", process=[
            dict(id=key, stage="环节"+str(i), design="对照教材讨论", secondary="") for i, key in enumerate(ids)]),
        budget=dict(durationMinutes=40, stages=[dict(processId=key, phase=phase, minutes=10,
            knowledgeAliases=["K1", "K2"], activity="比较固定题目", check="课堂口头检测", evidenceAliases=["E1"])
            for key, phase in zip(ids, ("introduction", "exploration", "practice", "conclusion"))]))


def data():
    return dict(title="教师原题", totalLessons="2", currentLessonNo="1", lessonTypes=["review", "new"],
        otherTypeText="教师课型", coreCompetencies="原素养", keyPoints="原要点", teachingDesign="原设计",
        process=[dict(id="old-safe", stage="原过程", design="原过程设计", secondary="原二次备课")],
        exercises="原练习", reflection="教师反思")


class Scene:
    @classmethod
    async def create(cls, root, protocol="openai_chat"):
        self = cls()
        self.root = root
        self.analysis = AnalysisScene(root)
        receipt = await self.analysis.ready()
        self.practice_scene = PracticesScene(self.analysis)
        self.practice_scene.run_id = receipt.run_id
        self.catalog = self.analysis.catalog
        self.rag_env = RagEnv(root / "rag")
        document = self.rag_env.add_document(title="固定集合教材", text=sample_text(title="集合", sentences=5))
        self.rag = self.rag_env.make_service()
        chunk = document.first_body_chunk()
        self.verified = self.rag.prepare_selected_evidence(self.rag_env.selection(document), [dict(
            documentRevisionId=document.revision_id, charStart=chunk.char_start, charEnd=chunk.char_end)])
        now = now_iso()
        context = dict(subjectId="math", classId="class", classNameAtSave="当前班名", analysis=None)
        with self.catalog.write_transaction() as conn:
            conn.execute("INSERT INTO lesson_plans VALUES('lesson','local','math','class','lesson-r',1,NULL,?,?)", (now,now))
            conn.execute("INSERT INTO lesson_plan_revisions VALUES('lesson-r','lesson','local',1,?,'seed','manual',?,NULL,NULL,NULL,'{}','[]','[]',?)",
                         (json.dumps(data(),ensure_ascii=False), json.dumps(context,ensure_ascii=False), now))
            conn.execute("INSERT INTO lesson_revision_reviews VALUES('lesson-r','lesson','local','unreviewed',NULL,?)", (now,))
        self.lesson = LessonView.model_validate(dict(lessonPlanId="lesson", subjectId="math", classId="class", revision=1,
            currentRevisionId="lesson-r", currentRevision=dict(lessonPlanId="lesson", revisionId="lesson-r", version=1,
                data=data(), contentHash="seed", source="manual", contextSnapshot=context, analysisRunId=None,
                acceptedProposalId=None, importEnvelope=None, selectedFields=[], processMetadata=[], reviewState="unreviewed", createdAt=now)))
        self.body = LessonGenerateRequest(submissionId="generate", baseRevisionId="lesson-r", baseServerRevision=1,
            analysisRunId=receipt.run_id, classId="class", selectedKnowledgePointIds=["k1", "k2"], requirements="按固定班级统计设计复习",
            durationMinutes=40, modelProfileId="isolated-profile", scopeSnapshot=self.verified.scope_snapshot,
            evidenceRefs=self.verified.evidence_refs, questionRevisionIds=[], practiceRevisionIds=[])
        self.wires, self.calls = [], 0
        self.reply, self.finish, self.delay, self.fail_http = reply(), "stop", 0, None
        self.started = asyncio.Event()
        async def transport_handler(request):
            self.calls += 1
            self.started.set()
            self.wires.append(dict(url=str(request.url), body=json.loads(request.content)))
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.fail_http:
                return httpx.Response(self.fail_http, json={"error": "fixture upstream failure"})
            text = self.reply if isinstance(self.reply, str) else json.dumps(self.reply,ensure_ascii=False)
            if protocol == "openai_chat":
                payload = {"choices":[{"message":{"content":text},"finish_reason":self.finish}]}
            elif protocol == "openai_responses":
                payload = {"status":"completed" if self.finish=="stop" else "incomplete",
                    "incomplete_details":{"reason":"max_output_tokens"},"output_text":text}
            else:
                payload = {"content":[{"type":"text","text":text}], "stop_reason":"end_turn" if self.finish=="stop" else "max_tokens"}
            return httpx.Response(200,json=payload)
        provider = {"openai_chat":OpenAIChatProvider,"openai_responses":OpenAIResponsesProvider,
                    "anthropic_messages":AnthropicMessagesProvider}[protocol]()
        original = provider.complete
        async def complete(config, request):
            return await original(config,request,transport=httpx.MockTransport(transport_handler))
        provider.complete = complete
        self.handle = ChatModelHandle("isolated-profile","isolated-model",provider,
            LLMConfig(protocol=getattr(ModelProtocol, protocol), baseUrl="http://127.0.0.1:9",modelId="isolated-model",apiKey="fixture-key"),50000)
        self.service = LessonGenerationService(self.catalog,analysis_reader=self.analysis.service,
            knowledge_catalog=self.practice_scene.knowledge, evidence_reader=self.rag,
            fixed_question_reader=FixedQuestionReader(self.practice_scene.questions), practice_reader=self.practice_scene.service,
            model_resolver=lambda _: self.handle, frozen_model_resolver=lambda _: self.handle, question_owner_id="local-user")
        self.store = JobStore(self.catalog,domain="teaching",table="workflow_jobs",kinds=frozenset({"analysis","lesson_generation"}))
        self.engine = JobEngine({"teaching": self.store})
        return self

    def prepare(self, body=None, lesson=None):
        return self.service.prepare(body or self.body,lesson=lesson or self.lesson,owner_id="local")

    def job(self, prepared=None):
        prepared = prepared or self.prepare()
        with self.catalog.write_transaction() as conn:
            job = self.store.create_in(conn,kind="lesson_generation",frozen_input=prepared.frozen_input,
                model_snapshot=prepared.model_snapshot,owner_id="local")
            self.service.insert_input_in(conn,job=job,prepared=prepared,owner_id="local")
        return job

    async def run(self, job=None):
        job = job or self.job()
        return await self.engine.run_job("teaching",job.job_id,self.service.executor_for(job),uses_model=True)

    def question(self,text="固定课堂问题",owner="local-user",subject="math"):
        content = dict(type="short_answer",stemMarkdown=text,options=[],answer=None,explanationMarkdown=None,assetIds=[],richContent=None)
        links = [dict(knowledgePointId=kp,knowledgeRevisionId=kp+"-r",subjectIdSnapshot=subject,knowledgeNameSnapshot="固定"+kp,role="primary") for kp in ("k1","k2")]
        with self.practice_scene.questions.write_transaction() as conn:
            return self.practice_scene.questions.insert_question_in(conn,owner_id=owner,content=content,
                metadata={"subjectId":subject,"difficulty":"easy"},answer_state="not_provided",content_fingerprint=canonical_hash(content),
                source_spans=[],import_id=None,knowledge_links=links)

    def count(self, table):
        assert table in {"lesson_ai_proposals","lesson_generation_inputs","lesson_plan_revisions"}
        with self.catalog.read_connection() as conn:
            return conn.execute("SELECT count(*) FROM "+table).fetchone()[0]

    async def close(self):
        await self.engine.shutdown()
        await self.rag.close()
        for cat in (self.catalog,self.practice_scene.knowledge,self.practice_scene.questions,self.practice_scene.textbooks,self.rag_env.catalog):
            cat.close()
