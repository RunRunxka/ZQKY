"""V00 · RV02 探针：结构化问题处置 / 计分叶题面闸门（自建场景 + 故障注入）。

缺陷回顾（B2-RV02）：任意 resolution JSON 可通过确认；空计分题面仍可确认。

本探针断言（负向 → 拒绝、正向 → 落地并可见内容变化）：
  A. 任意 JSON / 缺字段的处置一律 422；
  B. 内容损失码不能仅以 exclude 放行；
  C. supplement_text 空文本 / 目标非段落 / 未受管资产键 / 不存在的受管键 → 422；
  D. 合法 supplement_text 追加进目标段落块（DB block_json 真的变化，内容 API 可见）；
  E. 合法补录 + 知识点关联 → 确认成功；
  F. 计分叶 content={} → 422 ITEM_STEM_MISSING；题面引用不存在的共同材料 → 422 ITEM_MATERIAL_MISSING。

运行（在 apps/api 下）：
  .venv/Scripts/python.exe -X utf8 <abs>/p02_rv02_resolution.py
退出码 0 = 全部断言通过。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _v00 as V  # noqa: E402
from _v00_papers import (  # noqa: E402
    PapersProbe,
    blocks_payload_from_view,
    items_payload_from_view,
)

from tests.papers_support import build_paper_docx  # noqa: E402

SUPPLEMENT_TEXT = "补录：图中阴影部分由半圆与三角形组成（教师补录）。"


def main() -> int:
    results: dict[str, Any] = {}
    failures: list[str] = []
    probe = PapersProbe(V.PROBE_TMP / "rv02")
    try:
        point = probe.add_point(code="kp-1", name="一次函数")
        docx = build_paper_docx(V.PROBE_TMP / "rv02.docx", with_unknown_object=True)
        imported = probe.import_paper(Path(docx).read_bytes(), title="RV02 探针卷")
        assert imported.status_code == 201, imported.text
        paper_id = imported.json()["paper"]["paperId"]
        revision = imported.json()["revision"]
        revision_id = revision["paperRevisionId"]
        blocking = [i for i in revision["issues"] if i["severity"] == "blocking"]
        results["import"] = {
            "paperId": paper_id,
            "revisionId": revision_id,
            "blockingIssues": [
                {"code": i["code"], "status": i["status"], "blockId": i["blockId"],
                 "locator": i["locator"]}
                for i in blocking
            ],
        }
        if len(blocking) != 1 or blocking[0]["code"] != "UNSUPPORTED_OBJECT":
            failures.append("import: 期望一条 UNSUPPORTED_OBJECT 阻断问题")
        issue_id = blocking[0]["issueId"]
        blocks = revision["blocks"]
        items = revision["items"]
        paragraph_blocks = [b for b in blocks if b["kind"] == "paragraph"]
        formula_blocks = [b for b in blocks if b["kind"] == "formula"]
        target_paragraph = paragraph_blocks[0]["blockId"]
        target_formula = formula_blocks[0]["blockId"]

        def patch_issues(payload: list[dict[str, Any]], *, items_payload=None):
            body = {
                "expectedRevision": current_revision(),
                "issues": payload,
            }
            if items_payload is not None:
                body["items"] = items_payload
            return probe.client.patch(f"/api/v1/papers/{paper_id}/draft", json=body)

        def content():
            """当前修订（confirm 后可能已 fork 新草稿）的内容视图。"""
            paper_view = probe.client.get(f"/api/v1/papers/{paper_id}")
            assert paper_view.status_code == 200, paper_view.text
            current_id = paper_view.json()["currentRevisionId"]
            response = probe.client.get(
                f"/api/v1/papers/{paper_id}/revisions/{current_id}/content"
            )
            assert response.status_code == 200, response.text
            return response.json()

        def current_revision() -> int:
            view = probe.client.get(f"/api/v1/papers/{paper_id}")
            assert view.status_code == 200, view.text
            return view.json()["revision"]

        # 控制：未处置阻断问题不能确认
        control = probe.client.post(
            f"/api/v1/papers/{paper_id}/confirm",
            json={"expectedRevision": current_revision(), "submissionId": "rv02-control"},
        )
        results["control_unresolved_blocking"] = {
            "status": control.status_code,
            "code": control.json().get("code"),
        }
        if control.status_code != 422:
            failures.append("control: 未处置阻断问题竟然可确认")

        # A. 任意 JSON / 缺字段
        arbitrary = patch_issues(
            [{"issueId": issue_id, "status": "resolved", "resolution": {"anything": 1}}]
        )
        results["caseA_arbitrary_json"] = {
            "status": arbitrary.status_code,
            "code": arbitrary.json().get("code"),
        }
        if arbitrary.status_code != 422:
            failures.append("caseA: 任意 JSON 处置被接受")
        missing = patch_issues([{"issueId": issue_id, "status": "resolved"}])
        results["caseA_missing_resolution"] = {
            "status": missing.status_code,
            "code": missing.json().get("code"),
        }
        if missing.status_code != 422:
            failures.append("caseA2: 缺 resolution 被接受")

        # B. 内容损失不能仅排除
        exclude_loss = patch_issues(
            [
                {
                    "issueId": issue_id,
                    "status": "excluded",
                    "resolution": {"kind": "exclude", "reason": "嫌麻烦"},
                }
            ]
        )
        exclude_loss_body = exclude_loss.json()
        results["caseB_exclude_content_loss"] = {
            "status": exclude_loss.status_code,
            "code": exclude_loss_body.get("code"),
            "firstIssueField": (
                (exclude_loss_body.get("details") or {}).get("issues") or [{}]
            )[0].get("field"),
        }
        if exclude_loss.status_code != 422:
            failures.append("caseB: 内容损失问题被 exclude 放行")

        # C. 补录参数不合法
        empty_text = patch_issues(
            [
                {
                    "issueId": issue_id,
                    "status": "resolved",
                    "resolution": {"kind": "supplement_text", "targetBlockId": target_paragraph, "text": "   "},
                }
            ]
        )
        non_paragraph = patch_issues(
            [
                {
                    "issueId": issue_id,
                    "status": "resolved",
                    "resolution": {
                        "kind": "supplement_text",
                        "targetBlockId": target_formula,
                        "text": SUPPLEMENT_TEXT,
                    },
                }
            ]
        )
        evil_key = patch_issues(
            [
                {
                    "issueId": issue_id,
                    "status": "resolved",
                    "resolution": {
                        "kind": "supplement_asset",
                        "targetBlockId": target_paragraph,
                        "assetId": "../../etc/passwd",
                    },
                }
            ]
        )
        absent_key = patch_issues(
            [
                {
                    "issueId": issue_id,
                    "status": "resolved",
                    "resolution": {
                        "kind": "supplement_asset",
                        "targetBlockId": target_paragraph,
                        "assetId": "blobs/" + "a" * 64,
                    },
                }
            ]
        )
        results["caseC_supplement_rejections"] = {
            "emptyText": [empty_text.status_code, empty_text.json().get("code")],
            "nonParagraphTarget": [non_paragraph.status_code, non_paragraph.json().get("code")],
            "unmanagedKey": [evil_key.status_code, evil_key.json().get("code")],
            "absentManagedKey": [absent_key.status_code, absent_key.json().get("code")],
        }
        if any(
            r.status_code != 422
            for r in (empty_text, non_paragraph, evil_key, absent_key)
        ):
            failures.append("caseC: 非法补录存在被接受的分支")

        # D+E. 合法补录 → 内容真实变化 → 确认成功
        before_content = content()
        before_block = next(
            b for b in before_content["blocks"] if b["blockId"] == target_paragraph
        )
        items_with_knowledge = items_payload_from_view(
            items, content={}
        )
        for entry in items_with_knowledge:
            entry["knowledge"] = (
                [{"knowledgePointId": point.point_id, "role": "primary"}]
                if entry["isScored"]
                else []
            )
        good = patch_issues(
            [
                {
                    "issueId": issue_id,
                    "status": "resolved",
                    "resolution": {
                        "kind": "supplement_text",
                        "targetBlockId": target_paragraph,
                        "text": SUPPLEMENT_TEXT,
                    },
                }
            ],
            items_payload=items_with_knowledge,
        )
        results["caseD_supplement_patch"] = {
            "status": good.status_code,
            "code": good.json().get("code") if good.status_code != 200 else None,
        }
        if good.status_code != 200:
            failures.append("caseD: 合法 supplement_text 被拒绝")
        after_content = content()
        after_block = next(
            b for b in after_content["blocks"] if b["blockId"] == target_paragraph
        )
        db_rows = probe.raw_rows(
            "SELECT block_json FROM paper_source_blocks WHERE paper_revision_id = ? AND id = ?",
            (after_content["paperRevisionId"], target_paragraph),
        )
        db_text = json.loads(db_rows[0]["block_json"]).get("text", "") if db_rows else ""
        results["caseD_content_change"] = {
            "beforeText": before_block["content"].get("text"),
            "afterText": after_block["content"].get("text"),
            "dbTextHasSupplement": SUPPLEMENT_TEXT in db_text,
            "apiTextHasSupplement": SUPPLEMENT_TEXT in (after_block["content"].get("text") or ""),
        }
        if not (
            SUPPLEMENT_TEXT in (after_block["content"].get("text") or "")
            and SUPPLEMENT_TEXT in db_text
        ):
            failures.append("caseD: 补录文本没有真正写入目标块")

        confirm = probe.client.post(
            f"/api/v1/papers/{paper_id}/confirm",
            json={"expectedRevision": current_revision(), "submissionId": "rv02-good"},
        )
        results["caseE_confirm_after_supplement"] = {
            "status": confirm.status_code,
            "body": confirm.json() if confirm.status_code != 200 else {
                k: confirm.json()[k] for k in ("state", "scoredLeafCount", "totalScoreUnits")
            },
        }
        if confirm.status_code != 200:
            failures.append("caseE: 合法补录后确认未成功")

        # F. 空计分题面 / 缺共同材料：确认后 PATCH 会自动 fork 新草稿
        forked = content()
        forked_items = forked["items"]
        empty_items = items_payload_from_view(forked_items, content={})
        for entry in empty_items:
            if entry["isScored"]:
                entry["knowledge"] = [{"knowledgePointId": point.point_id, "role": "primary"}]
        # 只清空一个计分叶的 content
        target_leaf = next(e for e in empty_items if e["questionNo"] == "18")
        target_leaf["content"] = {}
        empty_patch = probe.client.patch(
            f"/api/v1/papers/{paper_id}/draft",
            json={
                "expectedRevision": current_revision(),
                "items": empty_items,
                "blocks": blocks_payload_from_view(forked["blocks"]),
            },
        )
        empty_confirm = probe.client.post(
            f"/api/v1/papers/{paper_id}/confirm",
            json={"expectedRevision": current_revision(), "submissionId": "rv02-empty-stem"},
        )
        empty_body = empty_confirm.json()
        results["caseF_empty_scored_stem"] = {
            "patchStatus": empty_patch.status_code,
            "patchBody": empty_patch.json() if empty_patch.status_code != 200 else None,
            "confirmStatus": empty_confirm.status_code,
            "code": empty_body.get("code"),
            "issues": (empty_body.get("details") or {}).get("issues"),
        }
        if empty_confirm.status_code != 422 or empty_body.get("code") != "ITEM_STEM_MISSING":
            failures.append("caseF: 空计分题面未被拒（或不是 ITEM_STEM_MISSING）")

        # G. 题面引用不存在的共同材料
        current = content()
        material_items = items_payload_from_view(current["items"], content={})
        for entry in material_items:
            if entry["isScored"]:
                entry["knowledge"] = [{"knowledgePointId": point.point_id, "role": "primary"}]
        # 恢复被清空的题面，再只破坏共同材料引用
        original_18 = next(i for i in forked_items if i["questionNo"] == "18")
        entry18 = next(e for e in material_items if e["questionNo"] == "18")
        broken_content = dict(original_18["content"])
        materials = broken_content.get("sharedMaterials") or []
        if materials and materials[0].get("blocks"):
            materials = list(materials)
            first = dict(materials[0])
            first["blocks"] = list(first["blocks"])
            first["blocks"][0] = {**first["blocks"][0], "id": "block-that-does-not-exist"}
            materials[0] = first
            broken_content["sharedMaterials"] = materials
        entry18["content"] = broken_content
        material_patch = probe.client.patch(
            f"/api/v1/papers/{paper_id}/draft",
            json={
                "expectedRevision": current_revision(),
                "items": material_items,
                "blocks": blocks_payload_from_view(current["blocks"]),
            },
        )
        material_confirm = probe.client.post(
            f"/api/v1/papers/{paper_id}/confirm",
            json={"expectedRevision": current_revision(), "submissionId": "rv02-missing-material"},
        )
        material_body = material_confirm.json()
        results["caseG_missing_material"] = {
            "patchStatus": material_patch.status_code,
            "patchBody": material_patch.json() if material_patch.status_code != 200 else None,
            "confirmStatus": material_confirm.status_code,
            "code": material_body.get("code"),
            "issues": (material_body.get("details") or {}).get("issues"),
        }
        if material_confirm.status_code != 422 or material_body.get("code") != "ITEM_MATERIAL_MISSING":
            failures.append("caseG: 引用不存在的共同材料未被拒（或不是 ITEM_MATERIAL_MISSING）")
    finally:
        probe.close()

    results["failures"] = failures
    results["verdict"] = "pass" if not failures else "fail"
    V.emit("p02_rv02_resolution", results)
    print(f"verdict={results['verdict']} failures={failures}")
    for key in (
        "import",
        "control_unresolved_blocking",
        "caseA_arbitrary_json",
        "caseB_exclude_content_loss",
        "caseC_supplement_rejections",
        "caseD_content_change",
        "caseE_confirm_after_supplement",
        "caseF_empty_scored_stem",
        "caseG_missing_material",
    ):
        print(key, json.dumps(results.get(key), ensure_ascii=False)[:400])
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        V.cleanup()
