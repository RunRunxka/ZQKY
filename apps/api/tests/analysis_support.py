"""T70 isolated real migrated catalog, rich fixed source and public JobEngine."""
import json
import struct
import zlib
from pathlib import Path
from app.contracts.b4 import AnalysisCreateRequest
from app.contracts.teaching_loop import RichContentV2
from app.core.sqlite import now_iso
from app.repositories.teaching.catalog import TeachingCatalog
from app.repositories.jobs.repository import JobStore
from app.services.assets.store import AssetStore
from app.services.analysis.service import AnalysisService
from app.services.jobs.engine import JobEngine


class ManualEngine(JobEngine):
    """Capture scheduling for deterministic pre-ready tests; actual execution is run_job."""
    def __init__(self, store):
        super().__init__({"teaching": store})
        self.accepted = []

    def schedule(self, domain, job_id, executor, *, uses_model=False):
        self.accepted.append((domain, job_id, executor, uses_model))


class AnalysisScene:
    def __init__(self, root: Path, *, participant_count=4, leaf_count=3, now=None, known_type=None):
        self.root = root
        self.catalog = TeachingCatalog(root / "teaching.sqlite3")
        self.catalog.migrate()
        self.assets = AssetStore(root / "assets")
        self.store = JobStore(self.catalog, domain="teaching", table="workflow_jobs", kinds=frozenset({"analysis"}), now=now)
        self.engine = ManualEngine(self.store)
        self.service = AnalysisService(self.catalog, job_engine=self.engine, asset_store=self.assets)
        self.participant_ids = [f"p{i:03d}" for i in range(participant_count)]
        self.item_ids = [f"i{i:03d}" for i in range(leaf_count)]
        self.known_type = known_type
        self.seed(participant_count, leaf_count)

    def seed(self, participant_count, leaf_count):
        now = now_iso()
        original = self.assets.store_original(b"owned paper fixture", media_type="text/plain", original_name="paper.txt")
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
        image_bytes = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
                       + chunk(b"IDAT", zlib.compress(b"\x00\x00\x64\xff\xff")) + chunk(b"IEND", b""))
        image = self.assets.store_original(image_bytes, media_type="image/png", original_name="image.png")
        self.image = image
        self.rich = {"version": 2, "stemBlocks": [
            {"id": "stem", "kind": "paragraph", "text": "固定题面 $x^2$"},
            {"id": "formula", "kind": "formula", "latex": "x^2"},
            {"id": "image", "kind": "image", "assetId": "image", "width": 20, "height": 10},
            {"id": "table", "kind": "table", "columnCount": 1,
             "cells": [{"text": "表格", "isHeader": False, "rowSpan": 1, "colSpan": 1}]}],
            "sharedMaterials": [{"id": "material", "blocks": [{"id": "shared", "kind": "paragraph", "text": "共同材料"}]}],
            "assets": [{"assetId": "image", "sha256": image.sha256, "mediaType": "image/png"}],
            "optionBlocks": {}, "answerBlocks": [{"id": "answer", "kind": "paragraph", "text": "固定答案"}],
            "explanationBlocks": [], "origin": {"originalAssetId": "original", "originalSha256": original.sha256, "sourceLocator": {"paragraphIndex": 1}}}
        RichContentV2.model_validate(self.rich)
        max_scores = [200, 300, 500] if leaf_count == 3 else [100] * leaf_count
        participants = [{"participantId": pid, "studentId": f"s{index:03d}", "studentNo": f"{index:05d}",
                         "name": chr(65 + index) if participant_count == 4 else f"学生{index}", "classId": "class",
                         "attemptNo": 1, "attendance": "absent" if participant_count == 4 and index == 2 else "present"}
                        for index, pid in enumerate(self.participant_ids)]
        items = [{"itemId": iid, "itemPath": f"Q{index + 1}", "maxScoreUnits": max_scores[index]} for index, iid in enumerate(self.item_ids)]
        with self.catalog.write_transaction() as conn:
            for aid, asset, kind in (("original", original, "paper"), ("image", image, "attachment")):
                conn.execute("INSERT INTO file_assets(id,kind,blob_key,sha256,original_name,media_type,byte_size,created_at) VALUES(?,?,?,?,?,?,?,?)",
                             (aid, kind, asset.blob_key, asset.sha256, aid, "image/png" if aid == "image" else "text/plain", asset.byte_size, now))
            conn.execute("INSERT INTO papers(id,subject_id,title) VALUES('paper','math','当前标题')")
            conn.execute("INSERT INTO paper_revisions(id,paper_id,version,source_file_id,total_score_units,title_snapshot,title_snapshot_source) VALUES('paper-r','paper',1,'original',?,'固定标题','human')", (sum(max_scores),))
            for index, item in enumerate(items):
                content = {**self.rich, **({"type": self.known_type} if self.known_type is not None else {})}
                conn.execute("INSERT INTO paper_items(id,paper_revision_id,question_no,ordinal,is_scored,max_score_units,content_json,source_locator_json) VALUES(?,'paper-r',?,?,1,?,?,?)",
                             (item["itemId"], item["itemPath"], index + 1, item["maxScoreUnits"], json.dumps(content), json.dumps({"paragraphIndex": index, "nodeKey": f"node-{index}"})))
                links = (["k1"] if index == 0 else ["k1", "k2"] if index == 1 else ["k2"]) if leaf_count == 3 else [f"k{index % 5}"]
                for kp in links:
                    conn.execute("INSERT INTO paper_item_knowledge(item_id,paper_revision_id,knowledge_point_id,knowledge_revision_id,knowledge_name_snapshot,role,source) VALUES(?,'paper-r',?,?,?,'primary','human')",
                                 (item["itemId"], kp, f"{kp}-r", f"固定{kp}"))
            conn.execute("INSERT INTO paper_source_blocks(id,paper_revision_id,ordinal,kind,block_json,locator_json,disposition) VALUES('shared','paper-r',1,'paragraph',?,?,'shared_material')",
                         (json.dumps(self.rich["sharedMaterials"][0]["blocks"][0]), json.dumps({"paragraphIndex": 1})))
            conn.execute("UPDATE paper_revisions SET state='confirmed',confirmed_at=? WHERE id='paper-r'", (now,))
            conn.execute("UPDATE papers SET current_revision_id='paper-r' WHERE id='paper'")
            conn.execute("INSERT INTO classes(id,code,name,school_year,grade_id) VALUES('class','c','现班名','2026','g')")
            conn.execute("INSERT INTO assessments(id,paper_revision_id,title,assessment_type,held_on) VALUES('assessment','paper-r','测验','exam','2026-10-01')")
            conn.execute("INSERT INTO assessment_classes VALUES('assessment','class')")
            for participant in participants:
                conn.execute("INSERT INTO students(id,student_no,name) VALUES(?,?,?)", (participant["studentId"], participant["studentNo"], participant["name"]))
                conn.execute("INSERT INTO assessment_participants(id,assessment_id,student_id,class_id,attendance,name_snapshot,student_no_snapshot) VALUES(?,'assessment',?,'class',?,?,?)",
                             (participant["participantId"], participant["studentId"], participant["attendance"], participant["name"], participant["studentNo"]))
            conn.execute("INSERT INTO score_revisions(id,assessment_id,version,participant_snapshot_json,item_snapshot_json) VALUES('score-r','assessment',1,?,?)", (json.dumps(participants), json.dumps(items)))
            cells = []
            sample = [[200, 200, 500], [200, 300, None], [None] * 3, [0, 300, 500]]
            for index, participant in enumerate(participants):
                for column, item in enumerate(items):
                    score = sample[index][column] if participant_count == 4 and leaf_count == 3 else max_scores[column] - (index % 3) * 10
                    state = "recorded" if score is not None else "absent" if index == 2 else "missing"
                    cells.append(("score-r", "assessment", "paper-r", participant["participantId"], item["itemId"], score, state))
            conn.executemany("INSERT INTO student_item_scores VALUES(?,?,?,?,?,?,?)", cells)
            conn.execute("UPDATE score_revisions SET state='confirmed',confirmed_at=? WHERE id='score-r'", (now,))
            conn.execute("UPDATE assessments SET active_score_revision_id='score-r' WHERE id='assessment'")

    def request(self, submission="s1", ids=None):
        return AnalysisCreateRequest(submissionId=submission, scoreRevisionId="score-r",
                                     selectedParticipantIds=self.participant_ids if ids is None else ids, ruleCode="any_loss_v1")

    async def accept(self, submission="s1", ids=None):
        return await self.service.create_run("assessment", self.request(submission, ids))

    async def ready(self):
        receipt = await self.accept()
        job = await self.engine.run_job("teaching", receipt.job.job_id, self.service.execute_job)
        assert job.state == "succeeded", job.error
        return receipt

    def http_client(self):
        # Imported after outer process/test conftest isolation. No listener or
        # Qdrant/Ollama client is bootstrapped for this real create_app router test.
        from app.main import create_app
        from app.core.config import Settings
        from app.core.secrets import SecretStore
        from fastapi.testclient import TestClient
        from app.services.jobs.registry import JobExecutorRegistry
        data_root = self.root / "http"
        data_root.mkdir(exist_ok=True)
        source = self.root / "empty-source"
        source.mkdir(exist_ok=True)
        settings = Settings(host="127.0.0.1", port=8001, env="test", data_dir=data_root,
                            allowed_origins=frozenset({"http://127.0.0.1:5174"}), credentials_file=None,
                            qdrant_url="http://127.0.0.1:16333", embedding_base_url="http://127.0.0.1:9", textbook_source_dir=source)
        app = create_app(settings, bootstrap_textbooks=False, secret_store=SecretStore())
        app.state.analysis_service, app.state.job_engine = self.service, self.engine
        app.state.job_stores = {"teaching": self.store}
        registry = JobExecutorRegistry()
        self.service.register_job_executors(registry)
        app.state.job_executors = registry
        return TestClient(app, base_url="http://127.0.0.1:8001")

    def count(self, table):
        assert table in ("analysis_runs", "workflow_jobs", "command_submissions", "analysis_evidence", "analysis_teacher_notes", "analysis_participants", "analysis_student_results", "analysis_class_results", "analysis_item_snapshots")
        with self.catalog.read_connection() as conn:
            return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def new_score(self, *, changes=None, extra_attempt=False, direct_bad=False):
        """New full immutable history, never mutating the seed confirmed matrix."""
        with self.catalog.write_transaction() as conn:
            prior = conn.execute("SELECT * FROM score_revisions WHERE id='score-r'").fetchone()
            participants = json.loads(prior["participant_snapshot_json"])
            if extra_attempt:
                new = {**participants[0], "participantId": "p-repeat", "attemptNo": 2}
                participants.append(new)
                conn.execute("INSERT INTO assessment_participants(id,assessment_id,student_id,class_id,attempt_no,attendance,name_snapshot,student_no_snapshot) VALUES('p-repeat','assessment','s000','class',2,'present','A','00000')")
            conn.execute("INSERT INTO score_revisions(id,assessment_id,version,participant_snapshot_json,item_snapshot_json) VALUES('score-r2','assessment',2,?,?)", (json.dumps(participants), prior["item_snapshot_json"]))
            cells = [dict(row) for row in conn.execute("SELECT * FROM student_item_scores WHERE score_revision_id='score-r'")]
            if extra_attempt:
                cells.extend([{**c, "participant_id": "p-repeat"} for c in cells if c["participant_id"] == "p000"])
            for cell in cells:
                key = (cell["participant_id"], cell["item_id"])
                if changes and key in changes:
                    cell["status"], cell["score_units"] = changes[key]
                if direct_bad and key == ("p000", "i000"):
                    continue
                conn.execute("INSERT INTO student_item_scores VALUES('score-r2',?,?,?,?,?,?)", (cell["assessment_id"], cell["paper_revision_id"], cell["participant_id"], cell["item_id"], cell["score_units"], cell["status"]))
            if direct_bad:
                # Deliberately represent a corrupted legacy row by bypassing only
                # this OWN fixture's confirmation gate; restore its exact SQL.
                trigger = conn.execute("SELECT sql FROM sqlite_master WHERE name='score_revision_confirm_gate'").fetchone()[0]
                conn.execute("DROP TRIGGER score_revision_confirm_gate")
                conn.execute("UPDATE score_revisions SET state='confirmed',confirmed_at=? WHERE id='score-r2'", (now_iso(),))
                conn.execute(trigger)
            else:
                conn.execute("UPDATE score_revisions SET state='confirmed',confirmed_at=? WHERE id='score-r2'", (now_iso(),))
        return "score-r2"
