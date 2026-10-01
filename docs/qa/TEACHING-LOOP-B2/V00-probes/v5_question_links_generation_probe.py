"""V00-B2 · V5 独立探针：T50 草稿/正式知识点关联与 AI 补题生成链。

全部经真实 HTTP（TestClient，真装配），模型为受控替身；任务经
``GET /workflow-jobs/{id}?domain=question`` 轮询六态。

覆盖：
  1. 草稿关联：提供即整表替换 / 提供 [] 清空 / revision+1 且回 needs_review；
  2. 生成链校验：非法 JSON / 截断 / 数量不符 / 未知知识点 / 虚构证据 / 任意 URL /
     盘符与绝对路径 / 未登记资产 → 整批 failed + **零批次零候选零 provenance**；
  3. 生成成功：批次 needs_review、候选 extraction_method=ai、草稿关联 source=ai、
     provenance source=ai 带 job_id 与模型快照、**候选不进正式题目表**；
  4. 确认入库：草稿关联冻结为 question_knowledge_links（含 subject_id_snapshot/名称快照）；
  5. 改内容复制旧关联 / 显式改关联替换 / 旧修订旧关联不可改（触发器）；
  6. 按知识点检索 GET /questions?knowledgePointId=。
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
_PROBE_TMP = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v5-"))
os.environ["ZQKY_DATA_DIR"] = str(_PROBE_TMP)  # 必须在导入 app.main 之前
sys.path.insert(0, str(REPO / "apps" / "api"))
sys.path.insert(0, str(HERE.parent))

import v00_support as S  # noqa: E402

RESULTS: list[dict] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    ok = bool(condition)
    RESULTS.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:400]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {str(detail)[:220]}")
    return ok


def error_of(response) -> tuple[int, str, dict]:
    body = response.json()
    error = body.get("error") or body
    return response.status_code, error.get("code"), error.get("details") or {}


def question_reply(entries: list[dict]) -> str:
    return json.dumps({"questions": entries}, ensure_ascii=False)


def candidate(stem: str = "1+1=?（V00 探针）", *, knowledge: list[str] | None = None,
              evidence: list[str] | None = None, assets: list[str] | None = None,
              qtype: str = "short_answer") -> dict:
    entry: dict = {
        "type": qtype,
        "stemMarkdown": stem,
        "options": [],
        "answer": {"choiceKeys": [], "accepted": None, "textMarkdown": "2"},
        "explanationMarkdown": None,
        "knowledgePointIds": knowledge or [],
        "evidenceIds": evidence or [],
        "assetIds": assets or [],
    }
    if qtype in ("single_choice", "multiple_choice"):
        entry["options"] = [{"key": "A", "textMarkdown": "甲"}, {"key": "B", "textMarkdown": "乙"}]
        entry["answer"] = {"choiceKeys": ["A"], "accepted": None, "textMarkdown": None}
    return entry


def current_revision_of(har, question_id: str) -> str:
    qb = har.db("question_bank")
    try:
        return qb.execute("SELECT current_revision_id FROM questions WHERE id=?", (question_id,)).fetchone()[0]
    finally:
        qb.close()


def counts(har) -> dict[str, int]:
    qb = har.db("question_bank")
    teaching = har.db("teaching")
    try:
        return {
            "imports": qb.execute("SELECT count(*) FROM question_imports").fetchone()[0],
            "drafts": qb.execute("SELECT count(*) FROM question_drafts").fetchone()[0],
            "provenance": qb.execute("SELECT count(*) FROM question_import_provenance").fetchone()[0],
            "questions": qb.execute("SELECT count(*) FROM questions").fetchone()[0],
            "links": qb.execute("SELECT count(*) FROM question_knowledge_links").fetchone()[0],
            "jobs": qb.execute("SELECT count(*) FROM question_jobs").fetchone()[0],
            "fingerprints": qb.execute("SELECT count(*) FROM question_content_fingerprints").fetchone()[0],
            "teaching_jobs": teaching.execute("SELECT count(*) FROM workflow_jobs").fetchone()[0],
        }
    finally:
        qb.close()
        teaching.close()


def job_error_code(view: dict) -> str | None:
    """通用 JobView 用 error.code，题库域视图用 errorCode；两者都读。"""
    error = view.get("error")
    if isinstance(error, dict) and error.get("code"):
        return error["code"]
    return view.get("errorCode")


def wait_job(har, job_id: str, *, timeout: float = 20.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        response = har.client.get(f"/api/v1/workflow-jobs/{job_id}", params={"domain": "question"})
        assert response.status_code == 200, response.text
        last = response.json()
        if last["state"] in ("succeeded", "failed", "cancelled", "interrupted"):
            return last
        time.sleep(0.05)
    return last


def main(evidence: str) -> int:
    work = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v5-work-"))
    har, provider = S.new_harness("v5", fake_replies=["{}"], with_client=True)
    point_a = har.make_point("V00-KP-A", "函数单调性")
    point_b = har.make_point("V00-KP-B", "导数几何意义")

    base = counts(har)

    def run_generation(body: dict) -> tuple[int, str | None, dict | None]:
        """返回 (HTTP 状态, 错误码, 任务视图)；建任务前被拒时视图为 None。"""
        response = har.client.post("/api/v1/question-generation-jobs", json=body)
        if response.status_code != 202:
            status, code, _details = error_of(response)
            return status, code, None
        view = wait_job(har, response.json()["jobId"])
        return 202, job_error_code(view), view

    # ---------------------------------------------------------------- 生成链校验
    cases = [
        ("V5.1 非法 JSON → GENERATION_INVALID_JSON 且零残留", "这不是 JSON", dict(count=1)),
        ("V5.2 截断 → GENERATION_OUTPUT_TRUNCATED 且零残留",
         (question_reply([candidate(knowledge=[point_a])]), "length"), dict(count=1)),
        ("V5.3 数量不符 → GENERATION_CANDIDATE_COUNT_MISMATCH 且零残留",
         question_reply([candidate(knowledge=[point_a])]), dict(count=2)),
        ("V5.4 未知知识点 → GENERATION_UNKNOWN_KNOWLEDGE 且零残留",
         question_reply([candidate(knowledge=["kp-unknown"])]), dict(count=1, knowledgePointIds=[point_a])),
        ("V5.5 虚构证据 → GENERATION_UNKNOWN_EVIDENCE 且零残留",
         question_reply([candidate(knowledge=[point_a], evidence=["m9"])]),
         dict(count=1, knowledgePointIds=[point_a], materials=["材料：函数 f(x)=x^2。"])),
        ("V5.6 题干含 URL → GENERATION_FORBIDDEN_REFERENCE 且零残留",
         question_reply([candidate("见 http://example.com/a 的说明", knowledge=[point_a])]), dict(count=1)),
        ("V5.7 题干含绝对路径 → GENERATION_FORBIDDEN_REFERENCE 且零残留",
         question_reply([candidate("答案见 /etc/passwd/data 文件", knowledge=[point_a])]), dict(count=1)),
        ("V5.8 题干含盘符路径 → GENERATION_FORBIDDEN_REFERENCE 且零残留",
         question_reply([candidate("见 C:\\data\\paper.docx", knowledge=[point_a])]), dict(count=1)),
        ("V5.9 非法 assetId → GENERATION_ASSET_INVALID 且零残留",
         question_reply([candidate(knowledge=[point_a], assets=["blobs/xyz"])]),
         dict(count=1, knowledgePointIds=[point_a])),
        ("V5.10 未登记资产 → GENERATION_ASSET_NOT_REGISTERED 且零残留",
         question_reply([candidate(knowledge=[point_a], assets=["blobs/" + "a" * 64])]),
         dict(count=1, knowledgePointIds=[point_a])),
        ("V5.11 材料含 URL（输入闸门）→ GENERATION_MATERIAL_INVALID 且零残留",
         question_reply([candidate(knowledge=[point_a])]),
         dict(count=1, materials=["材料见 https://example.com"])),
    ]
    for name, reply, extra in cases:
        provider.handler = None
        provider.replies = [reply]
        body = {"modelProfileId": "v00-fake-profile", "subjectId": "math", **extra}
        before = counts(har)
        status, code, view = run_generation(body)
        after = counts(har)
        delta = {key: after[key] - before[key] for key in ("imports", "drafts", "provenance", "questions", "links")}
        expect_code = name.split("→ ")[1].split(" 且")[0]
        ok = code == expect_code and all(value == 0 for value in delta.values())
        if view is not None:
            ok = ok and view["state"] == "failed"
        else:
            ok = ok and status == 422
        check(name, ok, f"http={status} state={view['state'] if view else None} code={code} delta={delta}")

    # 学科不一致闸门（建任务前即失败，不发上游）
    provider.replies = ["{}"]
    before_calls = len(provider.calls)
    mismatch = har.client.post("/api/v1/question-generation-jobs", json={
        "modelProfileId": "v00-fake-profile", "subjectId": "physics",
        "knowledgePointIds": [point_a], "count": 1})
    status, code, _details = error_of(mismatch)
    check("V5.12 知识点学科与 subjectId 不一致 → 422 KNOWLEDGE_SUBJECT_MISMATCH 且零上游调用",
          status == 422 and code == "KNOWLEDGE_SUBJECT_MISMATCH"
          and len(provider.calls) == before_calls, f"{status}/{code}")

    # ---------------------------------------------------------------- 生成成功
    provider.replies = [question_reply([
        candidate("V00 补题一：函数单调性判断", knowledge=[point_a], evidence=["m0"]),
    ])]
    before = counts(har)
    body = {
        "modelProfileId": "v00-fake-profile", "subjectId": "math",
        "knowledgePointIds": [point_a], "questionTypes": ["short_answer"],
        "difficulty": "easy", "count": 1, "instructions": "V00 探针",
        "materials": ["材料：函数 f(x)=x^2+1 在 R 上先减后增。"],
    }
    created = har.client.post("/api/v1/question-generation-jobs", json=body)
    check("V5.13a 合法补题建任务返回 202", created.status_code == 202, f"{created.status_code} {created.text[:160]}")
    view = wait_job(har, created.json()["jobId"])
    check("V5.13 合法补题 → succeeded 并返回批次 id 与候选数",
          view["state"] == "succeeded" and (view.get("result") or {}).get("importId")
          and (view.get("result") or {}).get("candidateCount") == 1,
          str({k: view[k] for k in ("state", "attempt")}) + str(view.get("result")))
    import_id = (view.get("result") or {}).get("importId")
    detail = har.client.get(f"/api/v1/question-imports/{import_id}").json()
    check("V5.14 批次 state=needs_review，候选 extractionMethod=ai / reviewState=needs_review",
          detail["state"] == "needs_review"
          and all(d["extractionMethod"] == "ai" and d["reviewState"] == "needs_review" for d in detail["drafts"]),
          f"{detail['state']} drafts={[(d['extractionMethod'], d['reviewState']) for d in detail['drafts']]}")
    check("V5.15 候选草稿带 AI 知识点关联（source=ai + 名称/学科快照）",
          all(link["source"] == "ai" and link["subjectIdSnapshot"] == "math"
              and link["knowledgeNameSnapshot"] == "函数单调性"
              for d in detail["drafts"] for link in d["knowledgeLinks"]),
          str([[l["source"], l["subjectIdSnapshot"], l["knowledgeNameSnapshot"]] for d in detail["drafts"] for l in d["knowledgeLinks"]]))
    after = counts(har)
    check("V5.16 候选不自动进正式题目表（questions/links 均 +0）",
          after["questions"] == before["questions"] and after["links"] == before["links"],
          f"questions {before['questions']}→{after['questions']} links {before['links']}→{after['links']}")
    qb = har.db("question_bank")
    try:
        prov = qb.execute(
            "SELECT source, job_id, model_snapshot_json FROM question_import_provenance WHERE import_id=?",
            (import_id,)).fetchone()
    finally:
        qb.close()
    snapshot = json.loads(prov["model_snapshot_json"])
    check("V5.17 生成原件来源 source=ai + job_id + 非敏感模型快照",
          prov is not None and prov["source"] == "ai" and prov["job_id"] == created.json()["jobId"]
          and snapshot.get("fingerprint", "").startswith("sha256:")
          and "apiKey" not in json.dumps(snapshot) and "sk-" not in json.dumps(snapshot),
          f"{prov['source'] if prov else None} {str(snapshot)[:120]}")

    # ---------------------------------------------------------------- 草稿关联整表替换
    draft = detail["drafts"][0]
    content = draft["content"]
    metadata = draft["metadata"]
    patch1 = har.client.patch(f"/api/v1/question-drafts/{draft['draftId']}", json={
        "expectedRevision": draft["revision"], "content": content, "metadata": metadata,
        "knowledgeLinks": [{"knowledgePointId": point_b, "role": "primary"}],
    })
    check("V5.18 草稿关联提供即整表替换（A → B）",
          patch1.status_code == 200 and [l["knowledgePointId"] for l in patch1.json()["knowledgeLinks"]] == [point_b],
          f"{patch1.status_code} {[l['knowledgePointId'][:8] for l in patch1.json().get('knowledgeLinks', [])]}")
    patched = patch1.json()
    patch2 = har.client.patch(f"/api/v1/question-drafts/{draft['draftId']}", json={
        "expectedRevision": patched["revision"], "content": content, "metadata": metadata,
        "reviewState": "reviewed", "knowledgeLinks": [{"knowledgePointId": point_a, "role": "primary"},
                                                       {"knowledgePointId": point_b, "role": "secondary"}],
    })
    check("V5.19 草稿关联可再替换为两条（primary+secondary）且 revision 前进",
          patch2.status_code == 200 and len(patch2.json()["knowledgeLinks"]) == 2
          and patch2.json()["revision"] > patched["revision"],
          f"{patch2.status_code} rev={patched['revision']}→{patch2.json().get('revision')}")
    cleared = har.client.patch(f"/api/v1/question-drafts/{draft['draftId']}", json={
        "expectedRevision": patch2.json()["revision"], "content": content, "metadata": metadata,
        "knowledgeLinks": [],
    })
    check("V5.20 提供 [] 清空草稿关联", cleared.status_code == 200 and cleared.json()["knowledgeLinks"] == [],
          f"{cleared.status_code} {cleared.json().get('knowledgeLinks')}")
    restored = har.client.patch(f"/api/v1/question-drafts/{draft['draftId']}", json={
        "expectedRevision": cleared.json()["revision"], "content": content, "metadata": metadata,
        "reviewState": "reviewed",
        "knowledgeLinks": [{"knowledgePointId": point_a, "role": "primary"},
                           {"knowledgePointId": point_b, "role": "secondary"}],
    })
    check("V5.21 关联变化强制回 needs_review（即使请求显式给 reviewed）",
          restored.status_code == 200 and restored.json()["reviewState"] == "needs_review",
          f"{restored.status_code} {restored.json().get('reviewState')}")
    marked = har.client.patch(f"/api/v1/question-drafts/{draft['draftId']}", json={
        "expectedRevision": restored.json()["revision"], "content": content, "metadata": metadata,
        "reviewState": "reviewed",
    })
    check("V5.21b 内容/关联不变的第二次 PATCH 可标记 reviewed",
          marked.status_code == 200 and marked.json()["reviewState"] == "reviewed"
          and marked.json()["revision"] > restored.json()["revision"],
          f"{marked.status_code} {marked.json().get('reviewState')} rev={restored.json()['revision']}→{marked.json().get('revision')}")

    # ---------------------------------------------------------------- 确认入库
    confirm = har.client.post(f"/api/v1/question-imports/{import_id}/confirm", json={
        "submissionId": "v00-qb-confirm-0001", "importId": import_id,
        "items": [{"draftId": draft["draftId"], "expectedDraftRevision": marked.json()["revision"]}],
    })
    check("V5.22 确认入库成功", confirm.status_code == 200 and len(confirm.json()["confirmedQuestionIds"]) == 1,
          f"{confirm.status_code} {confirm.text[:200]}")
    question_id = confirm.json()["confirmedQuestionIds"][0]
    detail_q = har.client.get(f"/api/v1/questions/{question_id}").json()
    links = detail_q["knowledgeLinks"]
    check("V5.23 确认时把草稿关联冻结为正式关联（含 subject_id_snapshot/名称快照/角色）",
          sorted(l["knowledgePointId"] for l in links) == sorted([point_a, point_b])
          and all(l["subjectIdSnapshot"] == "math" and l["knowledgeNameSnapshot"] in ("函数单调性", "导数几何意义")
                  for l in links)
          and {l["role"] for l in links} == {"primary", "secondary"},
          str([(l["knowledgePointId"][:6], l["role"], l["subjectIdSnapshot"]) for l in links]))
    old_revision_id = current_revision_of(har, question_id)

    # 按知识点检索
    by_a = har.client.get("/api/v1/questions", params={"knowledgePointId": point_a}).json()
    by_missing = har.client.get("/api/v1/questions", params={"knowledgePointId": "kp-none"}).json()
    check("V5.24 GET /questions?knowledgePointId= 命中该题；未知知识点返回空",
          any(item["questionId"] == question_id for item in by_a["questions"]) and by_missing["total"] == 0,
          f"hit={by_a['total']} miss={by_missing['total']}")

    # ---------------------------------------------------------------- 改题：复制 / 替换
    patch_content = dict(detail_q["content"], stemMarkdown="V00 改后题干：函数单调性判断（修订二）")
    copy_patch = har.client.patch(f"/api/v1/questions/{question_id}", json={
        "expectedRevision": detail_q["revision"], "content": patch_content, "metadata": detail_q["metadata"],
    })
    check("V5.25 改内容（缺省）→ 新修订并复制旧正式关联",
          copy_patch.status_code == 200
          and sorted(l["knowledgePointId"] for l in copy_patch.json()["knowledgeLinks"]) == sorted([point_a, point_b])
          and current_revision_of(har, question_id) != old_revision_id,
          f"{copy_patch.status_code} links={[l['knowledgePointId'][:6] for l in copy_patch.json().get('knowledgeLinks', [])]}")
    replaced = har.client.patch(f"/api/v1/questions/{question_id}", json={
        "expectedRevision": copy_patch.json()["revision"],
        "content": dict(copy_patch.json()["content"], stemMarkdown="V00 改后题干：只挂 B"),
        "metadata": copy_patch.json()["metadata"],
        "knowledgeLinks": [{"knowledgePointId": point_b, "role": "primary"}],
    })
    check("V5.26 显式提供 knowledgeLinks → 整表替换为新关联",
          replaced.status_code == 200
          and [l["knowledgePointId"] for l in replaced.json()["knowledgeLinks"]] == [point_b],
          f"{replaced.status_code} {[l['knowledgePointId'][:6] for l in replaced.json().get('knowledgeLinks', [])]}")
    qb = har.db("question_bank")
    try:
        old_rev_links = qb.execute(
            "SELECT count(*) FROM question_knowledge_links WHERE question_revision_id=?", (old_revision_id,)).fetchone()[0]
        new_rev_id = qb.execute("SELECT current_revision_id FROM questions WHERE id=?",
                                (question_id,)).fetchone()[0]
        new_rev_links = qb.execute(
            "SELECT knowledge_point_id FROM question_knowledge_links WHERE question_revision_id=?",
            (new_rev_id,)).fetchall()
    finally:
        qb.close()
    check("V5.27 旧修订的正式关联未被改动（2 条仍在），新修订只有 1 条",
          old_rev_links == 2 and [row[0] for row in new_rev_links] == [point_b],
          f"old={old_rev_links} new={[r[0][:6] for r in new_rev_links]}")

    # 直写触发器：正式关联不可改/删
    conn = sqlite3.connect(str(har.root / "data" / "question-bank" / "question-bank.sqlite3"))
    try:
        for label, sql in (
            ("V5.28 直写 UPDATE question_knowledge_links 被拒",
             "UPDATE question_knowledge_links SET role='secondary' WHERE question_revision_id=?"),
            ("V5.29 直写 DELETE question_knowledge_links 被拒",
             "DELETE FROM question_knowledge_links WHERE question_revision_id=?"),
        ):
            try:
                conn.execute("PRAGMA foreign_keys=ON")
                conn.execute(sql, (old_revision_id,))
                conn.commit()
                check(label, False, "语句被接受（缺陷）")
            except sqlite3.IntegrityError as exc:
                check(label, "IMMUTABLE_REVISION" in str(exc), str(exc)[:120])
    finally:
        conn.close()

    # 派生指纹
    qb = har.db("question_bank")
    try:
        fp_rows = qb.execute(
            "SELECT algorithm_version, fingerprint FROM question_content_fingerprints WHERE question_revision_id=?",
            (current_revision_of(har, question_id),)).fetchall()
    finally:
        qb.close()
    check("V5.30 正式修订写入版本化派生指纹", len(fp_rows) >= 1 and all(
        row["algorithm_version"] and len(row["fingerprint"]) == 64 for row in fp_rows),
        str([(row["algorithm_version"], row["fingerprint"][:12]) for row in fp_rows]))

    har.close()
    return finish(evidence)


def finish(evidence: str, reason: str = "") -> int:
    failed = [row for row in RESULTS if row["status"] == "FAIL"]
    print(f"\n== v5_question_links_generation_probe: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed; "
          f"failed={[row['name'] for row in failed]} {reason} ==")
    if evidence:
        target = Path(evidence)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"probe": "v5_question_links_generation_probe", "results": RESULTS},
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
