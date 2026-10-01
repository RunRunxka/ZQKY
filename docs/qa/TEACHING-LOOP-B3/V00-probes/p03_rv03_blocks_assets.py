"""V00 · RV03 探针：未归属/无题号块正文 + 受控资产内容接口（自建场景）。

缺陷回顾（B2-RV03）：`PaperSourceBlockView` 没有持久化 content，未归属块不可审阅；
图片资产字节没有受控读取入口。

断言：
  A. 无题号 DOCX：items=[]，但段落/表格块仍返回持久化正文（可审阅）；
  B. 正常原卷：段落/公式/合并表格/图片块 content 齐全（ommlXml / cells+colSpan / assetId）；
  C. 把块置为 unassigned：仍返回 disposition + 正文；
  D. 受控资产接口：引用过的键 200（PNG 字节）；非受管键 422；路径穿越 422；
     未被本修订引用的受管键 404；跨卷/不存在修订 404。

运行（在 apps/api 下）：.venv/Scripts/python.exe -X utf8 <abs>/p03_rv03_blocks_assets.py
退出码 0 = 全部断言通过。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _v00 as V  # noqa: E402
from _v00_papers import PapersProbe, blocks_payload_from_view  # noqa: E402

from tests.papers_support import build_no_question_docx, build_paper_docx  # noqa: E402


def main() -> int:
    results: dict[str, Any] = {}
    failures: list[str] = []
    probe = PapersProbe(V.PROBE_TMP / "rv03")
    try:
        # A. 无题号文档
        no_q = build_no_question_docx(V.PROBE_TMP / "noq.docx")
        imported_noq = probe.import_paper(Path(no_q).read_bytes(), title="无题号文档")
        assert imported_noq.status_code == 201, imported_noq.text
        noq_rev = imported_noq.json()["revision"]
        noq_blocks = noq_rev["blocks"]
        paragraph_texts = [
            b["content"].get("text")
            for b in noq_blocks
            if b["kind"] == "paragraph" and b["content"].get("text")
        ]
        table_cells = [
            cell.get("text")
            for b in noq_blocks
            if b["kind"] == "table"
            for cell in (b["content"].get("cells") or [])
        ]
        results["no_question_doc"] = {
            "itemCount": len(noq_rev["items"]),
            "blockCount": len(noq_blocks),
            "paragraphTexts": paragraph_texts,
            "tableCells": table_cells,
            "issues": [i["code"] for i in noq_rev["issues"]],
        }
        if not (
            noq_rev["items"] == []
            and any("没有题号" in (t or "") for t in paragraph_texts)
            and "甲" in table_cells and "乙" in table_cells
        ):
            failures.append("A: 无题号文档的块正文缺失")

        # B. 正常原卷的块内容形状
        docx = build_paper_docx(V.PROBE_TMP / "rv03.docx", with_unknown_object=True)
        imported = probe.import_paper(Path(docx).read_bytes(), title="RV03 探针卷")
        assert imported.status_code == 201, imported.text
        paper_id = imported.json()["paper"]["paperId"]
        revision = imported.json()["revision"]
        revision_id = revision["paperRevisionId"]
        blocks = revision["blocks"]
        by_kind: dict[str, list[dict[str, Any]]] = {}
        for block in blocks:
            by_kind.setdefault(block["kind"], []).append(block)
        image_block = by_kind.get("image", [None])[0]
        formula_block = by_kind.get("formula", [None])[0]
        table_block = by_kind.get("table", [None])[0]
        merged_spans = [
            cell.get("colSpan")
            for cell in ((table_block or {}).get("content", {}).get("cells") or [])
        ]
        results["block_content_shape"] = {
            "kinds": {kind: len(rows) for kind, rows in by_kind.items()},
            "paragraphSample": (by_kind.get("paragraph") or [{}])[0].get("content"),
            "formulaHasOmml": bool((formula_block or {}).get("content", {}).get("ommlXml")),
            "tableMergedColSpans": merged_spans,
            "imageAssetId": (image_block or {}).get("content", {}).get("assetId"),
        }
        if not (
            (by_kind.get("paragraph") or [{}])[0].get("content", {}).get("text")
            and (formula_block or {}).get("content", {}).get("ommlXml")
            and max(merged_spans or [0]) >= 2
            and str((image_block or {}).get("content", {}).get("assetId", "")).startswith("blobs/")
        ):
            failures.append("B: 段落/公式/合并表格/图片块 content 不完整")
        asset_id = (image_block or {}).get("content", {}).get("assetId")

        # C. 未归属块仍返回正文
        item_block = next(b for b in blocks if b["disposition"] == "item")
        patched = probe.client.patch(
            f"/api/v1/papers/{paper_id}/draft",
            json={
                "expectedRevision": probe.client.get(f"/api/v1/papers/{paper_id}").json()["revision"],
                "blocks": blocks_payload_from_view(
                    blocks, disposition={item_block["blockId"]: "unassigned"}
                ),
            },
        )
        assert patched.status_code == 200, patched.text
        refreshed = patched.json()
        unassigned = next(
            b for b in refreshed["blocks"] if b["blockId"] == item_block["blockId"]
        )
        results["unassigned_block_view"] = {
            "disposition": unassigned["disposition"],
            "hasContent": bool(unassigned["content"].get("text")),
            "text": unassigned["content"].get("text"),
        }
        if not (
            unassigned["disposition"] == "unassigned" and unassigned["content"].get("text")
        ):
            failures.append("C: 未归属块没有正文")

        # D. 受控资产内容
        positive = probe.client.get(
            f"/api/v1/papers/{paper_id}/revisions/{revision_id}/assets/{asset_id}/content"
        )
        illegal = probe.client.get(
            f"/api/v1/papers/{paper_id}/revisions/{revision_id}/assets/notes.txt/content"
        )
        traversal = probe.client.get(
            f"/api/v1/papers/{paper_id}/revisions/{revision_id}/assets/blobs%2F..%2F..%2Fsecret/content"
        )
        stored = probe.assets.store_original(
            b"\x89PNG\r\n\x1a\n" + b"unreferenced", media_type="image/png", original_name="other.png"
        )
        unreferenced_key = f"blobs/{stored.sha256}"
        unreferenced = probe.client.get(
            f"/api/v1/papers/{paper_id}/revisions/{revision_id}/assets/{unreferenced_key}/content"
        )
        # 另一卷（无题号、无图片块）的修订：受管键存在但未被该修订引用
        noq_paper_id = imported_noq.json()["paper"]["paperId"]
        noq_revision_id = imported_noq.json()["revision"]["paperRevisionId"]
        cross_paper = probe.client.get(
            f"/api/v1/papers/{noq_paper_id}/revisions/{noq_revision_id}/assets/{asset_id}/content"
        )
        missing_revision = probe.client.get(
            f"/api/v1/papers/{paper_id}/revisions/does-not-exist/assets/{asset_id}/content"
        )
        results["asset_endpoint"] = {
            "positive": [
                positive.status_code,
                positive.headers.get("content-type"),
                len(positive.content),
                positive.content[:8].hex(),
            ],
            "illegalKey": [illegal.status_code, illegal.json().get("code")],
            "traversal": [traversal.status_code, traversal.json().get("code")],
            "unreferencedManagedKey": [unreferenced.status_code, unreferenced.json().get("code")],
            "crossPaper": [cross_paper.status_code, cross_paper.json().get("code")],
            "missingRevision": [missing_revision.status_code, missing_revision.json().get("code")],
        }
        if not (
            positive.status_code == 200
            and positive.content.startswith(b"\x89PNG")
            and illegal.status_code == 422
            and traversal.status_code in (404, 422)
            and unreferenced.status_code == 404
            and cross_paper.status_code == 404
            and missing_revision.status_code == 404
        ):
            failures.append("D: 受控资产接口边界不符")
    finally:
        probe.close()

    results["failures"] = failures
    results["verdict"] = "pass" if not failures else "fail"
    V.emit("p03_rv03_blocks_assets", results)
    print(f"verdict={results['verdict']} failures={failures}")
    for key in ("no_question_doc", "block_content_shape", "unassigned_block_view", "asset_endpoint"):
        print(key, json.dumps(results.get(key), ensure_ascii=False)[:500])
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        V.cleanup()
