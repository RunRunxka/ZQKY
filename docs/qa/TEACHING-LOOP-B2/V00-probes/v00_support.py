"""V00-B2 探针公共支撑（独立实现；不使用实现方 tests/ 的任何 helper）。

- ``build_sample_docx``：自建 DOCX（本探针独立编写，不是 papers_support 的复制）：
  前导共同材料 2 段 / 两级小题 16.+(16(1),16(2)) / 行内 OMML / 独立 OMML / 真实 PNG 图片 /
  横向+纵向合并表格 / 独立计分题 17. / 无文本段落 / 未知对象 w:object；
- ``Harness``：真 ``create_app``（真装配：四库、受管资产、发布协调器、任务引擎），
  经 ``TestClient`` 走 HTTP；模型一律受控替身（_FakeProvider），不联网；
- ``make_point``：经真 ``POST /api/v1/knowledge-points`` 建知识点；
- 只写临时目录；不读正式 .local-data、不读 .env。
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import struct
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

EMU_PER_PX = 9525

MATERIAL_HEADING = "阅读材料：函数与导数"
MATERIAL_BODY = "材料正文：设函数 f(x)=x^2+1，讨论其单调性。"
Q16 = "16.（10 分）已知函数 f(x)=x^2+1。"
Q16_1 = "16(1)（4 分）求 f(1) 的值。"
Q16_2 = "16(2)（6 分）求 f'(x) 的表达式。"
Q17 = "17.（5 分）写出一个反例。"
UNKNOWN_PARAGRAPH = "18. 该段落含未支持对象。"
INLINE_OMML_TEXT = "由公式 "
STANDALONE_OMML_TEXT = "（公式见下）"

INLINE_OMML = (
    f'<m:oMath xmlns:m="{M}" xmlns:w="{W}">'
    '<m:r><m:t>x</m:t></m:r><m:r><m:t>+</m:t></m:r><m:r><m:t>1</m:t></m:r>'
    "</m:oMath>"
)
STANDALONE_OMML = (
    f'<m:oMath xmlns:m="{M}" xmlns:w="{W}">'
    '<m:r><m:t>f</m:t></m:r><m:r><m:t>(</m:t></m:r><m:r><m:t>x</m:t></m:r>'
    '<m:r><m:t>)</m:t></m:r><m:r><m:t>=</m:t></m:r><m:r><m:t>2x</m:t></m:r>'
    "</m:oMath>"
)


def make_png(width: int = 4, height: int = 3, rgb: tuple[int, int, int] = (200, 30, 40)) -> bytes:
    """生成真实可解码的 PNG（自写；不依赖 PIL）。"""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _append_xml(paragraph, xml: str) -> None:
    from lxml import etree

    paragraph._p.append(etree.fromstring(xml))


def build_sample_docx(path: Path, *, png: bytes | None = None) -> dict[str, Any]:
    """生成样本 DOCX 并返回期望值字典（块顺序/表格形状/图片散列等）。"""
    from docx import Document
    from docx.shared import Emu

    png = png if png is not None else make_png()
    doc = Document()
    doc.add_paragraph(MATERIAL_HEADING)
    doc.add_paragraph(MATERIAL_BODY)
    doc.add_paragraph(Q16)
    doc.add_paragraph(Q16_1)
    doc.add_paragraph(Q16_2)

    # 行内公式段落（文本 + OMML 混排）
    inline_p = doc.add_paragraph()
    inline_p.add_run(INLINE_OMML_TEXT)
    _append_xml(inline_p, INLINE_OMML)

    # 图片段落
    doc.add_picture(io.BytesIO(png), width=Emu(120 * EMU_PER_PX), height=Emu(60 * EMU_PER_PX))

    # 合并表格：3 列 2 行；行 0 的前两格横向合并；列 2 纵向合并
    table = doc.add_table(rows=2, cols=3)
    table.cell(0, 0).text = "得分表"
    table.cell(0, 2).text = "题号"
    table.cell(1, 0).text = "16(1)"
    table.cell(1, 1).text = "16(2)"
    table.cell(0, 0).merge(table.cell(0, 1))
    table.cell(0, 2).merge(table.cell(1, 2))

    doc.add_paragraph(Q17)

    standalone_p = doc.add_paragraph()
    standalone_p.add_run(STANDALONE_OMML_TEXT)
    _append_xml(standalone_p, STANDALONE_OMML)

    # 空段落（无可见内容 → 不产生块、不产生问题）
    doc.add_paragraph("")

    # 纯未知对象段落（无可见文本 → 不产生块；问题只有 locator，没有 block_id）
    bare_unknown = doc.add_paragraph()
    _append_xml(bare_unknown, f'<w:object xmlns:w="{W}"/>')

    # 未知对象 + 题号文本（问题挂在段落块上）
    unknown_p = doc.add_paragraph()
    unknown_p.add_run(UNKNOWN_PARAGRAPH)
    _append_xml(unknown_p, f'<w:object xmlns:w="{W}"/>')

    doc.save(str(path))
    return {
        "png": png,
        "png_sha256": hashlib.sha256(png).hexdigest(),
        "inline_omml": INLINE_OMML,
        "standalone_omml": STANDALONE_OMML,
        "path": path,
    }


def multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    boundary = "----v00b2boundary7f3a"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            (
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n"
                f"{value}\r\n"
            ).encode("utf-8")
        )
    for name, (filename, data, media) in files.items():
        head = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: {media}\r\n\r\n"
        ).encode("utf-8")
        parts.append(head + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


# --------------------------------------------------------------------------- 受控模型替身
class FakeProvider:
    """受控替身（LLMProvider 子类）：按 FIFO 返回预置文本，或用 handler 精细控制。"""

    def __init__(self, replies: list[Any] | None = None, handler=None) -> None:
        self.replies = list(replies or [])
        self.handler = handler
        self.calls: list[Any] = []

    async def complete(self, config, request, *, transport=None):  # noqa: ANN001
        from app.providers.llm.base import LLMResponse

        self.calls.append(request)
        if self.handler is not None:
            text, finish = await self.handler(request)
        else:
            item = self.replies.pop(0) if self.replies else "{}"
            text, finish = (item, "stop") if isinstance(item, str) else item
        return LLMResponse(text=text, finishReason=finish, usage=None)


# --------------------------------------------------------------------------- 装配
@dataclass
class Harness:
    root: Path
    app: Any
    client: Any
    subject_id: str = "math"
    _entered: bool = False

    def close(self) -> None:
        """收尾：若进入了 TestClient 上下文（长驻 portal），在此退出。"""
        if self._entered:
            self.client.__exit__(None, None, None)
            self._entered = False
        else:
            self.client.close()

    def state(self, name: str):
        return getattr(self.app.state, name)

    def db(self, name: str):
        import sqlite3

        path = {
            "teaching": self.root / "data" / "teaching" / "teaching.sqlite3",
            "question_bank": self.root / "data" / "question-bank" / "question-bank.sqlite3",
            "knowledge": self.root / "data" / "knowledge" / "knowledge.sqlite3",
        }[name]
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn

    def make_point(self, code: str, name: str, *, subject_id: str | None = None) -> str:
        body = {
            "subjectId": subject_id or self.subject_id,
            "code": code,
            "name": name,
        }
        response = self.client.post("/api/v1/knowledge-points", json=body)
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def import_docx(self, path: Path, *, title: str | None = None, subject_id: str | None = None):
        data, content_type = multipart(
            {"subjectId": subject_id or self.subject_id, **({"title": title} if title else {})},
            {"file": (path.name, path.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        return self.client.post(
            "/api/v1/paper-imports", content=data, headers={"content-type": content_type}
        )


def new_harness(prefix: str, *, fake_replies: list[Any] | None = None,
                with_client: bool = False) -> tuple[Harness, Any]:
    """建独立临时数据根 + 真应用；``fake_replies`` 存在时替换模型解析器（受控替身）。"""
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.main import create_app
    from app.providers.llm.base import LLMConfig
    from app.schemas.model_config import ModelProtocol
    from app.services.model_runtime import ChatModelHandle

    root = Path(tempfile.mkdtemp(prefix=f"zqky-v00b2-{prefix}-"))
    settings = Settings(
        host="127.0.0.1",
        port=8001,
        allowed_origins=frozenset({"http://127.0.0.1:5173", "http://127.0.0.1:5174"}),
        env="test",
        data_dir=root / "data",
    )
    app = create_app(settings)
    provider = FakeProvider(fake_replies)
    handle = ChatModelHandle(
        profile_id="v00-fake-profile",
        model_id="v00-fake-model",
        provider=provider,
        config=LLMConfig(
            protocol=ModelProtocol.openai_chat,
            baseUrl="http://127.0.0.1:9",
            modelId="v00-fake-model",
            apiKey=None,
            apiFormat="openai_chat",
        ),
    )
    if getattr(app.state, "paper_service", None) is not None:
        app.state.paper_service._model_resolver = lambda profile_id: handle  # noqa: SLF001
    if getattr(app.state, "question_bank_service", None) is not None:
        # 题库服务的公开属性名是 model_resolver（T50 原样）；两个名字都注入，避免依赖私有名
        app.state.question_bank_service.model_resolver = lambda profile_id: handle
        app.state.question_bank_service._model_resolver = lambda profile_id: handle  # noqa: SLF001
    client = TestClient(app, base_url="http://127.0.0.1:8001")
    harness = Harness(root=root, app=app, client=client)
    if with_client:
        # 进入上下文 → 长驻 portal 事件循环；后台任务（schedule）才会真正跑完
        client.__enter__()
        harness._entered = True  # noqa: SLF001
    return harness, provider


# --------------------------------------------------------------------------- 原卷草稿准备
def revision_snapshot(har: Harness, revision_id: str) -> dict[str, Any]:
    """该修订全部子记录的规范化快照（用于"旧修订逐字节不变"对账）。"""
    import hashlib as _hashlib

    conn = har.db("teaching")
    try:
        payload: dict[str, list] = {}
        for table, order in (
            ("paper_revisions", "id"),
            ("paper_items", "ordinal"),
            ("paper_item_knowledge", "item_id, knowledge_point_id"),
            ("paper_source_blocks", "ordinal"),
            ("paper_issues", "id"),
        ):
            if table == "paper_revisions":
                rows = conn.execute(f"SELECT * FROM {table} WHERE id=?", (revision_id,)).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM {table} WHERE paper_revision_id=? ORDER BY {order}", (revision_id,)
                ).fetchall()
            payload[table] = [dict(row) for row in rows]
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return {"digest": _hashlib.sha256(blob).hexdigest(), "payload": payload}
    finally:
        conn.close()


def prepare_ready_draft(har: Harness, sample: dict[str, Any], *, point_a: str, point_b: str,
                        title: str = "V00 待确认卷", drop_question_no: str = "18") -> dict[str, Any]:
    """导入样本 → 整表替换为"可确认"草稿（删掉未计分的 18、归属全部块、解决 blocking 问题）。"""
    imported = har.import_docx(sample["path"], title=title)
    assert imported.status_code == 201, imported.text
    view = imported.json()
    paper_id = view["paper"]["paperId"]
    revision_id = view["revision"]["paperRevisionId"]
    items = {item["questionNo"]: item for item in view["revision"]["items"]}

    conn = har.db("teaching")
    try:
        rows = conn.execute(
            "SELECT id, item_id FROM paper_source_blocks WHERE paper_revision_id=? ORDER BY ordinal",
            (revision_id,),
        ).fetchall()
    finally:
        conn.close()
    uuid_to_no = {item["itemId"]: no for no, item in items.items()}
    block_rows = [
        {"block_id": row["id"], "id": row["id"].split(":", 1)[1],
         "item_id": row["item_id"], "question_no": uuid_to_no.get(row["item_id"])}
        for row in rows
    ]
    kept = {no: item["itemId"] for no, item in items.items() if no != drop_question_no}

    def item_payload(no, item_id, *, parent=None, scored=False, score=None, ordinal=1, knowledge=()):
        entry = {"questionNo": no, "itemId": item_id, "ordinal": ordinal, "isScored": scored,
                 "content": {"text": no}, "sourceLocator": {}, "knowledge": list(knowledge)}
        if parent:
            entry["parentItemId"] = parent
        if score is not None:
            entry["maxScore"] = score
        return entry

    items_patch = [
        item_payload("16", kept["16"], ordinal=1),
        item_payload("16(1)", kept["16(1)"], parent=kept["16"], scored=True, score="4", ordinal=2,
                     knowledge=[{"knowledgePointId": point_a}]),
        item_payload("16(2)", kept["16(2)"], parent=kept["16"], scored=True, score="6", ordinal=3,
                     knowledge=[{"knowledgePointId": point_b}]),
        item_payload("17", kept["17"], scored=True, score="5", ordinal=4,
                     knowledge=[{"knowledgePointId": point_a}]),
    ]
    blocks_patch = []
    for row in block_rows:
        if row["id"] in ("p1", "p2"):
            blocks_patch.append({"blockId": row["block_id"], "disposition": "shared_material"})
        elif row["question_no"] in kept:
            blocks_patch.append({"blockId": row["block_id"], "disposition": "item",
                                 "itemId": kept[row["question_no"]]})
        else:
            blocks_patch.append({"blockId": row["block_id"], "disposition": "excluded",
                                 "excludeReason": "V00：解析损失，人工排除。"})
    issues_patch = [
        {"issueId": issue["issueId"], "status": "resolved", "resolution": {"note": "V00：人工补录"}}
        for issue in view["revision"]["issues"]
        if issue["severity"] == "blocking"
    ]
    response = har.client.patch(
        f"/api/v1/papers/{paper_id}/draft",
        json={"expectedRevision": view["paper"]["revision"], "title": title,
              "items": items_patch, "blocks": blocks_patch, "issues": issues_patch},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    paper = har.client.get(f"/api/v1/papers/{paper_id}").json()
    return {
        "paper_id": paper_id,
        "revision_id": revision_id,
        "items": {item["questionNo"]: item["itemId"] for item in body["items"]},
        "item_views": {item["questionNo"]: item for item in body["items"]},
        "issue_ids": {issue["code"]: issue["issueId"] for issue in body["issues"]},
        "revision": paper["revision"],
        "total_score_units": body["totalScoreUnits"],
        "view": body,
        "block_rows": block_rows,
    }
