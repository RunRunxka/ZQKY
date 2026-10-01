"""V00-G0 原卷/题库/施测探针支撑（自建装配：真 app + 真库 + 受控模型替身）。

- 走 ``create_app`` 真实装配路径，然后用**受控替身**替换域服务（模型解析注入）；
- 只使用临时数据目录（``_v00.PROBE_TMP``），不触网、不读写正式数据；
- DOCX 样本由 ``tests.papers_support`` 的构造器生成（仅作 fixture），断言与故障注入
  全部由本探针自建。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from _v00 import (  # noqa: F401  (重新导出给各探针)
    LOCAL_PROFILE,
    PROBE_TMP,
    FakeResolver,
    make_handle,
    make_settings,
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import _build_executor_registry, create_app  # noqa: E402
from app.repositories.knowledge.points import (  # noqa: E402
    KnowledgePointRepository,
    SubjectRepository,
)
from app.services.assets.store import AssetStore  # noqa: E402
from app.services.papers.service import build_paper_service  # noqa: E402

DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class PapersProbe:
    """真 app + 真 TeachingCatalog/KnowledgeCatalog/AssetStore + 受控模型替身。"""

    def __init__(self, data_dir: Path, *, resolver: Any | None = None) -> None:
        self.settings = make_settings(data_dir)
        self.app = create_app(self.settings)
        self.catalog = self.app.state.teaching
        self.assets: AssetStore = self.app.state.asset_store
        self.file_assets = self.app.state.file_assets
        self.knowledge = self.app.state.knowledge
        self.points = KnowledgePointRepository()
        self.subjects = SubjectRepository()
        self.resolver = resolver if resolver is not None else FakeResolver(make_handle())
        self.service = build_paper_service(
            self.catalog,
            asset_store=self.assets,
            file_assets=self.file_assets,
            knowledge_catalog=self.knowledge,
            coordinator=self.app.state.publication_coordinator,
            model_resolver=self.resolver,
            job_engine=self.app.state.job_engine,
        )
        self.app.state.paper_service = self.service
        _build_executor_registry(self.app)
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8001")
        self.client.__enter__()

    # ---------------------------------------------------------------- 便捷方法

    def add_point(self, *, code: str = "kp-1", name: str = "一次函数", subject_id: str = "math"):
        with self.knowledge.write_transaction() as conn:
            self.subjects.ensure_subject(conn, subject_id=subject_id, name=subject_id)
            return self.points.create_point(
                conn, subject_id=subject_id, code=code, name=name
            )

    def archive_point(self, point_id: str) -> None:
        with self.knowledge.write_transaction() as conn:
            point = self.points.require_point(conn, point_id)
            self.points.set_status(conn, point_id, expected_revision=point.revision, archived=True)

    def import_paper(
        self, content: bytes, *, subject_id: str = "math", title: str | None = None, name: str = "paper.docx"
    ):
        data: dict[str, str] = {"subjectId": subject_id}
        if title is not None:
            data["title"] = title
        return self.client.post(
            "/api/v1/paper-imports",
            files={"file": (name, content, DOCX_MEDIA)},
            data=data,
        )

    def raw_rows(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        import sqlite3

        connection = sqlite3.connect(str(self.catalog.db_path))
        connection.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in connection.execute(sql, list(params)).fetchall()]
        finally:
            connection.close()

    def close(self) -> None:
        self.client.__exit__(None, None, None)


def items_payload_from_view(items: list[dict[str, Any]], **overrides: Any) -> list[dict[str, Any]]:
    """由修订内容视图的 items 构造整表替换 payload（保持内容，可覆盖 content/knowledge）。"""
    overrides = dict(overrides)
    content_override = overrides.pop("content", {})
    payload: list[dict[str, Any]] = []
    for item in items:
        entry: dict[str, Any] = {
            "itemId": item["itemId"],
            "questionNo": item["questionNo"],
            "ordinal": item["ordinal"],
            "isScored": item["isScored"],
            "content": content_override.get(item["questionNo"], item.get("content") or {}),
            "sourceLocator": item.get("sourceLocator") or {},
            "knowledge": [
                {"knowledgePointId": link["knowledgePointId"], "role": link.get("role", "primary")}
                for link in item.get("knowledge") or []
            ],
        }
        if item.get("parentItemId"):
            entry["parentItemId"] = item["parentItemId"]
        if item.get("maxScore") is not None:
            entry["maxScore"] = item["maxScore"]
        payload.append(entry)
    return payload


def blocks_payload_from_view(blocks: list[dict[str, Any]], **overrides: Any) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for block in blocks:
        disposition = overrides.get("disposition", {}).get(
            block["blockId"], block["disposition"]
        )
        entry: dict[str, Any] = {
            "blockId": block["blockId"],
            "disposition": disposition,
        }
        if disposition == "item":
            item_id = overrides.get("item_id", {}).get(block["blockId"], block.get("itemId"))
            if item_id:
                entry["itemId"] = item_id
        if disposition == "excluded" and block.get("excludeReason"):
            entry["excludeReason"] = block["excludeReason"]
        payload.append(entry)
    return payload


def issues_payload_from_view(
    issues: list[dict[str, Any]],
    *,
    blocks: list[dict[str, Any]] | None = None,
    resolution_kind: str = "supplement_text",
    text: str = "补录：图中阴影部分由半圆与三角形组成。",
    asset_id: str | None = None,
    reason: str = "与本卷无关的版式噪声（非内容损失）。",
    keep_open: set[str] | None = None,
) -> list[dict[str, Any]]:
    """把修订问题视图转成处置请求（默认逐条结构化补录）。"""
    keep_open = keep_open or set()
    block_by_id = {block["blockId"]: block for block in (blocks or [])}
    payload: list[dict[str, Any]] = []
    for issue in issues:
        if issue["issueId"] in keep_open:
            continue
        if issue["status"] != "open":
            continue
        target = issue.get("blockId")
        if target is None and block_by_id:
            target = next(iter(block_by_id))
        resolution: dict[str, Any] = {"kind": resolution_kind}
        if resolution_kind == "supplement_text":
            resolution.update(targetBlockId=target, text=text)
        elif resolution_kind == "supplement_asset":
            resolution.update(targetBlockId=target, assetId=asset_id)
        else:
            resolution.update(reason=reason)
        payload.append(
            {
                "issueId": issue["issueId"],
                "status": "excluded" if resolution_kind == "exclude" else "resolved",
                "resolution": resolution,
            }
        )
    return payload


__all__ = [
    "DOCX_MEDIA",
    "LOCAL_PROFILE",
    "PROBE_TMP",
    "PapersProbe",
    "blocks_payload_from_view",
    "issues_payload_from_view",
    "items_payload_from_view",
    "make_handle",
]
