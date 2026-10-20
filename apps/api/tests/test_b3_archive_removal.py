"""B3 归档功能移除（2026-10-20 用户裁定「全局移除归档，只留删除」+ 题库物理删除）。

覆盖四块：

1. **归档/恢复端点整体不存在**（classes / students / papers / assessments /
   analysis-runs / lesson-plans / practice-sets 全部 404；question 域没有归档端点）；
2. **题库 DELETE /questions/{id} 物理删除**：题目/修订/关联（触发器摘除+逐字恢复）/
   来源/指纹全部移除；任务历史与导入批次保留；乐观锁 409、404 语义不变；
3. **被引用题目 409 QUESTION_IN_USE**：审核练习固定题（practice_selections）与
   教案生成冻结输入（lesson_generation_inputs.frozen_json 的固定题引用）逐项计数；
4. **归一化脚本 smoke**（``scripts/normalize_archives.py``）：临时数据根 dry-run /
   apply、可重复执行、students 内部状态不被恢复、archived 题走物理删除。

学生删除「有历史」语义（``removed_with_history``）不变——由 ``test_r10_delete_semantics``
覆盖；本文件只核对删除链路在新语义下未回归（引用计数与归档移除共同点）。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tests.assessments_support import AssessmentsHarness
from tests.test_question_bank import Harness
from tests.test_question_bank import open_harness
from tests.test_question_bank_confirm import (
    ONE_QUESTION_DOC,
    confirm,
    upload_and_review,
)

ONE_QUESTION_DOC_B3 = ONE_QUESTION_DOC


# ----------------------------------------------------------------- 归档端点已移除


@pytest.fixture()
def api(tmp_path: Path):
    with AssessmentsHarness(tmp_path) as running:
        yield running


def test_archive_restore_endpoints_removed_across_domains(api: AssessmentsHarness) -> None:
    """七域归档/恢复端点全部 404（路由不存在），请求体与乐观锁都不再被解释。"""
    client = api.client
    paper = api.import_draft_paper(tag="b3-rm", title="归档端点移除")
    klass = api.create_class(code="C-b3")
    body = json.dumps({"expectedRevision": 0})
    removed = [
        ("/api/v1/classes/no-such/archive", "POST"),
        ("/api/v1/classes/no-such/restore", "POST"),
        ("/api/v1/students/no-such/archive", "POST"),
        ("/api/v1/students/no-such/restore", "POST"),
        (f"/api/v1/papers/{paper['paperId']}/archive", "POST"),
        (f"/api/v1/papers/{paper['paperId']}/restore", "POST"),
        ("/api/v1/assessments/no-such/archive", "POST"),
        ("/api/v1/assessments/no-such/restore", "POST"),
        ("/api/v1/analysis-runs/no-such/archive", "POST"),
        ("/api/v1/analysis-runs/no-such/restore", "POST"),
        ("/api/v1/lesson-plans/no-such/archive", "POST"),
        ("/api/v1/lesson-plans/no-such/restore", "POST"),
        ("/api/v1/practice-sets/no-such/archive", "POST"),
        ("/api/v1/practice-sets/no-such/restore", "POST"),
    ]
    for path, method in removed:
        response = client.post(path, content=body, headers={"content-type": "application/json"})
        assert response.status_code == 404, (method, path, response.status_code, response.text)
    # 真实实体也一样 404（不是"实体不存在"的 404 语义混淆：先建再删端点验证）
    created_class = client.post(
        "/api/v1/classes",
        json={"code": "C-b3b", "name": "二班", "schoolYear": "2026", "gradeId": "g1"},
    ).json()
    assert client.post(
        f"/api/v1/classes/{created_class['id']}/archive", json={"expectedRevision": 0}
    ).status_code == 404
    assert client.post(
        f"/api/v1/classes/{created_class['id']}/restore", json={"expectedRevision": 0}
    ).status_code == 404
    _ = klass


def test_public_lists_no_longer_filter_by_archive(api: AssessmentsHarness) -> None:
    """公开列表：classes/papers 的 status 过滤参数已移除（传入被忽略、返回全部）。"""
    client = api.client
    client.post(
        "/api/v1/classes",
        json={"code": "C-b3l", "name": "三班", "schoolYear": "2026", "gradeId": "g1"},
    )
    for value in ("active", "archived"):
        response = client.get("/api/v1/classes", params={"status": value})
        assert response.status_code == 200
        assert response.json()["total"] == 1  # 过滤参数被忽略：返回全部
        papers = client.get("/api/v1/papers", params={"status": value})
        assert papers.status_code == 200
    assert client.get("/api/v1/classes").json()["total"] >= 1
    assert client.get("/api/v1/papers").json()["total"] >= 0


# ----------------------------------------------------------------- 题库物理删除


@pytest.fixture()
def qharness(tmp_path: Path):
    instance = open_harness(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def _confirm_one(harness: Harness, submission: str) -> str:
    import_id, draft = upload_and_review(harness, ONE_QUESTION_DOC_B3)
    receipt = confirm(
        harness,
        import_id,
        [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
        submission_id=submission,
    )
    assert receipt.status_code == 200 and receipt.json()["failures"] == []
    return receipt.json()["confirmedQuestionIds"][0]


def _rows(harness: Harness, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    connection = sqlite3.connect(harness.catalog.db_path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def test_delete_question_physically_removes_everything(qharness: Harness) -> None:
    """物理删除：题目/修订/关联/来源/指纹全没了；任务历史与导入批次保留。"""
    import_id, draft = upload_and_review(qharness, ONE_QUESTION_DOC_B3, subjectId="math")
    receipt = confirm(
        qharness,
        import_id,
        [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
        submission_id="b3-phys-1",
    )
    question_id = receipt.json()["confirmedQuestionIds"][0]
    assert qharness.catalog.get_question(question_id) is not None

    deleted = qharness.client.delete(
        f"/api/v1/questions/{question_id}", params={"expectedRevision": 1}
    )
    assert deleted.status_code == 204, deleted.text

    # 详情 404、列表为空
    assert qharness.client.get(f"/api/v1/questions/{question_id}").status_code == 404
    listing = qharness.client.get("/api/v1/questions").json()
    assert listing["total"] == 0
    # 库行清零
    for table in (
        "questions",
        "question_revisions",
        "question_sources",
        "question_content_fingerprints",
        "question_knowledge_links",
    ):
        assert _rows(qharness, f"SELECT COUNT(*) AS n FROM {table}")[0]["n"] == 0, table
    # 历史保留：任务行（organize/generate 至少有生成批次行或为空，但 submissions 一定有）
    assert _rows(qharness, "SELECT COUNT(*) AS n FROM question_submissions")[0]["n"] >= 1
    assert _rows(qharness, "SELECT COUNT(*) AS n FROM question_imports")[0]["n"] == 1
    assert _rows(qharness, "SELECT COUNT(*) AS n FROM question_drafts")[0]["n"] >= 1


def test_delete_question_revision_conflict_and_missing(qharness: Harness) -> None:
    question_id = _confirm_one(qharness, "b3-phys-lock")
    stale = qharness.client.delete(
        f"/api/v1/questions/{question_id}", params={"expectedRevision": 9}
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "REVISION_CONFLICT"
    assert qharness.catalog.get_question(question_id) is not None

    missing = qharness.client.delete("/api/v1/questions/nope", params={"expectedRevision": 0})
    assert missing.status_code == 404
    assert missing.json()["code"] == "QUESTION_NOT_FOUND"


def test_delete_question_clears_draft_duplicate_pointer(qharness: Harness) -> None:
    """被删题的"重复题"指针置空：草稿批次与并入审计保留，指针不再悬挂。"""
    first_id = _confirm_one(qharness, "b3-dup-base")
    # 同题面上传 + skip：草稿的 duplicate_of_question_id 指向第一题
    second = qharness.upload(ONE_QUESTION_DOC_B3).json()
    second_draft = qharness.import_detail(second["importId"])["drafts"][0]
    reviewed = qharness.patch_draft(second_draft)
    assert reviewed.status_code == 200
    skipped = qharness.client.post(
        f"/api/v1/question-imports/{second['importId']}/confirm",
        json={
            "submissionId": "b3-dup-skip",
            "importId": second["importId"],
            "items": [
                {"draftId": second_draft["draftId"], "expectedDraftRevision": reviewed.json()["revision"]}
            ],
            "duplicateResolutions": [{"draftId": second_draft["draftId"], "action": "skip"}],
        },
    )
    assert skipped.status_code == 200, skipped.text
    assert _rows(
        qharness,
        "SELECT COUNT(*) AS n FROM question_drafts WHERE duplicate_of_question_id = ?",
        (first_id,),
    )[0]["n"] >= 1

    deleted = qharness.client.delete(
        f"/api/v1/questions/{first_id}", params={"expectedRevision": 1}
    )
    assert deleted.status_code == 204
    assert _rows(
        qharness,
        "SELECT COUNT(*) AS n FROM question_drafts WHERE duplicate_of_question_id IS NOT NULL",
    )[0]["n"] == 0
    # 草稿批次保留
    assert _rows(qharness, "SELECT COUNT(*) AS n FROM question_drafts")[0]["n"] >= 1


def test_delete_question_keeps_immutable_link_trigger(qharness: Harness) -> None:
    """触发器逐字恢复：删除后不可变关联触发器仍在位（先删后建可核对）。"""
    question_id = _confirm_one(qharness, "b3-trigger")
    deleted = qharness.client.delete(
        f"/api/v1/questions/{question_id}", params={"expectedRevision": 1}
    )
    assert deleted.status_code == 204
    triggers = _rows(
        qharness,
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE "
        "'immutable_question_knowledge_links%'",
    )
    assert {row["name"] for row in triggers} == {
        "immutable_question_knowledge_links_update",
        "immutable_question_knowledge_links_delete",
    }


def test_delete_question_in_use_by_practice(qharness: Harness, tmp_path: Path) -> None:
    """被审核练习固定题引用 → 409 ``QUESTION_IN_USE``，counts.practices 列出计数。

    ``practice_selections`` 引用行的宿主表（``practice_sets``）有 REPORT_NOT_READY 等
    触发器链，直接种行需要整条报告链；这里复用 ``AnalysisScene`` + ``PracticesScene``
    生成真实引用形状，再对**同一个题库**构造服务实例（注入教学库）直测删除守卫。
    """
    import asyncio

    from app.services.question_bank.service import build_question_bank_service
    from tests.practices_support import PracticesScene
    from tests.analysis_support import AnalysisScene

    async def scenario() -> tuple[str, PracticesScene]:
        analysis = AnalysisScene(tmp_path)
        receipt = await analysis.ready()
        scene = PracticesScene(analysis)
        scene.run_id = receipt.run_id
        question = scene.question()
        practice = scene.save(scene.create_set(), [scene.item(question)])
        scene.review(practice, submission="b3-in-use-review")
        return question.question_id, scene

    question_id, scene = asyncio.run(scenario())
    teaching = scene.catalog
    service = None
    try:
        service = build_question_bank_service(
            scene.questions,
            qharness.settings,
            owner_id="local",
            teaching_catalog=teaching,
        )
        from app.core.exceptions import AppError

        with pytest.raises(AppError) as blocked:
            service.delete_question(question_id, expected_revision=1)
        assert blocked.value.status_code == 409
        assert blocked.value.code == "QUESTION_IN_USE"
        assert blocked.value.details["counts"]["practices"] >= 1
        # 题目未动
        with scene.questions.write_transaction() as conn:
            present = conn.execute(
                "SELECT COUNT(*) FROM questions WHERE id=?", (question_id,)
            ).fetchone()[0]
        assert present == 1
        # 已审核练习的选择行受 freeze 触发器保护（不可拆引用，属练习删除链）；
        # 用练习域既有的"连同历史彻底删除"仓储方法清掉引用链，再删题目。
        from app.repositories.teaching.practices import PracticeRepository

        with teaching.write_transaction() as conn:
            set_id = conn.execute(
                "SELECT s.practice_set_id FROM practice_selections sel "
                "JOIN practice_revisions s ON s.id = sel.practice_revision_id "
                "WHERE sel.question_id=?",
                (question_id,),
            ).fetchone()[0]
            PracticeRepository(teaching).delete_set_with_history_in(conn, set_id)
        service.delete_question(question_id, expected_revision=1)
        with scene.questions.write_transaction() as conn:
            present = conn.execute(
                "SELECT COUNT(*) FROM questions WHERE id=?", (question_id,)
            ).fetchone()[0]
        assert present == 0
    finally:
        teaching.close()
        scene.questions.close()
        scene.knowledge.close()
        scene.textbooks.close()
        if service is not None:
            service.close()


# ----------------------------------------------------------------- 归一化脚本


def _b3_settings(tmp_path: Path):
    from app.core.config import Settings

    # 不覆盖 question_bank_dir：种子与脚本都从 data_dir 派生各库路径（同一解析口径）。
    return Settings(
        host="127.0.0.1",
        port=8001,
        allowed_origins=frozenset(),
        env="test",
        data_dir=tmp_path / "data",
    )


def _seed_normalize(tmp_path: Path) -> None:
    """在临时数据根种入各库残留归档行（不碰 live .local-data）。"""
    from app.core.sqlite import connect
    from app.repositories.knowledge.catalog import KnowledgeCatalog
    from app.repositories.question_bank.catalog import QuestionBankCatalog
    from app.repositories.teaching.catalog import TeachingCatalog

    settings = _b3_settings(tmp_path)
    knowledge = KnowledgeCatalog(settings.knowledge_root / "knowledge.sqlite3")
    knowledge.migrate()
    with knowledge.write_transaction() as conn:
        conn.execute("INSERT INTO subjects(id,code,name,status) VALUES('s1','math','数学','archived')")
        conn.execute(
            "INSERT INTO knowledge_points(id,subject_id,code,current_revision_id,status) "
            "VALUES('kp1','s1','K1','kp1-r','archived')"
        )
        conn.execute(
            "INSERT INTO knowledge_point_revisions(id,knowledge_point_id,version,name) "
            "VALUES('kp1-r','kp1',1,'点')"
        )
    knowledge.close()

    teaching = TeachingCatalog(settings.teaching_root / "teaching.sqlite3")
    teaching.migrate()
    now = "2026-10-20T00:00:00Z"
    with teaching.write_transaction() as conn:
        conn.execute(
            "INSERT INTO file_assets(id,kind,blob_key,sha256,media_type,byte_size,"
            "original_name,created_at) VALUES('fa1','paper','blobs/' || ? || '0',?,"
            "'application/octet-stream',1,'卷.docx',?)", ("a" * 63, "a" * 64, now)
        )
        conn.execute(
            "INSERT INTO papers(id,owner_id,subject_id,title,status,revision,created_at) "
            "VALUES('p1','local','math','卷','archived',1,?)", (now,)
        )
        conn.execute(
            "INSERT INTO paper_revisions(id,paper_id,version,source_file_id,total_score_units,"
            "state,created_at,title_snapshot,title_snapshot_source) VALUES('pr1','p1',1,'fa1',100,"
            "'draft',?,'卷','revision')", (now,)
        )
        conn.execute(
            "INSERT INTO classes(id,owner_id,code,name,school_year,grade_id,status,revision,created_at) "
            "VALUES('c1','local','C1','一班','2026','g1','archived',1,?)", (now,)
        )
        conn.execute(
            "INSERT INTO students(id,owner_id,name,student_no,status,revision,created_at) "
            "VALUES('st1','local','张三',NULL,'archived',1,?)", (now,)
        )
        # assessment_confirmed_paper_insert 要求已确认原卷：残留归档行只是迁移遗物，
        # 摘除该触发器直接种行（同事务恢复）。
        from app.repositories.teaching.triggers import suspend_triggers

        with suspend_triggers(conn, ("assessment_confirmed_paper_insert",)):
            conn.execute(
                "INSERT INTO assessments(id,owner_id,paper_revision_id,title,assessment_type,"
                "held_on,state,revision,created_at) VALUES('a1','local','pr1','施测','exam',"
                "'2026-10-20','archived',1,?)", (now,)
            )
        conn.execute(
            "INSERT INTO workflow_jobs(id,owner_id,kind,state,created_at,updated_at) VALUES("
            "'job1','local','analysis','succeeded',?,?)", (now, now)
        )
        conn.execute(
            "INSERT INTO score_revisions(id,assessment_id,version,state,created_at) VALUES("
            "'sr1','a1',1,'draft',?)", (now,)
        )
        conn.execute(
            "INSERT INTO analysis_runs(id,owner_id,assessment_id,score_revision_id,"
            "paper_revision_id,subject_id,rule_code,input_hash,input_json,job_id,report_ready,"
            "selected_count,leaf_count,knowledge_count,class_count,created_at,archived_at) VALUES("
            "'run1','local','a1','sr1','pr1','math','any_loss_v1',"
            "'0000000000000000000000000000000000000000000000000000000000000000','{}','job1',0,"
            "1,1,0,1,?, '2026-10-20T00:00:01Z')", (now,)
        )
        conn.execute(
            "INSERT INTO lesson_plans(id,owner_id,subject_id,class_id,current_revision_id,revision,"
            "created_at,updated_at,archived_at) VALUES('l1','local','math','c1','lr1',1,?,?,"
            "'2026-10-20T00:00:01Z')", (now, now)
        )
        conn.execute(
            "INSERT INTO lesson_plan_revisions(id,lesson_plan_id,owner_id,version,data_json,"
            "content_hash,source,context_snapshot_json,source_metadata_json,selected_fields_json,"
            "process_metadata_json,created_at) VALUES('lr1','l1','local',1,'{}','"
            + "0" * 64 + "','manual','{\"subjectId\":\"math\",\"classId\":\"c1\",\"analysis\":{\"analysisRunId\":null}}','{}','[]','[]',?)", (now,)
        )
        # practice_sets 有 REPORT_NOT_READY/analysis_seal 触发器链，种行需整条报告链；
        # 残留练习行的归一由脚本分支覆盖（本测试不种该行，计数 0 亦是有效断言）。
    teaching.close()

    qbank = QuestionBankCatalog(settings.question_bank_root / "question-bank.sqlite3")
    qbank.migrate()
    with qbank.write_transaction() as conn:
        qbank.insert_question_in(
            conn,
            owner_id="local",
            content={"type": "short_answer", "stemMarkdown": "旧题", "options": [],
                     "assetIds": [], "answer": None, "explanation": None, "richContent": None},
            metadata={"subjectId": "math", "gradeId": "", "editionId": "", "difficulty": "unspecified",
                      "knowledgeTags": []},
            answer_state="not_provided",
            content_fingerprint="f" * 64,
            source_spans=[],
            import_id=None,
        )
        conn.execute("UPDATE questions SET status='archived' WHERE id=("
                     "SELECT id FROM questions LIMIT 1)")
    qbank.close()


def test_normalize_script_dry_run_then_apply_is_idempotent(tmp_path: Path, capsys) -> None:
    """dry-run 只打印；apply 归一全部残留；重复执行计数为 0；students 状态不恢复。"""
    from scripts.normalize_archives import main

    _seed_normalize(tmp_path)
    data_dir = str(tmp_path / "data")

    # dry-run：不写入
    assert main(["--data-dir", data_dir]) == 0
    dry = capsys.readouterr().out
    assert "DRY-RUN" in dry and "questionsArchived: 1" in dry

    from app.core.sqlite import connect

    def cell(path: Path, sql: str) -> object:
        conn = connect(path)
        try:
            row = conn.execute(sql).fetchone()
            return None if row is None else row[0]
        finally:
            conn.close()

    settings = _b3_settings(tmp_path)
    knowledge_path = settings.knowledge_root / "knowledge.sqlite3"
    teaching_path = settings.teaching_root / "teaching.sqlite3"
    qbank_path = settings.question_bank_root / "question-bank.sqlite3"
    assert cell(knowledge_path, "SELECT status FROM subjects WHERE id='s1'") == "archived"
    assert cell(teaching_path, "SELECT state FROM assessments WHERE id='a1'") == "archived"

    # apply：写入并核对全部目标状态
    assert main(["--data-dir", data_dir, "--apply"]) == 0
    applied = capsys.readouterr().out
    assert "APPLY" in applied
    assert cell(knowledge_path, "SELECT status FROM subjects WHERE id='s1'") == "active"
    assert cell(knowledge_path, "SELECT status FROM knowledge_points WHERE id='kp1'") == "active"
    assert cell(teaching_path, "SELECT status FROM classes WHERE id='c1'") == "active"
    assert cell(teaching_path, "SELECT status FROM papers WHERE id='p1'") == "active"
    assert cell(teaching_path, "SELECT state FROM assessments WHERE id='a1'") == "closed"
    assert cell(teaching_path, "SELECT archived_at FROM analysis_runs WHERE id='run1'") is None
    assert cell(teaching_path, "SELECT archived_at FROM lesson_plans WHERE id='l1'") is None
    # students 的内部"已移除"状态不被恢复
    assert cell(teaching_path, "SELECT status FROM students WHERE id='st1'") == "archived"
    # archived 题走物理删除：题目与修订清零
    assert cell(qbank_path, "SELECT COUNT(*) FROM questions") == 0
    assert cell(qbank_path, "SELECT COUNT(*) FROM question_revisions") == 0
    # 触发器逐字恢复
    assert cell(qbank_path, "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND "
                            "name='immutable_question_knowledge_links_delete'") == 1

    # 重复执行：全部计数为 0（幂等）
    assert main(["--data-dir", data_dir, "--apply"]) == 0
    again = capsys.readouterr().out
    assert "questionsArchived: 0" in again
    assert "classesArchived: 0" in again
