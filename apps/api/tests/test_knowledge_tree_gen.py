"""教材目录 → 知识点树生成（C4-1）：规划纯函数 + 端点集成 + 幂等回归。

- plan_tree：文档根节点 + 章/节链、同路径幂等 code、MAX_NODES 上限、噪声/习题段透明；
- 端点：真实教材目录临时库（ExtractionHarness 建书与封存正文）→ 目录取正文 Markdown 标题
  （R11 口径，习题标题不建节点）→ 首次 created>0、树结构正确；再次生成 created=0
  skipped=全部（幂等）；
- 未装配 catalog / 教材原文读取器 → 503。
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

    def test_exercise_segment_is_transparent(self) -> None:
        """习题/练习类标题段不建节点，且对其透明（R11 修正）。"""
        books = [TextbookInput(title="数学必修一", document_id="d", chapter_paths=(
            ("第一章 集合",),
            ("第一章 集合", "1.1 集合的概念"),
            ("第一章 集合", "1.1 集合的概念", "习题1.1"),
            ("第一章 集合", "1.2 集合间的基本关系"),
            ("第一章 集合", "习题1.2"),
            ("第一章 集合", "复习参考题1"),
        ))]
        plan = plan_tree("math", books)
        assert {n.name for n in plan.nodes} == {
            "数学必修一", "第一章 集合", "1.1 集合的概念", "1.2 集合间的基本关系",
        }


@pytest.mark.asyncio
async def test_endpoint_generates_and_is_idempotent(tmp_path: Path) -> None:
    harness = ExtractionHarness(tmp_path)
    try:
        # 两本书：目录取**封存正文的 Markdown 标题**（R11 口径）；习题标题不建节点
        book_text = (
            "# 第一章 有理数\n\n"
            "有理数的概念与运算。\n\n"
            "## 1.1 正数与负数\n\n"
            "大于零的数叫正数。\n\n"
            "### 习题1.1\n\n"
            "1. 判断下列各数是正数还是负数。\n\n"
            "## 1.2 数轴\n\n"
            "规定了原点、正方向与单位长度的直线叫数轴。\n\n"
            "## 复习参考题1\n\n"
            "1. 在数轴上表示下列各数。\n\n"
            "# 第二章 整式\n\n"
            "整式的加减运算。\n"
        )
        harness.add_document(title="数学教材甲", text=book_text)
        harness.add_document(title="数学教材乙", text="# 第三章 几何初步\n\n图形的初步认识。\n")

        body = {"subjectId": SUBJECT}
        r1 = harness.client.post("/api/v1/knowledge-points/tree-from-textbook", json=body)
        assert r1.status_code == 200, r1.text
        first_result = r1.json()
        # 2 根 + 3 章 + 2 节 = 7（习题1.1 / 复习参考题1 不是知识点）
        assert first_result["created"] == 7, first_result
        assert first_result["skipped"] == 0
        assert first_result["books"] == 2

        r2 = harness.client.post("/api/v1/knowledge-points/tree-from-textbook", json=body)
        assert r2.status_code == 200
        assert r2.json()["created"] == 0 and r2.json()["skipped"] == 7

        # 树结构可读：两个文档节点；章下有节；习题标题不在树里
        listed = harness.client.get(f"/api/v1/knowledge-points?subjectId={SUBJECT}&limit=200").json()
        names = [item["name"] for item in listed["items"]]
        assert "数学教材甲" in names and "第一章 有理数" in names and "1.1 正数与负数" in names
        assert not any("习题" in name or "复习参考题" in name for name in names), names
    finally:
        harness.close()


@pytest.mark.asyncio
async def test_endpoint_without_evidence_reader_is_unavailable(tmp_path: Path) -> None:
    """教材原文读取器缺失：503，不按"没有标题"给出空树（不假成功）。"""
    harness = ExtractionHarness(tmp_path)
    try:
        harness.add_document(title="数学教材甲")
        harness.app.state.textbook_evidence = None
        resp = harness.client.post("/api/v1/knowledge-points/tree-from-textbook", json={"subjectId": SUBJECT})
        assert resp.status_code == 503, resp.text
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
