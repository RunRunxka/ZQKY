"""V00-B2 · V2 独立探针：T40 导入（自建 DOCX）与草稿 PATCH 整表替换。

自建样本 DOCX（见 v00_support.build_sample_docx）：前导共同材料 2 段 / 两级小题
（16. + 16(1)/16(2)）/ 行内 OMML / 独立 OMML / 真实 PNG / 横向+纵向合并表格 /
独立计分题 17. / 空段落 / 纯未知对象段落（无 block_id 的问题）/ 未知对象+题号 18.。

断言：块顺序与定位、图片真实字节与 sha256、OMML 逐字节、合并表格形状、
规则拆题父子与分值、块处置与归属；PATCH 整表替换（新增/删除/复用 itemId）；
逐项 422 定位（题号重复/环/跨卷父/非叶子计分/分值非法/容器带分/知识点非法）；
expectedRevision 409 + currentRevision；失败不落库。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
PROBE_DIR = HERE.parent
_PROBE_TMP = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v2-import-"))
os.environ["ZQKY_DATA_DIR"] = str(_PROBE_TMP)  # 必须在导入 app.main 之前
sys.path.insert(0, str(REPO / "apps" / "api"))
sys.path.insert(0, str(PROBE_DIR))

import v00_support as S  # noqa: E402

from lxml import etree  # noqa: E402

RESULTS: list[dict] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    ok = bool(condition)
    RESULTS.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:400]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {str(detail)[:220]}")
    return ok


def err(response) -> tuple[int, str, dict]:
    body = response.json()
    error = body.get("error") or body
    return response.status_code, error.get("code"), error.get("details") or {}


def blocks_json(har, revision_id: str) -> dict[str, dict]:
    conn = har.db("teaching")
    try:
        rows = conn.execute(
            "SELECT id, ordinal, kind, block_json, locator_json, disposition, item_id, exclude_reason "
            "FROM paper_source_blocks WHERE paper_revision_id=? ORDER BY ordinal",
            (revision_id,),
        ).fetchall()
        return {
            row["id"].split(":", 1)[1]: {
                "block_id": row["id"],
                "id": row["id"].split(":", 1)[1],
                "ordinal": row["ordinal"],
                "kind": row["kind"],
                "block_json": row["block_json"],
                "locator_json": row["locator_json"],
                "disposition": row["disposition"],
                "item_id": row["item_id"],
                "exclude_reason": row["exclude_reason"],
            }
            for row in rows
        }
    finally:
        conn.close()


def main(evidence: str) -> int:
    work = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v2-work-"))
    sample = S.build_sample_docx(work / "v00-sample.docx")
    print(f"样本 DOCX：{sample['path']}")
    har, _provider = S.new_harness("v2")

    # ---------------------------------------------------------------- 导入
    response = har.import_docx(sample["path"], title="V00 期中卷")
    check("V2.1 导入返回 201", response.status_code == 201, f"{response.status_code} {response.text[:200]}")
    if response.status_code != 201:
        return finish(evidence, reason="import failed")
    data = response.json()
    revision = data["revision"]
    paper = data["paper"]
    revision_id = revision["paperRevisionId"]
    check("V2.2 草稿修订 version=1 / state=draft", revision["version"] == 1 and revision["state"] == "draft",
          f"version={revision['version']} state={revision['state']}")
    check("V2.3 导入告警包含解析损失", any("UNSUPPORTED_OBJECT" in w for w in data["warnings"]),
          str(data["warnings"])[:200])

    items = {item["questionNo"]: item for item in revision["items"]}
    check("V2.4 规则拆题 = {16,16(1),16(2),17,18}", set(items) == {"16", "16(1)", "16(2)", "17", "18"},
          str(sorted(items)))
    if set(items) == {"16", "16(1)", "16(2)", "17", "18"}:
        check("V2.5 16 是容器（不计分）/ 16(1),16(2),17 计分",
              (not items["16"]["isScored"]) and items["16"]["maxScoreUnits"] is None
              and items["16(1)"]["maxScore"] == "4" and items["16(2)"]["maxScore"] == "6"
              and items["17"]["maxScore"] == "5",
              f"16={items['16']['isScored']} 16(1)={items['16(1)']['maxScore']} 16(2)={items['16(2)']['maxScore']}")
        check("V2.6 父题路径：16(1)/16(2) 的 parentItemId = 16",
              items["16(1)"]["parentItemId"] == items["16"]["itemId"]
              and items["16(2)"]["parentItemId"] == items["16"]["itemId"],
              f"{items['16(1)']['parentItemId']} == {items['16']['itemId']}")
        check("V2.7 18 是未识别满分的不计分叶（不伪造 0 分）", items["18"]["isScored"] is False
              and items["18"]["maxScore"] is None, str(items["18"]["isScored"]))
    check("V2.8 导入合计 = 4+6+5 = 15 分（1500 单位）", revision["totalScoreUnits"] == 1500,
          str(revision["totalScoreUnits"]))

    issue_codes = [(issue["code"], issue["severity"], issue["blockId"]) for issue in revision["issues"]]
    check("V2.9 未知对象问题落库（含无 block_id 与有 block_id 两种）",
          sum(1 for code, _sev, _bid in issue_codes if code == "UNSUPPORTED_OBJECT") >= 2
          and any(code == "UNSUPPORTED_OBJECT" and bid is None for code, _s, bid in issue_codes)
          and any(code == "UNSUPPORTED_OBJECT" and bid for code, _s, bid in issue_codes),
          str(issue_codes)[:240])
    check("V2.10 未知对象判 blocking 且必须 resolution/exclude",
          all(sev == "blocking" for code, sev, _ in issue_codes if code == "UNSUPPORTED_OBJECT"),
          str([sev for code, sev, _ in issue_codes if code == "UNSUPPORTED_OBJECT"]))
    check("V2.11 18 未识别满分 → blocking ITEM_SCORE_MISSING",
          any(code == "ITEM_SCORE_MISSING" for code, _s, _b in issue_codes),
          str([c for c, _s, _b in issue_codes]))

    # 块顺序 / 定位 / 处置 / 归属
    blocks = blocks_json(har, revision_id)
    order = sorted(blocks.values(), key=lambda row: row["ordinal"])
    ids_in_order = [row["id"] for row in order]
    expected_ids = ["p1", "p2", "p3", "p4", "p5", "p6", "p6-1", "p7", "t8", "p9", "p10", "p10-1", "p13"]
    check("V2.12 块顺序与 id 与原件 body 顺序一致", ids_in_order == expected_ids, str(ids_in_order))
    kinds = [row["kind"] for row in order]
    check("V2.13 块类型序列（含 formula/image/table）",
          kinds == ["paragraph", "paragraph", "paragraph", "paragraph", "paragraph", "paragraph",
                    "formula", "image", "table", "paragraph", "paragraph", "formula", "paragraph"],
          str(kinds))
    locators = {row["id"]: json.loads(row["locator_json"]) for row in order}
    check("V2.14 定位 blockStart 与 body 顺序一致",
          locators["p1"] == {"blockStart": 1, "blockEnd": 1}
          and locators["t8"]["blockStart"] == 8 and locators["p10"]["blockStart"] == 10
          and locators["p13"]["blockStart"] == 13,
          f"p1={locators['p1']} t8={locators['t8']} p13={locators['p13']}")
    check("V2.15 表格定位含 tableColumns/tableRows", locators["t8"].get("tableColumns") == 3
          and locators["t8"].get("tableRows") == 2, str(locators["t8"]))
    disposition = {row["id"]: row["disposition"] for row in order}
    check("V2.16 前导共同材料 p1/p2 → shared_material", disposition["p1"] == "shared_material"
          and disposition["p2"] == "shared_material", str({k: disposition[k] for k in ("p1", "p2")}))
    owner = {row["id"]: (row["item_id"].split(":", 1)[0] if row["item_id"] else None)
             for row in order}
    item_ids = {q: item["itemId"] for q, item in items.items()}
    check("V2.17 块归属题目正确（16(2) 收 6/6-1/7/t8；17 收 9/10/10-1；18 收 13）",
          owner["p6-1"] == item_ids.get("16(2)") and owner["p7"] == item_ids.get("16(2)")
          and owner["t8"] == item_ids.get("16(2)") and owner["p9"] == item_ids.get("17")
          and owner["p10-1"] == item_ids.get("17") and owner["p13"] == item_ids.get("18"),
          str({k: owner[k][:8] if owner[k] else None for k in ("p6-1", "p7", "t8", "p9", "p10-1", "p13")}))

    # 图片真实字节与 sha256（直接读受管资产根）
    image_payload = json.loads(blocks["p7"]["block_json"])
    asset_id = image_payload.get("assetId") or ""
    blob_path = har.root / "data" / "assets" / asset_id
    ok_bytes = blob_path.is_file() and blob_path.read_bytes() == sample["png"]
    check("V2.18 图片块引用受管资产且字节 == 原件 PNG", ok_bytes and asset_id == f"blobs/{sample['png_sha256']}",
          f"assetId={asset_id} file={blob_path.is_file()}")
    check("V2.19 图片尺寸（extent EMU → px）", image_payload.get("width") == 120 and image_payload.get("height") == 60,
          f"{image_payload.get('width')}x{image_payload.get('height')}")

    # OMML 逐字节（lxml 在把节点序列化回字符串时会带上祖先文档继承的命名空间声明，
    # 因此"未改写"的判据是：子树结构/属性/文本逐节点相同 + 原始 m:oMath 标签与 m:t 字面量原样存在）
    def _omml_fingerprint(element) -> str:
        def walk(node) -> list:
            return [
                node.tag,
                dict(node.attrib),
                node.text,
                node.tail,
                [walk(child) for child in node],
            ]

        return json.dumps(walk(element), ensure_ascii=False, sort_keys=True)

    inline_payload = json.loads(blocks["p6-1"]["block_json"])
    standalone_payload = json.loads(blocks["p10-1"]["block_json"])
    got_inline_xml = inline_payload.get("ommlXml") or ""
    got_standalone_xml = standalone_payload.get("ommlXml") or ""
    inline_same = (
        _omml_fingerprint(etree.fromstring(got_inline_xml))
        == _omml_fingerprint(etree.fromstring(sample["inline_omml"]))
    )
    standalone_same = (
        _omml_fingerprint(etree.fromstring(got_standalone_xml))
        == _omml_fingerprint(etree.fromstring(sample["standalone_omml"]))
    )
    check("V2.20 行内 OMML 子树逐节点未改写（结构/属性/文本相同 + m:oMath 原样）",
          inline_same and got_inline_xml.startswith("<m:oMath") and got_inline_xml.rstrip().endswith("</m:oMath>"),
          f"same={inline_same} head={got_inline_xml[:100]}")
    check("V2.21 独立 OMML 子树逐节点未改写（结构/属性/文本相同 + m:oMath 原样）",
          standalone_same and got_standalone_xml.startswith("<m:oMath"),
          f"same={standalone_same} head={got_standalone_xml[:100]}")
    inline_text = "".join(node.text or "" for node in
                          etree.fromstring(got_inline_xml).iter("{http://schemas.openxmlformats.org/officeDocument/2006/math}t"))
    check("V2.22 OMML 可见文本未丢（x+1）", inline_text == "x+1", inline_text)
    ommml_dump = work / "omml-observed.txt"
    ommml_dump.write_text(f"INLINE:\n{got_inline_xml}\n\nSTANDALONE:\n{got_standalone_xml}\n", encoding="utf-8")

    # 合并表格（只在起始位置出现一次）
    table_payload = json.loads(blocks["t8"]["block_json"])
    cells = table_payload.get("cells") or []
    shape = [
        {"text": cell.get("text"), "colSpan": cell.get("colSpan"), "rowSpan": cell.get("rowSpan"),
         "header": cell.get("isHeader")}
        for cell in cells
    ]
    check("V2.23 合并表格 columnCount=3", table_payload.get("columnCount") == 3, str(table_payload.get("columnCount")))
    check("V2.24 横向合并只出现一次且 colSpan=2（得分表）",
          sum(1 for cell in cells if cell.get("text") == "得分表") == 1
          and next(cell for cell in cells if cell.get("text") == "得分表").get("colSpan") == 2,
          str(shape))
    check("V2.25 纵向合并 rowSpan=2（题号）",
          next((cell.get("rowSpan") for cell in cells if cell.get("text") == "题号"), None) == 2,
          str(shape))
    check("V2.26 被覆盖单元格不再产生条目（4 个起始格）", len(cells) == 4, f"cells={len(cells)} {shape}")
    check("V2.27 首行 isHeader", cells[0].get("isHeader") is True and cells[2].get("isHeader") is False,
          f"{cells[0].get('isHeader')}/{cells[2].get('isHeader')}")

    # 列表与内容读取
    listing = har.client.get("/api/v1/papers", params={"subjectId": "math"})
    check("V2.28 GET /papers 列表含该卷", listing.status_code == 200
          and any(row["paperId"] == paper["paperId"] for row in listing.json()["items"]),
          f"{listing.status_code} total={listing.json().get('total')}")
    content = har.client.get(f"/api/v1/papers/{paper['paperId']}/revisions/{revision_id}/content")
    check("V2.29 GET 修订内容可读且状态 draft", content.status_code == 200 and content.json()["state"] == "draft",
          f"{content.status_code}")

    # ---------------------------------------------------------------- 知识点
    point_a = har.make_point("V00-KP-A", "函数单调性")
    point_b = har.make_point("V00-KP-B", "导数几何意义")
    other = har.client.post("/api/v1/knowledge-points",
                            json={"subjectId": "physics", "code": "V00-KP-PHY", "name": "物理量"})
    point_physics = other.json()["id"]
    archived = har.make_point("V00-KP-ARC", "将归档点")
    arch = har.client.post(f"/api/v1/knowledge-points/{archived}/archive",
                           json={"expectedRevision": 0})
    check("V2.30 预备：知识点建档/归档成功", arch.status_code == 200 and arch.json()["status"] == "archived",
          f"{arch.status_code}")

    # ---------------------------------------------------------------- 草稿 PATCH
    def item_payload(question_no, item_id=None, parent=None, scored=False, score=None, ordinal=1,
                     knowledge=None, is_container_children=()):
        entry = {
            "questionNo": question_no,
            "ordinal": ordinal,
            "isScored": scored,
            "content": {"text": question_no},
            "sourceLocator": {},
            "knowledge": knowledge or [],
        }
        if item_id:
            entry["itemId"] = item_id
        if parent:
            entry["parentItemId"] = parent
        if score is not None:
            entry["maxScore"] = score
        return entry

    def full_blocks_patch(rows, *, exclude=("p13",), assign=None):
        assign = assign or {}
        patches = []
        for row in rows:
            block_id = row["id"]
            if block_id in exclude:
                patches.append({"blockId": row["block_id"], "disposition": "excluded",
                                "excludeReason": "V00 探针：与题意无关的解析损失，已人工排除。"})
            elif block_id in ("p1", "p2"):
                patches.append({"blockId": row["block_id"], "disposition": "shared_material"})
            else:
                patches.append({"blockId": row["block_id"], "disposition": "item",
                                "itemId": assign[block_id]})
        return patches

    blocks_rows = []
    conn = har.db("teaching")
    try:
        for row in conn.execute(
            "SELECT id, item_id FROM paper_source_blocks WHERE paper_revision_id=? ORDER BY ordinal",
            (revision_id,),
        ):
            blocks_rows.append({
                "block_id": row["id"],
                "id": row["id"].split(":", 1)[1],
                "item_id": row["item_id"],
            })
    finally:
        conn.close()
    new_ids = {"16": items["16"]["itemId"], "16(1)": items["16(1)"]["itemId"],
               "16(2)": items["16(2)"]["itemId"], "17": items["17"]["itemId"]}
    uuid_to_no = {item["itemId"]: no for no, item in items.items()}
    assign = {}
    for row in blocks_rows:
        if row["item_id"] is not None:
            question_no = uuid_to_no.get(row["item_id"])
            assign[row["id"]] = new_ids.get(question_no) if question_no in new_ids else None
    check("V2.P0 块→题目映射可用（p3..p10-1 覆盖；p13 属被删的 18）",
          all(assign.get(block_id) for block_id in
              ("p3", "p4", "p5", "p6", "p6-1", "p7", "t8", "p9", "p10", "p10-1"))
          and assign.get("p13") is None,
          str({k: (v or "")[:6] for k, v in assign.items()}))
    items_patch = [
        item_payload("16", item_id=new_ids["16"], ordinal=1),
        item_payload("16(1)", item_id=new_ids["16(1)"], parent=new_ids["16"], scored=True, score="4",
                     ordinal=2, knowledge=[{"knowledgePointId": point_a}]),
        item_payload("16(2)", item_id=new_ids["16(2)"], parent=new_ids["16"], scored=True, score="6",
                     ordinal=3, knowledge=[{"knowledgePointId": point_b, "role": "secondary"}]),
        item_payload("17", item_id=new_ids["17"], scored=True, score="5", ordinal=4,
                     knowledge=[{"knowledgePointId": point_a}]),
    ]
    patch_blocks = full_blocks_patch(
        blocks_rows,
        exclude=("p13",),
        assign={k: v for k, v in assign.items() if v is not None},
    )
    patch = {
        "expectedRevision": paper["revision"],
        "title": "V00 期中卷（校对后）",
        "items": items_patch,
        "blocks": patch_blocks,
    }
    first = har.client.patch(f"/api/v1/papers/{paper['paperId']}/draft", json=patch)
    check("V2.31 PATCH 整表替换成功（删除 18）", first.status_code == 200, f"{first.status_code} {first.text[:200]}")
    if first.status_code == 200:
        body = first.json()
        check("V2.32 替换后题目 = 4 道（18 已删除）", len(body["items"]) == 4, str(len(body["items"])))
        check("V2.33 知识点按请求写入（human）",
              sum(len(item["knowledge"]) for item in body["items"]) == 3
              and all(entry["source"] == "human" for item in body["items"] for entry in item["knowledge"]),
              str([[e["knowledgePointId"][:8], e["source"]] for item in body["items"] for e in item["knowledge"]]))
        check("V2.34 替换后总分 = 1500 保持", body["totalScoreUnits"] == 1500, str(body["totalScoreUnits"]))
        check("V2.35 标题已更新", body["title"] == "V00 期中卷（校对后）", body["title"])
    after = har.client.get(f"/api/v1/papers/{paper['paperId']}")
    check("V2.36 papers.revision 同事务 +1", after.json()["revision"] == paper["revision"] + 1,
          f"{paper['revision']} → {after.json()['revision']}")
    check("V2.37 被删除题目的块归属被清空并记 warning",
          any(issue["code"] == "PAPER_BLOCK_ITEM_RESET" for issue in first.json()["issues"]),
          str([i["code"] for i in first.json()["issues"]]))

    # 复用被删 itemId（同修订内重用）
    reuse_id = items["18"]["itemId"]
    reuse_items = list(items_patch)
    reuse_items.append(item_payload("18", item_id=reuse_id, scored=True, score="3", ordinal=5,
                                    knowledge=[{"knowledgePointId": point_b}]))
    reuse = har.client.patch(f"/api/v1/papers/{paper['paperId']}/draft",
                             json={"expectedRevision": after.json()["revision"], "items": reuse_items})
    check("V2.38 复用已删除的 itemId 建新题成功", reuse.status_code == 200
          and any(item["itemId"] == reuse_id and item["questionNo"] == "18" for item in reuse.json()["items"]),
          f"{reuse.status_code} {reuse.text[:160]}")
    rev_after_reuse = har.client.get(f"/api/v1/papers/{paper['paperId']}").json()["revision"]

    # 跨修订占用：另建一卷，用它的 itemId 在本卷 PATCH
    second_import = har.import_docx(sample["path"], title="V00 另一卷")
    other_item_id = second_import.json()["revision"]["items"][0]["itemId"]

    # ---------------------------------------------------------------- 错误路径
    base_rev = rev_after_reuse
    taken_items = list(reuse_items) + [item_payload("19", item_id=other_item_id, scored=True,
                                                    score="2", ordinal=6,
                                                    knowledge=[{"knowledgePointId": point_a}])]
    scenarios = [
        ("V2.39 题号重复 → ITEM_QUESTION_NO_DUPLICATE",
         {"items": reuse_items[:3] + [dict(reuse_items[3], questionNo="16(2)", ordinal=9)]},
         422, "ITEM_QUESTION_NO_DUPLICATE", "questionNo"),
        ("V2.40 父子成环 → ITEM_CYCLE",
         {"items": [
             item_payload("20", item_id="v00cy1", parent="v00cy2", scored=False, ordinal=1),
             item_payload("20(1)", item_id="v00cy2", parent="v00cy1", scored=False, ordinal=2),
         ]},
         422, "ITEM_CYCLE", "parentItemId"),
        ("V2.41 父题不在本批（跨卷父） → ITEM_PARENT_INVALID",
         {"items": [item_payload("21", item_id="v00orphan", parent=other_item_id, scored=False, ordinal=1)]},
         422, "ITEM_PARENT_INVALID", "parentItemId"),
        ("V2.42 容器计分（非叶子计分） → SCORED_ITEM_MUST_BE_LEAF",
         {"items": [
             item_payload("22", item_id="v00par", scored=True, score="5", ordinal=1,
                          knowledge=[{"knowledgePointId": point_a}]),
             item_payload("22(1)", item_id="v00kid", parent="v00par", scored=True, score="5", ordinal=2,
                          knowledge=[{"knowledgePointId": point_a}]),
         ]},
         422, "SCORED_ITEM_MUST_BE_LEAF", "isScored"),
        ("V2.43 负分 → 422（schema 拒绝）",
         {"items": [item_payload("23", item_id="v00neg", scored=True, score="-1", ordinal=1,
                                 knowledge=[{"knowledgePointId": point_a}])]},
         422, "INVALID_REQUEST", None),
        ("V2.44 三位小数 → 422（schema 拒绝）",
         {"items": [item_payload("24", item_id="v00dec", scored=True, score="2.555", ordinal=1,
                                 knowledge=[{"knowledgePointId": point_a}])]},
         422, "INVALID_REQUEST", None),
        ("V2.45 零分 → ITEM_SCORE_INVALID",
         {"items": [item_payload("25", item_id="v00zero", scored=True, score="0", ordinal=1,
                                 knowledge=[{"knowledgePointId": point_a}])]},
         422, "ITEM_SCORE_INVALID", "maxScore"),
        ("V2.46 容器带分 → ITEM_SCORE_INVALID",
         {"items": [
             item_payload("26", item_id="v00c", scored=False, score="5", ordinal=1),
             item_payload("26(1)", item_id="v00c1", parent="v00c", scored=True, score="5", ordinal=2,
                          knowledge=[{"knowledgePointId": point_a}]),
         ]},
         422, "ITEM_SCORE_INVALID", "maxScore"),
        ("V2.47 expectedRevision 过期 → 409 + currentRevision",
         {"expectedRevision": base_rev + 5, "items": reuse_items},
         409, "PAPER_REVISION_STALE", None),
        ("V2.48 未知知识点 → KNOWLEDGE_REFERENCE_INVALID",
         {"items": [item_payload("27", item_id="v00kp", scored=True, score="5", ordinal=1,
                                 knowledge=[{"knowledgePointId": "nope" * 4}])]},
         422, "KNOWLEDGE_REFERENCE_INVALID", "knowledgePointId"),
        ("V2.49 跨学科知识点 → KNOWLEDGE_REFERENCE_INVALID",
         {"items": [item_payload("28", item_id="v00phy", scored=True, score="5", ordinal=1,
                                 knowledge=[{"knowledgePointId": point_physics}])]},
         422, "KNOWLEDGE_REFERENCE_INVALID", "knowledgePointId"),
        ("V2.50 已归档知识点 → KNOWLEDGE_REFERENCE_INVALID",
         {"items": [item_payload("29", item_id="v00arc", scored=True, score="5", ordinal=1,
                                 knowledge=[{"knowledgePointId": archived}])]},
         422, "KNOWLEDGE_REFERENCE_INVALID", "knowledgePointId"),
        ("V2.51 排序号重复 → ITEM_ORDINAL_DUPLICATE",
         {"items": [dict(item, ordinal=7) for item in reuse_items]},
         422, "ITEM_ORDINAL_DUPLICATE", "ordinal"),
        ("V2.52 引用其他修订已占用的 itemId → ITEM_ID_INVALID",
         {"items": taken_items},
         422, "ITEM_ID_INVALID", "itemId"),
        ("V2.53 块补丁引用不存在的 blockId → PAPER_BLOCK_INVALID",
         {"blocks": [{"blockId": "no-such-block", "disposition": "shared_material"}]},
         422, "PAPER_BLOCK_INVALID", "blockId"),
        ("V2.54 问题补丁引用不存在 issueId → PAPER_ISSUE_NOT_FOUND",
         {"issues": [{"issueId": "no-such-issue", "status": "resolved", "resolution": {"note": "x"}}]},
         422, "PAPER_ISSUE_NOT_FOUND", "issueId"),
    ]
    for name, patch_body, expect_status, expect_code, expect_field in scenarios:
        body = {"expectedRevision": base_rev, **patch_body}
        response = har.client.patch(f"/api/v1/papers/{paper['paperId']}/draft", json=body)
        status, code, details = err(response)
        ok = status == expect_status and code == expect_code
        detail = f"{status}/{code}"
        if ok and expect_field is not None:
            issues = details.get("issues") or []
            has_field = any(issue.get("field") == expect_field for issue in issues)
            has_row = any(issue.get("row") is not None for issue in issues)
            ok = has_field
            detail += f" field={expect_field}:{has_field} rows={[i.get('row') for i in issues]}"
        if ok and expect_code == "PAPER_REVISION_STALE":
            ok = details.get("currentRevision") == base_rev
            detail += f" currentRevision={details.get('currentRevision')}"
        check(name, ok, detail)
        if response.status_code == 200:
            check(f"{name}（并列断言）失败路径不得返回 200", False, response.text[:200])

    # 失败后草稿未被污染
    conn = har.db("teaching")
    try:
        current_revision_id = conn.execute(
            "SELECT current_revision_id FROM papers WHERE id=?", (paper["paperId"],)
        ).fetchone()[0]
        item_count = conn.execute(
            "SELECT count(*) FROM paper_items WHERE paper_revision_id=?", (current_revision_id,)
        ).fetchone()[0]
    finally:
        conn.close()
    check("V2.55 全部失败后题数仍为 5（4+复用 1）且修订未变",
          item_count == 5 and current_revision_id == revision_id, f"items={item_count}")

    # 阻断问题的 resolution 负/正向路径（问题清单提供即更新）
    detail_view = har.client.get(f"/api/v1/papers/{paper['paperId']}/revisions/{revision_id}/content").json()
    blocking = [issue for issue in detail_view["issues"]
                if issue["severity"] == "blocking" and issue["status"] == "open"]
    check("V2.56 当前草稿仍有 blocking 未解决问题（至少 3 条）", len(blocking) >= 3,
          str([(i["code"], i["blockId"]) for i in blocking]))
    if blocking:
        no_resolution = har.client.patch(
            f"/api/v1/papers/{paper['paperId']}/draft",
            json={"expectedRevision": base_rev,
                  "issues": [{"issueId": blocking[0]["issueId"], "status": "resolved"}]},
        )
        status, code, details = err(no_resolution)
        check("V2.57 阻断问题无 resolution → 422 PAPER_ISSUE_BLOCKING 且可定位",
              status == 422 and code == "PAPER_ISSUE_BLOCKING"
              and any(issue.get("field") == "resolution" for issue in details.get("issues") or []),
              f"{status}/{code} {details}")
        issues_patch = [
            {"issueId": issue["issueId"], "status": "resolved",
             "resolution": {"note": "V00 探针：已人工补录该损失"}}
            for issue in blocking
        ]
        resolved = har.client.patch(
            f"/api/v1/papers/{paper['paperId']}/draft",
            json={"expectedRevision": base_rev, "issues": issues_patch},
        )
        blocking_after = [issue for issue in resolved.json().get("issues", [])
                          if issue["severity"] == "blocking"]
        check("V2.58 阻断问题带 resolution 可解决（warning 仍可保持 open）",
              resolved.status_code == 200 and blocking_after
              and all(issue["status"] == "resolved" for issue in blocking_after),
              f"{resolved.status_code} blocking={[(i['code'], i['status']) for i in blocking_after]}")

    har.client.close()
    return finish(evidence)


def finish(evidence: str, reason: str = "") -> int:
    failed = [row for row in RESULTS if row["status"] == "FAIL"]
    print(f"\n== v2_papers_import_probe: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed; "
          f"failed={[row['name'] for row in failed]} {reason} ==")
    if evidence:
        target = Path(evidence)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"probe": "v2_papers_import_probe", "results": RESULTS},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"证据：{evidence}")
    return 1 if failed else 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="")
    _args = parser.parse_args()
    try:
        raise SystemExit(main(_args.evidence))
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        RESULTS.append({"name": "probe crashed", "status": "FAIL", "detail": traceback.format_exc()[-300:]})
        raise SystemExit(finish(_args.evidence, reason="crashed"))
