"""V8 施测契约探针（TEACHING-LOOP B1 / V00）。

- ``POST /api/v1/assessments``（及 GET/PATCH/PUT/DELETE）真 HTTP 501 FEATURE_NOT_IMPLEMENTED，
  不是 200/空对象；路由表里没有 assessments 的真实现。
- ``UnavailablePaperReader`` 任何调用 → 501 PAPER_READER_UNAVAILABLE。
- 未装配状态（``bootstrap_textbooks=False``）：knowledge / roster 路由 503 SERVICE_UNAVAILABLE，
  不返回空列表。
- 施测三表（assessments/assessment_classes/assessment_participants）不在本批迁移。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_common import Probe, ensure_api_on_path, temp_data_root  # noqa: E402

p = Probe("v8_assessment_contract")
root = temp_data_root("v8")
ensure_api_on_path()

from fastapi.testclient import TestClient  # noqa: E402

from app.contracts.roster import (  # noqa: E402
    ConfirmedPaperRevisionView,
    UnavailablePaperReader,
)
from app.core.config import Settings  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.main import create_app  # noqa: E402

ALLOWED = frozenset({"http://127.0.0.1:5173", "http://127.0.0.1:5174"})
settings = Settings(host="127.0.0.1", port=8001, allowed_origins=ALLOWED, env="test", data_dir=root / "data")

client = TestClient(create_app(settings), base_url="http://127.0.0.1:8001")
client.__enter__()
try:
    for method in ("post", "get", "patch", "put", "delete"):
        response = client.request(method, "/api/v1/assessments", json={"paperRevisionId": "p1"})
        body = response.json()
        p.check(
            f"v8.1 {method.upper()} /api/v1/assessments → 501 FEATURE_NOT_IMPLEMENTED",
            response.status_code == 501 and body.get("code") == "FEATURE_NOT_IMPLEMENTED",
            f"{response.status_code} {json.dumps(body, ensure_ascii=False)[:160]}",
        )
    assessment_paths = [
        route.path
        for route in client.app.routes
        if "assessment" in getattr(route, "path", "")
    ]
    p.check(
        "v8.2 路由表没有 assessments 真实现（只有通配占位）",
        assessment_paths == [] or all("{" in path for path in assessment_paths),
        json.dumps(assessment_paths),
    )
    unknown = client.get("/api/v1/not-a-real-endpoint")
    p.check(
        "v8.3 未知 /api/v1 路径同样 501（不返回 404/空 200）",
        unknown.status_code == 501 and unknown.json().get("code") == "FEATURE_NOT_IMPLEMENTED",
        f"{unknown.status_code} {unknown.json().get('code')}",
    )
    created = client.post(
        "/api/v1/knowledge-points",
        json={"subjectId": "math", "code": "V8-1", "name": "施测契约探针"},
    )
    p.check(
        "v8.4 全套装配下知识点路由可用（对照：同 app 内 501 是施测专属）",
        created.status_code == 201,
        f"{created.status_code}",
    )
finally:
    client.__exit__(None, None, None)

# ------------------------------------------------------------------ UnavailablePaperReader
reader = UnavailablePaperReader()
raised = None
try:
    reader.read_confirmed_paper_revision("paper-rev-1")
except AppError as exc:
    raised = exc
p.check(
    "v8.5 UnavailablePaperReader → 501 PAPER_READER_UNAVAILABLE（不伪造原卷）",
    raised is not None
    and raised.code == "PAPER_READER_UNAVAILABLE"
    and raised.status_code == 501,
    f"{type(raised).__name__}: {getattr(raised, 'code', None)} {raised}",
)
p.check(
    "v8.6 端口返回类型符合契约（ConfirmedPaperRevisionView 字段可构造）",
    set(ConfirmedPaperRevisionView.model_fields)
    == {"paper_id", "paper_revision_id", "title", "subject_id", "total_score_units", "scored_leaf_count"},
    json.dumps(sorted(ConfirmedPaperRevisionView.model_fields)),
)

# ------------------------------------------------------------------ 未装配状态
unassembled = Settings(
    host="127.0.0.1", port=8001, allowed_origins=ALLOWED, env="test", data_dir=root / "bare"
)
bare_client = TestClient(create_app(unassembled, bootstrap_textbooks=False), base_url="http://127.0.0.1:8001")
bare_client.__enter__()
try:
    probes = [
        ("GET", "/api/v1/knowledge-points", None),
        ("POST", "/api/v1/knowledge-points", {"subjectId": "math", "code": "X-1", "name": "n"}),
        ("GET", "/api/v1/classes", None),
        ("POST", "/api/v1/classes", {"code": "C1", "name": "班", "schoolYear": "2026-2027", "gradeId": "g1"}),
        ("GET", "/api/v1/students", None),
        ("GET", "/api/v1/roster-imports", None),
    ]
    for method, path, payload in probes:
        response = bare_client.request(method, path, json=payload) if payload else bare_client.request(method, path)
        body = response.json()
        p.check(
            f"v8.7 未装配 {method} {path} → 503 SERVICE_UNAVAILABLE（不是空列表）",
            response.status_code == 503
            and body.get("code") == "SERVICE_UNAVAILABLE"
            and "items" not in body,
            f"{response.status_code} {json.dumps(body, ensure_ascii=False)[:160]}",
        )
    # 记录：POST 体不合法时 FastAPI 先做 422 校验（未到服务解析），这是框架顺序而非假成功
    malformed = bare_client.post("/api/v1/knowledge-points", json={})
    p.check(
        "v8.7b 未装配 + 请求体不合法 → 422 校验优先（记录顺序，不视为假成功）",
        malformed.status_code == 422 and malformed.json().get("code") == "INVALID_REQUEST",
        f"{malformed.status_code} {malformed.json().get('code')}",
    )
    bare_assessment = bare_client.post("/api/v1/assessments", json={})
    p.check(
        "v8.8 未装配下施测仍是 501（不是 503——无服务可缺）",
        bare_assessment.status_code == 501
        and bare_assessment.json().get("code") == "FEATURE_NOT_IMPLEMENTED",
        f"{bare_assessment.status_code} {bare_assessment.json().get('code')}",
    )
finally:
    bare_client.__exit__(None, None, None)

# ------------------------------------------------------------------ 施测三表不在本批
teaching_db = root / "data" / "teaching" / "teaching.sqlite3"
conn = sqlite3.connect(str(teaching_db))
tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
conn.close()
p.check(
    "v8.9 教学库不含施测三表（assessments/assessment_classes/assessment_participants）",
    not ({"assessments", "assessment_classes", "assessment_participants"} & tables),
    json.dumps(sorted(tables)),
)

sys.exit(p.finish())
