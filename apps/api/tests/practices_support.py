"""T80 real migrated four catalogs and actual T70/T30/JobEngine; no provider."""
import copy
import hashlib
import io
import json
import zipfile
import uuid
from app.contracts import b4
from app.contracts.teaching_loop import canonical_hash
from app.repositories.assets.file_assets import FileAssetsRepository
from app.repositories.jobs.repository import JobStore
from app.repositories.knowledge.catalog import KnowledgeCatalog
from app.repositories.question_bank.catalog import QuestionBankCatalog
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.services.assessments.service import AssessmentService
from app.services.papers.reader import ConfirmedPaperReaderAdapter
from app.services.practices.service import PracticeService
from app.services.publication import PublicationCoordinator
from app.services.question_bank.fixed import FixedQuestionReader
from app.services.question_bank.rich import project_blocks
from app.contracts.teaching_loop import RichContentV2
from tests.analysis_support import AnalysisScene, ManualEngine
from tests.rich_content_support import minimal_png


class PracticesScene:
    def __init__(self, analysis):
        self.analysis_scene = analysis
        self.root, self.catalog, self.assets = analysis.root, analysis.catalog, analysis.assets
        self.knowledge = KnowledgeCatalog(self.root / "knowledge.sqlite3")
        self.questions = QuestionBankCatalog(self.root / "question_bank.sqlite3")
        self.textbooks = TextbookCatalog(self.root / "textbook.sqlite3")
        for catalog in (self.knowledge, self.questions, self.textbooks):
            catalog.migrate()
        with self.knowledge.write_transaction() as conn:
            conn.execute("INSERT INTO subjects(id,code,name) VALUES('math','math','数学')")
            for kp in ("k1", "k2"):
                conn.execute("INSERT INTO knowledge_points(id,subject_id,code,current_revision_id) VALUES(?,'math',?,?)", (kp,kp,kp+"-r"))
                conn.execute("INSERT INTO knowledge_point_revisions(id,knowledge_point_id,version,name) VALUES(?,?,1,?)", (kp+"-r",kp,"固定"+kp))
        with self.catalog.write_transaction() as conn:
            for n in range(4):
                conn.execute("INSERT INTO class_memberships(id,class_id,student_id,joined_on) VALUES(?,'class',?,'2026-01-01')", (f"m{n}",f"s{n:03d}"))
        self.store = JobStore(self.catalog, domain="teaching", table="workflow_jobs", kinds=frozenset({"analysis","export"}))
        self.engine = ManualEngine(self.store)
        self.coordinator = PublicationCoordinator()
        self.assessments = AssessmentService(self.catalog, reader=ConfirmedPaperReaderAdapter(self.catalog))
        self.service = PracticeService(self.catalog, analysis_reader=analysis.service, fixed_question_reader=FixedQuestionReader(self.questions),
            knowledge_catalog=self.knowledge, coordinator=self.coordinator, assets=self.assets,
            question_asset_reader=self.read_asset, job_engine=self.engine, file_assets=FileAssetsRepository(self.catalog), assessment_service=self.assessments)
        self.source_assets = {}

    @classmethod
    async def create(cls, root):
        analysis = AnalysisScene(root)
        ready = await analysis.ready()
        scene = cls(analysis)
        scene.run_id = ready.run_id
        return scene

    def read_asset(self, asset_id):
        assert not self.coordinator.busy, "IO must occur before publication"
        return self.source_assets[asset_id]

    def question(self, text="新题", *, kps=("k1","k2"), difficulty="easy", rich=None, answer=True, subject="math", qtype="short_answer"):
        content = dict(type=qtype,stemMarkdown=text,options=[],assetIds=[],answer={"textMarkdown":"ANS_PRIVATE"} if answer else None,
                       explanationMarkdown="EXPL_PRIVATE" if answer else None,richContent=None)
        if rich:
            rich_model = RichContentV2.model_validate(rich)
            content.update(richContent=rich_model.model_dump(by_alias=True),stemMarkdown=project_blocks(rich_model.stem_blocks),
                answer={"textMarkdown":project_blocks(rich_model.answer_blocks)} if rich_model.answer_blocks else None,
                explanationMarkdown=project_blocks(rich_model.explanation_blocks),assetIds=[a.asset_id for a in rich_model.assets],
                options=[dict(key=k,textMarkdown=project_blocks(v)) for k,v in rich_model.option_blocks.items()])
        links = [dict(knowledgePointId=kp,knowledgeRevisionId=kp+"-r",subjectIdSnapshot=subject,knowledgeNameSnapshot="固定"+kp,role="primary") for kp in kps]
        with self.questions.write_transaction() as conn:
            return self.questions.insert_question_in(conn,owner_id="local",content=content,metadata={"subjectId":subject,"difficulty":difficulty},
                answer_state="provided" if answer else "not_provided",content_fingerprint=canonical_hash(content),source_spans=[],import_id=None,knowledge_links=links)

    def rich(self):
        image = minimal_png()
        digest = hashlib.sha256(image).hexdigest()
        asset_id = "blobs/"+digest
        self.source_assets[asset_id] = (image,"image/png")
        return dict(version=2, stemBlocks=[dict(id="stem",kind="paragraph",text="完整题干"),dict(id="f",kind="formula",latex=r"\frac{x}{2}"),
            dict(id="i",kind="image",assetId=asset_id,width=20,height=10),dict(id="t",kind="table",columnCount=2,cells=[
                dict(text="表头",isHeader=True,rowSpan=1,colSpan=2),dict(text="单元甲",rowSpan=1,colSpan=1),dict(text="单元乙",rowSpan=1,colSpan=1)])],
            sharedMaterials=[dict(id="m",blocks=[dict(id="mb",kind="paragraph",text="共享材料唯一出现")])],
            optionBlocks={"A":[dict(id="a",kind="paragraph",text="选项甲")],"B":[dict(id="b",kind="paragraph",text="选项乙")]},
            answerBlocks=[dict(id="ans",kind="paragraph",text="ANS_PRIVATE")],explanationBlocks=[dict(id="exp",kind="paragraph",text="EXPL_PRIVATE")],
            assets=[dict(assetId=asset_id,sha256=digest,mediaType="image/png")],
            origin=dict(originalAssetId="fixture-source",originalSha256="ab"*32,sourceLocator={"paragraphIndex":7}))

    def create_set(self, *, count=1, submission="create", targets=("k1","k2"), **constraints):
        return self.service.create_practice(b4.PracticeCreateRequest(submissionId=submission,analysisRunId=self.run_id,title="针对练习",
            targetKnowledgePointIds=list(targets),constraints=dict(count=count,**constraints)))

    def item(self, question, *, ordinal=1, score="1.25", nodes=None, kps=("k1","k2")):
        from app.services.practices.selection import as_rich
        snapshot = self.service.questions.read_revision(question.current_revision_id)
        rich = as_rich(snapshot)
        ids = [x["id"] for x in rich["stemBlocks"]]+[x["id"] for v in rich["optionBlocks"].values() for x in v]
        nodes = nodes or [dict(nodeKey="leaf",parentNodeKey=None,questionNo=str(ordinal),ordinal=1,isScored=True,maxScore=score,
                               knowledgePointIds=list(kps),sourceBlockIds=ids)]
        return dict(itemKey="item-"+str(ordinal),questionRevisionId=question.current_revision_id,ordinal=ordinal,maxScore=score,
            selectedKnowledgePointIds=list(kps),itemStructure={"nodes":nodes})

    def save(self, practice, items, *, submission=None):
        return self.service.save_draft(practice.practice_set_id,b4.PracticeDraftPatch(submissionId=submission or uuid.uuid4().hex, expectedRevision=practice.revision,
            items=items,constraints=practice.current_revision.constraints))

    def review(self, practice, submission="review"):
        return self.service.review(practice.practice_set_id,b4.PracticeReviewRequest(submissionId=submission,expectedRevision=practice.revision))

    def conversion(self, practice, *, submission="conversion", participants=None, **kwargs):
        request = b4.PracticeConversionRequest(submissionId=submission,title="练习施测",heldOn="2026-10-02",classIds=["class"],
            participants=participants or [dict(studentId="s000",classId="class",attendance="present",attemptNo=1)],**kwargs)
        return self.service.convert(practice.practice_set_id,practice.current_revision.practice_revision_id,request)

    async def export(self, practice, *, variant="student", submission=None, assessment_id=None):
        receipt = await self.service.create_export(practice.practice_set_id,practice.current_revision.practice_revision_id,
            b4.ExportRequest(submissionId=submission or variant,variant=variant,assessmentId=assessment_id))
        return receipt

    async def finish(self, receipt):
        return await self.engine.run_job("teaching",receipt.job.job_id,self.service._export_executor)

    def artifact(self, practice, export_id=None):
        result = self.service.list_exports(practice.practice_set_id,practice.current_revision.practice_revision_id)
        artifact = next(x for x in result.items if x.export_id==export_id) if export_id else result.items[0]
        file = self.service.file_assets.get(artifact.file_asset_id)
        return artifact,self.assets.read(file.blob_key)

    def count(self, table):
        assert table in {"papers","paper_revisions","paper_items","assessments","practice_conversions","practice_paper_item_mappings","practice_exports","export_artifacts","file_assets","command_submissions"}
        with self.catalog.read_connection() as conn:
            return conn.execute("SELECT count(*) FROM "+table).fetchone()[0]

    def integrity(self):
        from app.core.sqlite import open_readonly
        for cat in (self.catalog,self.knowledge,self.questions,self.textbooks):
            conn=open_readonly(cat.db_path)
            try:
                assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
                assert conn.execute("PRAGMA foreign_key_check").fetchall()==[]
            finally:
                conn.close()


def package_parts(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None
        return {name:archive.read(name) for name in archive.namelist()}


def marked_png(marker):
    """Valid stdlib PNG text chunk; no image packages or downloads."""
    import struct
    import zlib
    original=minimal_png()
    content=b"fixture\0"+marker.encode("utf-8")
    chunk=struct.pack(">I",len(content))+b"tEXt"+content+struct.pack(">I",zlib.crc32(b"tEXt"+content)&0xffffffff)
    assert original[-8:-4]==b"IEND"
    return original[:-12]+chunk+original[-12:]


def open_api_scene(root):
    """Reusable standard-main API context; owns no listener and keeps isolated files."""
    from contextlib import contextmanager
    from app.core.config import Settings
    from app.main import create_app
    from fastapi.testclient import TestClient
    @contextmanager
    def context():
        (root/"empty-textbooks").mkdir(parents=True,exist_ok=True)
        settings=Settings(host="127.0.0.1",port=8001,allowed_origins=frozenset({"http://127.0.0.1:5174"}),env="test",data_dir=root/"data",
            credentials_file=None,qdrant_url="http://127.0.0.1:16333",embedding_base_url="http://127.0.0.1:9",textbook_source_dir=root/"empty-textbooks")
        app=create_app(settings)
        with TestClient(app,base_url="http://127.0.0.1:8001") as client:
            yield app,client,settings
    return context()


def seed_api_loop(app, client, *, tag="t80-api"):
    """Actual HTTP T60→T70→T80→T30→T60→T70 and all three exports.

    Only the initial fixed source paper and confirmed bank question are fixture seeds,
    written using real repositories/confirmation DB guards. No business fetch mocks.
    Caller can keep this context open for root backup/recovery and browser seed work.
    """
    import time
    import uuid
    from types import SimpleNamespace
    from openpyxl import Workbook
    from app.repositories.teaching.papers import PaperRepository, ItemKnowledgeRecord
    from app.core.sqlite import now_iso

    def request(method,path,status=200,**kwargs):
        response=getattr(client,method)("/api/v1"+path,**kwargs)
        assert response.status_code==status,(path,response.status_code,response.text)
        return response.json()

    def ready(receipt):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            job=request("get","/workflow-jobs/"+receipt["job"]["jobId"],params={"domain":"teaching"})
            if job["state"] in {"succeeded","failed","cancelled","interrupted"}:
                assert job["state"]=="succeeded",job
                return job
            time.sleep(.03)
        raise AssertionError("bounded actual job wait expired")

    def score(assessment,student,question_no,submission):
        workbook=Workbook();sheet=workbook.active
        sheet.append(["学号","姓名",question_no]);sheet.append([student["studentNo"],student["name"],0])
        data=io.BytesIO();workbook.save(data)
        imported=request("post",f"/assessments/{assessment['assessmentId']}/score-imports",201,
            files={"file":("scores.xlsx",data.getvalue(),"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        return request("post",f"/score-imports/{imported['importId']}/confirm",json={"submissionId":submission,
            "expectedImportRevision":imported["revision"],"expectedAssessmentRevision":assessment["revision"],
            "previewVersion":imported["previewVersion"],"baseScoreRevisionId":None})

    points=[request("post","/knowledge-points",201,json=dict(subjectId="math",code=tag+str(n),name=tag+"知识点"+str(n))) for n in (1,2)]
    links=[dict(knowledgePointId=x["id"],knowledgeRevisionId=x["revisionId"],subjectIdSnapshot="math",knowledgeNameSnapshot=x["name"],role="primary") for x in points]
    helper=SimpleNamespace(source_assets={})
    rich=PracticesScene.rich(helper)
    for aid,(data,media) in helper.source_assets.items():
        app.state.asset_store.store_original(data,media_type=media,original_name="fixed.png")
    original=copy.deepcopy(rich);original["stemBlocks"][0]["text"]="初测独立题面"
    # Programmatic original file retained as real managed bytes, no formal template.
    from app.services.rich_content.renderer_docx import render_rich_document
    original_bytes=render_rich_document(rich=RichContentV2.model_validate(original),assets=app.state.asset_store,variant="teacher",title="原始测验")
    stored=app.state.asset_store.store_original(original_bytes,media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",original_name="source.docx")
    repository=PaperRepository(app.state.teaching)
    with app.state.teaching.write_transaction() as conn:
        file=app.state.file_assets.create_in(conn,kind="paper",blob_key=stored.blob_key,sha256=stored.sha256,byte_size=stored.byte_size,original_name="source.docx",media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        for a in original["assets"]:
            app.state.file_assets.create_in(conn,kind="attachment",blob_key="blobs/"+a["sha256"],sha256=a["sha256"],byte_size=len(helper.source_assets[a["assetId"]][0]),original_name="fixed.png",media_type=a["mediaType"],asset_id=a["assetId"])
        paper=repository.create_paper_in(conn,subject_id="math",title="初测原卷")
        revision=repository.create_revision_in(conn,paper_id=paper.paper_id,version=1,source_file_id=file.asset_id,total_score_units=125,title_snapshot="初测原卷")
        item_id=uuid.uuid4().hex
        repository.insert_items_in(conn,paper_revision_id=revision.revision_id,items=[dict(item_id=item_id,parent_item_id=None,question_no="Q1",ordinal=1,is_scored=True,max_score_units=125,content=original,source_locator={"paragraphIndex":1})])
        repository.insert_item_knowledge_in(conn,item_id=item_id,paper_revision_id=revision.revision_id,knowledge=[ItemKnowledgeRecord(x["knowledgePointId"],x["knowledgeRevisionId"],x["knowledgeNameSnapshot"],"primary","human") for x in links])
        repository.confirm_revision_in(conn,revision.revision_id);repository.set_current_revision_in(conn,paper.paper_id,revision.revision_id)
    klass=request("post","/classes",201,json={"code":tag,"name":"测试班级","schoolYear":"2026","gradeId":"g"})
    student=request("post","/students",201,json={"name":"测试学生","studentNo":"00001","classId":klass["id"],"joinedOn":"2026-01-01"})
    participants=[dict(studentId=student["id"],classId=klass["id"],attendance="present",attemptNo=1)]
    assessment=request("post","/assessments",201,json=dict(submissionId=tag+"-initial-assessment",paperRevisionId=revision.revision_id,title="初测",assessmentType="exam",heldOn="2026-10-02",classIds=[klass["id"]],participants=participants))
    initial_score=score(assessment["assessment"],student,"Q1",tag+"-initial-score")
    analysis=request("post",f"/assessments/{assessment['assessment']['assessmentId']}/analysis-runs",202,json=dict(submissionId=tag+"-initial-analysis",scoreRevisionId=initial_score["revisionId"],selectedParticipantIds=[assessment["participants"][0]["participantId"]],ruleCode="any_loss_v1"))
    ready(analysis)
    note=request("post",f"/analysis-runs/{analysis['runId']}/notes",201,json=dict(submissionId=tag+"-note",participantId=assessment["participants"][0]["participantId"],knowledgePointId=links[0]["knowledgePointId"],note="教师补充：具体错因待核实"))
    model=RichContentV2.model_validate(rich)
    content=dict(type="short_answer",stemMarkdown=project_blocks(model.stem_blocks),options=[dict(key=k,textMarkdown=project_blocks(v)) for k,v in model.option_blocks.items()],
        answer={"textMarkdown":project_blocks(model.answer_blocks)},explanationMarkdown=project_blocks(model.explanation_blocks),assetIds=[a.asset_id for a in model.assets],richContent=model.model_dump(by_alias=True))
    with app.state.question_bank.write_transaction() as conn:
        question=app.state.question_bank.insert_question_in(conn,owner_id=app.state.question_bank_service.owner_id,content=content,metadata={"subjectId":"math","difficulty":"easy"},answer_state="provided",content_fingerprint=canonical_hash(content),source_spans=[],import_id=None,knowledge_links=links)
    practice=request("post","/practice-sets",201,json=dict(submissionId=tag+"-create",analysisRunId=analysis["runId"],title="闭环练习",targetKnowledgePointIds=[x["knowledgePointId"] for x in links],constraints={"count":1}))
    set_id=practice["practiceSetId"]
    suggestions=request("post",f"/practice-sets/{set_id}/suggestions",json={"expectedRevision":0,"constraints":{"count":1}})
    assert suggestions["selectedCount"]==1 and suggestions["gaps"]==[]
    node=dict(nodeKey="leaf",parentNodeKey=None,questionNo="1",ordinal=1,isScored=True,maxScore="1.25",knowledgePointIds=[x["knowledgePointId"] for x in links],sourceBlockIds=[x["id"] for x in rich["stemBlocks"]]+[x["id"] for v in rich["optionBlocks"].values() for x in v])
    draft=dict(itemKey="item",questionRevisionId=question.current_revision_id,ordinal=1,maxScore="1.25",selectedKnowledgePointIds=node["knowledgePointIds"],itemStructure={"nodes":[node]})
    saved=request("patch",f"/practice-sets/{set_id}/draft",json={"submissionId":tag+"-draft-save","expectedRevision":0,"items":[draft],"constraints":{"count":1}})
    practice=request("post",f"/practice-sets/{set_id}/review",json={"submissionId":tag+"-review","expectedRevision":saved["revision"]})
    fixed=practice["currentRevision"]["practiceRevisionId"]
    conversion=request("post",f"/practice-sets/{set_id}/revisions/{fixed}/assessments",201,json=dict(submissionId=tag+"-conversion",title="练习施测",heldOn="2026-10-02",classIds=[klass["id"]],participants=participants))
    exports=[]
    for variant in ("student","teacher","score_template"):
        receipt=request("post",f"/practice-sets/{set_id}/revisions/{fixed}/exports",202,json=dict(submissionId=tag+"-"+variant,variant=variant,assessmentId=conversion["assessmentId"] if variant=="score_template" else None))
        job=ready(receipt)
        artifact=request("get","/export-artifacts/"+job["result"]["artifactId"])
        response=client.get(artifact["downloadUrl"])
        assert response.status_code==200 and hashlib.sha256(response.content).hexdigest()==artifact["sha256"]
        exports.append(artifact)
    converted=request("get","/assessments/"+conversion["assessmentId"])
    returned_score=score(converted["assessment"],student,"1",tag+"-returned-score")
    returned=request("post",f"/assessments/{conversion['assessmentId']}/analysis-runs",202,json=dict(submissionId=tag+"-returned-analysis",scoreRevisionId=returned_score["revisionId"],selectedParticipantIds=[converted["participants"][0]["participantId"]],ruleCode="any_loss_v1"))
    ready(returned)
    evidence=request("get",f"/analysis-runs/{returned['runId']}/evidence")
    assert evidence["items"][0]["practiceRevisionId"]==fixed and evidence["items"][0]["practiceItemId"]==practice["currentRevision"]["items"][0]["practiceItemId"]
    return dict(analysis=analysis,note=note,practice=practice,conversion=conversion,initialScore=initial_score,returnedScore=returned_score,
        returnedAnalysis=returned,returnedEvidence=evidence,exports=exports,questionId=question.question_id,questionRevisionId=question.current_revision_id,
        classId=klass["id"],studentId=student["id"],catalogPaths={k:str(getattr(app.state,k).db_path) for k in ("catalog","knowledge","question_bank","teaching")})
