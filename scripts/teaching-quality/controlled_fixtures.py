"""New anonymous source rebuild through production catalogs/services only.

Case facts come from the original handwritten spec, never an old QA module.
No app.main, external vector/embedding service or model is imported/called.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import replace
from pathlib import Path

import httpx2 as httpx

from common import canonical, require, sha_bytes
from app.contracts.assessments import AssessmentCreateRequest
from app.contracts.b4 import AnalysisCreateRequest
from app.contracts.lesson_plans import LessonCreateRequest, LessonGenerateRequest
from app.contracts.scores import ScoreParticipantSnapshot, ScoreItemSnapshot
from app.contracts.teaching_loop import canonical_hash
from app.core.sqlite import now_iso
from app.providers.llm.base import LLMConfig
from app.providers.llm.openai_chat import OpenAIChatProvider
from app.providers.llm.openai_responses import OpenAIResponsesProvider
from app.providers.llm.anthropic_messages import AnthropicMessagesProvider
from app.repositories.jobs.repository import JobStore
from app.repositories.knowledge.catalog import KnowledgeCatalog
from app.repositories.question_bank.catalog import QuestionBankCatalog
from app.repositories.teaching.catalog import TeachingCatalog
from app.repositories.teaching.papers import PaperRepository, ItemKnowledgeRecord
from app.repositories.teaching.scores import ScoreRepository
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.schemas.model_config import ModelProtocol
from app.services.analysis.service import AnalysisService
from app.services.assets.store import AssetStore
from app.services.assessments.service import AssessmentService
from app.services.document_parsing import parse_document, source_map_payload, chunk_document, DEFAULT_CHUNK_POLICY, PARSER_VERSION, chunk_manifest_sha256, chunk_policy_fingerprint
from app.services.jobs.engine import JobEngine
from app.services.lesson_generation.service import LessonGenerationService
from app.services.lesson_plans.service import LessonPlanService
from app.services.model_runtime import ChatModelHandle, fingerprint_of_handle
from app.services.papers.reader import ConfirmedPaperReaderAdapter
from app.services.practices.service import PracticeService
from app.services.publication import PublicationCoordinator
from app.services.question_bank.fixed import FixedQuestionReader
from app.services.rag_v2.service import RagV2Service
from app.services.textbook_ingest.blobs import BlobStore, sha256_text
from app.services.textbook_ingest.generation_doc import generation_policy_document


def lesson_data():
    return dict(title="教师保留题目", totalLessons="2", currentLessonNo="1", lessonTypes=["review"], otherTypeText="教师课型",
        coreCompetencies="原素养", keyPoints="原要点", teachingDesign="原设计", exercises="原练习", reflection="教师保留反思",
        process=[dict(id="old-process", stage="原环节", design="原设计", secondary="教师二次备课原文")])


def fixture_answer(spec):
    ids = ["new:N1", "new:N2", "new:N3", "new:N4"]
    # Deliberately differs from the old stageMinutes exact fixture fingerprint.
    duration = spec["durationMinutes"]
    minutes = [1,1,2,1] if duration == 5 else [max(1, duration//4-1), duration//4+1, duration//4, duration-3*(duration//4)]
    aliases = ["K"+str(n+1) for n in range(len(spec["selectedKnowledgeIndexes"]))]
    return dict(patch=dict(coreCompetencies="对照固定依据解释运算", keyPoints="符号与绝对值", teachingDesign=spec["interpretation"], exercises="待教师审核的课堂检测建议",
        process=[dict(id=x, stage="环节"+str(n+1), design="对照固定依据解释步骤", secondary="教师可补充课堂观察") for n,x in enumerate(ids)]),
        budget=dict(durationMinutes=duration, stages=[dict(processId=x, phase=phase, minutes=m, knowledgeAliases=aliases,
            activity="依据固定教材进行比较", check="课堂出口检测", evidenceAliases=["E1"])
            for x,phase,m in zip(ids,("introduction","exploration","practice","conclusion"),minutes)]))


class SourceScene:
    def __init__(self, root, protocol="openai-chat"):
        self.root, self.protocol = Path(root), protocol
        self.root.mkdir(parents=True, exist_ok=True)
        self.catalog = TeachingCatalog(self.root / "teaching.sqlite3")
        self.knowledge = KnowledgeCatalog(self.root / "knowledge.sqlite3")
        self.questions = QuestionBankCatalog(self.root / "question-bank.sqlite3")
        self.textbooks = TextbookCatalog(self.root / "textbooks" / "catalog.sqlite3")
        for catalog in (self.catalog, self.knowledge, self.questions, self.textbooks):
            catalog.migrate()
        self.assets = AssetStore(self.root / "assets")
        self.store = JobStore(self.catalog, domain="teaching", table="workflow_jobs", kinds=frozenset({"analysis","lesson_generation","export"}))
        self.engine = JobEngine({"teaching": self.store}, model_limit=1)
        self.analysis = AnalysisService(self.catalog, job_engine=self.engine, asset_store=self.assets)
        self.coordinator = PublicationCoordinator()
        self.points = []
        with self.knowledge.write_transaction() as conn:
            conn.execute("INSERT INTO subjects(id,code,name) VALUES('math','math','数学')")
            for n,name in enumerate(("有理数加法", "符号与绝对值", "无题知识点")):
                key, revision = uuid.uuid4().hex, uuid.uuid4().hex
                conn.execute("INSERT INTO knowledge_points(id,subject_id,code,current_revision_id) VALUES(?,'math',?,?)", (key,"K"+str(n),revision))
                conn.execute("INSERT INTO knowledge_point_revisions(id,knowledge_point_id,version,name) VALUES(?,?,1,?)", (revision,key,name))
                self.points.append(dict(knowledgePointId=key,knowledgeRevisionId=revision,name=name,role="primary"))
        self.rag = self._textbook()
        self.fixed_questions = FixedQuestionReader(self.questions)
        content = dict(type="short_answer",stemMarkdown="计算同号两数的和并说明符号",options=[],answer=None,explanationMarkdown=None,assetIds=[],richContent=None)
        with self.questions.write_transaction() as conn:
            question = self.questions.insert_question_in(conn,owner_id="local-user",content=content,metadata={"subjectId":"math","difficulty":"easy"},answer_state="not_provided",
                content_fingerprint=canonical_hash(content),source_spans=[],import_id=None,knowledge_links=[dict(knowledgePointId=p["knowledgePointId"],knowledgeRevisionId=p["knowledgeRevisionId"],subjectIdSnapshot="math",knowledgeNameSnapshot=p["name"],role="primary") for p in self.points[:2]])
        self.question_revision_id = question.current_revision_id
        self.practices = PracticeService(self.catalog, analysis_reader=self.analysis, fixed_question_reader=self.fixed_questions,
            knowledge_catalog=self.knowledge, coordinator=self.coordinator, assets=self.assets, question_asset_reader=lambda _id: None,
            job_engine=self.engine, file_assets=None, assessment_service=AssessmentService(self.catalog,reader=ConfirmedPaperReaderAdapter(self.catalog)),question_owner_id="local-user")
        provider = {"openai-chat": OpenAIChatProvider, "openai-responses": OpenAIResponsesProvider, "anthropic-messages": AnthropicMessagesProvider}[protocol]()
        self.handle = ChatModelHandle("controlled-fixture-profile", "controlled-fixture-model", provider,
            LLMConfig(protocol=ModelProtocol(protocol),baseUrl="http://127.0.0.1:9",modelId="controlled-fixture-model",apiKey="fixture-only-key",modelProfileId="controlled-fixture-profile"),4096)
        self.generation = LessonGenerationService(self.catalog, analysis_reader=self.analysis, knowledge_catalog=self.knowledge,
            evidence_reader=self.rag, fixed_question_reader=self.fixed_questions, practice_reader=self.practices,
            model_resolver=lambda _: self.handle, frozen_model_resolver=lambda _: self.handle, question_owner_id="local-user")
        self.lessons = LessonPlanService(self.catalog,analysis_reader=self.analysis,knowledge_catalog=self.knowledge,coordinator=self.coordinator,
            job_engine=self.engine,generation_service=self.generation,evidence_reader=self.rag)
        self.actual_wire_sends = 0
        self.response_text, self.finish, self.usage, self.status, self.delay = None, "stop", None, 200, 0
        self.started = asyncio.Event()

    def _textbook(self):
        blobs = BlobStore(self.textbooks.db_path.parent)
        blobs.ensure_dirs()
        profile = self.textbooks.create_embedding_profile(fingerprint="controlled-fixture-embedding-"+uuid.uuid4().hex,
            adapter="ollama",native_base_url="http://127.0.0.1:9",model_name="fixture-not-called",model_manifest_digest="fixture-digest",
            dimensions=8,distance="cosine",query_prefix="",document_prefix="",normalization="none")
        generation = self.textbooks.create_generation(profile_id=profile.profile_id,collection_name="controlled_fixture",
            chunk_policy_json=generation_policy_document(DEFAULT_CHUNK_POLICY,[]),state="building")
        self.textbooks.publish_generation(generation.generation_id)
        self.textbooks.set_active_generation(generation.generation_id)
        library = self.textbooks.create_library(kind="base",owner_id="system",display_name="匿名固定教材",grade_id="senior-1",subject_id="math",edition_id="renjiao-a")
        path = self.root / "owned-textbook.md"
        path.write_text("# 有理数加法\n\n同号两数相加，取相同符号，并把绝对值相加。异号两数相加，取绝对值较大加数的符号，并用较大绝对值减较小绝对值。具体错因需教师核实。\n",encoding="utf-8")
        parsed = parse_document(path=path,file_name=path.name)
        sealed = {}
        for area,key,data in (("normalized","normalized",parsed.normalized_text.encode("utf-8")),("normalized","map",canonical(source_map_payload(parsed))),("blobs","original",path.read_bytes())):
            blob = blobs.write_staged_bytes(data)
            blobs.seal(area=area,blob_id=blob)
            sealed[key] = blob
        doc = self.textbooks.create_document(owner_id="system",title="匿名有理数教材",stage_id="senior",grade_ids=["senior-1"],subject_id="math",edition_id="renjiao-a",library_ids=[library.library_id])
        revision = self.textbooks.create_document_revision(doc.document_id,original_file_sha256=sealed["original"],normalized_text_sha256=sha256_text(parsed.normalized_text),
            parser_version=PARSER_VERSION,original_blob_id=sealed["original"],normalized_blob_id=sealed["normalized"],source_map_blob_id=sealed["map"],char_count=len(parsed.normalized_text))
        chunks = chunk_document(parsed,policy=DEFAULT_CHUNK_POLICY)
        chunk_set = self.textbooks.create_chunk_set(revision.revision_id,policy_fingerprint=chunk_policy_fingerprint(),manifest_sha256=chunk_manifest_sha256(chunks),chunks=chunks)
        self.textbooks.publish_document_revision(doc.document_id,revision_id=revision.revision_id,metadata_revision_id=doc.current_metadata_revision_id)
        self.textbooks.upsert_generation_revision(generation.generation_id,revision.revision_id,chunk_set.chunk_set_id,state="ready",expected_chunk_count=len(chunks),manifest_sha256=chunk_manifest_sha256(chunks))
        rag = RagV2Service(catalog=self.textbooks)
        chunk = next(x for x in chunks if x.region == "body")
        self.verified = rag.prepare_selected_evidence(dict(gradeId="senior-1",subjectId="math",editionId="renjiao-a",documentIds=[doc.document_id]),
            [dict(documentRevisionId=revision.revision_id,charStart=chunk.char_start,charEnd=chunk.char_end)])
        return rag

    async def fixed_sources(self, spec):
        key = spec["caseId"]
        original = self.assets.store_original(b"owned anonymous paper",media_type="text/plain",original_name="owned-paper.txt")
        original_id = uuid.uuid4().hex
        repository = PaperRepository(self.catalog)
        items = []
        with self.catalog.write_transaction() as conn:
            conn.execute("INSERT INTO file_assets(id,kind,blob_key,sha256,original_name,media_type,byte_size,created_at) VALUES(?,'paper',?,?,?,'text/plain',?,?)",(original_id,original.blob_key,original.sha256,"owned-paper.txt",original.byte_size,now_iso()))
            paper = repository.create_paper_in(conn,subject_id="math",title="匿名原卷"+key)
            revision = repository.create_revision_in(conn,paper_id=paper.paper_id,version=1,source_file_id=original_id,total_score_units=sum(x["maxScoreUnits"] for x in spec["items"]),title_snapshot="匿名原卷"+key)
            for n,item in enumerate(spec["items"]):
                iid = uuid.uuid4().hex
                items.append(iid)
                rich = dict(version=2,stemBlocks=[dict(id="stem",kind="paragraph",text="计算有理数并说明依据")],sharedMaterials=[],optionBlocks={},answerBlocks=[],explanationBlocks=[],assets=[],origin=dict(originalAssetId=original_id,originalSha256=original.sha256,sourceLocator={"paragraphIndex":n+1}))
                repository.insert_items_in(conn,paper_revision_id=revision.revision_id,items=[dict(item_id=iid,parent_item_id=None,question_no="Q"+str(n+1),ordinal=n+1,is_scored=True,max_score_units=item["maxScoreUnits"],content=rich,source_locator={"paragraphIndex":n+1})])
                repository.insert_item_knowledge_in(conn,item_id=iid,paper_revision_id=revision.revision_id,knowledge=[ItemKnowledgeRecord(self.points[k]["knowledgePointId"],self.points[k]["knowledgeRevisionId"],self.points[k]["name"],"primary","human") for k in item["knowledgeIndexes"]])
            repository.confirm_revision_in(conn,revision.revision_id)
            repository.set_current_revision_in(conn,paper.paper_id,revision.revision_id)
            classes = [uuid.uuid4().hex for _ in range(max(x["classIndex"] for x in spec["participants"])+1)]
            for n,cid in enumerate(classes):
                conn.execute("INSERT INTO classes(id,code,name,school_year,grade_id) VALUES(?,?,?,'2026','g')",(cid,key+str(n),"匿名班"+key+str(n)))
            students = {}
            for participant in spec["participants"]:
                if participant["alias"] not in students:
                    sid = uuid.uuid4().hex
                    students[participant["alias"]] = sid
                    conn.execute("INSERT INTO students(id,student_no,name) VALUES(?,?,?)",(sid,"owned-"+key+"-"+participant["alias"],"自有匿名样本"+key+participant["alias"]))
                    conn.execute("INSERT INTO class_memberships(id,class_id,student_id,joined_on) VALUES(?,?,?,'2026-01-01')",(uuid.uuid4().hex,classes[participant["classIndex"]],sid))
        requested = [dict(studentId=students[x["alias"]],classId=classes[x["classIndex"]],attendance=x["attendance"],attemptNo=x["attemptNo"],classConfirmed=True,classConfirmationNote="匿名QA固定样本指定本次班级") for x in spec["participants"]]
        assessment = AssessmentService(self.catalog,reader=ConfirmedPaperReaderAdapter(self.catalog)).create_assessment(AssessmentCreateRequest(submissionId=key+"-assessment",paperRevisionId=revision.revision_id,title="匿名施测"+key,assessmentType="exam",heldOn="2026-10-04",classIds=classes,participants=requested))
        actual = [next(p for p in assessment.participants if p.student_id == r["studentId"] and p.class_id == r["classId"] and p.attempt_no == r["attemptNo"]) for r in requested]
        snapshots = [ScoreParticipantSnapshot(participantId=p.participant_id,studentId=p.student_id,classId=p.class_id,attemptNo=p.attempt_no,attendance=p.attendance,name=p.name_snapshot,studentNo=p.student_no_snapshot) for p in actual]
        scores = ScoreRepository(self.catalog)
        with self.catalog.write_transaction() as conn:
            rid = scores.insert_revision_in(conn,assessment_id=assessment.assessment.assessment_id,version=1,source_import_id=None,base_revision_id=None,participant_snapshot=snapshots,item_snapshot=[ScoreItemSnapshot(itemId=iid,itemPath="Q"+str(n+1),maxScoreUnits=spec["items"][n]["maxScoreUnits"]) for n,iid in enumerate(items)])
            scores.insert_matrix_in(conn,revision_id=rid,assessment_id=assessment.assessment.assessment_id,paper_revision_id=revision.revision_id,cells=[(actual[n].participant_id,iid,state,units) for n,p in enumerate(spec["participants"]) for iid,(state,units) in zip(items,p["cells"])])
            scores.seal_revision_in(conn,rid)
            scores.set_active_revision_in(conn,assessment.assessment.assessment_id,revision_id=rid,expected_revision=assessment.assessment.revision)
        receipt = await self.analysis.create_run(assessment.assessment.assessment_id,AnalysisCreateRequest(submissionId=key+"-analysis",scoreRevisionId=rid,selectedParticipantIds=[actual[n].participant_id for n in spec["selectedParticipantIndexes"]],ruleCode="any_loss_v1"))
        done = await self.engine.schedule("teaching",receipt.job.job_id,self.analysis.execute_job)
        require(done.state == "succeeded", "analysis", "new fixed source analysis failed")
        report = self.analysis.read_ready_report(receipt.run_id)
        cid = classes[spec["selectedClassIndex"]]
        for point_index, expected in zip(spec["selectedKnowledgeIndexes"],spec["expectedTargetCounts"]):
            row = next(x for x in report["classes"] if x["classId"] == cid and x["knowledgePoint"]["knowledgePointId"] == self.points[point_index]["knowledgePointId"])
            require({k:row[k] for k in expected} == expected,"fixedCounts","production facts differ from independent handwritten oracle")
        return receipt.run_id, cid

    async def case(self, spec):
        run_id,cid = await self.fixed_sources(spec)
        context = dict(analysisRunId=run_id,selectedKnowledgePointIds=[self.points[n]["knowledgePointId"] for n in spec["selectedKnowledgeIndexes"]])
        created = self.lessons.create_lesson(LessonCreateRequest(submissionId=spec["caseId"]+"-create",subjectId="math",classId=cid,data=lesson_data(),context=context,source="manual"))
        lesson_id = created["lessonPlanId"]
        lesson = self.lessons.get_lesson(lesson_id)
        body = LessonGenerateRequest(submissionId=spec["caseId"]+"-generate",baseRevisionId=lesson["currentRevisionId"],baseServerRevision=lesson["revision"],analysisRunId=run_id,classId=cid,
            selectedKnowledgePointIds=[self.points[n]["knowledgePointId"] for n in spec["selectedKnowledgeIndexes"]],requirements=spec["requirements"],durationMinutes=spec["durationMinutes"],
            modelProfileId=self.handle.profile_id,scopeSnapshot=self.verified.scope_snapshot,evidenceRefs=self.verified.evidence_refs,questionRevisionIds=[self.question_revision_id] if spec["questionSource"] == "confirmed" else [],practiceRevisionIds=[])
        self.response_text = json.dumps(fixture_answer(spec),ensure_ascii=False)
        return lesson_id,body

    def transport(self):
        async def handler(request):
            self.actual_wire_sends += 1
            self.started.set()
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.status != 200:
                return httpx.Response(self.status,json={"error":"controlled fixture failure"})
            usage = self.usage
            if usage is None:
                usage = {"prompt_tokens":120,"completion_tokens":80,"total_tokens":200} if self.protocol == "openai-chat" else {"input_tokens":120,"output_tokens":80,"total_tokens":200}
            if self.protocol == "openai-chat":
                data = {"choices":[{"message":{"content":self.response_text},"finish_reason":self.finish}],"usage":usage}
            elif self.protocol == "openai-responses":
                data = {"output_text":self.response_text,"status":"completed" if self.finish == "stop" else "incomplete","incomplete_details":{"reason":"max_output_tokens"},"usage":usage}
            else:
                data = {"content":[{"type":"text","text":self.response_text}],"stop_reason":"end_turn" if self.finish == "stop" else "max_tokens","usage":usage}
            return httpx.Response(200,json=data)
        return httpx.MockTransport(handler)

    async def close(self):
        await self.engine.shutdown()
        await self.rag.close()
        for catalog in (self.catalog,self.knowledge,self.questions,self.textbooks):
            catalog.close()
