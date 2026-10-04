"""Prepare initial facts only. No analysis, note, practice, export or conversion.

Run by CTRL before its own backend starts. Keeps all four real standard-main
catalogs and real managed DOCX/PNG bytes in a newly owned OS temporary root.
"""
import copy
import hashlib
import io
import json
import struct
import uuid
import zlib
from urllib.parse import quote
from isolation import isolated_settings

settings = isolated_settings()  # BEFORE indirect standard main imports
from fastapi.testclient import TestClient
from openpyxl import Workbook
from app.main import create_app
from app.core.secrets import SecretStore
from app.contracts.teaching_loop import RichContentV2, canonical_hash
from app.repositories.teaching.papers import PaperRepository, ItemKnowledgeRecord
from app.services.question_bank.rich import project_blocks
from app.services.rich_content.renderer_docx import render_rich_document


def png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind+data) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\x00\x00\x64\xff\xff\xff\x00\x00\xff")) + chunk(b"IEND", b"")


def seed():
    application = create_app(settings, secret_store=SecretStore())
    with TestClient(application, base_url="http://127.0.0.1:8001") as client:
        def request(method, path, expected=200, **kwargs):
            response = getattr(client, method)("/api/v1"+path, **kwargs)
            assert response.status_code == expected, (path, response.status_code, response.text)
            return response.json()
        points = [request("post", "/knowledge-points", 201, json={"subjectId":"math", "code":code, "name":name})
                  for code, name in (("F10-RATIONAL", "有理数"), ("B4-FIXED-K2", "运算关联"))]
        links = [dict(knowledgePointId=p["id"], knowledgeRevisionId=p["revisionId"], subjectIdSnapshot="math", knowledgeNameSnapshot=p["name"], role="primary") for p in points]
        image = application.state.asset_store.store_original(png(), media_type="image/png", original_name="synthetic.png")
        aid = image.blob_key
        rich = dict(version=2, stemBlocks=[
            dict(id="s", kind="paragraph", text="正式富题：求有理数运算结果。"),
            dict(id="f", kind="formula", latex=r"\frac{x}{2}+1"),
            dict(id="i", kind="image", assetId=aid, width=120, height=60),
            dict(id="t", kind="table", columnCount=2, cells=[dict(text="数据", isHeader=True, rowSpan=1, colSpan=2), dict(text="甲", rowSpan=1, colSpan=1), dict(text="乙", rowSpan=1, colSpan=1)])],
            sharedMaterials=[dict(id="m", blocks=[dict(id="mb", kind="paragraph", text="共同材料：保持完整上下文。")])],
            optionBlocks={"A":[dict(id="a",kind="paragraph",text="3")],"B":[dict(id="b",kind="paragraph",text="-3")]},
            answerBlocks=[dict(id="answer",kind="paragraph",text="B4_TEACHER_ANSWER_731")],
            explanationBlocks=[dict(id="explanation",kind="paragraph",text="B4_TEACHER_EXPLANATION_947")],
            assets=[dict(assetId=aid,sha256=image.sha256,mediaType="image/png")],
            origin=dict(originalAssetId="synthetic-q-source",originalSha256="ab"*32,sourceLocator={"paragraphIndex":1}))
        original = copy.deepcopy(rich)
        original["stemBlocks"][0]["text"] = "初测原题：逐叶独立计分。"
        original_bytes = render_rich_document(rich=RichContentV2.model_validate(original), assets=application.state.asset_store, variant="teacher", title="B4独立初测")
        stored = application.state.asset_store.store_original(original_bytes, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", original_name="initial-source.docx")
        papers = PaperRepository(application.state.teaching)
        items = []
        with application.state.teaching.write_transaction() as conn:
            file = application.state.file_assets.create_in(conn,kind="paper",blob_key=stored.blob_key,sha256=stored.sha256,byte_size=stored.byte_size,original_name="initial-source.docx",media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            application.state.file_assets.create_in(conn,kind="attachment",blob_key=image.blob_key,sha256=image.sha256,byte_size=image.byte_size,original_name="synthetic.png",media_type="image/png",asset_id=aid)
            paper = papers.create_paper_in(conn,subject_id="math",title="B4独立初测")
            revision = papers.create_revision_in(conn,paper_id=paper.paper_id,version=1,source_file_id=file.asset_id,total_score_units=1000,title_snapshot="B4独立初测")
            source_ordinal = 0
            for index, maximum in enumerate((200,300,500)):
                item_id = uuid.uuid4().hex
                content = copy.deepcopy(original)
                content["stemBlocks"][0]["text"] += " Q"+str(index+1)
                item = dict(item_id=item_id,parent_item_id=None,question_no="Q"+str(index+1),ordinal=index+1,is_scored=True,max_score_units=maximum,content=content,source_locator={"paragraphIndex":index+1,"fixture":"B4-V00-F"})
                # Store the complete fixed rich source, with explicit per-item assignment;
                # item content alone does not grant the paper asset endpoint access.
                sections = [("stem", content["stemBlocks"]), ("source", content.get("sourceBlocks", []))]
                sections.extend(("material:"+material["id"], material["blocks"]) for material in content["sharedMaterials"])
                sections.extend(("option:"+key, blocks) for key, blocks in content["optionBlocks"].items())
                sections.extend((("answer", content["answerBlocks"]), ("explanation", content["explanationBlocks"])))
                blocks = []
                for section, section_blocks in sections:
                    for block_index, block in enumerate(section_blocks):
                        source_ordinal += 1
                        blocks.append(dict(block_id=f"{revision.revision_id}:{item_id}:{block['id']}",
                            ordinal=source_ordinal, kind=block["kind"], block=copy.deepcopy(block),
                            locator=dict(fixture="B4-V00-F", sourceFileAssetId=file.asset_id, sourceFileSha256=stored.sha256,
                                questionNo=item["question_no"], section=section, blockIndex=block_index),
                            disposition="item", item_id=item_id))
                item["source_locator"].update(sourceFileAssetId=file.asset_id, sourceFileSha256=stored.sha256,
                    sourceBlockIds=[block["block_id"] for block in blocks])
                papers.insert_items_in(conn,paper_revision_id=revision.revision_id,items=[item])
                papers.insert_blocks_in(conn,paper_revision_id=revision.revision_id,blocks=blocks)
                selected = links[:1] if index == 0 else links if index == 1 else links[1:]
                papers.insert_item_knowledge_in(conn,item_id=item_id,paper_revision_id=revision.revision_id,knowledge=[ItemKnowledgeRecord(x["knowledgePointId"],x["knowledgeRevisionId"],x["knowledgeNameSnapshot"],"primary","human") for x in selected])
                items.append(dict(itemId=item_id,questionNo=item["question_no"],maxScoreUnits=maximum))
            papers.confirm_revision_in(conn,revision.revision_id)
            papers.set_current_revision_in(conn,paper.paper_id,revision.revision_id)
        asset_response = client.get(f"/api/v1/papers/{paper.paper_id}/revisions/{revision.revision_id}/assets/{quote(aid, safe='')}/content")
        assert asset_response.status_code == 200, (asset_response.status_code, asset_response.text)
        assert asset_response.content == png()
        assert hashlib.sha256(asset_response.content).hexdigest() == image.sha256
        assert asset_response.headers["content-type"].split(";", 1)[0] == "image/png"
        klass = request("post","/classes",201,json=dict(code="B4-V00-F",name="B4独立合成班",schoolYear="2026",gradeId="g"))
        students = [request("post","/students",201,json=dict(name="合成"+label+"-B4",studentNo=f"00{index+1:03d}",classId=klass["id"],joinedOn="2026-01-01")) for index,label in enumerate(("甲","乙","丙","丁"))]
        inputs = [dict(studentId=s["id"],classId=klass["id"],attendance="absent" if index==2 else "present",attemptNo=1) for index,s in enumerate(students)]
        inputs.append(dict(studentId=students[0]["id"],classId=klass["id"],attendance="present",attemptNo=2))
        assessment = request("post","/assessments",201,json=dict(submissionId="b4-v00-initial-assessment",paperRevisionId=revision.revision_id,title="B4独立初测",assessmentType="exam",heldOn="2026-10-02",classIds=[klass["id"]],participants=inputs))
        participants = assessment["participants"]
        workbook = Workbook(); sheet = workbook.active; sheet.title = "初测"
        sheet.append(["学号","姓名","Q1","Q2","Q3"])
        values = ((2,2,5),(2,3,None),(None,None,None),(0,3,5),(2,3,5))
        for index, scores in enumerate(values):
            s = students[index if index<4 else 0]
            sheet.append([s["studentNo"],s["name"],*scores])
        output = io.BytesIO(); workbook.save(output)
        imported = request("post",f"/assessments/{assessment['assessment']['assessmentId']}/score-imports",201,files={"file":("initial.xlsx",output.getvalue(),"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},data={"workSheet":"初测"})
        by_attempt = {(p["studentId"],p["attemptNo"]):p for p in participants}
        imported = request("patch","/score-imports/"+imported["importId"],json=dict(expectedRevision=imported["revision"],rows=[dict(rowNo=2,participantId=by_attempt[(students[0]["id"],1)]["participantId"]),dict(rowNo=6,participantId=by_attempt[(students[0]["id"],2)]["participantId"])]))
        # Exact known fixture ranges, never deriving the expected A9/Bnull/Cnull/D8
        # oracle from production aggregation.
        bpid=by_attempt[(students[1]["id"],1)]["participantId"]; cpid=by_attempt[(students[2]["id"],1)]["participantId"]
        score = request("post","/score-imports/"+imported["importId"]+"/confirm",json=dict(submissionId="b4-v00-initial-score",expectedImportRevision=imported["revision"],expectedAssessmentRevision=assessment["assessment"]["revision"],previewVersion=imported["previewVersion"],baseScoreRevisionId=None,absences=[dict(classId=klass["id"],participantIds=[cpid])],missing=dict(participantIds=[bpid],cellCount=1)))
        model=RichContentV2.model_validate(rich)
        content=dict(type="short_answer",stemMarkdown=project_blocks(model.stem_blocks),options=[dict(key=k,textMarkdown=project_blocks(v)) for k,v in model.option_blocks.items()],answer={"textMarkdown":project_blocks(model.answer_blocks)},explanationMarkdown=project_blocks(model.explanation_blocks),assetIds=[aid],richContent=model.model_dump(by_alias=True))
        with application.state.question_bank.write_transaction() as conn:
            question=application.state.question_bank.insert_question_in(conn,owner_id=application.state.question_bank_service.owner_id,content=content,metadata={"subjectId":"math","difficulty":"easy"},answer_state="provided",content_fingerprint=canonical_hash(content),source_spans=[],import_id=None,knowledge_links=links)
        # The browser must build every B4 fact itself, starting with zero B4 rows.
        with application.state.teaching.read_connection() as conn:
            empty_counts={t:conn.execute("SELECT count(*) FROM "+t).fetchone()[0] for t in ("analysis_runs","analysis_teacher_notes","practice_sets","practice_conversions","practice_exports")}
        assert set(empty_counts.values())=={0},empty_counts
        metadata=dict(task="B4-V00-F v1",dataDir=str(settings.data_dir),sourcePaperId=paper.paper_id,sourcePaperRevisionId=revision.revision_id,assessmentId=assessment["assessment"]["assessmentId"],scoreRevisionId=score["revisionId"],classId=klass["id"],students=students,participants=participants,points=points,items=items,questionId=question.question_id,questionRevisionId=question.current_revision_id,emptyB4Counts=empty_counts,sourceBytesSHA256=hashlib.sha256(original_bytes).hexdigest(),imageSHA256=image.sha256,catalogPaths={k:str(getattr(application.state,k).db_path) for k in ("catalog","knowledge","question_bank","teaching")})
        metadata["initialAssetHTTP"] = dict(assetId=aid, paperId=paper.paper_id, paperRevisionId=revision.revision_id,
            sourceBlockCount=source_ordinal, status=asset_response.status_code, mediaType=asset_response.headers["content-type"],
            byteSize=len(asset_response.content), sha256=hashlib.sha256(asset_response.content).hexdigest())
        path=settings.data_dir.parent/"browser-seed.json";path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({"seed":str(path),"emptyB4Counts":empty_counts,"assessmentId":metadata["assessmentId"],"scoreRevisionId":score["revisionId"]},ensure_ascii=False))


if __name__ == "__main__":
    seed()
