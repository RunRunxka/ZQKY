"""知识点彻底删除验收（任务①）：成功 / 三类跨库守卫 / 404 / 乐观锁 / 端口缺失 503。

全部用 ``TestClient`` + ``tmp_path`` 隔离数据根；跨库引用直接往教学库/题库的
``*_knowledge*`` 表插最小行（触发器允许的形状），不触网、不调模型、不读写正式数据。
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
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
        # R3 适配：教学库（R5-BE 批次）不在 main 装配范围，本台自建临时 TeachingCatalog
        from app.repositories.teaching.catalog import TeachingCatalog

        self.teaching = TeachingCatalog(tmp_path / "teaching" / "teaching.sqlite3")
        self.teaching.migrate()
        # R3 适配：题库域（R4-BE 批次）未装配；这里用冻结迁移建**裸**题库临时库，
        # 跨库引用按生产同一物理表/列名直接插最小行（守卫只读这些表）。
        from app.core.migrations import apply_migrations as qb_apply
        from app.core.sqlite import connect as qb_connect

        qb_path = tmp_path / "question-bank" / "question-bank.sqlite3"
        qb_path.parent.mkdir(parents=True, exist_ok=True)
        connection = qb_connect(qb_path)
        try:
            qb_apply(connection, database="question_bank")
        finally:
            connection.close()

        class _BareQuestionBank:
            """迁移后的裸题库库：只提供 db_path 与事务入口（测试插最小行用）。"""

            def __init__(self, db_path: Path) -> None:
                self.db_path = db_path

            @contextmanager
            def write_transaction(self):
                from app.core.sqlite import transaction

                connection = qb_connect(self.db_path)
                try:
                    with transaction(connection, immediate=True) as conn:
                        conn.execute("PRAGMA defer_foreign_keys = ON")
                        yield conn
                finally:
                    connection.close()

            @contextmanager
            def read_connection(self):
                from app.core.sqlite import read_transaction

                connection = qb_connect(self.db_path)
                try:
                    with read_transaction(connection) as conn:
                        yield conn
                finally:
                    connection.close()

        self.question_bank = _BareQuestionBank(qb_path)
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
    # R3 适配：题库 catalog 未取回，正式关联按生产同一物理表插最小行
    # （questions → question_revisions → question_knowledge_links，同事务）。
    question_id = uuid.uuid4().hex
    revision_id = uuid.uuid4().hex
    with harness.question_bank.write_transaction() as conn:
        conn.execute(
            "INSERT INTO questions (id, owner_id, current_revision_id, status, created_at) "
            "VALUES (?, 'local', ?, 'confirmed', '2026-10-12T00:00:00Z')",
            (question_id, revision_id),
        )
        conn.execute(
            "INSERT INTO question_revisions (id, question_id, content_json, metadata_json, "
            "answer_state, content_fingerprint, confirmed_at) "
            "VALUES (?, ?, '{}', '{}', 'provided', 'fp-test', '2026-10-12T00:00:00Z')",
            (revision_id, question_id),
        )
        conn.execute(
            "INSERT INTO question_knowledge_links (question_revision_id, knowledge_point_id, "
            "knowledge_revision_id, subject_id_snapshot, knowledge_name_snapshot, role, created_at) "
            "VALUES (?, ?, ?, 'math', ?, 'primary', '2026-10-12T00:00:00Z')",
            (revision_id, point["id"], point["revisionId"], "知识点 M7-G3"),
        )
    # 题库草稿关联：最小 import + draft + draft link
    import_row_id = uuid.uuid4().hex
    with harness.question_bank.write_transaction() as conn:
        conn.execute(
            "INSERT INTO question_imports (id, owner_id, file_sha256, original_blob_id, "
            "uploaded_file_name, uploaded_bytes, state, revision, warnings_json, "
            "created_at, updated_at) "
            "VALUES (?, 'local', ?, ?, 'x.json', 1, 'uploaded', 0, '[]', "
            "'2026-10-12T00:00:00Z', '2026-10-12T00:00:00Z')",
            (import_row_id, "a" * 64, "blobs/" + "b" * 64),
        )
        draft_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO question_drafts (id, import_id, revision, content_json, metadata_json, "
            "source_spans_json, extraction_method, review_state, missing_answer_acknowledged, "
            "warnings_json, content_fingerprint, duplicate_of_question_id) "
            "VALUES (?, ?, 0, '{}', '{}', '[]', 'ai', 'needs_review', 0, '[]', '', NULL)",
            (draft_id, import_row_id),
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


def test_delete_parent_cascades_subtree(harness: DeleteHarness) -> None:
    """父节点删除 = 整棵子树物理删除（用户 2026-10-20 裁定）。"""
    parent = harness.create_point(code="M7-GP", name="父")
    child = harness.create_point(code="M7-GC", name="子", parentId=parent["id"])
    grandchild = harness.create_point(code="M7-GG", name="孙", parentId=child["id"])

    deleted = harness.delete(parent["id"], expected_revision=0)
    assert deleted.status_code == 204, deleted.text
    for point in (parent, child, grandchild):
        assert harness.client.get(f"/api/v1/knowledge-points/{point['id']}").status_code == 404
    assert harness.counts("knowledge_points", harness.catalog.db_path) == 0
    assert harness.counts("knowledge_point_revisions", harness.catalog.db_path) == 0


def test_delete_subtree_blocked_by_child_reference(harness: DeleteHarness) -> None:
    """子树中任一节点被引用 → 409，details.points 点名该子节点。"""
    parent = harness.create_point(code="M7-GP2", name="父")
    child = harness.create_point(code="M7-GC2", name="子", parentId=parent["id"])
    harness.add_textbook_link(child, revision_id="rev-child")

    response = harness.delete(parent["id"], expected_revision=0)
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "KNOWLEDGE_POINT_IN_USE"
    details = body["details"]
    assert details["subtreeSize"] == 2
    blocked = {item["pointId"]: item for item in details["points"]}
    assert set(blocked) == {child["id"]}
    assert blocked[child["id"]]["name"] == "子"
    counts = {item["key"]: item["count"] for item in blocked[child["id"]]["counts"]}
    assert counts["textbookKnowledgeLinks"] == 1
    # 数据不乱：父子都还在
    assert harness.client.get(f"/api/v1/knowledge-points/{parent['id']}").status_code == 200
    assert harness.client.get(f"/api/v1/knowledge-points/{child['id']}").status_code == 200


def test_delete_clears_import_row_target(harness: DeleteHarness) -> None:
    """导入预览行的 target 外键不再是删除死路：同事务置 NULL 后删除成功。"""
    point = harness.create_point(code="M7-IMP", name="导入命中点")
    import_id = uuid.uuid4().hex
    with harness.catalog.write_transaction() as conn:
        conn.execute(
            "INSERT INTO knowledge_imports (id, source, subject_id, file_asset_id, "
            "created_at, updated_at) VALUES (?, 'file', 'math', 'blob-1', "
            "'2026-10-20T00:00:00Z', '2026-10-20T00:00:00Z')",
            (import_id,),
        )
        conn.execute(
            "INSERT INTO knowledge_import_rows (import_id, row_no, name, code, "
            "target_knowledge_point_id) VALUES (?, 1, '导入行', 'X1', ?)",
            (import_id, point["id"]),
        )

    deleted = harness.delete(point["id"], expected_revision=0)
    assert deleted.status_code == 204, deleted.text
    connection = sqlite3.connect(harness.catalog.db_path)
    try:
        row = connection.execute(
            "SELECT target_knowledge_point_id FROM knowledge_import_rows WHERE import_id = ?",
            (import_id,),
        ).fetchone()
        assert row is not None and row[0] is None
    finally:
        connection.close()


def test_reference_checker_late_binding_resolves_catalogs() -> None:
    """知识域先装配：provider 在调用时解析 teaching/question_bank，而不是构造时。"""
    from app.services.knowledge.references import CrossLibraryReferenceChecker

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        harness = DeleteHarness(Path(tmp))
        try:
            point = harness.create_point(code="M7-LATE", name="晚绑定")
            state: dict[str, object | None] = {"teaching": None, "question_bank": None}
            checker = CrossLibraryReferenceChecker(
                knowledge_catalog=harness.catalog,
                teaching_catalog_provider=lambda: state["teaching"],
                question_bank_catalog_provider=lambda: state["question_bank"],
            )
            assert checker.count_references(point["id"]).total == 0

            state["teaching"] = harness.teaching
            state["question_bank"] = harness.question_bank
            harness.teaching_exec(
                "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
                "knowledge_revision_id, knowledge_name_snapshot, role, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"item-{uuid.uuid4().hex[:8]}", f"paperrev-{uuid.uuid4().hex[:8]}",
                 point["id"], point["revisionId"], "知识点 M7-LATE", "primary", "human"),
            )
            assert checker.count_references(point["id"]).paper_items == 1
        finally:
            harness.close()


def test_build_reference_checker_uses_late_binding() -> None:
    """真实装配函数也必须晚绑定（生产 main.py 的域装配顺序）。"""
    from app.services.knowledge.assembly import _build_reference_checker

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        harness = DeleteHarness(Path(tmp))
        try:
            class _App:
                def __init__(self) -> None:
                    self.state = type("_State", (), {})()
                    self.state.knowledge = harness.catalog

            app = _App()
            checker = _build_reference_checker(app)
            point = harness.create_point(code="M7-LATE2", name="装配晚绑定")
            assert checker.count_references(point["id"]).total == 0

            app.state.teaching = harness.teaching
            harness.teaching_exec(
                "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
                "knowledge_revision_id, knowledge_name_snapshot, role, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"item-{uuid.uuid4().hex[:8]}", f"paperrev-{uuid.uuid4().hex[:8]}",
                 point["id"], point["revisionId"], "知识点 M7-LATE2", "primary", "human"),
            )
            assert checker.count_references(point["id"]).paper_items == 1
        finally:
            harness.close()


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
