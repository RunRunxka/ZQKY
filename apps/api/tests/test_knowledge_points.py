"""知识点后端验收：CRUD、父树、别名、归档、教材依据（TEACHING-LOOP B1 / T20 验收 A5）。

全部用 ``TestClient`` + ``tmp_path`` 隔离数据根：真实知识点库/教学库/教材目录临时文件，
教材证据分别用**假 reader** 与**真教材目录临时库**各验一遍；不触网、不读写正式
``.local-data`` / ``.env``。B1 的路由由本测试显式挂载（CTRL 装配前 main.py 尚未注册）。
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import knowledge as knowledge_route
from app.contracts.knowledge import TEXTBOOK_EVIDENCE_UNAVAILABLE
from app.core.exceptions import AppError
from app.main import create_app
from app.repositories.assets.file_assets import FileAssetsRepository
from app.services.assets.store import AssetStore
from app.services.knowledge.evidence import EvidenceText, TextbookEvidenceReader
from app.services.knowledge.service import build_knowledge_service
from app.services.publication import PublicationCoordinator
from app.services.rag_v2.source_text import ImmutableSource
from app.services.textbook_ingest.blobs import BlobStore, sha256_text
from tests.conftest import make_settings

FAKE_TEXT = (
    "第一章 有理数\n"
    "有理数加法法则：同号两数相加，取相同的符号，并把绝对值相加。\n"
    "有理数减法法则：减去一个数，等于加上这个数的相反数。"
)
FAKE_TITLE = "人教版数学七年级上册"

_UNSET = object()


def ensure_knowledge_router(app) -> None:
    """挂载 B1 知识点路由；通配 501 占位必须留在最后（否则抢先匹配）。"""
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
    """教材证据替身：区间切片 + 固定标题；``missing-revision`` 模拟不可用。"""

    def __init__(self, *, title: str = FAKE_TITLE, text: str = FAKE_TEXT) -> None:
        self.title = title
        self.text = text
        self.calls: list[tuple[str, int, int]] = []

    def read(self, *, document_revision_id: str, char_start: int, char_end: int) -> EvidenceText:
        self.calls.append((document_revision_id, char_start, char_end))
        if document_revision_id == "missing-revision":
            raise AppError(
                "教材修订不存在。",
                code=TEXTBOOK_EVIDENCE_UNAVAILABLE,
                status_code=503,
                retryable=True,
            )
        text = self.text[char_start:char_end]
        return EvidenceText(
            document_revision_id=document_revision_id,
            char_start=char_start,
            char_end=char_end,
            title=self.title,
            text=text,
            sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            locator={
                "charStart": char_start,
                "charEnd": char_end,
                "lineStart": 2,
                "lineEnd": 2,
            },
        )


def make_real_evidence(app):
    """真教材目录临时库：目录 + 规范化文本 blob + ``ImmutableSource``。"""
    catalog = app.state.catalog
    document = catalog.create_document(
        owner_id="local-user",
        title=FAKE_TITLE,
        stage_id="stage-1",
        grade_ids=("g7",),
        subject_id="math",
        edition_id="rj",
    )
    blobs = BlobStore(app.state.settings.textbooks_root)
    blob_id = blobs.write_staged_text(FAKE_TEXT)
    blobs.seal(area="normalized", blob_id=blob_id)
    revision = catalog.create_document_revision(
        document.document_id,
        original_file_sha256=hashlib.sha256(FAKE_TEXT.encode("utf-8")).hexdigest(),
        normalized_text_sha256=sha256_text(FAKE_TEXT),
        parser_version="test-parser-1",
        original_blob_id=blob_id,
        normalized_blob_id=blob_id,
        source_map_blob_id=blob_id,
        char_count=len(FAKE_TEXT),
    )
    source = ImmutableSource(catalog=catalog, blobs_root=app.state.settings.textbooks_root)
    reader = TextbookEvidenceReader(catalog, source=source)
    # 测试便捷：把本次创建的教材修订 id 挂在 reader 上（reader 无 __slots__）
    reader.revision_id = revision.revision_id  # type: ignore[attr-defined]
    return reader


class KnowledgeHarness:
    """一次测试用的完整应用：四库临时目录 + 注入替身的知识点服务。"""

    def __init__(
        self,
        tmp_path: Path,
        *,
        evidence: object = _UNSET,
        evidence_factory=None,
        coordinator: PublicationCoordinator | None = None,
    ) -> None:
        self.settings = make_settings(tmp_path / "data")
        self.app = create_app(self.settings)
        self.catalog = self.app.state.knowledge
        assert self.catalog is not None, "知识点库未装配"
        self.teaching = self.app.state.teaching
        assert self.teaching is not None, "教学库未装配"
        self.assets = AssetStore(self.settings.assets_root)
        self.file_assets = FileAssetsRepository(self.teaching)
        if evidence_factory is not None:
            self.evidence = evidence_factory(self.app)
        elif evidence is _UNSET:
            self.evidence = None
        else:
            self.evidence = evidence
        self.coordinator = coordinator or PublicationCoordinator()
        self.service = build_knowledge_service(
            self.catalog,
            asset_store=self.assets,
            file_assets=self.file_assets,
            evidence=self.evidence,
            coordinator=self.coordinator,
            model_resolver=None,
            job_engine=self.app.state.job_engine,
        )
        self.app.state.knowledge_service = self.service
        ensure_knowledge_router(self.app)
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8001")
        self.client.__enter__()

    def close(self) -> None:
        self.client.__exit__(None, None, None)

    # -------------------------------------------------------------- 便捷方法

    def create_point(self, code: str = "M7-01", **overrides: object) -> dict:
        payload = {
            "subjectId": "math",
            "code": code,
            "name": f"知识点 {code}",
        }
        payload.update(overrides)
        response = self.client.post("/api/v1/knowledge-points", json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    def point(self, point_id: str) -> dict:
        response = self.client.get(f"/api/v1/knowledge-points/{point_id}")
        assert response.status_code == 200, response.text
        return response.json()

    def count(self, table: str) -> int:
        connection = sqlite3.connect(self.catalog.db_path)
        try:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            connection.close()


@pytest.fixture()
def harness(tmp_path: Path):
    instance = KnowledgeHarness(tmp_path, evidence=FakeEvidenceReader())
    try:
        yield instance
    finally:
        instance.close()


# --------------------------------------------------------------------------- CRUD


def test_create_and_read_point_view_fields(harness: KnowledgeHarness) -> None:
    point = harness.create_point(
        code="M7-01",
        name="有理数",
        description="引入负数后的数系",
        aliases=["有理数集", "Rational"],
    )
    assert point["subjectId"] == "math"
    assert point["code"] == "M7-01"
    assert point["name"] == "有理数"
    assert point["description"] == "引入负数后的数系"
    assert point["parentId"] is None and point["parentCode"] is None
    assert point["status"] == "active"
    assert point["revision"] == 0
    assert point["version"] == 1
    assert point["revisionId"]
    assert point["aliases"] == ["有理数集", "Rational"]
    assert point["createdAt"]

    fetched = harness.point(point["id"])
    assert fetched == point

    missing = harness.client.get("/api/v1/knowledge-points/nope")
    assert missing.status_code == 404
    assert missing.json()["code"] == "KNOWLEDGE_POINT_NOT_FOUND"


def test_duplicate_code_in_subject_conflicts(harness: KnowledgeHarness) -> None:
    harness.create_point(code="M7-01")
    response = harness.client.post(
        "/api/v1/knowledge-points",
        json={"subjectId": "math", "code": "M7-01", "name": "重复"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "KNOWLEDGE_CODE_CONFLICT"
    assert harness.count("knowledge_points") == 1
    # 同学科同 code 才冲突：其他学科可用同一 code
    other = harness.client.post(
        "/api/v1/knowledge-points",
        json={"subjectId": "physics", "code": "M7-01", "name": "物理同编码"},
    )
    assert other.status_code == 201, other.text


def test_list_pagination_and_filters(harness: KnowledgeHarness) -> None:
    for index in range(3):
        harness.create_point(code=f"M7-{index}", name=f"有理数 {index}")
    harness.create_point(code="P1", name="力", subjectId="physics")
    parent = harness.create_point(code="M7-P", name="数与代数")
    harness.create_point(code="M7-C", name="有理数加法", parentId=parent["id"])

    listing = harness.client.get(
        "/api/v1/knowledge-points", params={"subjectId": "math", "limit": 2, "offset": 0}
    )
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total"] == 5 and body["limit"] == 2 and body["offset"] == 0
    assert len(body["items"]) == 2

    children = harness.client.get(
        "/api/v1/knowledge-points", params={"subjectId": "math", "parentId": parent["id"]}
    ).json()
    assert [item["code"] for item in children["items"]] == ["M7-C"]

    by_name = harness.client.get(
        "/api/v1/knowledge-points", params={"q": "有理数加法"}
    ).json()
    assert [item["code"] for item in by_name["items"]] == ["M7-C"]

    archived_view = harness.client.get(
        "/api/v1/knowledge-points", params={"subjectId": "math", "status": "archived"}
    ).json()
    assert archived_view["total"] == 0

    too_large = harness.client.get("/api/v1/knowledge-points", params={"limit": 201})
    assert too_large.status_code == 422
    assert too_large.json()["code"] == "INVALID_REQUEST"


def test_invalid_body_returns_422_with_fields(harness: KnowledgeHarness) -> None:
    response = harness.client.post("/api/v1/knowledge-points", json={"subjectId": "math"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "INVALID_REQUEST"
    assert body["details"]["fields"]


# --------------------------------------------------------------------------- 更新/修订


def test_rename_appends_revision_and_old_revision_is_immutable(
    harness: KnowledgeHarness,
) -> None:
    point = harness.create_point(name="有理数")
    old_revision_id = point["revisionId"]

    renamed = harness.client.patch(
        f"/api/v1/knowledge-points/{point['id']}",
        json={"expectedRevision": 0, "name": "有理数与数轴"},
    )
    assert renamed.status_code == 200, renamed.text
    body = renamed.json()
    assert body["name"] == "有理数与数轴"
    assert body["version"] == 2
    assert body["revision"] == 1
    assert body["revisionId"] != old_revision_id

    # 旧修订仍在且不可改（DB 触发器兜底）
    connection = sqlite3.connect(harness.catalog.db_path)
    try:
        rows = connection.execute(
            "SELECT version, name FROM knowledge_point_revisions "
            "WHERE knowledge_point_id = ? ORDER BY version",
            (point["id"],),
        ).fetchall()
        assert rows == [(1, "有理数"), (2, "有理数与数轴")]
        with pytest.raises(sqlite3.IntegrityError) as excinfo:
            connection.execute(
                "UPDATE knowledge_point_revisions SET name = '被篡改' WHERE id = ?",
                (old_revision_id,),
            )
        assert "IMMUTABLE_REVISION" in str(excinfo.value)
    finally:
        connection.close()


def test_blank_fields_do_not_change_and_clear_fields_clears(
    harness: KnowledgeHarness,
) -> None:
    parent = harness.create_point(code="M7-P", name="数与代数")
    child = harness.create_point(
        code="M7-C",
        name="有理数",
        description="原说明",
        parentId=parent["id"],
        aliases=["一次函数"],
    )
    assert child["parentCode"] == "M7-P"

    blank = harness.client.patch(
        f"/api/v1/knowledge-points/{child['id']}",
        json={
            "expectedRevision": 0,
            "description": "   ",
            "aliases": [],
            "parentId": None,
            "parentCode": None,
        },
    )
    assert blank.status_code == 200, blank.text
    body = blank.json()
    assert body["description"] == "原说明"  # 空白默认不动
    assert body["aliases"] == ["一次函数"]
    assert body["parentId"] == parent["id"]
    assert body["revision"] == 0  # 没有任何实际变化

    cleared = harness.client.patch(
        f"/api/v1/knowledge-points/{child['id']}",
        json={"expectedRevision": 0, "clearFields": ["description", "parentId", "aliases"]},
    )
    assert cleared.status_code == 200, cleared.text
    body = cleared.json()
    assert body["description"] == ""
    assert body["parentId"] is None and body["parentCode"] is None
    assert body["aliases"] == []
    assert body["revision"] == 1
    # 清空说明也算内容变化 → 追加内容修订
    assert body["version"] == 2


def test_expected_revision_conflict_carries_current_revision(
    harness: KnowledgeHarness,
) -> None:
    point = harness.create_point()
    harness.client.patch(
        f"/api/v1/knowledge-points/{point['id']}", json={"expectedRevision": 0, "name": "新名"}
    )
    stale = harness.client.patch(
        f"/api/v1/knowledge-points/{point['id']}", json={"expectedRevision": 0, "name": "旧名"}
    )
    assert stale.status_code == 409
    body = stale.json()
    assert body["code"] == "REVISION_CONFLICT"
    assert body["details"]["currentRevision"] == 1


# --------------------------------------------------------------------------- 父树


def test_create_child_by_parent_code(harness: KnowledgeHarness) -> None:
    parent = harness.create_point(code="M7-P", name="数与代数")
    child = harness.create_point(code="M7-C", name="有理数", parentCode="M7-P")
    assert child["parentId"] == parent["id"]
    assert child["parentCode"] == "M7-P"

    both = harness.client.post(
        "/api/v1/knowledge-points",
        json={
            "subjectId": "math",
            "code": "M7-X",
            "name": "两个父字段",
            "parentId": parent["id"],
            "parentCode": "M7-P",
        },
    )
    assert both.status_code == 422
    assert both.json()["code"] == "INVALID_REQUEST"


def test_cross_subject_and_missing_parent_are_located(harness: KnowledgeHarness) -> None:
    physics = harness.create_point(code="P1", name="力", subjectId="physics")

    cross = harness.client.post(
        "/api/v1/knowledge-points",
        json={
            "subjectId": "math",
            "code": "M7-C",
            "name": "跨学科父",
            "parentId": physics["id"],
        },
    )
    assert cross.status_code == 422
    body = cross.json()
    assert body["code"] == "KNOWLEDGE_CROSS_SUBJECT_PARENT"
    assert body["details"]["issues"][0]["field"] == "parentId"

    missing = harness.client.post(
        "/api/v1/knowledge-points",
        json={
            "subjectId": "math",
            "code": "M7-D",
            "name": "缺父",
            "parentCode": "NOPE",
        },
    )
    assert missing.status_code == 422
    body = missing.json()
    assert body["code"] == "KNOWLEDGE_PARENT_INVALID"
    assert body["details"]["issues"][0]["field"] == "parentCode"
    assert harness.count("knowledge_points") == 1


def test_self_parent_and_cycle_rejected_without_db_damage(
    harness: KnowledgeHarness,
) -> None:
    first = harness.create_point(code="A", name="A")
    second = harness.create_point(code="B", name="B", parentId=first["id"])

    self_parent = harness.client.patch(
        f"/api/v1/knowledge-points/{first['id']}",
        json={"expectedRevision": 0, "parentId": first["id"]},
    )
    assert self_parent.status_code == 422
    self_body = self_parent.json()
    assert self_body["code"] == "KNOWLEDGE_PARENT_INVALID"
    # F1：自指父必须可按契约定位字段
    assert self_body["details"]["issues"][0]["field"] == "parentId"
    assert self_body["details"]["issues"][0]["code"] == "KNOWLEDGE_PARENT_INVALID"

    # parentCode 指向自身编码同样是自指（field 按实际入参给 parentCode）
    self_by_code = harness.client.patch(
        f"/api/v1/knowledge-points/{first['id']}",
        json={"expectedRevision": 0, "parentCode": "A"},
    )
    assert self_by_code.status_code == 422
    assert self_by_code.json()["code"] == "KNOWLEDGE_PARENT_INVALID"
    assert self_by_code.json()["details"]["issues"][0]["field"] == "parentCode"

    cycle = harness.client.patch(
        f"/api/v1/knowledge-points/{first['id']}",
        json={"expectedRevision": 0, "parentId": second["id"]},
    )
    assert cycle.status_code == 422
    cycle_body = cycle.json()
    assert cycle_body["code"] == "KNOWLEDGE_CYCLE"
    # F1：成环父必须可按契约定位字段
    assert cycle_body["details"]["issues"][0]["field"] == "parentId"
    assert cycle_body["details"]["issues"][0]["code"] == "KNOWLEDGE_CYCLE"

    # DB 不乱：A 仍无父节点、B 仍挂在 A 下
    assert harness.point(first["id"])["parentId"] is None
    assert harness.point(second["id"])["parentId"] == first["id"]


def test_parent_trigger_backstop_reports_same_details_shape(
    harness: KnowledgeHarness,
) -> None:
    """绕过服务层预检直接写仓储：DB 触发器兜底的翻译结果同样带 details.issues。"""
    first = harness.create_point(code="A", name="A")
    second = harness.create_point(code="B", name="B", parentId=first["id"])

    with pytest.raises(AppError) as cycle:
        with harness.catalog.write_transaction() as conn:
            harness.service.points.update_point(
                conn, first["id"], expected_revision=0, parent_id=second["id"]
            )
    assert cycle.value.code == "KNOWLEDGE_CYCLE"
    assert cycle.value.details["issues"][0]["field"] == "parentId"

    with pytest.raises(AppError) as self_parent:
        with harness.catalog.write_transaction() as conn:
            harness.service.points.update_point(
                conn, first["id"], expected_revision=0, parent_id=first["id"]
            )
    assert self_parent.value.code == "KNOWLEDGE_PARENT_INVALID"
    assert self_parent.value.details["issues"][0]["field"] == "parentId"

    # 回滚干净：A 仍无父节点
    assert harness.point(first["id"])["parentId"] is None


def test_archived_point_rejects_new_references_and_restore_allows(
    harness: KnowledgeHarness,
) -> None:
    parent = harness.create_point(code="P", name="父")
    archived = harness.client.post(
        f"/api/v1/knowledge-points/{parent['id']}/archive",
        json={"expectedRevision": 0},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"
    assert archived.json()["revision"] == 1

    child = harness.client.post(
        "/api/v1/knowledge-points",
        json={"subjectId": "math", "code": "C", "name": "子", "parentId": parent["id"]},
    )
    assert child.status_code == 409
    assert child.json()["code"] == "KNOWLEDGE_ARCHIVED"

    link = harness.client.post(
        f"/api/v1/knowledge-points/{parent['id']}/textbook-links",
        json={
            "expectedRevision": 1,
            "documentRevisionId": "rev-1",
            "charStart": 0,
            "charEnd": 10,
        },
    )
    assert link.status_code == 409
    assert link.json()["code"] == "KNOWLEDGE_ARCHIVED"

    restored = harness.client.post(
        f"/api/v1/knowledge-points/{parent['id']}/restore", json={"expectedRevision": 1}
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"
    ok = harness.client.post(
        "/api/v1/knowledge-points",
        json={"subjectId": "math", "code": "C", "name": "子", "parentId": parent["id"]},
    )
    assert ok.status_code == 201, ok.text


# --------------------------------------------------------------------------- 别名


def test_alias_normalization_dedupe_and_search(harness: KnowledgeHarness) -> None:
    point = harness.create_point(
        code="M7-A", name="有理数", aliases=[" ABC ", "abc", "一次  函数"]
    )
    # NFKC + casefold 后 " ABC " 与 "abc" 同值 → 只留首见；展示保留教师原文
    assert point["aliases"] == ["ABC", "一次  函数"]

    found = harness.client.get("/api/v1/knowledge-points", params={"q": "abc"}).json()
    assert [item["id"] for item in found["items"]] == [point["id"]]
    # 规范化检索：查询的多余空白折叠后仍命中
    spaced = harness.client.get(
        "/api/v1/knowledge-points", params={"q": "一次 函数"}
    ).json()
    assert [item["id"] for item in spaced["items"]] == [point["id"]]
    full_width = harness.create_point(code="M7-B", name="数轴", aliases=["ＡＢＣ"])
    assert full_width["aliases"] == ["ＡＢＣ"]
    matched = harness.client.get("/api/v1/knowledge-points", params={"q": "abc"}).json()
    assert {item["id"] for item in matched["items"]} == {point["id"], full_width["id"]}


def test_cross_point_alias_only_warns(harness: KnowledgeHarness, caplog) -> None:
    first = harness.create_point(code="M7-A", name="有理数", aliases=["一次函数"])
    with caplog.at_level(logging.WARNING, logger="zhiqikeyuan.knowledge"):
        second = harness.create_point(code="M7-B", name="一次函数图像", aliases=["一次函数"])
    assert second["aliases"] == ["一次函数"]
    assert first["id"] != second["id"]
    assert harness.count("knowledge_points") == 2
    assert any("别名歧义" in record.message for record in caplog.records)


# --------------------------------------------------------------------------- 教材依据


def test_textbook_links_with_fake_evidence(harness: KnowledgeHarness) -> None:
    point = harness.create_point(code="M7-A", name="有理数加法")
    created = harness.client.post(
        f"/api/v1/knowledge-points/{point['id']}/textbook-links",
        json={
            "expectedRevision": 0,
            "documentRevisionId": "rev-1",
            "charStart": 0,
            "charEnd": 12,
            "source": "human",
        },
    )
    assert created.status_code == 201, created.text
    link = created.json()
    assert link["titleSnapshot"] == FAKE_TITLE
    assert link["knowledgePointId"] == point["id"]
    assert link["knowledgeRevisionId"] == point["revisionId"]
    assert link["charStart"] == 0 and link["charEnd"] == 12
    assert len(link["locatorHash"]) == 64
    assert link["source"] == "human"

    duplicate = harness.client.post(
        f"/api/v1/knowledge-points/{point['id']}/textbook-links",
        json={
            "expectedRevision": 0,
            "documentRevisionId": "rev-1",
            "charStart": 0,
            "charEnd": 12,
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "KNOWLEDGE_LINK_DUPLICATE"

    unavailable = harness.client.post(
        f"/api/v1/knowledge-points/{point['id']}/textbook-links",
        json={
            "expectedRevision": 0,
            "documentRevisionId": "missing-revision",
            "charStart": 0,
            "charEnd": 12,
        },
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["code"] == "TEXTBOOK_EVIDENCE_UNAVAILABLE"
    assert unavailable.json()["retryable"] is True

    ranged = harness.client.post(
        f"/api/v1/knowledge-points/{point['id']}/textbook-links",
        json={
            "expectedRevision": 0,
            "documentRevisionId": "rev-1",
            "charStart": 40,
            "charEnd": 12,
        },
    )
    assert ranged.status_code == 422  # 契约层拦截 charEnd <= charStart

    listing = harness.client.get(f"/api/v1/knowledge-points/{point['id']}/textbook-links")
    assert listing.status_code == 200
    assert len(listing.json()["items"]) == 1

    stale_delete = harness.client.delete(
        f"/api/v1/knowledge-points/{point['id']}/textbook-links/{link['linkId']}",
        params={"expectedRevision": 5},
    )
    assert stale_delete.status_code == 409
    assert stale_delete.json()["code"] == "REVISION_CONFLICT"

    other = harness.create_point(code="M7-B", name="别的知识点")
    wrong_point = harness.client.delete(
        f"/api/v1/knowledge-points/{other['id']}/textbook-links/{link['linkId']}",
        params={"expectedRevision": 0},
    )
    assert wrong_point.status_code == 404
    assert wrong_point.json()["code"] == "KNOWLEDGE_LINK_NOT_FOUND"

    deleted = harness.client.delete(
        f"/api/v1/knowledge-points/{point['id']}/textbook-links/{link['linkId']}",
        params={"expectedRevision": 0},
    )
    assert deleted.status_code == 204
    assert harness.client.get(
        f"/api/v1/knowledge-points/{point['id']}/textbook-links"
    ).json()["items"] == []


def test_textbook_links_with_real_textbook_catalog(tmp_path: Path) -> None:
    harness = KnowledgeHarness(tmp_path, evidence_factory=make_real_evidence)
    try:
        reader = harness.evidence
        revision_id = reader.revision_id
        point = harness.create_point(code="M7-A", name="有理数加法")

        created = harness.client.post(
            f"/api/v1/knowledge-points/{point['id']}/textbook-links",
            json={
                "expectedRevision": 0,
                "documentRevisionId": revision_id,
                "charStart": 6,
                "charEnd": 20,
            },
        )
        assert created.status_code == 201, created.text
        link = created.json()
        assert link["titleSnapshot"] == FAKE_TITLE
        assert reader is harness.service.evidence
        assert len(link["locatorHash"]) == 64

        out_of_range = harness.client.post(
            f"/api/v1/knowledge-points/{point['id']}/textbook-links",
            json={
                "expectedRevision": 0,
                "documentRevisionId": revision_id,
                "charStart": 0,
                "charEnd": len(FAKE_TEXT) + 1,
            },
        )
        assert out_of_range.status_code == 422
        assert out_of_range.json()["code"] == "TEXTBOOK_EVIDENCE_INVALID"

        unknown_revision = harness.client.post(
            f"/api/v1/knowledge-points/{point['id']}/textbook-links",
            json={
                "expectedRevision": 0,
                "documentRevisionId": "nope",
                "charStart": 0,
                "charEnd": 5,
            },
        )
        assert unknown_revision.status_code == 503
        assert unknown_revision.json()["code"] == "TEXTBOOK_EVIDENCE_UNAVAILABLE"

        # 真实 reader：冻结标题 + 文本区间（直接读服务层返回值）
        evidence = harness.service.evidence.read(
            document_revision_id=revision_id, char_start=6, char_end=20
        )
        assert evidence.title == FAKE_TITLE
        assert evidence.text == FAKE_TEXT[6:20]
        assert evidence.sha256 == hashlib.sha256(evidence.text.encode("utf-8")).hexdigest()
        assert evidence.locator["charStart"] == 6 and evidence.locator["charEnd"] == 20
    finally:
        harness.close()


def test_unassembled_service_returns_503(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path / "data"), bootstrap_textbooks=False)
    ensure_knowledge_router(app)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        response = client.get("/api/v1/knowledge-points")
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert body["retryable"] is True


# --------------------------------------------------------------------------- 范围/年级（任务②）


def _install_fake_scope(harness: KnowledgeHarness, *, revision_grades: dict[str, tuple[str, ...]]) -> None:
    """给测试台挂一个范围替身：任意范围都解析成给定修订集合。"""
    from app.services.knowledge.textbook_scope import TextbookScopeSnapshot

    class FakeScopeReader:
        def __init__(self) -> None:
            self.snapshot = TextbookScopeSnapshot(
                document_ids=("doc-1",),
                revision_ids=tuple(revision_grades.keys()),
                grade_ids_by_document={doc: grades for doc, grades in [("doc-1", grades) for grades in revision_grades.values()]},
            )

        def resolve_taught_scope(self) -> TextbookScopeSnapshot:
            return self.snapshot

        def grade_ids_of_revisions(self, revision_ids):
            return {rid: revision_grades.get(rid, ()) for rid in revision_ids}

    harness.service.scope_reader = FakeScopeReader()


class _Selection:
    """最小任教设置形状（schema 校验在真实 reader 里，替身直接给对象）。"""

    gradeId = "g7"
    subjectId = "math"
    editionId = "rj"
    documentIds = ["doc-1"]


def test_list_without_scope_unchanged(harness: KnowledgeHarness) -> None:
    """不带 scope 的旧调用语义不变：scope_reader 缺省也不影响。"""
    point = harness.create_point(code="M7-01")
    listing = harness.client.get("/api/v1/knowledge-points").json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == point["id"]


def test_list_scope_taught_requires_reader(harness: KnowledgeHarness) -> None:
    """scope=taught 而端口缺失 → 503（不静默回退全部）。"""
    harness.create_point(code="M7-01")
    response = harness.client.get("/api/v1/knowledge-points", params={"scope": "taught"})
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"


def test_list_scope_invalid_value_is_422(harness: KnowledgeHarness) -> None:
    response = harness.client.get("/api/v1/knowledge-points", params={"scope": "everything"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "INVALID_REQUEST"
    assert "scope" in body["details"]["fields"]


def test_list_scope_taught_in_and_out_of_range(harness: KnowledgeHarness) -> None:
    """scope=taught：有任教范围教材依据的命中；没有的排除；total 与过滤一致。"""
    inside = harness.create_point(code="M7-IN", name="范围内")
    outside = harness.create_point(code="M7-OUT", name="范围外")
    harness.client.post(
        f"/api/v1/knowledge-points/{inside['id']}/textbook-links",
        json={"expectedRevision": 0, "documentRevisionId": "rev-g7", "charStart": 0, "charEnd": 5},
    )
    harness.client.post(
        f"/api/v1/knowledge-points/{outside['id']}/textbook-links",
        json={"expectedRevision": 0, "documentRevisionId": "rev-other", "charStart": 0, "charEnd": 5},
    )
    _install_fake_scope(harness, revision_grades={"rev-g7": ("g7",)})

    listing = harness.client.get(
        "/api/v1/knowledge-points", params={"scope": "taught"}
    ).json()
    assert listing["total"] == 1
    assert [item["id"] for item in listing["items"]] == [inside["id"]]

    # scope=subject 是显式"该学科全部"，不做任教范围收敛
    subject = harness.client.get(
        "/api/v1/knowledge-points", params={"scope": "subject"}
    ).json()
    assert subject["total"] == 2


def test_list_scope_taught_empty_scope_returns_empty_page(harness: KnowledgeHarness) -> None:
    """任教范围里没有教材（修订集合为空）→ 空页，不回退全部。"""
    harness.create_point(code="M7-01")
    from app.services.knowledge.textbook_scope import TextbookScopeSnapshot

    class EmptyScope:
        def resolve_taught_scope(self):
            return TextbookScopeSnapshot(
                document_ids=(), revision_ids=(), grade_ids_by_document={}
            )

        def grade_ids_of_revisions(self, revision_ids):
            return {}

    harness.service.scope_reader = EmptyScope()
    listing = harness.client.get("/api/v1/knowledge-points", params={"scope": "taught"}).json()
    assert listing["total"] == 0
    assert listing["items"] == []


def test_list_grade_id_filter_and_grade_ids_view(harness: KnowledgeHarness) -> None:
    """gradeId 过滤落在教材依据文档的年级；视图 gradeIds 为依据修订的年级并集。"""
    g7 = harness.create_point(code="M7-G7", name="七年级点")
    g8 = harness.create_point(code="M7-G8", name="八年级点")
    plain = harness.create_point(code="M7-N", name="无依据点")
    harness.client.post(
        f"/api/v1/knowledge-points/{g7['id']}/textbook-links",
        json={"expectedRevision": 0, "documentRevisionId": "rev-g7", "charStart": 0, "charEnd": 5},
    )
    harness.client.post(
        f"/api/v1/knowledge-points/{g8['id']}/textbook-links",
        json={"expectedRevision": 0, "documentRevisionId": "rev-g8", "charStart": 0, "charEnd": 5},
    )
    _install_fake_scope(harness, revision_grades={"rev-g7": ("g7", "g9"), "rev-g8": ("g8",)})

    filtered = harness.client.get(
        "/api/v1/knowledge-points", params={"gradeId": "g7"}
    ).json()
    assert filtered["total"] == 1
    assert [item["id"] for item in filtered["items"]] == [g7["id"]]
    # 视图补 gradeIds：依据修订的年级去重并集；无依据点为空列表
    listing = harness.client.get("/api/v1/knowledge-points").json()
    grades_by_id = {item["id"]: item["gradeIds"] for item in listing["items"]}
    assert grades_by_id[g7["id"]] == ["g7", "g9"]
    assert grades_by_id[g8["id"]] == ["g8"]
    assert grades_by_id[plain["id"]] == []


def test_list_scope_taught_unready_scope_is_409(harness: KnowledgeHarness) -> None:
    """任教范围未就绪（真实 reader 抛 409）→ 原样 409，不静默回退。"""
    harness.create_point(code="M7-01")
    from app.services.knowledge.textbook_scope import CatalogTextbookScopeReader

    # 真实 reader + 空教材目录：没有任教设置 → 409
    harness.service.scope_reader = CatalogTextbookScopeReader(harness.app.state.catalog)
    response = harness.client.get("/api/v1/knowledge-points", params={"scope": "taught"})
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "KNOWLEDGE_SCOPE_UNAVAILABLE"
    assert "任教范围" in body["message"]
