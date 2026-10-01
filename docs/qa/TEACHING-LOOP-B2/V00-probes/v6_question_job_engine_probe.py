"""V00-B2 · V6 独立探针：T50 统一任务（JobEngine）六态 / 取消 / 重启收敛 / 旧 checkpoint。

真装配 + 真 HTTP（长驻 TestClient portal，后台任务才会真正跑完）；模型受控替身，
其回复**从真实提示词里读块 id**，避免伪造来源。

覆盖：
  1. organize 经统一引擎：attempt / 六态视图 / 冻结输入含契约版本与模型指纹；
  2. model 名额并发上限 = 1（两个模型任务并发时上游调用不重叠）；
  3. 取消：queued 立即 cancelled（零上游调用）；running 期间取消 → 批间/迟到不发布；
  4. 重启收敛：造 running → reconcile → interrupted（不重叫模型）→ 显式 recover → succeeded；
  5. 旧语义 checkpoint → ORGANIZER_MODEL_RESELECT_REQUIRED 且 provider 零调用。
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
_PROBE_TMP = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v6-"))
os.environ["ZQKY_DATA_DIR"] = str(_PROBE_TMP)  # 必须在导入 app.main 之前
sys.path.insert(0, str(REPO / "apps" / "api"))
sys.path.insert(0, str(HERE.parent))

import v00_support as S  # noqa: E402

from app.schemas.question_bank import OrganizeRequest  # noqa: E402

RESULTS: list[dict] = []
SIX_STATES = {"queued", "running", "succeeded", "failed", "cancelled", "interrupted"}

MARKDOWN = """1. V00 探针题一
下列说法正确的是（ ）
A. 甲
B. 乙
2. V00 探针题二
函数 f(x)=x^2 的导数是（ ）
A. 2x
B. x
"""


def check(name: str, condition: bool, detail: str = "") -> bool:
    ok = bool(condition)
    RESULTS.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:400]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {str(detail)[:220]}")
    return ok


def organizer_reply(user_text: str, *, stem: str = "V00 整理题干") -> str:
    block_ids = re.findall(r"\[块 ([^\]]+)\]", user_text)
    return json.dumps({
        "type": "short_answer",
        "stem": stem,
        "options": [],
        "answer": None,
        "explanation": None,
        "sourceBlockIds": block_ids[:1],
    }, ensure_ascii=False)


def make_import(har, name: str, text: str = MARKDOWN) -> str:
    data, content_type = S.multipart({"subjectId": "math", "gradeId": "senior-1"},
                                     {"file": (name, text.encode("utf-8"), "text/markdown")})
    response = har.client.post("/api/v1/question-imports", content=data,
                               headers={"content-type": content_type})
    assert response.status_code == 201, response.text
    return response.json()["importId"]


def latest_organize_job(har):
    qb = har.db("question_bank")
    try:
        row = qb.execute(
            "SELECT id, state, attempt, error_code, checkpoint_json, frozen_input_json, "
            "model_snapshot_json, lease_token FROM question_jobs WHERE kind='organize' "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1").fetchone()
        return dict(row) if row else None
    finally:
        qb.close()


def job_row(har, job_id: str):
    qb = har.db("question_bank")
    try:
        row = qb.execute("SELECT * FROM question_jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        qb.close()


def suggestion_count(har, job_id: str) -> int:
    qb = har.db("question_bank")
    try:
        return qb.execute("SELECT count(*) FROM question_suggestions WHERE organization_job_id=?",
                          (job_id,)).fetchone()[0]
    finally:
        qb.close()


def main(evidence: str) -> int:
    har, provider = S.new_harness("v6", fake_replies=["{}"], with_client=True)
    service = har.app.state.question_bank_service
    portal = har.client.portal

    # ---------------------------------------------------------------- 1. organize 正常
    import_id = make_import(har, "v00-organize.md")
    provider.handler = _noop_handler
    response = har.client.post(f"/api/v1/question-imports/{import_id}/organize",
                               json={"modelProfileId": "v00-fake-profile"})
    view = response.json()
    check("V6.1 organize 返回六态视图 + attempt（succeeded，建议数 ≥1）",
          response.status_code == 200 and view["state"] == "succeeded"
          and view["suggestionCount"] >= 1 and isinstance(view["attempt"], int) and view["attempt"] >= 1,
          str({k: view[k] for k in ("jobId", "state", "attempt", "suggestionCount", "failedBatches")}))
    job_id = view["jobId"]
    record = latest_organize_job(har)
    frozen = json.loads(record["frozen_input_json"])
    snapshot = json.loads(record["model_snapshot_json"])
    check("V6.2 冻结输入含契约版本/模型 profile 与指纹/批次快照（checkpoint 冻结）",
          frozen.get("contractVersion") == 2 and frozen.get("modelProfileId") == "v00-fake-profile"
          and str(frozen.get("modelFingerprint", "")).startswith("sha256:")
          and isinstance(frozen.get("batches"), list) and frozen["batches"]
          and snapshot.get("profileId") == "v00-fake-profile",
          f"contract={frozen.get('contractVersion')} batches={len(frozen.get('batches') or [])} "
          f"fp={str(frozen.get('modelFingerprint'))[:16]}")
    generic = har.client.get(f"/api/v1/workflow-jobs/{job_id}", params={"domain": "question"}).json()
    check("V6.3 公共任务视图：状态在六态集合内且 attempt 一致",
          generic["state"] in SIX_STATES and generic["attempt"] == view["attempt"],
          f"{generic['state']} attempt={generic['attempt']}")

    # ---------------------------------------------------------------- 2. model 名额并发上限
    concurrency = {"current": 0, "max": 0, "calls": 0, "events": []}
    lock = threading.Lock()

    async def counting_handler(request):
        with lock:
            concurrency["current"] += 1
            concurrency["calls"] += 1
            concurrency["max"] = max(concurrency["max"], concurrency["current"])
            concurrency["events"].append(("start", concurrency["calls"]))
        try:
            import asyncio as _a
            await _a.sleep(0.4)
            user = request.messages[-1].content
            return organizer_reply(user, stem="V00 并发探针"), "stop"
        finally:
            with lock:
                concurrency["current"] -= 1
                concurrency["events"].append(("end", concurrency["calls"]))

    provider.handler = counting_handler
    import_a = make_import(har, "v00-conc-a.md")
    import_b = make_import(har, "v00-conc-b.md")
    outcomes: dict[str, object] = {}

    def worker(key: str, target: str):
        try:
            outcomes[key] = portal.call(service.organize, target,
                                        OrganizeRequest(modelProfileId="v00-fake-profile"))
        except Exception as exc:  # noqa: BLE001
            outcomes[key] = exc

    threads = [threading.Thread(target=worker, args=("a", import_a)),
               threading.Thread(target=worker, args=("b", import_b))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    events = concurrency["events"]
    proper = True
    open_call = None
    for kind, seq in events:
        if kind == "start":
            if open_call is not None:
                proper = False
            open_call = seq
        else:
            if open_call != seq:
                proper = False
            open_call = None
    check("V6.4 model 名额上限 = 1：两个并发模型任务的模型调用严格串行（不重叠）",
          concurrency["max"] == 1 and concurrency["calls"] == 4 and proper and open_call is None
          and all(not isinstance(value, Exception) for value in outcomes.values()),
          f"max_concurrent={concurrency['max']} calls={concurrency['calls']} "
          f"trace={events} states={[getattr(v, 'state', v) for v in outcomes.values()]}")
    provider.handler = None

    # ---------------------------------------------------------------- 3a. queued 立即取消
    import_q = make_import(har, "v00-cancel-queued.md")
    # 用真实路径准备一份合法冻结输入（跑一次失败的 organize，保留 frozen_input）
    async def boom(request):
        raise RuntimeError("V00 探针：故意上游崩溃")

    provider.handler = boom
    portal.call(service.organize, import_q, OrganizeRequest(modelProfileId="v00-fake-profile"))
    failed_row = latest_organize_job(har)
    store = har.app.state.job_engine.store("question")
    queued = store.create(kind="organize",
                          frozen_input=json.loads(failed_row["frozen_input_json"]),
                          model_snapshot=json.loads(failed_row["model_snapshot_json"]),
                          owner_id="local")
    calls_before = len(provider.calls)
    cancel = har.client.post(f"/api/v1/workflow-jobs/{queued.job_id}/cancel", json={"domain": "question"})
    after = job_row(har, queued.job_id)
    check("V6.5 queued 任务取消 → 立即 cancelled 且零上游调用",
          cancel.status_code == 200 and cancel.json()["state"] == "cancelled"
          and after["state"] == "cancelled" and len(provider.calls) == calls_before,
          f"{cancel.status_code} {cancel.json()['state']}")
    provider.handler = None

    # ---------------------------------------------------------------- 3b. running 取消（迟到不发布）
    import_r = make_import(har, "v00-cancel-running.md")
    release = threading.Event()
    started = threading.Event()

    async def gated(request):
        started.set()
        import asyncio as _a
        await _a.to_thread(release.wait, 30)
        return organizer_reply(request.messages[-1].content, stem="V00 取消探针"), "stop"

    provider.handler = gated
    running_out: dict[str, object] = {}

    def running_worker():
        try:
            running_out["view"] = portal.call(service.organize, import_r,
                                              OrganizeRequest(modelProfileId="v00-fake-profile"))
        except Exception as exc:  # noqa: BLE001
            running_out["error"] = exc

    thread = threading.Thread(target=running_worker)
    thread.start()
    started.wait(15)
    time.sleep(0.2)
    live = latest_organize_job(har)
    calls_before = len(provider.calls)
    cancel_running = har.client.post(f"/api/v1/workflow-jobs/{live['id']}/cancel",
                                     json={"domain": "question"})
    release.set()
    thread.join(timeout=60)
    final = job_row(har, live["id"])
    check("V6.6 running 任务取消 → 终态 cancelled 且零建议落库（迟到结果不发布）",
          cancel_running.status_code == 200 and final["state"] == "cancelled"
          and suggestion_count(har, live["id"]) == 0,
          f"cancel={cancel_running.json().get('state')} final={final['state']} "
          f"suggestions={suggestion_count(har, live['id'])}")
    check("V6.7 取消只影响在飞调用：provider 调用数未额外增加",
          len(provider.calls) == calls_before + 0, f"{calls_before} → {len(provider.calls)}")
    provider.handler = None

    # ---------------------------------------------------------------- 4. 重启收敛 + 显式恢复
    import_c = make_import(har, "v00-restart.md")
    provider.replies = ["{}"]
    provider.handler = boom
    portal.call(service.organize, import_c, OrganizeRequest(modelProfileId="v00-fake-profile"))
    seed_row = latest_organize_job(har)
    restart_job = store.create(kind="organize",
                               frozen_input=json.loads(seed_row["frozen_input_json"]),
                               model_snapshot=json.loads(seed_row["model_snapshot_json"]),
                               owner_id="local")
    qb = har.db("question_bank")
    try:
        qb.execute("UPDATE question_jobs SET state='running', attempt=1, lease_token='v00-stale-lease', "
                   "lease_expires_at='2099-01-01T00:00:00Z', started_at='2026-10-01T00:00:00Z' WHERE id=?",
                   (restart_job.job_id,))
        qb.commit()
    finally:
        qb.close()
    provider.handler = None
    calls_before = len(provider.calls)
    interrupted = store.reconcile_interrupted()
    after_reconcile = job_row(har, restart_job.job_id)
    check("V6.8 重启收敛：running → interrupted 且不重叫模型",
          restart_job.job_id in interrupted and after_reconcile["state"] == "interrupted"
          and len(provider.calls) == calls_before,
          f"reconciled={len(interrupted)} state={after_reconcile['state']} calls={len(provider.calls)}")
    check("V6.9 重复 reconcile 幂等（第二次不再返回该任务）",
          restart_job.job_id not in store.reconcile_interrupted(), "")
    provider.handler = _noop_handler
    recovered = portal.call(service.recover_organize_jobs)
    after_recover = job_row(har, restart_job.job_id)
    check("V6.10 显式 recover → succeeded 且 attempt 递增（保留冻结输入）",
          after_recover["state"] == "succeeded" and after_recover["attempt"] >= 2
          and suggestion_count(har, restart_job.job_id) >= 1,
          f"recovered={recovered} state={after_recover['state']} attempt={after_recover['attempt']}")
    provider.handler = None

    # ---------------------------------------------------------------- 5. 旧 checkpoint
    import_l = make_import(har, "v00-legacy.md")
    legacy = store.create(kind="organize",
                          frozen_input={"contractVersion": 1, "modelName": "legacy-model",
                                        "batches": [{"index": 0, "draftId": "d0", "blockIds": ["b0"],
                                                     "inputText": "旧语义"}]},
                          model_snapshot={"profileId": "legacy-model"},
                          owner_id="local")
    calls_before = len(provider.calls)
    stale_view = portal.call(service.run_organize_job, legacy.job_id)
    stale_row = job_row(har, legacy.job_id)
    check("V6.11 旧语义 checkpoint → ORGANIZER_MODEL_RESELECT_REQUIRED 且 provider 零调用",
          stale_view.state == "failed"
          and (stale_view.errorCode == "ORGANIZER_MODEL_RESELECT_REQUIRED")
          and len(provider.calls) == calls_before,
          f"state={stale_view.state} code={stale_view.errorCode} calls+{len(provider.calls) - calls_before}")
    checkpoint = json.loads(stale_row["checkpoint_json"])
    check("V6.12 旧 checkpoint 不回写伪造指纹，只标记需重新选择模型",
          checkpoint.get("needsModelReselection") is True
          and "modelFingerprint" not in checkpoint and "frozen" not in json.dumps(checkpoint),
          str({k: checkpoint.get(k) for k in ("needsModelReselection", "contractVersion")}))
    unchanged_frozen = json.loads(stale_row["frozen_input_json"])
    check("V6.13 旧任务冻结输入未被改写（仍是旧语义）",
          unchanged_frozen.get("contractVersion") == 1, str(unchanged_frozen)[:120])
    recovered_stale = portal.call(service.recover_organize_jobs)
    stale_again = job_row(har, legacy.job_id)
    check("V6.14 显式 recover 对旧 checkpoint 也只标重选（不重叫模型）",
          stale_again["state"] == "failed" and len(provider.calls) == calls_before,
          f"recovered={recovered_stale} state={stale_again['state']} calls+{len(provider.calls) - calls_before}")

    har.close()
    return finish(evidence)


async def _noop_handler(request) -> tuple[str, str]:
    """从真实提示词里读块 id 再回答（受控替身，不伪造来源）。"""
    return organizer_reply(request.messages[-1].content), "stop"


def finish(evidence: str, reason: str = "") -> int:
    failed = [row for row in RESULTS if row["status"] == "FAIL"]
    print(f"\n== v6_question_job_engine_probe: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed; "
          f"failed={[row['name'] for row in failed]} {reason} ==")
    if evidence:
        target = Path(evidence)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"probe": "v6_question_job_engine_probe", "results": RESULTS},
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
