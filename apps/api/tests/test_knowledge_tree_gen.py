"""教材目录 → 知识点树生成（C4-1）：规划纯函数 + 端点集成 + 幂等回归。

- plan_tree：文档根节点 + 章/节链、同路径幂等 code、MAX_NODES 上限；
- 端点：真实教材目录临时库（ExtractionHarness 建书与带 chapter_path 的 chunks）→
  首次生成 created>0、树结构正确；再次生成 created=0 skipped=全部（幂等）；
- 未装配 catalog → 503。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.services.knowledge.tree_gen import MAX_NODES, TextbookInput, plan_tree
from tests.test_knowledge_extraction import ExtractionHarness, SUBJECT


class TestPlanTree:
    def test_roots_and_paths(self) -> None:
        books = [
            TextbookInput(title="数学必修一", document_id="d1", chapter_paths=(
                ("第一章 有理数", "1.1 正数与负数"),
                ("第一章 有理数", "1.2 数轴"),
                ("第二章 整式",),
            )),
            TextbookInput(title="数学必修二", document_id="d2", chapter_paths=(
                ("第六章 平面几何",),
            )),
        ]
        plan = plan_tree("math", books)
        by_code = {n.code: n for n in plan.nodes}
        # 两个文档根 + 3 章 + 2 节 = 7
        assert len(plan.nodes) == 7
        roots = [n for n in plan.nodes if n.parent_code is None]
        assert {r.name for r in roots} == {"数学必修一", "数学必修二"}
        ch1 = next(n for n in plan.nodes if n.name == "第一章 有理数")
        assert ch1.parent_code == by_code[ch1.code].parent_code
        assert ch1.parent_code is not None and by_code[ch1.parent_code].name == "数学必修一"
        sec = next(n for n in plan.nodes if n.name == "1.2 数轴")
        assert by_code[sec.parent_code].name == "第一章 有理数"

    def test_same_path_is_idempotent_in_plan(self) -> None:
        books = [TextbookInput(title="书", document_id="d", chapter_paths=(
            ("第一章",), ("第一章",), ("第一章", "1.1"),
        ))]
        plan = plan_tree("math", books)
        assert len(plan.nodes) == 3  # 根 + 章 + 节（重复路径不重复建）

    def test_max_nodes_cap(self) -> None:
        books = [TextbookInput(title="书", document_id="d",
                               chapter_paths=tuple((f"第{i}章",) for i in range(MAX_NODES + 50)))]
        plan = plan_tree("math", books)
        assert len(plan.nodes) == MAX_NODES

    def test_watermark_segment_is_transparent(self) -> None:
        """版式噪声段（广告行）不建节点，且子级直接挂到其父级（R9 修正）。"""
        books = [TextbookInput(title="数学必修一", document_id="d", chapter_paths=(
            ("本教材最新教材配套资源 微信扫码 免费下载", "第一章 集合"),
            ("第一章 集合", "1.1 集合的概念"),
        ))]
        plan = plan_tree("math", books)
        names = {n.name for n in plan.nodes}
        assert not any("微信扫码" in name for name in names)
        by_code = {n.code: n for n in plan.nodes}
        chapter = next(n for n in plan.nodes if n.name == "第一章 集合")
        # 噪声段透明：章直接挂在文档根下，节挂在章下
        assert by_code[chapter.parent_code].name == "数学必修一"
        section = next(n for n in plan.nodes if n.name == "1.1 集合的概念")
        assert by_code[section.parent_code].name == "第一章 集合"
        assert len(plan.nodes) == 3  # 根 + 章 + 节

    def test_symbol_only_segment_is_transparent(self) -> None:
        """纯符号装饰标题（如「● ●」）不建节点，子级直挂父级（R9 修正）。"""
        books = [TextbookInput(title="数学必修一", document_id="d", chapter_paths=(
            ("● ●", "第一章 集合"),
        ))]
        plan = plan_tree("math", books)
        assert {n.name for n in plan.nodes} == {"数学必修一", "第一章 集合"}
        chapter = next(n for n in plan.nodes if n.name == "第一章 集合")
        assert next(n for n in plan.nodes if n.code == chapter.parent_code).name == "数学必修一"


@pytest.mark.asyncio
async def test_endpoint_generates_and_is_idempotent(tmp_path: Path) -> None:
    harness = ExtractionHarness(tmp_path)
    try:
        # 两本书：第一本两章各一节，第二本一章（chunks 自建，chapter_path 不同）
        first = harness.add_document(title="数学教材甲")
        second = harness.add_document(title="数学教材乙")
        import hashlib
        from app.repositories.textbook_catalog.records import ChunkInput

        def make_chunks(revision_id: str, paths: list[list[str]]) -> None:
            text = "x" * 40
            harness.catalog.create_chunk_set(
                revision_id, policy_fingerprint="policy-tree-1", manifest_sha256="m" * 64,
                chunks=[ChunkInput(ordinal=i, char_start=0, char_end=40, region="body",
                                   chapter_path=p, text_sha256=hashlib.sha256(text.encode()).hexdigest())
                        for i, p in enumerate(paths)],
            )
        make_chunks(first["revision"].revision_id, [["第一章 有理数"], ["第一章 有理数", "1.1 正数与负数"], ["第二章 整式"]])
        make_chunks(second["revision"].revision_id, [["第三章 几何初步"]])

        body = {"subjectId": SUBJECT}
        r1 = harness.client.post("/api/v1/knowledge-points/tree-from-textbook", json=body)
        assert r1.status_code == 200, r1.text
        first_result = r1.json()
        assert first_result["created"] == 7  # 2 根 + 3 章 + 2 节
        assert first_result["skipped"] == 0

        r2 = harness.client.post("/api/v1/knowledge-points/tree-from-textbook", json=body)
        assert r2.status_code == 200
        assert r2.json()["created"] == 0 and r2.json()["skipped"] == 7

        # 树结构可读：roots 有两个文档节点，第一章有子节点
        listed = harness.client.get(f"/api/v1/knowledge-points?subjectId={SUBJECT}&limit=200").json()
        names = [item["name"] for item in listed["items"]]
        assert "数学教材甲" in names and "第一章 有理数" in names and "1.1 正数与负数" in names
    finally:
        harness.close()


def test_endpoint_without_catalog(tmp_path: Path) -> None:
    from app.core.config import Settings
    from app.main import create_app
    from fastapi.testclient import TestClient

    settings = Settings(host="127.0.0.1", port=8001, allowed_origins=frozenset({"http://127.0.0.1:5173"}),
                        env="test", data_dir=tmp_path)
    app = create_app(settings, bootstrap_textbooks=False)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        resp = client.post("/api/v1/knowledge-points/tree-from-textbook", json={"subjectId": "math"})
        assert resp.status_code == 503
