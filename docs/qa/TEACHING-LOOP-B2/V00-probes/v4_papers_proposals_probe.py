"""V00-B2 · V4 独立探针：T40 AI 知识点建议与 ConfirmedPaperReader（受控替身）。

不经 TestClient（任务引擎的并发名额信号量必须绑定到本探针自己的事件循环），
直接驱动 ``app.state.paper_service`` 与任务引擎；模型一律受控替身，不联网。

覆盖：
  1. 四类非法/截断输出 → 任务 failed（稳定错误码）+ ai_proposals 零行；
  2. 发布期冻结失败（草稿在建议生成期间被改） → PAPER_PROPOSAL_STALE + 零建议；
  3. 应用前 revision 变化 → 409 PAPER_PROPOSAL_STALE；选择与建议不符 → 422；
     非计分题 → 422；新知识点候选不创建知识点；
  4. apply 写入 ai_confirmed 关联；reject 置 rejected；重复 apply/reject → 409；
  5. ConfirmedPaperReader：不存在 → 404；draft → 422；confirmed → 真实标题/学科/计数；
     损坏库（触发器被移除）下的零总分/无计分叶 → 422（纵深防御）。
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
_PROBE_TMP = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v4-"))
os.environ["ZQKY_DATA_DIR"] = str(_PROBE_TMP)  # 必须在导入 app.main 之前
sys.path.insert(0, str(REPO / "apps" / "api"))
sys.path.insert(0, str(HERE.parent))

import v00_support as S  # noqa: E402

from app.contracts.papers import (  # noqa: E402
    PaperConfirmRequest,
    PaperDraftPatchRequest,
    PaperProposalDecisionRequest,
    PaperProposalJobRequest,
)
from app.core.exceptions import AppError  # noqa: E402

RESULTS: list[dict] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    ok = bool(condition)
    RESULTS.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:400]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {str(detail)[:220]}")
    return ok


def proposal_count(har) -> int:
    conn = har.db("teaching")
    try:
        return conn.execute("SELECT count(*) FROM ai_proposals").fetchone()[0]
    finally:
        conn.close()


def knowledge_count(har) -> int:
    conn = har.db("knowledge")
    try:
        return conn.execute("SELECT count(*) FROM knowledge_points").fetchone()[0]
    finally:
        conn.close()


async def wait_job(har, job_id: str, *, timeout: float = 15.0):
    store = har.app.state.job_engine.store("teaching")
    waited = 0.0
    while waited < timeout:
        record = store.get(job_id)
        if record.state in ("succeeded", "failed", "cancelled", "interrupted"):
            return record
        await asyncio.sleep(0.05)
        waited += 0.05
    return store.get(job_id)


async def run_job(har, service, paper_id: str, revision: int):
    view = await service.create_proposal_job(
        paper_id, PaperProposalJobRequest(modelProfileId="v00-fake-profile", expectedRevision=revision)
    )
    return view, await wait_job(har, view.job_id)


async def main(evidence: str) -> int:
    work = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v4-work-"))
    sample = S.build_sample_docx(work / "v00-sample.docx")
    har, provider = S.new_harness("v4", fake_replies=["{}"])
    service = har.app.state.paper_service
    point_a = har.make_point("V00-KP-A", "函数单调性")
    point_b = har.make_point("V00-KP-B", "导数几何意义")

    state = S.prepare_ready_draft(har, sample, point_a=point_a, point_b=point_b)
    paper_id = state["paper_id"]
    items = state["items"]
    item_16_1 = items["16(1)"]
    item_16_2 = items["16(2)"]
    item_17 = items["17"]

    def current_revision() -> int:
        return service.get_paper(paper_id).revision

    def valid_reply(entries: list[dict]) -> str:
        return json.dumps({"items": entries}, ensure_ascii=False)

    # ---------------------------------------------------------------- 非法输出（0 建议）
    illegal_cases = [
        ("V4.1 非法 JSON → 任务 failed 且零建议", "这不是 JSON"),
        ("V4.2 截断（finishReason=length）→ 任务 failed 且零建议",
         (valid_reply([{"itemId": item_16_1, "knowledgePointId": point_a}]), "length")),
        ("V4.3 JSON 非对象 → 任务 failed 且零建议", json.dumps([1, 2, 3])),
        ("V4.4 未知知识点id → 任务 failed 且零建议",
         valid_reply([{"itemId": item_16_1, "knowledgePointId": "kp-unknown"}])),
        ("V4.5 未知题目id → 任务 failed 且零建议",
         valid_reply([{"itemId": "no-such-item", "knowledgePointId": point_a}])),
        ("V4.6 证据越界 → 任务 failed 且零建议",
         valid_reply([{"itemId": item_16_1, "knowledgePointId": point_a, "evidence": ["no-such-item"]}])),
        ("V4.7 既无既有知识点也无新候选 → 任务 failed 且零建议",
         valid_reply([{"itemId": item_16_1}])),
    ]
    for name, reply in illegal_cases:
        provider.handler = None
        provider.replies = [reply]
        before = proposal_count(har)
        view, record = await run_job(har, service, paper_id, current_revision())
        after = proposal_count(har)
        check(name, record.state == "failed" and after == before and record.error_code == "PAPER_PROPOSAL_INVALID",
              f"state={record.state} code={record.error_code} proposals={before}->{after}")

    # ---------------------------------------------------------------- 发布期 stale（零建议）
    gate = asyncio.Event()
    captured: dict = {}

    async def gated(request):
        captured["request"] = request
        await gate.wait()
        return valid_reply([{"itemId": item_16_1, "knowledgePointId": point_b}]), "stop"

    provider.handler = gated
    before_revision = current_revision()
    before_proposals = proposal_count(har)
    view = await service.create_proposal_job(
        paper_id, PaperProposalJobRequest(modelProfileId="v00-fake-profile", expectedRevision=before_revision))
    waited = 0.0
    while "request" not in captured and waited < 10:
        await asyncio.sleep(0.05)
        waited += 0.05
    check("V4.8 建议任务已开始（模型调用已发生）", "request" in captured, f"waited={waited:.2f}s")
    # 在此期间教师改了草稿（revision+1）
    bumped = service.patch_draft(
        paper_id,
        PaperDraftPatchRequest(expectedRevision=before_revision, title="V00 建议期间被改"),
    )
    check("V4.9 建议期间草稿被改（revision 前进）", bumped.title == "V00 建议期间被改",
          f"rev {before_revision} → {current_revision()}")
    gate.set()
    record = await wait_job(har, view.job_id, timeout=5.0)
    check("V4.10a 发布期冻结失败：任务未 succeeded 且零建议（无半批结果）",
          record.state != "succeeded" and proposal_count(har) == before_proposals,
          f"state={record.state} code={record.error_code} proposals={proposal_count(har)}")
    observation_publish_stuck = record.state
    check("V4.10b 登记边界核对：发布失败后任务停在 running（引擎按异常上抛、由重启收敛）",
          record.state in ("running", "failed", "interrupted"),
          f"state={record.state}（README §5.3：publish 失败收尾只在 question 域）")
    provider.handler = None

    # 用真实执行器 + 真实发布回调直接跑一轮，捕获发布期错误码（同一个 ProposalRunner）
    from app.services.jobs.engine import JobEngine as _JobEngine  # noqa: F401
    from app.services.papers.proposals import ProposalRunner
    store = har.app.state.job_engine.store("teaching")
    conn = har.db("teaching")
    try:
        sample_row = conn.execute(
            "SELECT frozen_input_json, model_snapshot_json FROM workflow_jobs "
            "WHERE kind='paper_mapping' AND state IN ('running','succeeded','failed') "
            "ORDER BY created_at DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    copied_input = json.loads(sample_row["frozen_input_json"])
    copied_input["baseRevision"] = current_revision()
    copied_input["paperRevisionId"] = state["revision_id"]
    copied_snapshot = json.loads(sample_row["model_snapshot_json"])
    runner_job = store.create(kind="paper_mapping", frozen_input=copied_input,
                              model_snapshot=copied_snapshot, owner_id="local")
    provider.replies = [valid_reply([{"itemId": item_16_1, "knowledgePointId": point_a}])]
    # 先把草稿推进一格，制造"发布时 baseRevision 已过期"
    service.patch_draft(paper_id, PaperDraftPatchRequest(expectedRevision=current_revision()))
    proposals_before_direct = proposal_count(har)
    captured_error = None
    runner = ProposalRunner(resolve_model=service._resolve_model_for_job,  # noqa: SLF001
                            publish_proposal=service._publish_proposal)  # noqa: SLF001
    try:
        await har.app.state.job_engine.run_job("teaching", runner_job.job_id, runner, uses_model=True)
    except AppError as exc:
        captured_error = exc
    except Exception as exc:  # noqa: BLE001
        captured_error = exc
    check("V4.10c 发布期 baseRevision 过期 → PAPER_PROPOSAL_STALE（真实发布回调抛出）",
          captured_error is not None and getattr(captured_error, "code", None) == "PAPER_PROPOSAL_STALE"
          and getattr(captured_error, "status_code", None) == 409,
          f"{type(captured_error).__name__} {getattr(captured_error, 'code', None)} "
          f"{getattr(captured_error, 'status_code', None)}")
    check("V4.10d 发布回滚后零建议写入",
          proposal_count(har) == proposals_before_direct, f"{proposals_before_direct} → {proposal_count(har)}")

    # ---------------------------------------------------------------- 正常建议 + 应用
    provider.replies = [valid_reply([
        {"itemId": item_17, "knowledgePointId": point_b, "evidence": [item_17], "ambiguity": False},
        {"itemId": item_16_2, "proposedCode": "V00-NEW-1", "proposedName": "待确认的新知识点",
         "evidence": [item_16_2]},
    ])]
    knowledge_before = knowledge_count(har)
    view, record = await run_job(har, service, paper_id, current_revision())
    check("V4.11 合法建议 → 任务 succeeded 且建议仅进 ai_proposals(pending)",
          record.state == "succeeded" and proposal_count(har) == 1,
          f"state={record.state} proposals={proposal_count(har)} {str(record.result)[:160]}")
    proposal_id = (record.result or {}).get("proposalId")
    proposal = service.get_proposal(proposal_id)
    check("V4.12 建议视图：既有知识点 + 新知识点候选 + 证据 + 不 stale",
          proposal.state == "pending" and proposal.stale is False and len(proposal.items) == 2
          and any(entry.knowledge_point_id == point_b for entry in proposal.items)
          and any(entry.proposed_code == "V00-NEW-1" for entry in proposal.items),
          str([(e.item_id[:6], e.knowledge_point_id, e.proposed_code) for e in proposal.items]))

    # 应用前 revision 变化 → stale
    service.patch_draft(paper_id, PaperDraftPatchRequest(expectedRevision=current_revision()))
    stale_error = None
    try:
        service.apply_proposal(proposal_id, PaperProposalDecisionRequest(
            expectedRevision=current_revision(), selections=[{"itemId": item_17, "knowledgePointId": point_b}]))
    except AppError as exc:
        stale_error = exc
    check("V4.13 应用前 revision 变化 → 409 PAPER_PROPOSAL_STALE 且零写入",
          stale_error is not None and stale_error.status_code == 409
          and stale_error.code == "PAPER_PROPOSAL_STALE",
          f"{getattr(stale_error, 'code', None)} {getattr(stale_error, 'status_code', None)}")
    check("V4.14 stale 拒绝后建议仍未应用", service.get_proposal(proposal_id).state == "pending",
          service.get_proposal(proposal_id).state)

    # 重新发起建议（新 revision 基线）
    provider.replies = [valid_reply([
        {"itemId": item_17, "knowledgePointId": point_b, "evidence": [item_17]},
        {"itemId": item_16_2, "proposedCode": "V00-NEW-1", "proposedName": "待确认的新知识点"},
    ])]
    view, record = await run_job(har, service, paper_id, current_revision())
    proposal2 = service.get_proposal((record.result or {}).get("proposalId"))
    base_rev = current_revision()

    # 选择与建议不符 → 422
    mismatch = None
    try:
        service.apply_proposal(proposal2.proposal_id, PaperProposalDecisionRequest(
            expectedRevision=base_rev, selections=[{"itemId": item_16_2, "knowledgePointId": point_a}]))
    except AppError as exc:
        mismatch = exc
    check("V4.15 选择与建议内容不符 → 422 PAPER_PROPOSAL_INVALID 且可定位",
          mismatch is not None and mismatch.status_code == 422
          and mismatch.code == "PAPER_PROPOSAL_INVALID"
          and any(issue.get("field") == "knowledgePointId" for issue in (mismatch.details or {}).get("issues", [])),
          f"{getattr(mismatch, 'code', None)} {(mismatch.details if mismatch else {})}")

    # 非计分题（容器 16）→ 422
    container_error = None
    try:
        service.apply_proposal(proposal2.proposal_id, PaperProposalDecisionRequest(
            expectedRevision=base_rev, selections=[{"itemId": items["16"], "knowledgePointId": point_b}]))
    except AppError as exc:
        container_error = exc
    check("V4.16 选择非计分容器 → 422 PAPER_PROPOSAL_INVALID",
          container_error is not None and container_error.code == "PAPER_PROPOSAL_INVALID"
          and any(issue.get("field") == "itemId" for issue in (container_error.details or {}).get("issues", [])),
          f"{getattr(container_error, 'code', None)}")

    # 应用（既有知识点）
    applied = service.apply_proposal(proposal2.proposal_id, PaperProposalDecisionRequest(
        expectedRevision=base_rev, selections=[{"itemId": item_17, "knowledgePointId": point_b}]))
    entry_17 = next(item for item in applied.items if item.item_id == item_17)
    check("V4.17 应用后写入关联且 source=ai_confirmed/role=primary",
          any(k.knowledge_point_id == point_b and k.source == "ai_confirmed" and k.role == "primary"
              for k in entry_17.knowledge),
          str([(k.knowledge_point_id[:6], k.source, k.role) for k in entry_17.knowledge]))
    check("V4.18 应用后建议状态 applied 且重复应用被拒（409）",
          service.get_proposal(proposal2.proposal_id).state == "applied", "")
    repeat = None
    try:
        service.apply_proposal(proposal2.proposal_id, PaperProposalDecisionRequest(
            expectedRevision=current_revision(), selections=[{"itemId": item_17, "knowledgePointId": point_b}]))
    except AppError as exc:
        repeat = exc
    check("V4.18b 重复应用 → 409 PAPER_PROPOSAL_INVALID",
          repeat is not None and repeat.status_code == 409, f"{getattr(repeat, 'code', None)}")

    # 新知识点候选：不创建知识点（只作为候选留在建议 payload）
    check("V4.19 新知识点候选不创建正式知识点（knowledge_points 计数不变）",
          knowledge_count(har) == knowledge_before, f"{knowledge_before} → {knowledge_count(har)}")

    # reject
    provider.replies = [valid_reply([{"itemId": item_16_1, "knowledgePointId": point_a, "evidence": [item_16_1]}])]
    view, record = await run_job(har, service, paper_id, current_revision())
    proposal3 = service.get_proposal((record.result or {}).get("proposalId"))
    rejected = service.reject_proposal(proposal3.proposal_id,
                                       PaperProposalDecisionRequest(expectedRevision=current_revision()))
    check("V4.20 reject → 状态 rejected 且之后不能应用（409）",
          rejected.state == "rejected", rejected.state)
    reject_apply = None
    try:
        service.apply_proposal(proposal3.proposal_id, PaperProposalDecisionRequest(
            expectedRevision=current_revision(), selections=[{"itemId": item_16_1, "knowledgePointId": point_a}]))
    except AppError as exc:
        reject_apply = exc
    check("V4.21 已拒绝建议不能再应用（409）",
          reject_apply is not None and reject_apply.status_code == 409, f"{getattr(reject_apply, 'code', None)}")

    # 建议任务冻结输入含模型指纹且不含凭证
    conn = har.db("teaching")
    try:
        row = conn.execute(
            "SELECT frozen_input_json, model_snapshot_json FROM workflow_jobs WHERE kind='paper_mapping' "
            "ORDER BY created_at DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    frozen = json.loads(row["frozen_input_json"])
    snapshot = json.loads(row["model_snapshot_json"])
    check("V4.22 冻结输入含计分叶子白名单/允许知识点/模型指纹，且无凭证字样",
          frozen.get("allowedItemIds") and frozen.get("allowedKnowledgePointIds")
          and snapshot.get("fingerprint", "").startswith("sha256:")
          and "sk-" not in json.dumps(frozen) + json.dumps(snapshot),
          f"items={len(frozen.get('allowedItemIds') or [])} fp={snapshot.get('fingerprint', '')[:20]}")

    # ---------------------------------------------------------------- reader
    reader = har.app.state.confirmed_paper_reader
    draft_result = None
    try:
        reader.read(state["revision_id"])
    except AppError as exc:
        draft_result = exc
    check("V4.23 reader：draft 修订 → 422 ASSESSMENT_PAPER_INVALID",
          draft_result is not None and draft_result.status_code == 422
          and draft_result.code == "ASSESSMENT_PAPER_INVALID",
          f"{getattr(draft_result, 'code', None)}")
    missing = None
    try:
        reader.read("no-such-revision")
    except AppError as exc:
        missing = exc
    check("V4.24 reader：不存在的修订 → 404 PAPER_NOT_FOUND",
          missing is not None and missing.status_code == 404 and missing.code == "PAPER_NOT_FOUND",
          f"{getattr(missing, 'code', None)}")

    # 确认本卷，再读 reader
    confirmed = service.confirm(paper_id, PaperConfirmRequest(
        expectedRevision=current_revision(), submissionId="v00-v4-confirm"))
    snapshot_view = reader.read_confirmed_paper_revision(confirmed.paper_revision_id)
    conn = har.db("teaching")
    try:
        paper_row = conn.execute("SELECT subject_id, title FROM papers WHERE id=?", (paper_id,)).fetchone()
    finally:
        conn.close()
    check("V4.25 reader：返回真实标题/学科/总分/计分叶数（与库一致）",
          snapshot_view.title == paper_row["title"] and snapshot_view.subject_id == paper_row["subject_id"]
          and snapshot_view.total_score_units == 1500 and snapshot_view.scored_leaf_count == 3,
          f"{snapshot_view.title} {snapshot_view.subject_id} {snapshot_view.total_score_units} {snapshot_view.scored_leaf_count}")
    check("V4.26 reader.read_current：确认后返回同一修订",
          reader.read_current(paper_id).paper_revision_id == confirmed.paper_revision_id, "")

    # 损坏库纵深防御：移除确认触发器后造零总分 / 无计分叶的"已确认"修订
    corrupt_root = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v4-corrupt-"))
    corrupt = sqlite3.connect(str(corrupt_root / "teaching.sqlite3"))
    corrupt.row_factory = sqlite3.Row
    from app.core.migrations import apply_migrations
    from app.repositories.teaching.catalog import TeachingCatalog
    from app.services.papers.reader import ConfirmedPaperReaderAdapter

    apply_migrations(corrupt, database="teaching")
    corrupt.execute("DROP TRIGGER paper_confirm")
    corrupt.execute("DROP TRIGGER no_direct_sealed_paper_revisions")
    corrupt.execute(
        "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, media_type, "
        "byte_size, created_at) VALUES ('a1','local','paper','blobs/x',?, 'p.docx','application/vnd',1,'2026-10-01T00:00:00Z')",
        ("a" * 64,))
    corrupt.execute("INSERT INTO papers (id, owner_id, subject_id, title) VALUES ('p1','local','math','损坏卷')")
    for rid, version, total in (("rz", 1, 0), ("ro", 2, 100)):
        corrupt.execute(
            "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, total_score_units, state, "
            "confirmed_at, created_at) VALUES (?, 'p1', ?, 'a1', ?, 'confirmed', '2026-10-01T00:00:00Z', "
            "'2026-10-01T00:00:00Z')", (rid, version, total))
    corrupt.execute("UPDATE papers SET current_revision_id='ro' WHERE id='p1'")
    corrupt.commit()
    catalog = TeachingCatalog(str(corrupt_root / "teaching.sqlite3"))
    catalog.migrate()  # 登记已应用（幂等）；被 DROP 的触发器不会被重建
    corrupt_reader = ConfirmedPaperReaderAdapter(catalog)
    zero_total = None
    try:
        corrupt_reader.read("rz")
    except AppError as exc:
        zero_total = exc
    no_leaf = None
    try:
        corrupt_reader.read("ro")
    except AppError as exc:
        no_leaf = exc
    check("V4.27 reader 纵深防御：零总分「已确认」修订 → 422",
          zero_total is not None and zero_total.code == "ASSESSMENT_PAPER_INVALID",
          f"{getattr(zero_total, 'code', None)} {getattr(zero_total, 'status_code', None)}")
    check("V4.28 reader 纵深防御：无计分叶「已确认」修订 → 422",
          no_leaf is not None and no_leaf.code == "ASSESSMENT_PAPER_INVALID",
          f"{getattr(no_leaf, 'code', None)} {getattr(no_leaf, 'status_code', None)}")
    corrupt.close()

    return finish(evidence)


def finish(evidence: str, reason: str = "") -> int:
    failed = [row for row in RESULTS if row["status"] == "FAIL"]
    print(f"\n== v4_papers_proposals_probe: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed; "
          f"failed={[row['name'] for row in failed]} {reason} ==")
    if evidence:
        target = Path(evidence)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"probe": "v4_papers_proposals_probe", "results": RESULTS},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"证据：{evidence}")
    return 1 if failed else 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="")
    _args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(main(_args.evidence)))
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        RESULTS.append({"name": "probe crashed", "status": "FAIL", "detail": traceback.format_exc()[-300:]})
        raise SystemExit(finish(_args.evidence, reason="crashed"))
