"""Independent P-card fixtures and literal/stdlib oracles; not author assertions.

Only open_api_scene/seed_api_loop are reused as actual standard-main business seeds.
No imports below this guard may run against a default/formal data root.
"""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile
import zlib

assert os.environ.get("ZQKY_ENV") == "test"
assert os.environ.get("ZQKY_QDRANT_URL") == "http://127.0.0.1:16333"
assert os.environ.get("ZQKY_EMBEDDING_BASE_URL") == "http://127.0.0.1:9"
assert os.environ.get("ZQKY_DATA_DIR") and os.environ.get("B4_P_RUN_ROOT")
RUN_ROOT = Path(os.environ["B4_P_RUN_ROOT"]).resolve()
assert Path(os.environ["ZQKY_DATA_DIR"]).resolve().is_relative_to(RUN_ROOT)
assert Path(os.environ["ZQKY_TEXTBOOK_SOURCE_DIR"]).resolve().is_relative_to(RUN_ROOT)

import pytest
from app.contracts.teaching_loop import RichContentV2
from app.core.sqlite import open_readonly
from app.services.question_bank.rich import project_blocks
from tests.practices_support import open_api_scene, seed_api_loop


def record(name, value):
    safe=re.sub(r'[^A-Za-z0-9._-]+','-',name)[:110]+'-'+hashlib.sha256(name.encode()).hexdigest()[:12]
    destination = Path(os.environ["B4_P_EVIDENCE_DIR"]) / (safe + ".json")
    assert not destination.exists(), f"evidence overwrite refused: {destination}"
    destination.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str)+"\n", encoding="utf-8")


def http(client, method, path, expected=200, **kw):
    response = getattr(client, method)("/api/v1"+path, **kw)
    assert response.status_code == expected, (method, path, response.status_code, response.text)
    if expected >= 400:
        value = response.json()
        assert all(k in value for k in ("code", "message", "requestId", "retryable")), value
        return value
    return response.json()


def wait_job(client, receipt, state="succeeded"):
    deadline = time.monotonic()+20
    observed = []
    while time.monotonic() < deadline:
        value = http(client, "get", "/workflow-jobs/"+receipt["job"]["jobId"], params={"domain":"teaching"})
        observed.append(value["state"])
        if value["state"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            assert value["state"] == state, (value, observed)
            return value
        time.sleep(.02)
    raise AssertionError(("bounded job wait", receipt, observed))


def rows(connection, table):
    assert table.replace("_", "").isalnum()
    return sorted([dict(r) for r in connection.execute('SELECT * FROM "'+table+'"')],
                  key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False, default=str))


def database_snapshot(path):
    conn = open_readonly(Path(path))
    try:
        assert [r[0] for r in conn.execute("PRAGMA integrity_check")] == ["ok"]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {n: rows(conn, n) for n in names}
    finally:
        conn.close()


@pytest.fixture
def scene(tmp_path, request):
    with open_api_scene(tmp_path) as (app, client, settings):
        assert settings.credentials_file is None
        from app.core.config import Settings
        assert Settings.from_env().credentials_file is None
        seeded = seed_api_loop(app, client, tag="p-"+uuid.uuid4().hex[:10])
        value = Scene(app, client, seeded, tmp_path)
        yield value
        checks = {domain: {"tables":len(database_snapshot(path)), "integrity":"ok", "fkRows":0}
                  for domain,path in seeded["catalogPaths"].items()}
        record(request.node.name+"-resources", {"root":tmp_path,"catalogs":checks,"listenersCreated":0,"formalCredentialsRead":False})


class Scene:
    def __init__(self, app, client, seed, root):
        self.app,self.client,self.seed,self.root = app,client,seed,root
        self.service=app.state.practice_service
        self.catalog=app.state.teaching
        self.points=seed["practice"]["currentRevision"]["targetKnowledgePoints"]
        self.kps=[p["knowledgePointId"] for p in self.points]
        self.rich=copy.deepcopy(seed["practice"]["currentRevision"]["items"][0]["content"])

    def create(self, count=1, **constraints):
        self.last_create=dict(submissionId=uuid.uuid4().hex,analysisRunId=self.seed["analysis"]["runId"],title="独立固定练习",
            targetKnowledgePointIds=self.kps,constraints=dict(count=count,**constraints))
        return http(self.client,"post","/practice-sets",201,json=self.last_create)

    def question(self, text, *, difficulty="easy", qtype="short_answer", rich=None, kps=None):
        rich=copy.deepcopy(self.rich if rich is None else rich)
        rich["stemBlocks"][0]["text"]=text
        model=RichContentV2.model_validate(rich)
        content=dict(type=qtype,stemMarkdown=project_blocks(model.stem_blocks),
            options=[dict(key=k,textMarkdown=project_blocks(v)) for k,v in model.option_blocks.items()],
            answer={"textMarkdown":project_blocks(model.answer_blocks)} if model.answer_blocks else None,
            explanationMarkdown=project_blocks(model.explanation_blocks),assetIds=[a.asset_id for a in model.assets],richContent=rich)
        links=[dict(knowledgePointId=p["knowledgePointId"],knowledgeRevisionId=p["knowledgeRevisionId"],subjectIdSnapshot="math",
            knowledgeNameSnapshot=p["name"],role=p["role"]) for p in self.points if p["knowledgePointId"] in (kps or self.kps)]
        # Fixture seed only: actual repository and immutable fixed links, no business response stub.
        with self.app.state.question_bank.write_transaction() as conn:
            q=self.app.state.question_bank.insert_question_in(conn,owner_id=self.app.state.question_bank_service.owner_id,content=content,
                metadata={"subjectId":"math","difficulty":difficulty},answer_state="provided" if model.answer_blocks else "not_provided",
                content_fingerprint=hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False,separators=(",", ":")).encode()).hexdigest(),
                source_spans=[],import_id=None,knowledge_links=links)
        return {"questionId":q.question_id,"questionRevisionId":q.current_revision_id,"rich":rich}

    def item(self, question, number="16", ordinal=1, nodes=None):
        rich=question["rich"]
        source=[b["id"] for b in rich["stemBlocks"]]+[b["id"] for v in rich["optionBlocks"].values() for b in v]
        return dict(itemKey="item-"+str(ordinal),questionRevisionId=question["questionRevisionId"],ordinal=ordinal,maxScore="1.25",
            selectedKnowledgePointIds=self.kps,itemStructure={"nodes":nodes or [dict(nodeKey="leaf",parentNodeKey=None,questionNo=number,
            ordinal=1,isScored=True,maxScore="1.25",knowledgePointIds=self.kps,sourceBlockIds=source)]})

    def save(self, practice, items, expected=200):
        return http(self.client,"patch",f"/practice-sets/{practice['practiceSetId']}/draft",expected,
            json=dict(expectedRevision=practice["revision"],items=items,constraints=practice["currentRevision"]["constraints"]))

    def review(self, practice, expected=200, submission=None):
        self.last_review=dict(submissionId=submission or uuid.uuid4().hex,expectedRevision=practice["revision"])
        return http(self.client,"post",f"/practice-sets/{practice['practiceSetId']}/review",expected,json=self.last_review)

    def reviewed(self, *, rich=None, text="独立新题"):
        q=self.question(text,rich=rich)
        return self.review(self.save(self.create(),[self.item(q)]))

    def convert(self, practice, *, expected=201, submission=None, **overrides):
        self.last_conversion=dict(submissionId=submission or uuid.uuid4().hex,title="独立返回施测",heldOn="2026-10-02",
            classIds=[self.seed["classId"]],participants=[dict(studentId=self.seed["studentId"],classId=self.seed["classId"],attendance="present",attemptNo=1)])
        self.last_conversion.update(overrides)
        return http(self.client,"post",self.path(practice)+"/assessments",expected,json=self.last_conversion)

    @staticmethod
    def path(practice):
        return f"/practice-sets/{practice['practiceSetId']}/revisions/{practice['currentRevision']['practiceRevisionId']}"

    def export(self, practice, variant="student", assessment=None, submission=None):
        self.last_export=dict(submissionId=submission or uuid.uuid4().hex,variant=variant)
        if assessment is not None:self.last_export["assessmentId"]=assessment
        return http(self.client,"post",self.path(practice)+"/exports",202,json=self.last_export)

    def artifact(self, practice, receipt):
        wait_job(self.client,receipt)
        history=http(self.client,"get",self.path(practice)+"/exports")
        meta=next(a for a in history["items"] if a["exportId"]==receipt["exportId"])
        actual=http(self.client,"get","/export-artifacts/"+meta["artifactId"])
        assert actual==meta
        response=self.client.get(meta["downloadUrl"])
        assert response.status_code==200
        assert hashlib.sha256(response.content).hexdigest()==meta["sha256"]
        assert len(response.content)==meta["byteSize"]
        assert response.headers["content-type"]==meta["mediaType"]
        return meta,response.content

    def counts(self, names):
        with self.catalog.read_connection() as conn:
            return {name:conn.execute('SELECT count(*) FROM "'+name+'"').fetchone()[0] for name in names}

    def image(self, marker, alias=None):
        # Own stdlib-generated valid PNG with visible unique tEXt marker.
        raw=b"\x00\xff\x00\x00\xff"
        def chunk(kind,payload):return struct.pack(">I",len(payload))+kind+payload+struct.pack(">I",zlib.crc32(kind+payload)&0xffffffff)
        data=b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",1,1,8,6,0,0,0))+chunk(b"tEXt",b"oracle\x00"+marker.encode())+chunk(b"IDAT",zlib.compress(raw))+chunk(b"IEND",b"")
        stored=self.app.state.asset_store.store_original(data,media_type="image/png",original_name="qa.png")
        aid=alias or stored.blob_key
        with self.catalog.write_transaction() as conn:
            if self.app.state.file_assets.get(aid) is None:
                self.app.state.file_assets.create_in(conn,kind="attachment",blob_key=stored.blob_key,sha256=stored.sha256,
                    byte_size=stored.byte_size,original_name="qa.png",media_type="image/png",asset_id=aid)
        return dict(assetId=aid,sha256=stored.sha256,mediaType="image/png"),data


def zip_oracle(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None
        names=archive.namelist()
        assert len(names)==len(set(names))
        parts={name:archive.read(name) for name in names}
    assert data[-22:-18]==b"PK\x05\x06"  # closed ZIP, no optional archive comment
    root=ET.fromstring(parts["word/document.xml"])
    ns={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "m":"http://schemas.openxmlformats.org/officeDocument/2006/math"}
    text="".join(root.itertext())
    return parts,root,ns,text


NEW_TABLES=("analysis_runs","analysis_participants","analysis_item_snapshots","analysis_student_results","analysis_class_results",
    "analysis_evidence","analysis_teacher_notes","practice_sets","practice_revisions","practice_selections","practice_items",
    "practice_item_knowledge","practice_conversions","practice_paper_item_mappings","practice_exports","export_artifacts")
