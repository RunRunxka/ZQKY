"""V2 知识点 CRUD / 父树 / 别名 / 归档 探针（TEACHING-LOOP B1 / V00）。

HTTP 层（TestClient，临时数据根）覆盖：
  - 创建/详情/列表分页与 q 检索、改名=追加修订、旧修订不可变、expectedRevision 409
  - 同 code 409；跨学科父 / 缺父 / 自指 / 环 的错误码与可定位字段 details.issues[].field
  - 归档后显式编辑 vs 归档后新增引用（父节点、教材依据）两种行为
  - 别名规范化、跨点同名只 warning（不合并、不报错）
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_common import Probe, ensure_api_on_path, temp_data_root  # noqa: E402

p = Probe("v2_knowledge_points")
root = temp_data_root("v2")
ensure_api_on_path()

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.knowledge.service import build_knowledge_service  # noqa: E402

ALLOWED = frozenset({"http://127.0.0.1:5173", "http://127.0.0.1:5174"})
settings = Settings(
    host="127.0.0.1",
    port=8001,
    allowed_origins=ALLOWED,
    env="test",
    data_dir=root / "data",
)

client = TestClient(create_app(settings), base_url="http://127.0.0.1:8001")
client.__enter__()


def api(method: str, path: str, **kwargs):
    return client.request(method, f"/api/v1{path}", **kwargs)


def err(resp):
    try:
        return resp.json()
    except ValueError:
        return {"code": None, "message": resp.text[:200]}


try:
    # ------------------------------------------------------------------ A 创建/读取
    created = api(
        "POST",
        "/knowledge-points",
        json={
            "subjectId": "math",
            "code": "M-01",
            "name": "有理数",
            "description": "desc-1",
            "sortOrder": 5,
            "aliases": ["\uff21\uff22\uff23", "abc"],
        },
    )
    p.check("v2.1a 创建知识点 201", created.status_code == 201, f"{created.status_code} {err(created)}")
    point = created.json()
    p.check(
        "v2.1b 首修订 version=1 / revision=0 / revisionId 非空",
        point["version"] == 1 and point["revision"] == 0 and bool(point["revisionId"]),
        json.dumps({k: point[k] for k in ("version", "revision", "revisionId", "status")}, ensure_ascii=False),
    )
    p.check(
        "v2.1c 别名按规范化（NFKC+casefold）在点内去重",
        point["aliases"] == ["\uff21\uff22\uff23"],
        f"aliases={point['aliases']}",
    )
    pid = point["id"]

    detail = api("GET", f"/knowledge-points/{pid}")
    p.check("v2.1d 详情读取一致", detail.status_code == 200 and detail.json()["code"] == "M-01", f"{detail.status_code}")

    # 第二点 + 子点，供列表/父树使用
    parent = api("POST", "/knowledge-points", json={"subjectId": "math", "code": "M-00", "name": "数与式"}).json()
    child = api(
        "POST",
        "/knowledge-points",
        json={"subjectId": "math", "code": "M-02", "name": "相反数", "parentCode": "M-01"},
    )
    p.check("v2.1e parentCode 解析成功（子点创建 201）", child.status_code == 201, f"{child.status_code} {err(child)}")
    p.check(
        "v2.1f 子点 parentId/parentCode 正确回填",
        child.json()["parentId"] == pid and child.json()["parentCode"] == "M-01",
        json.dumps({k: child.json()[k] for k in ("parentId", "parentCode")}),
    )

    listing = api("GET", "/knowledge-points", params={"subjectId": "math", "limit": 2, "offset": 1})
    body = listing.json()
    p.check(
        "v2.1g 列表分页形状 {items,total,offset,limit}",
        listing.status_code == 200
        and set(body) == {"items", "total", "offset", "limit"}
        and body["total"] == 3
        and body["offset"] == 1
        and body["limit"] == 2
        and len(body["items"]) == 2,
        json.dumps({k: body[k] for k in ("total", "offset", "limit")}) + f" items={len(body['items'])}",
    )
    by_alias = api("GET", "/knowledge-points", params={"subjectId": "math", "q": "abc"})
    p.check(
        "v2.1h q 可命中别名（规范化后模糊）",
        by_alias.status_code == 200 and [item["code"] for item in by_alias.json()["items"]] == ["M-01"],
        json.dumps(by_alias.json()["items"], ensure_ascii=False)[:200],
    )
    by_parent = api("GET", "/knowledge-points", params={"subjectId": "math", "parentId": pid})
    p.check(
        "v2.1i parentId 过滤",
        [item["code"] for item in by_parent.json()["items"]] == ["M-02"],
        json.dumps([item["code"] for item in by_parent.json()["items"]]),
    )

    # ------------------------------------------------------------------ B 修订与乐观锁
    renamed = api(
        "PATCH",
        f"/knowledge-points/{pid}",
        json={"expectedRevision": point["revision"], "name": "有理数与无理数"},
    )
    p.check("v2.2a 改名 200", renamed.status_code == 200, f"{renamed.status_code} {err(renamed)}")
    renamed_body = renamed.json()
    p.check(
        "v2.2b 改名追加修订（version 2 / revision 1 / revisionId 变化）",
        renamed_body["version"] == 2
        and renamed_body["revision"] == 1
        and renamed_body["revisionId"] != point["revisionId"]
        and renamed_body["name"] == "有理数与无理数",
        json.dumps({k: renamed_body[k] for k in ("version", "revision", "name")}, ensure_ascii=False),
    )

    stale = api(
        "PATCH",
        f"/knowledge-points/{pid}",
        json={"expectedRevision": point["revision"], "name": "更名再试"},
    )
    stale_body = err(stale)
    p.check(
        "v2.2c 过期 expectedRevision → 409 REVISION_CONFLICT + details.currentRevision",
        stale.status_code == 409
        and stale_body.get("code") == "REVISION_CONFLICT"
        and (stale_body.get("details") or {}).get("currentRevision") == 1,
        f"{stale.status_code} {json.dumps(stale_body, ensure_ascii=False)}",
    )

    dup = api("POST", "/knowledge-points", json={"subjectId": "math", "code": "M-01", "name": "重复"})
    dup_body = err(dup)
    p.check(
        "v2.2d 同学科同 code → 409 KNOWLEDGE_CODE_CONFLICT",
        dup.status_code == 409 and dup_body.get("code") == "KNOWLEDGE_CODE_CONFLICT",
        f"{dup.status_code} {dup_body.get('code')}",
    )

    blank = api(
        "PATCH",
        f"/knowledge-points/{pid}",
        json={"expectedRevision": 1, "description": "   "},
    )
    p.check(
        "v2.2e 空白可选字段默认不修改",
        blank.status_code == 200 and blank.json()["description"] == "desc-1",
        f"{blank.status_code} desc={blank.json().get('description')!r}",
    )
    cleared = api(
        "PATCH",
        f"/knowledge-points/{pid}",
        json={"expectedRevision": blank.json()["revision"], "clearFields": ["description", "aliases"]},
    )
    p.check(
        "v2.2f clearFields 才清空（description/aliases）",
        cleared.status_code == 200
        and cleared.json()["description"] == ""
        and cleared.json()["aliases"] == [],
        json.dumps({k: cleared.json()[k] for k in ("description", "aliases")}, ensure_ascii=False),
    )
    cur_revision = cleared.json()["revision"]

    # 旧修订不可变（直接 SQL 尝试 UPDATE/DELETE）
    from app.repositories.knowledge.catalog import KnowledgeCatalog

    catalog = KnowledgeCatalog(root / "data" / "knowledge" / "knowledge.sqlite3")
    conn = sqlite3.connect(str(catalog.db_path))
    conn.row_factory = sqlite3.Row
    old_revision_id = point["revisionId"]
    immutability: list[str] = []
    for sql in (
        "UPDATE knowledge_point_revisions SET name = 'tampered' WHERE id = ?",
        "DELETE FROM knowledge_point_revisions WHERE id = ?",
    ):
        savepoint = "sp_probe"
        try:
            conn.execute(f"SAVEPOINT {savepoint}")
            conn.execute(sql, (old_revision_id,))
            immutability.append("no-error")
        except sqlite3.IntegrityError as exc:
            immutability.append(str(exc))
        finally:
            conn.execute("ROLLBACK TO sp_probe")
            conn.execute("RELEASE sp_probe")
    rows = conn.execute(
        "SELECT version, name FROM knowledge_point_revisions WHERE knowledge_point_id = ? ORDER BY version",
        (pid,),
    ).fetchall()
    conn.close()
    p.check(
        "v2.2g 历史修订不可变（UPDATE/DELETE 均被 DB 触发器拒绝）",
        all("IMMUTABLE_REVISION" in item for item in immutability),
        f"{immutability}",
    )
    p.check(
        "v2.2h 历史修订全部保留（v1 改名前后、v3 clearFields 追加）",
        [(row["version"], row["name"]) for row in rows]
        == [(1, "有理数"), (2, "有理数与无理数"), (3, "有理数与无理数")],
        f"{[(row['version'], row['name']) for row in rows]}",
    )

    # ------------------------------------------------------------------ C 父树错误定位
    other = api("POST", "/knowledge-points", json={"subjectId": "physics", "code": "P-01", "name": "质点"}).json()
    cross = api(
        "POST",
        "/knowledge-points",
        json={"subjectId": "math", "code": "M-90", "name": "跨科", "parentId": other["id"]},
    )
    cross_body = err(cross)
    cross_issues = (cross_body.get("details") or {}).get("issues") or []
    p.check(
        "v2.3a 跨学科父 → 422 KNOWLEDGE_CROSS_SUBJECT_PARENT + issues[].field=parentId",
        cross.status_code == 422
        and cross_body.get("code") == "KNOWLEDGE_CROSS_SUBJECT_PARENT"
        and cross_issues
        and cross_issues[0].get("field") == "parentId",
        f"{cross.status_code} {json.dumps(cross_body, ensure_ascii=False)[:300]}",
    )

    missing_id = api(
        "POST",
        "/knowledge-points",
        json={"subjectId": "math", "code": "M-91", "name": "缺父id", "parentId": "no-such-id"},
    )
    mi_body = err(missing_id)
    p.check(
        "v2.3b 缺父（parentId）→ 422 KNOWLEDGE_PARENT_INVALID + field=parentId",
        missing_id.status_code == 422
        and mi_body.get("code") == "KNOWLEDGE_PARENT_INVALID"
        and ((mi_body.get("details") or {}).get("issues") or [{}])[0].get("field") == "parentId",
        f"{missing_id.status_code} {json.dumps(mi_body, ensure_ascii=False)[:300]}",
    )
    missing_code = api(
        "POST",
        "/knowledge-points",
        json={"subjectId": "math", "code": "M-92", "name": "缺父code", "parentCode": "NOPE"},
    )
    mc_body = err(missing_code)
    p.check(
        "v2.3c 缺父（parentCode）→ 422 KNOWLEDGE_PARENT_INVALID + field=parentCode",
        missing_code.status_code == 422
        and mc_body.get("code") == "KNOWLEDGE_PARENT_INVALID"
        and ((mc_body.get("details") or {}).get("issues") or [{}])[0].get("field") == "parentCode",
        f"{missing_code.status_code} {json.dumps(mc_body, ensure_ascii=False)[:300]}",
    )
    both = api(
        "POST",
        "/knowledge-points",
        json={"subjectId": "math", "code": "M-93", "name": "双父", "parentId": pid, "parentCode": "M-01"},
    )
    p.check(
        "v2.3d parentId 与 parentCode 同时给出 → 422 INVALID_REQUEST",
        both.status_code == 422 and err(both).get("code") == "INVALID_REQUEST",
        f"{both.status_code} {json.dumps(err(both), ensure_ascii=False)[:200]}",
    )

    self_parent = api(
        "PATCH", f"/knowledge-points/{pid}", json={"expectedRevision": cur_revision, "parentId": pid}
    )
    sp_body = err(self_parent)
    p.check(
        "v2.3e 自指父 → 422 KNOWLEDGE_PARENT_INVALID（记录是否带 issues 定位）",
        self_parent.status_code == 422 and sp_body.get("code") == "KNOWLEDGE_PARENT_INVALID",
        f"{self_parent.status_code} {json.dumps(sp_body, ensure_ascii=False)[:300]}",
    )
    p.check(
        "v2.3f 自指父错误带 details.issues[].field（契约 §2.2 可定位要求）",
        ((sp_body.get("details") or {}).get("issues") or [{}])[0].get("field") in ("parentId", "parentCode"),
        f"details={json.dumps(sp_body.get('details'), ensure_ascii=False)}",
    )

    # 环：child(M-02) 目前 parent=M-01(pid)；把 pid.parent 设为 child → 形成环
    cycle = api(
        "PATCH",
        f"/knowledge-points/{pid}",
        json={"expectedRevision": cur_revision, "parentId": child.json()["id"]},
    )
    cy_body = err(cycle)
    p.check(
        "v2.3g 成环父 → 422 KNOWLEDGE_CYCLE（DB 触发器兜底）",
        cycle.status_code == 422 and cy_body.get("code") == "KNOWLEDGE_CYCLE",
        f"{cycle.status_code} {json.dumps(cy_body, ensure_ascii=False)[:300]}",
    )
    p.check(
        "v2.3h 环错误带 details.issues[].field（契约 §2.2 可定位要求）",
        ((cy_body.get("details") or {}).get("issues") or [{}])[0].get("field") in ("parentId", "parentCode"),
        f"details={json.dumps(cy_body.get('details'), ensure_ascii=False)}",
    )
    still = api("GET", f"/knowledge-points/{pid}").json()
    p.check(
        "v2.3i 成环被拒后原父关系不变（无部分写入）",
        still["parentId"] is None and still["revision"] == cur_revision,
        json.dumps({k: still[k] for k in ("parentId", "revision")}),
    )

    # ------------------------------------------------------------------ D 归档
    archived = api("POST", f"/knowledge-points/{pid}/archive", json={"expectedRevision": cur_revision})
    p.check(
        "v2.4a 归档 200 + status=archived + revision+1",
        archived.status_code == 200
        and archived.json()["status"] == "archived"
        and archived.json()["revision"] == cur_revision + 1,
        f"{archived.status_code} {json.dumps({k: archived.json().get(k) for k in ('status', 'revision')})}",
    )
    arch_revision = archived.json()["revision"]

    edited = api(
        "PATCH",
        f"/knowledge-points/{pid}",
        json={"expectedRevision": arch_revision, "description": "归档后仍可显式编辑"},
    )
    p.check(
        "v2.4b 归档后显式编辑仍允许（§8 预先登记行为）",
        edited.status_code == 200 and edited.json()["description"] == "归档后仍可显式编辑",
        f"{edited.status_code} {json.dumps(err(edited), ensure_ascii=False)[:200]}",
    )

    child_of_archived = api(
        "POST",
        "/knowledge-points",
        json={"subjectId": "math", "code": "M-94", "name": "归档父的新子", "parentCode": "M-01"},
    )
    coa_body = err(child_of_archived)
    p.check(
        "v2.4c 归档知识点作为新父 → 409 KNOWLEDGE_ARCHIVED + field=parentCode",
        child_of_archived.status_code == 409
        and coa_body.get("code") == "KNOWLEDGE_ARCHIVED"
        and ((coa_body.get("details") or {}).get("issues") or [{}])[0].get("field") == "parentCode",
        f"{child_of_archived.status_code} {json.dumps(coa_body, ensure_ascii=False)[:300]}",
    )

    # 归档后新增教材依据（服务级：用受控 evidence 替身，避免依赖真实教材目录）
    from app.contracts.knowledge import TextbookLinkCreateRequest
    from app.core.exceptions import AppError
    from app.services.publication import PublicationCoordinator

    class _Evidence:
        def read(self, *, document_revision_id, char_start, char_end):
            from dataclasses import dataclass

            @dataclass(frozen=True)
            class _E:
                document_revision_id: str
                char_start: int
                char_end: int
                title: str
                locator: dict

            return _E(document_revision_id, char_start, char_end, "标题快照", {"page": 1})

    probe_service = build_knowledge_service(
        client.app.state.knowledge,
        asset_store=client.app.state.asset_store,
        file_assets=client.app.state.file_assets,
        evidence=_Evidence(),
        coordinator=PublicationCoordinator(),
        model_resolver=None,
        job_engine=None,
    )
    link_err = None
    try:
        probe_service.add_textbook_link(
            pid,
            TextbookLinkCreateRequest(
                expected_revision=edited.json()["revision"],
                document_revision_id="docrev-1",
                char_start=0,
                char_end=10,
            ),
        )
    except AppError as exc:
        link_err = exc
    p.check(
        "v2.4d 归档知识点新增教材依据被拒 409 KNOWLEDGE_ARCHIVED",
        link_err is not None
        and link_err.code == "KNOWLEDGE_ARCHIVED"
        and link_err.status_code == 409,
        f"{type(link_err).__name__}: {getattr(link_err, 'code', None)} {link_err}",
    )
    restored = api("POST", f"/knowledge-points/{pid}/restore", json={"expectedRevision": edited.json()["revision"]})
    p.check(
        "v2.4e 恢复 200 + status=active",
        restored.status_code == 200 and restored.json()["status"] == "active",
        f"{restored.status_code} {json.dumps(err(restored), ensure_ascii=False)[:200]}",
    )

    # ------------------------------------------------------------------ E 别名跨点
    warnings: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if "别名歧义" in record.getMessage():
                warnings.append(record.getMessage())

    logger = logging.getLogger("zhiqikeyuan.knowledge")
    handler = _Capture()
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    # 先在已存在知识点上留下别名（上一步 clearFields 已把 pid 的别名清空）
    seeded = api(
        "PATCH",
        f"/knowledge-points/{parent['id']}",
        json={"expectedRevision": parent["revision"], "aliases": ["ABC"]},
    )
    p.check(
        "v2.5a 预置别名到另一点（PATCH aliases）",
        seeded.status_code == 200 and seeded.json()["aliases"] == ["ABC"],
        f"{seeded.status_code} {json.dumps(seeded.json().get('aliases'), ensure_ascii=False)}",
    )
    other_alias = api(
        "POST",
        "/knowledge-points",
        json={"subjectId": "math", "code": "M-95", "name": "别名撞车", "aliases": ["ABC"]},
    )
    logger.removeHandler(handler)
    p.check(
        "v2.5a2 跨点同别名不报错（只提示，201 成功）",
        other_alias.status_code == 201,
        f"{other_alias.status_code} {json.dumps(err(other_alias), ensure_ascii=False)[:200]}",
    )
    p.check(
        "v2.5b 跨点同别名记 warning（不合并、不自动改数据）",
        len(warnings) >= 1,
        f"warnings={warnings[:2]}",
    )
    first_aliases = api("GET", f"/knowledge-points/{pid}").json()["aliases"]
    second_aliases = api("GET", f"/knowledge-points/{other_alias.json()['id']}").json()["aliases"]
    p.check(
        "v2.5c 两点各自保留自己的别名（未合并/未清空）",
        first_aliases == [] and second_aliases == ["ABC"],
        f"first={first_aliases} second={second_aliases}",
    )
    dup_alias = api(
        "POST",
        "/knowledge-points",
        json={"subjectId": "math", "code": "M-96", "name": "重复别名", "aliases": ["x", "x"]},
    )
    p.check(
        "v2.5d 同一请求内重复别名被 422 拒绝（不静默去重）",
        dup_alias.status_code == 422,
        f"{dup_alias.status_code} {json.dumps(err(dup_alias), ensure_ascii=False)[:200]}",
    )

    # ------------------------------------------------------------------ F 未找到
    missing = api("GET", "/knowledge-points/nope")
    p.check(
        "v2.6a 不存在知识点 → 404 KNOWLEDGE_POINT_NOT_FOUND",
        missing.status_code == 404 and err(missing).get("code") == "KNOWLEDGE_POINT_NOT_FOUND",
        f"{missing.status_code} {err(missing).get('code')}",
    )
finally:
    client.__exit__(None, None, None)

sys.exit(p.finish())
