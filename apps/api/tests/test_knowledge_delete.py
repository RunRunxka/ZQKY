"""知识点彻底删除验收（任务①）：成功 / 三类跨库守卫 / 404 / 乐观锁 / 端口缺失 503。

全部用 ``TestClient`` + ``tmp_path`` 隔离数据根；跨库引用直接往教学库/题库的
``*_knowledge*`` 表插最小行（触发器允许的形状），不触网、不调模型、不读写正式数据。
"""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import knowledge as knowledge_route
from app.main import create_app
from app.repositories.assets.file_assets import FileAssetsRepository
from app.services.assets.store import AssetStore
from app.services.knowledge.evidence import EvidenceText
from app.services.knowledge.references import CrossLibraryReferenceChecker
from app.services.knowledge.service import build_knowledge_service
from app.services.publication import PublicationCoordinator
from tests.conftest import make_settings


def ensure_knowledge_router(app) -> None:
    paths = {getattr(route, "path", None) for route in app.router.routes}
    if "/api/v1/knowledge-points" not in paths:
        app.include_router(knowledge_route.router, prefix="/api/v1")
    routes = list(app.router.routes)
    catch = [
        route for route in routes if getattr(route, "name", "") == "feature_not_implemented"
    ]
    if catch:
        app.router.routes[:] = [route for route in routes if route not in catch] + catch


class FakeEvidenceReader:
    """教材证据替身：固定标题 + 区间切片（供建立教材依据）。"""

    def read(self, *, document_revision_id: str, char_start: int, char_end: int) -> EvidenceText:
        import hashlib

        text = "x" * (char_end - char_start)
        return EvidenceText(
            document_revision_id=document_revision_id,
            char_start=char_start,
            char_end=char_end,
            title="人教版数学七年级上册",
            text=text,
            sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            locator={"charStart": char_start, "charEnd": char_end},
        )


class DeleteHarness:
    """删除验收测试台：四库临时目录 + 注入端口的知识点服务（真实装配路径）。"""

    def __init__(self, tmp_path: Path, *, with_reference_checker: bool = True) -> None:
        self.settings = make_settings(tmp_path / "data")
        self.app = create_app(self.settings)
        self.catalog = self.app.state.knowledge
        self.teaching = self.app.state.teaching
        self.question_bank = self.app.state.question_bank
        self.assets = AssetStore(self.settings.assets_root)
        self.file_assets = FileAssetsRepository(self.teaching)
        self.coordinator = PublicationCoordinator()
        checker = CrossLibraryReferenceChecker(
            knowledge_catalog=self.catalog,
            teaching_catalog=self.teaching,
            question_bank_catalog=self.question_bank,
        ) if with_reference_checker else None
        self.service = build_knowledge_service(
            self.catalog,
            asset_store=self.assets,
            file_assets=self.file_assets,
            evidence=FakeEvidenceReader(),
            coordinator=self.coordinator,
            model_resolver=None,
            job_engine=self.app.state.job_engine,
            reference_checker=checker,
        )
        self.app.state.knowledge_service = self.service
        ensure_knowledge_router(self.app)
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8001")
        self.client.__enter__()

    def close(self) -> None:
        self.client.__exit__(None, None, None)

    # -------------------------------------------------------------- 便捷方法

    def create_point(self, code: str = "M7-01", **overrides: object) -> dict:
        payload = {"subjectId": "math", "code": code, "name": f"知识点 {code}"}
        payload.update(overrides)
        response = self.client.post("/api/v1/knowledge-points", json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    def delete(self, point_id: str, *, expected_revision: int) -> "object":
        return self.client.delete(
            f"/api/v1/knowledge-points/{point_id}",
            params={"expectedRevision": expected_revision},
        )

    def add_textbook_link(self, point: dict, *, revision_id: str = "rev-1") -> dict:
        response = self.client.post(
            f"/api/v1/knowledge-points/{point['id']}/textbook-links",
            json={
                "expectedRevision": point["revision"],
                "documentRevisionId": revision_id,
                "charStart": 0,
                "charEnd": 5,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    def teaching_exec(self, sql: str, params: tuple = ()) -> None:
        connection = sqlite3.connect(self.teaching.db_path)
        try:
            connection.execute(sql, params)
            connection.commit()
        finally:
            connection.close()

    def qb_exec(self, sql: str, params: tuple = ()) -> None:
        connection = sqlite3.connect(self.question_bank.db_path)
        try:
            connection.execute(sql, params)
            connection.commit()
        finally:
            connection.close()

    def counts(self, table: str, db_path: Path) -> int:
        connection = sqlite3.connect(db_path)
        try:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            connection.close()


@pytest.fixture()
def harness(tmp_path: Path):
    instance = DeleteHarness(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


# --------------------------------------------------------------------------- 成功路径


def test_delete_success_removes_identity_revisions_aliases(harness: DeleteHarness) -> None:
    point = harness.create_point(code="M7-D1", name="待删除", aliases=["别名甲"])
    # 改一次名：产生第二个修订（历史修订必须一并删除）
    renamed = harness.client.patch(
        f"/api/v1/knowledge-points/{point['id']}",
        json={"expectedRevision": 0, "name": "待删除改"},
    )
    assert renamed.status_code == 200, renamed.text

    deleted = harness.delete(point["id"], expected_revision=1)
    assert deleted.status_code == 204, deleted.text
    # 身份行、修订行、别名行全部消失
    assert harness.counts("knowledge_points", harness.catalog.db_path) == 0
    assert harness.counts("knowledge_point_revisions", harness.catalog.db_path) == 0
    assert harness.counts("knowledge_aliases", harness.catalog.db_path) == 0

    gone = harness.client.get(f"/api/v1/knowledge-points/{point['id']}")
    assert gone.status_code == 404
    assert gone.json()["code"] == "KNOWLEDGE_POINT_NOT_FOUND"


def test_delete_without_textbook_links_happy_path(harness: DeleteHarness) -> None:
    point = harness.create_point(code="M7-D2")
    # 有教材依据时删除被守卫拒绝（另一用例）；先确认 0 依据可删
    deleted = harness.delete(point["id"], expected_revision=0)
    assert deleted.status_code == 204, deleted.text


def test_revision_immutability_trigger_restored_after_delete(harness: DeleteHarness) -> None:
    """彻底删除后，修订不可变触发器必须原样恢复（守卫后的受控行为不留后门）。"""
    point = harness.create_point(code="M7-T1", name="触发器恢复")
    deleted = harness.delete(point["id"], expected_revision=0)
    assert deleted.status_code == 204, deleted.text

    # 新知识点的历史修订仍然不可删（触发器兜底生效）
    other = harness.create_point(code="M7-T2", name="仍在")
    connection = sqlite3.connect(harness.catalog.db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError) as excinfo:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            connection.execute(
                "DELETE FROM knowledge_point_revisions WHERE knowledge_point_id = ?",
                (other["id"],),
            )
            connection.execute("ROLLBACK")
        assert "IMMUTABLE_REVISION" in str(excinfo.value)
        # 触发器对象仍在 schema 里
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' "
            "AND name='immutable_knowledge_point_revisions_delete'"
        ).fetchone()
        assert row is not None
    finally:
        connection.close()


# --------------------------------------------------------------------------- 守卫


def test_delete_guarded_by_textbook_links(harness: DeleteHarness) -> None:
    point = harness.create_point(code="M7-G1")
    harness.add_textbook_link(point, revision_id="rev-1")
    response = harness.delete(point["id"], expected_revision=0)
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "KNOWLEDGE_POINT_IN_USE"
    counts = {item["key"]: item["count"] for item in body["details"]["counts"]}
    assert counts["textbookKnowledgeLinks"] == 1
    assert counts["paperItemKnowledge"] == 0
    # 数据不乱：知识点仍在
    assert harness.client.get(f"/api/v1/knowledge-points/{point['id']}").status_code == 200


def test_delete_guarded_by_paper_item_knowledge(harness: DeleteHarness) -> None:
    point = harness.create_point(code="M7-G2")
    # 教学库插入最小题目知识点关联行（paper_item_knowledge 无外键约束，形状与迁移一致）
    harness.teaching_exec(
        "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
        "knowledge_revision_id, knowledge_name_snapshot, role, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"item-{uuid.uuid4().hex[:8]}", f"paperrev-{uuid.uuid4().hex[:8]}",
         point["id"], point["revisionId"], "知识点 M7-G2", "primary", "human"),
    )
    response = harness.delete(point["id"], expected_revision=0)
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "KNOWLEDGE_POINT_IN_USE"
    counts = {item["key"]: item["count"] for item in body["details"]["counts"]}
    assert counts["paperItemKnowledge"] == 1
    assert harness.client.get(f"/api/v1/knowledge-points/{point['id']}").status_code == 200


def test_delete_guarded_by_question_bank_links(harness: DeleteHarness) -> None:
    point = harness.create_point(code="M7-G3")
    # 题库正式关联：经 catalog 单事务接口插最小题目 + 关联（确认入库同一形状）
    with harness.question_bank.write_transaction() as conn:
        record = harness.question_bank.insert_question_in(
            conn,
            owner_id="local",
            content={"stem": "题干"},
            metadata={"subjectId": "math"},
            answer_state="provided",
            content_fingerprint="fp-test",
            source_spans=[],
            import_id=None,
            knowledge_links=[
                {
                    "knowledgePointId": point["id"],
                    "knowledgeRevisionId": point["revisionId"],
                    "subjectIdSnapshot": "math",
                    "knowledgeNameSnapshot": "知识点 M7-G3",
                    "role": "primary",
                }
            ],
        )
        assert record is not None
    # 题库草稿关联：最小 import + draft + draft link
    imported = harness.question_bank.create_import(
        owner_id="local",
        file_sha256="a" * 64,
        original_blob_id="blobs/" + "b" * 64,
        uploaded_file_name="x.json",
        uploaded_bytes=1,
    )
    with harness.question_bank.write_transaction() as conn:
        draft_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO question_drafts (id, import_id, revision, content_json, metadata_json, "
            "source_spans_json, extraction_method, review_state, missing_answer_acknowledged, "
            "warnings_json, content_fingerprint, duplicate_of_question_id) "
            "VALUES (?, ?, 0, '{}', '{}', '[]', 'ai', 'needs_review', 0, '[]', '', NULL)",
            (draft_id, imported.import_id),
        )
        conn.execute(
            "INSERT INTO question_draft_knowledge_links (draft_id, knowledge_point_id, "
            "knowledge_revision_id, subject_id_snapshot, knowledge_name_snapshot, role, source, created_at) "
            "VALUES (?, ?, ?, 'math', ?, 'primary', 'human', '2026-10-08T00:00:00Z')",
            (draft_id, point["id"], point["revisionId"], "知识点 M7-G3"),
        )
    response = harness.delete(point["id"], expected_revision=0)
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "KNOWLEDGE_POINT_IN_USE"
    counts = {item["key"]: item["count"] for item in body["details"]["counts"]}
    assert counts["questionKnowledgeLinks"] == 1
    assert counts["questionDraftKnowledgeLinks"] == 1
    # 数据不乱：知识点仍在
    assert harness.client.get(f"/api/v1/knowledge-points/{point['id']}").status_code == 200


def test_delete_guarded_by_child_points(harness: DeleteHarness) -> None:
    parent = harness.create_point(code="M7-GP", name="父")
    harness.create_point(code="M7-GC", name="子", parentId=parent["id"])
    response = harness.delete(parent["id"], expected_revision=0)
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "KNOWLEDGE_POINT_IN_USE"
    assert "子节点" in body["message"]


# --------------------------------------------------------------------------- 404 / 乐观锁 / 端口缺失


def test_delete_missing_point_is_404(harness: DeleteHarness) -> None:
    response = harness.delete("no-such-point", expected_revision=0)
    assert response.status_code == 404
    assert response.json()["code"] == "KNOWLEDGE_POINT_NOT_FOUND"


def test_delete_stale_revision_is_conflict(harness: DeleteHarness) -> None:
    point = harness.create_point(code="M7-S1")
    harness.client.patch(
        f"/api/v1/knowledge-points/{point['id']}",
        json={"expectedRevision": 0, "name": "改名"},
    )
    stale = harness.delete(point["id"], expected_revision=0)
    assert stale.status_code == 409
    body = stale.json()
    assert body["code"] == "REVISION_CONFLICT"
    assert body["details"]["currentRevision"] == 1
    # 数据未被删除
    assert harness.client.get(f"/api/v1/knowledge-points/{point['id']}").status_code == 200


def test_delete_without_reference_checker_is_503(tmp_path: Path) -> None:
    harness = DeleteHarness(tmp_path, with_reference_checker=False)
    try:
        point = harness.create_point(code="M7-N1")
        response = harness.delete(point["id"], expected_revision=0)
        assert response.status_code == 503
        body = response.json()
        assert body["code"] == "SERVICE_UNAVAILABLE"
        assert body["retryable"] is True
        # 未删除
        assert harness.client.get(f"/api/v1/knowledge-points/{point['id']}").status_code == 200
    finally:
        harness.close()


def test_import_summary_carries_uploaded_file_name(tmp_path: Path) -> None:
    """顺带验收：KnowledgeImportSummary.uploadedFileName 读 file_assets.original_name。"""
    from io import BytesIO

    from openpyxl import Workbook

    harness = DeleteHarness(tmp_path)
    try:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["code", "name"])
        worksheet.append(["X1", "单元格知识点"])
        buffer = BytesIO()
        workbook.save(buffer)
        response = harness.client.post(
            "/api/v1/knowledge-imports",
            files={"file": ("我的知识点表.xlsx", buffer.getvalue(), "application/octet-stream")},
            data={"subjectId": "math"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["uploadedFileName"] == "我的知识点表.xlsx"
        listing = harness.client.get("/api/v1/knowledge-imports").json()["items"][0]
        assert listing["uploadedFileName"] == "我的知识点表.xlsx"
    finally:
        harness.close()
