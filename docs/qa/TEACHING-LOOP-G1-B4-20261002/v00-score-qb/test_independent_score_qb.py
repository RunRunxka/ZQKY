"""Independent G1 HTTP oracles. No production identity function is an oracle."""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import os
import struct
import tempfile
import uuid
import zipfile
import zlib
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

# Must precede app.main, including the default module-level app construction.
BOOT = Path(tempfile.mkdtemp(prefix="zqky-g1-v00-score-qb-boot-"))
os.environ["ZQKY_DATA_DIR"] = str(BOOT)
os.environ["ZQKY_ENV"] = "test"
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from app.core.config import Settings
from app.core.sqlite import connect, now_iso, transaction
from app.main import create_app

QA = Path(__file__).resolve().parent
SOURCES = QA / "sources"
SOURCES.mkdir(exist_ok=True)
HEADERS = ["学号", "姓名", "Q1", "Q2", "总分", "出勤"]
NORMAL = ["0007", "独立甲", "0.50", "1.50", "2.00", "出勤"]
COUNT_TABLES = ["score_imports", "score_import_rows", "score_revisions",
                "student_item_scores", "score_revision_corrections", "file_assets", "command_submissions"]
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOCUMENT = "1. 根据给定实验条件选择正确结论（ ）\nA. 条件成立\nB. 条件不成立\n答案：A\n解析：逐项核对条件。\n"

def receipt(kind, **data):
    with (QA / "http-receipts.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"kind": kind, **data}, ensure_ascii=False) + "\n")

class Rig:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="zqky-g1-v00-score-qb-case-"))
        self.settings = Settings(host="127.0.0.1", port=8001, env="test",
            allowed_origins=frozenset({"http://127.0.0.1:5174"}),
            data_dir=self.root / "data", credentials_file=None)
        self.app = create_app(self.settings)
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8001")
        self.client.__enter__()
        self.db = self.settings.teaching_root / "teaching.sqlite3"
        self.qdb = self.settings.question_bank_root / "question-bank.sqlite3"
        databases = list(self.settings.data_dir.rglob("*.sqlite3"))
        assert len(databases) == 4, databases
        receipt("resources", root=str(self.root), bootstrap=str(BOOT),
                databases=[str(p) for p in databases], credentialsFile=None)

    def close(self):
        self.client.__exit__(None, None, None)

    def call(self, method, path, **kwargs):
        response = self.client.request(method, "/api/v1" + path, **kwargs)
        return response

    def json(self, method, path, status=200, **kwargs):
        response = self.call(method, path, **kwargs)
        assert response.status_code == status, response.text
        return response.json()

    def rows(self, sql, args=(), question=False):
        conn = connect(self.qdb if question else self.db)
        try:
            return [dict(row) for row in conn.execute(sql, args)]
        finally:
            conn.close()

    def counts(self):
        return {table: self.rows("SELECT count(*) AS n FROM " + table)[0]["n"] for table in COUNT_TABLES}

    def blobs(self):
        root = self.settings.assets_root / "blobs"
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob("*") if p.is_file()}

    def scene(self, four=False):
        # Two fixed leaves are a test prerequisite, inserted through real migration
        # constraints and the actual draft->confirmed trigger, not mock repositories.
        raw = b"Independent immutable source paper fixture, Q1=2 and Q2=3"
        asset = self.app.state.asset_store.store_original(raw,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            original_name="independent-paper.docx")
        conn = connect(self.db)
        try:
            with transaction(conn, immediate=True):
                stamp = now_iso()
                conn.execute("INSERT INTO file_assets(id,owner_id,kind,blob_key,sha256,original_name,media_type,byte_size,created_at) VALUES('independent-file','local','paper',?,?,?,'application/vnd.openxmlformats-officedocument.wordprocessingml.document',?,?)",
                             (asset.blob_key, asset.sha256, "independent-paper.docx", len(raw), stamp))
                conn.execute("INSERT INTO papers(id,owner_id,subject_id,title,status,revision,created_at) VALUES('independent-paper','local','math','独立两叶固定卷','active',1,?)", (stamp,))
                conn.execute("INSERT INTO paper_revisions(id,paper_id,version,source_file_id,total_score_units,state,title_snapshot,title_snapshot_source,created_at) VALUES('independent-pr','independent-paper',1,'independent-file',500,'draft','独立两叶固定卷','human',?)", (stamp,))
                for i, units in [(1, 200), (2, 300)]:
                    conn.execute("INSERT INTO paper_items(id,paper_revision_id,parent_item_id,question_no,ordinal,is_scored,max_score_units,content_json,source_locator_json) VALUES(?,'independent-pr',NULL,?,?,1,?,'{}','{}')", (f"independent-item-{i}", f"Q{i}", i, units))
                    conn.execute("INSERT INTO paper_item_knowledge(item_id,paper_revision_id,knowledge_point_id,knowledge_revision_id,knowledge_name_snapshot,role,source) VALUES(?,'independent-pr',?,?,'固定知识点','primary','human')", (f"independent-item-{i}", f"independent-kp-{i}", f"independent-kpr-{i}"))
                conn.execute("UPDATE paper_revisions SET state='confirmed',confirmed_at=? WHERE id='independent-pr'", (stamp,))
                conn.execute("UPDATE papers SET current_revision_id='independent-pr' WHERE id='independent-paper'")
        finally:
            conn.close()
        klass = self.json("POST", "/classes", 201, json={"code":"V00","name":"独立班","schoolYear":"2026-2027","gradeId":"senior-1"})
        specs = [("独立甲", "0007", "present")]
        if four:
            specs += [("独立乙", "0008", "present"), ("独立丙", "0009", "absent"), ("独立丁", "0010", "exempt")]
        participants = []
        for name, number, attendance in specs:
            student = self.json("POST", "/students", 201, json={"name":name,"studentNo":number,"classId":klass["id"],"joinedOn":"2020-01-01"})
            participants.append({"studentId":student["id"],"classId":klass["id"],"attendance":attendance})
        result = self.json("POST", "/assessments", 201, json={"submissionId":"v00-scene","paperRevisionId":"independent-pr","title":"独立成绩验证","heldOn":date.today().isoformat(),"classIds":[klass["id"]],"participants":participants})
        return result["assessment"]

    def upload_score(self, assessment, source):
        return self.call("POST", f"/assessments/{assessment['assessmentId']}/score-imports",
            files={"file":(source.name, source.read_bytes(), "application/octet-stream")})

    def confirm_score(self, assessment, view):
        return self.json("POST", f"/score-imports/{view['importId']}/confirm", json={
            "submissionId":"independent-score-confirm", "expectedImportRevision":view["revision"],
            "expectedAssessmentRevision":assessment["revision"], "previewVersion":view["previewVersion"],
            "baseScoreRevisionId":view["baseScoreRevisionId"], **view["requiredAcknowledgements"]})

    def qb_upload(self, document=DOCUMENT):
        return self.json("POST", "/question-imports", 201,
            files={"file":("independent-question.md", document.encode(), "text/markdown")}, data={"subjectId":"math"})

    def review(self, draft, content=None):
        content = copy.deepcopy(content or draft["content"])
        for state in ("needs_review", "reviewed"):
            draft = self.json("PATCH", f"/question-drafts/{draft['draftId']}", json={
                "expectedRevision":draft["revision"],"content":content,"metadata":draft["metadata"],"reviewState":state})
        assert draft["reviewState"] == "reviewed"
        return draft

    def qb_confirm(self, import_id, drafts, key, action=None):
        package = {"submissionId":"v00-independent-"+key,"importId":import_id,
            "items":[{"draftId":d["draftId"],"expectedDraftRevision":d["revision"]} for d in drafts],
            "duplicateResolutions":[{"draftId":drafts[-1]["draftId"],"action":action}] if action else []}
        response = self.call("POST", f"/question-imports/{import_id}/confirm", json=package)
        receipt("question-confirm", request=package, status=response.status_code, response=response.json())
        assert response.status_code == 200, response.text
        return response.json(), package

    def formal_count(self):
        return self.json("GET", "/questions")["total"]

@pytest.fixture
def rig():
    h = Rig()
    try:
        yield h
    finally:
        h.close()

def source_file(kind, rows, formula_cache=None):
    identifier = uuid.uuid4().hex
    path = SOURCES / (identifier + (".csv" if kind == "csv" else ".xlsx"))
    # Physical row four is intentionally different from typical row-two fixtures.
    table = [[], [], HEADERS, *rows]
    if kind == "csv":
        buffer = io.StringIO(newline="")
        csv.writer(buffer).writerows(table)
        path.write_bytes(buffer.getvalue().encode("utf-8-sig"))
    else:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "独立成绩页"
        for row in table:
            worksheet.append(row)
        workbook.save(path)
        workbook.close()
        if formula_cache:
            buffer = io.BytesIO()
            with zipfile.ZipFile(path) as original, zipfile.ZipFile(buffer,"w",zipfile.ZIP_DEFLATED) as dest:
                for info in original.infolist():
                    data = original.read(info.filename)
                    if info.filename == "xl/worksheets/sheet1.xml":
                        root = ET.fromstring(data)
                        for address, value in formula_cache.items():
                            cell = root.find(f".//{{{NS}}}c[@r='{address}']")
                            assert cell is not None
                            cell.set("t","str")
                            cached = cell.find(f"{{{NS}}}v")
                            if cached is None:
                                cached = ET.SubElement(cell, f"{{{NS}}}v")
                            cached.text = value
                        data = ET.tostring(root, encoding="utf-8")
                    dest.writestr(info,data)
            path.write_bytes(buffer.getvalue())
    return path

@pytest.mark.parametrize("kind,mode", [("csv","raw"),("xlsx","raw"),("xlsx","formula"),("xlsx","cached")])
@pytest.mark.parametrize("index,column", [(0,"A"),(1,"B"),(2,"C"),(4,"E"),(5,"F")])
def test_overlong_http_rejects_all_authority_columns_without_writes(rig, kind, mode, index, column):
    assessment = rig.scene()
    row = NORMAL.copy()
    exploit = "1." + "0" * 19998 + "1"
    assert len(exploit) == 20001  # Hard-coded independent supported boundary.
    if mode == "formula":
        value = "=" + "1" * 20000
    else:
        value = exploit
    cache = None
    row[index] = value
    if mode == "cached":
        row[index] = "=1"
        cache = {column+"4":value}
    source = source_file(kind,[row],cache)
    original = source.read_bytes()
    before = rig.counts(), rig.blobs(), rig.json("GET",f"/assessments/{assessment['assessmentId']}")
    response = rig.upload_score(assessment,source)
    payload = response.json()
    receipt("score-rejected", source=source.name, sha256=hashlib.sha256(original).hexdigest(),
            scenario=[kind,mode,column], beforeCounts=before[0], afterCounts=rig.counts(),
            status=response.status_code, response=payload)
    assert response.status_code == 422, response.text
    assert payload["code"] == "TABLE_TOO_LARGE" and payload["requestId"] and payload["retryable"] is False
    assert payload["details"] == {"sheet":"CSV" if kind=="csv" else "独立成绩页", "row":4,
        "column":column,"address":column+"4","view":"csv" if kind=="csv" else "cached" if mode=="cached" else "formula",
        "actualLength":20001,"maxLength":20000}
    assert rig.counts() == before[0] and rig.blobs() == before[1]
    assert rig.json("GET",f"/assessments/{assessment['assessmentId']}") == before[2]
    assert source.read_bytes() == original

@pytest.mark.parametrize("kind,cache", [("csv",False),("xlsx",False),("xlsx",True)])
@pytest.mark.parametrize("number,units", [("1."+"0"*19998,100),("0."+"0"*19998,0)], ids=["one-20000","zero-20000"])
def test_supported_full_text_and_zero_survive_to_confirmed_matrix(rig, kind, cache, number, units):
    assessment = rig.scene()
    row = NORMAL.copy()
    row[2] = "=1" if cache else number
    row[3], row[4] = "1.50", "2.50" if units else "1.50"
    source = source_file(kind,[row],{"C4":number} if cache else None)
    response = rig.upload_score(assessment,source)
    assert response.status_code == 201, response.text
    view = response.json()
    rows = rig.rows("SELECT raw_cells_json FROM score_import_rows WHERE import_id=? AND row_no=4", (view["importId"],))
    original_cell = next(c for c in json.loads(rows[0]["raw_cells_json"]) if c["column"]=="C")
    assert original_cell["text"] == ("=1" if cache else number)
    assert original_cell["cachedText"] == number
    assert rig.app.state.asset_store.read(view["fileAsset"]["blobKey"]) == source.read_bytes()
    result = rig.confirm_score(assessment,view)
    matrix = rig.json("GET", f"/score-revisions/{result['revisionId']}/matrix")
    assert matrix["rows"][0]["cells"][0] == {"itemId":"independent-item-1","status":"recorded","scoreUnits":units}
    assert matrix["rows"][0]["participant"]["studentNo"] == "0007"
    assert matrix["rows"][0]["participant"]["totalUnits"] == units+150
    receipt("score-full-boundary",source=source.name,sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            rawLength=len(original_cell["cachedText"]),confirmed=result,matrix=matrix)

@pytest.mark.parametrize("kind",["xlsx","csv"])
def test_supported_nonzero_precision_tail_is_invalid_without_writes(rig,kind):
    assessment=rig.scene()
    row=NORMAL.copy()
    row[2]="1."+"0"*19997+"1"
    assert len(row[2]) == 20000
    source=source_file(kind,[row])
    before=rig.counts(),rig.blobs()
    response=rig.upload_score(assessment,source)
    assert response.status_code==422,response.text
    body=response.json()
    assert body["code"]=="SCORE_CELL_INVALID"
    assert any(e.get("row")==4 and e.get("column")=="C" for e in body["details"]["issues"])
    assert before==(rig.counts(),rig.blobs())
    receipt("nonzero-tail",source=source.name,status=response.status_code,response=body)

@pytest.mark.parametrize("kind",["xlsx","csv"])
def test_four_states_are_distinct_and_only_complete_recorded_has_total(rig,kind):
    assessment=rig.scene(four=True)
    rows=[["0007","独立甲","0","1.5","1.5","出勤"],
          ["0008","独立乙","","3","","出勤"],
          ["0009","独立丙","缺考","缺考","","缺考"],
          ["0010","独立丁","免考","免考","","免考"]]
    source=source_file(kind,rows)
    response=rig.upload_score(assessment,source)
    assert response.status_code==201,response.text
    result=rig.confirm_score(assessment,response.json())
    matrix=rig.json("GET",f"/score-revisions/{result['revisionId']}/matrix")
    actual={r["participant"]["studentNo"]:([c["status"] for c in r["cells"]],[c["scoreUnits"] for c in r["cells"]],r["participant"]["totalUnits"]) for r in matrix["rows"]}
    assert actual=={"0007":(["recorded","recorded"],[0,150],150),"0008":(["missing","recorded"],[None,300],None),
                    "0009":(["absent","absent"],[None,None],None),"0010":(["exempt","exempt"],[None,None],None)}
    assert rig.rows("SELECT count(*) AS n FROM student_item_scores")[0]["n"]==8
    receipt("four-states",source=source.name,result=result,matrix=matrix)

def test_touched_csv_parser_failure_uses_error_envelope_without_any_upload_write(rig):
    assessment=rig.scene()
    source=source_file("csv",[[*NORMAL,"x"*131073]])
    before=rig.counts(),rig.blobs()
    response=rig.upload_score(assessment,source)
    assert response.status_code==422,response.text
    body=response.json()
    assert body["code"]=="TABLE_PARSE_FAILED" and body["requestId"] and body["retryable"] is False
    assert body["details"]["sheet"]=="CSV" and body["details"]["row"]==4
    assert "column" not in body["details"]
    assert before==(rig.counts(),rig.blobs())
    receipt("csv-parser-observation",response=body,source=source.name)

def png_rgb(r,g,b):
    def chunk(kind,data):
        return struct.pack("!I",len(data))+kind+data+struct.pack("!I",zlib.crc32(kind+data))
    return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack("!IIBBBBB",1,1,8,2,0,0,0))+chunk(b"IDAT",zlib.compress(bytes([0,r,g,b])))+chunk(b"IEND",b"")

def projection(blocks):
    # Fixture-only projection, never used to compute expected duplicate identity.
    return "\n\n".join(b["text"] if b["kind"]=="paragraph" else
        "[表格]\n"+" | ".join(c["text"] for c in b["cells"]) if b["kind"]=="table" else
        "$$"+b["latex"]+"$$" if b["kind"]=="formula" else f"![图片]({b['assetId']})" for b in blocks)

def new_question(rig, *, material="实验浓度为 1 mol/L。", change=None, rich=True, image=None, storage="managed"):
    imported=rig.qb_upload()
    draft=imported["drafts"][0]
    content=copy.deepcopy(draft["content"])
    if rich:
        source=rig.rows("SELECT original_blob_id,file_sha256 FROM question_imports WHERE id=?",(imported["importId"],),True)[0]
        rc={"version":2,"sharedMaterials":[{"id":"context","blocks":[{"id":"context-p","kind":"paragraph","text":material}]}],
            "stemBlocks":[{"id":"stem-p","kind":"paragraph","text":content["stemMarkdown"]},
                {"id":"stem-formula","kind":"formula","latex":"a+b","ommlXml":"<m:oMath><m:r><m:t>a+b</m:t></m:r></m:oMath>"},
                {"id":"stem-table","kind":"table","columnCount":2,"cells":[{"text":"条件","colSpan":2},{"text":"甲"},{"text":"乙"}]}],
            "optionBlocks":{o["key"]:[{"id":"option-"+o["key"],"kind":"paragraph","text":o["textMarkdown"]}] for o in content["options"]},
            "answerBlocks":[{"id":"answer-p","kind":"paragraph","text":"A"}],
            "explanationBlocks":[{"id":"teacher-p","kind":"paragraph","text":content["explanationMarkdown"]}],
            "assets":[],"origin":{"originalAssetId":source["original_blob_id"],"originalSha256":source["file_sha256"],"sourceLocator":{"kind":"markdown","lineStart":1}}}
        content["richContent"]=rc
        if image:
            if storage=="managed":
                asset_id=rig.app.state.asset_store.store_original(image,media_type="image/png",original_name="independent.png").blob_key
            else:
                asset_id,_=rig.app.state.question_bank_service.blobs.write(image)
            rc["sharedMaterials"][0]["blocks"].append({"id":"context-image","kind":"image","assetId":asset_id,"width":1,"height":1})
            rc["assets"].append({"assetId":asset_id,"sha256":hashlib.sha256(image).hexdigest(),"mediaType":"image/png"})
            content["assetIds"]=[asset_id]
        if change:
            change(content)
        content["stemMarkdown"]=projection(rc["stemBlocks"])
        for option in content["options"]:
            option["textMarkdown"]=projection(rc["optionBlocks"][option["key"]])
        content["explanationMarkdown"]=projection(rc["explanationBlocks"])
    reviewed=rig.review(draft,content)
    return imported["importId"],reviewed

def one_formal(rig, import_id, draft, key="first", action=None):
    result,_=rig.qb_confirm(import_id,[draft],key,action)
    assert result["failures"]==[] and result["skippedDraftIds"]==[]
    assert len(result["confirmedQuestionIds"])==1
    return result["confirmedQuestionIds"][0]

def preview(rig,import_id):
    return rig.json("GET",f"/question-imports/{import_id}")["drafts"][0]

@pytest.mark.parametrize("action",[None,"edit_as_new"])
def test_different_material_is_two_formal_questions_for_both_default_and_explicit_new(rig,action):
    ia,da=new_question(rig)
    first=one_formal(rig,ia,da)
    ib,db=new_question(rig,material="实验浓度为 2 mol/L。")
    assert da["content"]["stemMarkdown"]==db["content"]["stemMarkdown"]
    assert da["content"]["options"]==db["content"]["options"]
    assert preview(rig,ib)["duplicateOfQuestionId"] is None
    second=one_formal(rig,ib,db,"second",action)
    assert first!=second and rig.formal_count()==2
    assert rig.json("GET",f"/questions/{first}")["content"]["richContent"]["sharedMaterials"][0]["blocks"][0]["text"]=="实验浓度为 1 mol/L。"
    assert rig.json("GET",f"/questions/{second}")["content"]["richContent"]["sharedMaterials"][0]["blocks"][0]["text"]=="实验浓度为 2 mol/L。"

@pytest.mark.parametrize("change",["stem","option","omml-only","formula","table-span","table-text","image-bytes"])
def test_authority_surface_changes_distinguish_questions_without_using_identity_oracle(rig,change):
    image=png_rgb(12,34,56) if change=="image-bytes" else None
    ia,da=new_question(rig,image=image)
    first=one_formal(rig,ia,da)
    def mutate(content):
        rc=content["richContent"]
        if change=="stem":rc["stemBlocks"][0]["text"]+="，附加条件。"
        elif change=="option":rc["optionBlocks"]["A"][0]["text"]+="，另一边界。"
        elif change=="omml-only":rc["stemBlocks"][1]["ommlXml"]="<m:oMath><m:r><m:t>a-b</m:t></m:r></m:oMath>"
        elif change=="formula":rc["stemBlocks"][1]["latex"]="a-b"
        elif change=="table-span":rc["stemBlocks"][2]["cells"][0]["colSpan"]=1
        elif change=="table-text":rc["stemBlocks"][2]["cells"][1]["text"]="丙"
    ib,db=new_question(rig,change=mutate,image=png_rgb(56,34,12) if image else None)
    if change in {"omml-only","table-span","image-bytes"}:
        assert da["content"]["stemMarkdown"]==db["content"]["stemMarkdown"]
    assert preview(rig,ib)["duplicateOfQuestionId"] is None
    assert one_formal(rig,ib,db,"second","edit_as_new")!=first
    assert rig.formal_count()==2

@pytest.mark.parametrize("action",[None,"link_existing","edit_as_new"])
def test_true_repeat_and_conflicting_answer_require_teacher_resolution_keep_original(rig,action):
    ia,da=new_question(rig)
    first=one_formal(rig,ia,da)
    original=rig.json("GET",f"/questions/{first}")
    def mutate(content):
        rc=content["richContent"]
        rc["sharedMaterials"][0]["id"]="other-context-id"
        for i,b in enumerate([*[b for m in rc["sharedMaterials"] for b in m["blocks"]],*rc["stemBlocks"],*[b for bs in rc["optionBlocks"].values() for b in bs],*rc["answerBlocks"],*rc["explanationBlocks"]]):b["id"]=f"fresh-{i}"
        rc["origin"]["sourceLocator"]["lineStart"]=411
        content["answer"]["choiceKeys"]=["B"]
        rc["answerBlocks"][0]["text"]="B"
        rc["explanationBlocks"][0]["text"]="教师需要校对的另一答案。"
    ib,db=new_question(rig,change=mutate)
    view=preview(rig,ib)
    assert view["duplicateOfQuestionId"]==first
    assert any("答案不同" in w for w in view["warnings"])
    result,_=rig.qb_confirm(ib,[db],"repeat",action)
    if action=="edit_as_new":
        assert [f["code"] for f in result["failures"]]==["DUPLICATE_UNRESOLVED"]
        assert result["confirmedQuestionIds"]==[] and result["skippedDraftIds"]==[]
    elif action=="link_existing":
        assert result["failures"]==[] and result["linkedQuestionIds"]==[first]
        assert result["confirmedQuestionIds"]==[] and result["skippedDraftIds"]==[]
    else:
        assert result["failures"]==[] and result["skippedDraftIds"]==[db["draftId"]]
    current=rig.json("GET",f"/questions/{first}")
    assert rig.formal_count()==1
    assert {k:v for k,v in current.items() if k!="sources"}=={k:v for k,v in original.items() if k!="sources"}
    assert all(source in current["sources"] for source in original["sources"])
    if action=="link_existing":
        assert len(current["sources"])>len(original["sources"])
    else:
        assert current["sources"]==original["sources"]
    assert preview(rig,ib)["content"]["answer"]["choiceKeys"]==["B"]

@pytest.mark.parametrize("rich",[False,True])
def test_old_revisions_missing_new_fingerprint_compare_read_only_and_preserve_both_old_versions(rig,rich):
    ia,da=new_question(rig,rich=rich)
    first=one_formal(rig,ia,da)
    old=rig.rows("SELECT r.* FROM question_revisions r JOIN questions q ON q.current_revision_id=r.id WHERE q.id=?",(first,),True)[0]
    before=rig.rows("SELECT algorithm_version,fingerprint FROM question_content_fingerprints WHERE question_revision_id=? ORDER BY algorithm_version",(old["id"],),True)
    assert {row["algorithm_version"] for row in before}=={"derived-v1","question-surface-v1"}
    conn=connect(rig.qdb)
    try:
        with transaction(conn,immediate=True):conn.execute("DELETE FROM question_content_fingerprints WHERE algorithm_version='question-surface-v1'")
    finally:conn.close()
    retained=rig.rows("SELECT * FROM question_content_fingerprints WHERE question_revision_id=?",(old["id"],),True)
    ib,db=new_question(rig,rich=rich)
    assert preview(rig,ib)["duplicateOfQuestionId"]==first
    result,_=rig.qb_confirm(ib,[db],"legacy")
    assert result["skippedDraftIds"]==[db["draftId"]] and rig.formal_count()==1
    assert rig.rows("SELECT * FROM question_revisions WHERE id=?",(old["id"],),True)==[old]
    assert rig.rows("SELECT * FROM question_content_fingerprints WHERE question_revision_id=?",(old["id"],),True)==retained
    receipt("legacy-fingerprint",rich=rich,oldRevision=old,retainedFingerprint=retained,result=result)

def test_same_actual_image_bytes_across_storage_aliases_are_true_duplicates(rig):
    data=png_rgb(10,20,30)
    ia,da=new_question(rig,image=data)
    first=one_formal(rig,ia,da)
    ib,db=new_question(rig,image=data,storage="bare")
    assert da["content"]["assetIds"]!=db["content"]["assetIds"]
    assert preview(rig,ib)["duplicateOfQuestionId"]==first
    result,_=rig.qb_confirm(ib,[db],"image-alias")
    assert result["skippedDraftIds"]==[db["draftId"]] and rig.formal_count()==1

@pytest.mark.parametrize("action",[None,"edit_as_new"])
def test_same_package_two_true_duplicates_never_publish_two_formal_questions(rig,action):
    imported=rig.qb_upload(DOCUMENT+"\n"+DOCUMENT.replace("1.","2.",1))
    assert len(imported["drafts"])==2
    drafts=[rig.review(d) for d in imported["drafts"]]
    result,_=rig.qb_confirm(imported["importId"],drafts,"same-batch",action)
    if action:
        assert [f["code"] for f in result["failures"]]==["DUPLICATE_UNRESOLVED"]
        assert rig.formal_count()==0 and rig.rows("SELECT * FROM question_submissions WHERE submission_id='v00-independent-same-batch'",question=True)==[]
    else:
        assert result["failures"]==[] and len(result["confirmedQuestionIds"])==1
        assert result["skippedDraftIds"]==[drafts[1]["draftId"]] and rig.formal_count()==1

def test_completed_confirmation_replays_frozen_package_before_current_asset_revalidation(rig):
    data=png_rgb(255,42,90)
    import_id,draft=new_question(rig,image=data)
    result,package=rig.qb_confirm(import_id,[draft],"replay-package")
    assert result["failures"]==[] and len(result["confirmedQuestionIds"])==1
    asset_path=rig.app.state.asset_store.path_of(draft["content"]["assetIds"][0])
    bytes_before=asset_path.read_bytes()
    asset_path.write_bytes(b"changed environment only inside temporary V00 root")
    try:
        replay=rig.json("POST",f"/question-imports/{import_id}/confirm",json=package)
        assert replay==result and rig.formal_count()==1
        altered=copy.deepcopy(package)
        altered["items"][0]["expectedDraftRevision"]+=1
        conflict=rig.call("POST",f"/question-imports/{import_id}/confirm",json=altered)
        assert conflict.status_code==409 and conflict.json()["code"]=="IDEMPOTENCY_CONFLICT"
        receipt("frozen-replay",first=result,replay=replay,conflict=conflict.json())
    finally:
        asset_path.write_bytes(bytes_before)

@pytest.mark.parametrize("kind",["xlsx","csv"])
def test_numerically_valid_zero_tail_above_file_limit_is_still_explicitly_rejected(rig,kind):
    assessment=rig.scene()
    row=NORMAL.copy()
    row[2]="1."+"0"*19999
    assert len(row[2])==20001
    source=source_file(kind,[row])
    before=rig.counts(),rig.blobs()
    response=rig.upload_score(assessment,source)
    assert response.status_code==422,response.text
    body=response.json()
    assert body["code"]=="TABLE_TOO_LARGE" and body["details"]["actualLength"]==20001
    assert body["details"]["row"]==4 and body["details"]["column"]=="C"
    assert before==(rig.counts(),rig.blobs())
    receipt("numerically-valid-over-limit",source=source.name,response=body)

def test_paragraph_only_rich_matches_old_plain_question(rig):
    ia,da=new_question(rig,rich=False)
    first=one_formal(rig,ia,da)
    def simplify(content):
        content["richContent"]["sharedMaterials"]=[]
        content["richContent"]["stemBlocks"]=content["richContent"]["stemBlocks"][:1]
    ib,db=new_question(rig,change=simplify)
    assert db["content"]["stemMarkdown"]==da["content"]["stemMarkdown"]
    assert preview(rig,ib)["duplicateOfQuestionId"]==first
    result,_=rig.qb_confirm(ib,[db],"plain-rich-equivalent")
    assert result["skippedDraftIds"]==[db["draftId"]] and rig.formal_count()==1

def test_same_package_equal_plain_but_different_material_creates_two_fixed_questions(rig):
    _,template=new_question(rig)
    imported=rig.qb_upload(DOCUMENT+"\n"+DOCUMENT.replace("1.","2.",1))
    origin=rig.rows("SELECT original_blob_id,file_sha256 FROM question_imports WHERE id=?",(imported["importId"],),True)[0]
    drafts=[]
    for index,draft in enumerate(imported["drafts"],start=1):
        content=copy.deepcopy(template["content"])
        content["richContent"]["sharedMaterials"][0]["blocks"][0]["text"]=f"实验浓度为 {index} mol/L。"
        content["richContent"]["origin"]["originalAssetId"]=origin["original_blob_id"]
        content["richContent"]["origin"]["originalSha256"]=origin["file_sha256"]
        drafts.append(rig.review(draft,content))
    assert len(drafts)==2 and drafts[0]["content"]["stemMarkdown"]==drafts[1]["content"]["stemMarkdown"]
    result,_=rig.qb_confirm(imported["importId"],drafts,"distinct-material-batch")
    assert result["failures"]==[] and result["skippedDraftIds"]==[]
    assert len(set(result["confirmedQuestionIds"]))==2 and rig.formal_count()==2
