"""Teacher-selected fixed questions, sealed review, managed export and return loop."""
from __future__ import annotations
import asyncio
import uuid
import anyio
from app.contracts import b4
from app.contracts.teaching_loop import canonical_hash
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.teaching.practices import PracticeRepository
from app.repositories.teaching.assessments import AssessmentRepository
from app.services.jobs.engine import JobOutcome
from app.services.knowledge_refs import KnowledgeReference, require_active_knowledge_references
from app.services.submissions import execute_command, make_command
from app.schemas.question_bank import QuestionType, Difficulty
from typing import get_args
from .common import decode, encode, invalid, page, stale, unique
from .selection import as_rich, prepare, surface, original_surfaces
from .conversion import convert_in
from .exports import render


class PracticeService:
    json = staticmethod(decode)
    hash = staticmethod(canonical_hash)

    def __init__(self, catalog, *, analysis_reader, fixed_question_reader, knowledge_catalog, coordinator,
                 assets, question_asset_reader, job_engine, file_assets, assessment_service, owner_id="local",
                 question_owner_id=None):
        self.catalog = catalog
        self.repo = PracticeRepository(catalog)
        self.analysis = analysis_reader
        self.questions = fixed_question_reader
        self.knowledge = knowledge_catalog
        self.coordinator = coordinator
        self.assets = assets
        self.read_question_asset = question_asset_reader
        self.engine = job_engine
        self.file_assets = file_assets
        self.assessment_service = assessment_service
        self.owner_id = owner_id
        # The teaching and question-bank domains retain their own stored owner ids.
        self.question_owner_id = owner_id if question_owner_id is None else question_owner_id

    def _command(self, operation, body):
        payload = body.model_dump(by_alias=True, mode="json", exclude={"submission_id"})
        for field in ("targetKnowledgePointIds", "classIds"):
            if field in payload:
                unique(payload[field], field)
                payload[field] = sorted(payload[field])
        if "constraints" in payload:
            for field in ("questionTypes", "difficulties"):
                unique(payload["constraints"][field], field)
                payload["constraints"][field] = sorted(payload["constraints"][field])
        if "participants" in payload:
            payload["participants"] = sorted(payload["participants"], key=lambda x: (x["studentId"], x["classId"], x["attemptNo"] or 1))
        return make_command(operation=operation, submission_id=body.submission_id, payload=payload, owner_id=self.owner_id)

    def _constraints(self, value):
        unique(value.question_types, "questionTypes")
        unique(value.difficulties, "difficulties")
        if not set(value.question_types) <= set(get_args(QuestionType)) or not set(value.difficulties) <= set(get_args(Difficulty)):
            raise invalid("题型或难度约束非法。", "constraints")

    def _replay_in(self, conn, command):
        row = conn.execute("SELECT request_hash,result_json FROM command_submissions WHERE owner_id=? AND operation=? AND submission_id=?",
            (command.owner_id, command.operation, command.submission_id)).fetchone()
        if row is None:
            return None
        if row["request_hash"] != command.request_hash:
            raise AppError("同一提交标识对应不同请求。", code="SUBMISSION_CONFLICT", status_code=409)
        return dict(decode(row["result_json"]), replayed=True)

    def _replay(self, command):
        with self.catalog.read_connection() as conn:
            return self._replay_in(conn, command)

    def _revision_view(self, conn, practice, revision):
        selection = decode(revision["selection_snapshot_json"])
        items = []
        for row in self.repo.items_in(conn, revision["id"]):
            items.append(b4.PracticeItemView(practiceItemId=row["id"], selectionId=row["selection_id"], itemKey=row["item_key"],
                nodeKey=row["node_key"], parentItemId=row["parent_item_id"], questionNo=row["question_no"], ordinal=row["ordinal"],
                isScored=bool(row["is_scored"]), maxScoreUnits=row["max_score_units"], questionId=row["question_id"],
                questionRevisionId=row["question_revision_id"], content=decode(row["content_json"]),
                knowledgePoints=[dict(knowledgePointId=k["knowledge_point_id"], knowledgeRevisionId=k["knowledge_revision_id"], name=k["name_snapshot"], role=k["role"])
                    for k in self.repo.knowledge_in(conn, row["id"])], sourceLocator=decode(row["source_locator_json"]),
                reason=decode(row["reason_json"])["reason"], answerState=row["answer_state"]))
        return b4.PracticeRevisionView(practiceSetId=practice["id"], practiceRevisionId=revision["id"], version=revision["version"],
            state=revision["state"], title=revision["title_snapshot"], subjectId=practice["subject_id"], analysisRunId=practice["analysis_run_id"],
            targetKnowledgePoints=selection["targetKnowledgePoints"], constraints=decode(revision["constraints_json"]), inputHash=revision["input_hash"],
            totalScoreUnits=revision["total_score_units"], draftItems=decode(revision["draft_items_json"], list), items=items,
            reviewedAt=revision["reviewed_at"], createdAt=revision["created_at"])

    def _set_view(self, conn, set_id):
        practice = self.repo.set_in(conn, set_id, self.owner_id)
        revisions = [self._revision_view(conn, practice, row) for row in conn.execute("SELECT * FROM practice_revisions WHERE practice_set_id=? ORDER BY version", (set_id,))]
        current = next((r for r in revisions if r.practice_revision_id == practice["current_revision_id"]), None)
        if current is None:
            raise AppError("练习当前修订损坏。", code="PRACTICE_DATA_CORRUPT", status_code=500)
        return b4.PracticeSetView(practiceSetId=set_id, title=practice["title"], subjectId=practice["subject_id"], analysisRunId=practice["analysis_run_id"],
            revision=practice["revision"], currentRevision=current, revisions=revisions)

    def get_practice(self, set_id):
        with self.catalog.read_connection() as conn:
            return self._set_view(conn, set_id)

    def get_revision(self, set_id, revision_id):
        with self.catalog.read_connection() as conn:
            practice = self.repo.set_in(conn, set_id, self.owner_id)
            return self._revision_view(conn, practice, self.repo.revision_in(conn, set_id, revision_id, self.owner_id))

    def read_reviewed_revision(self, revision_id, *, owner_id="local"):
        """Read an exact sealed revision and its owner in one SQL snapshot.

        No current pointer, asset preparation, or temporary mutation of this
        service's owner is involved. Missing and foreign identities stay neutral.
        """
        with self.catalog.read_connection() as conn:
            row = conn.execute(
                "SELECT r.id,r.practice_set_id,r.state FROM practice_revisions r "
                "JOIN practice_sets p ON p.id=r.practice_set_id WHERE r.id=? AND p.owner_id=?",
                (revision_id, owner_id),
            ).fetchone()
            if row is None:
                raise AppError("所选固定练习不可用。", code="NOT_FOUND", status_code=404)
            if row["state"] != "reviewed":
                raise AppError("所选练习修订尚未审核。", code="LESSON_INVALID", status_code=422,
                    details={"issues": [{"field": "practiceRevisionIds", "code": "PRACTICE_NOT_REVIEWED", "message": "请选择已审核的固定练习修订。"}]})
            practice = self.repo.set_in(conn, row["practice_set_id"], owner_id)
            revision = self.repo.revision_in(conn, row["practice_set_id"], revision_id, owner_id)
            return self._revision_view(conn, practice, revision)

    def list_practices(self, *, analysis_run_id=None, offset=0, limit=50):
        page(offset, limit)
        with self.catalog.read_connection() as conn:
            where = "owner_id=?" + (" AND analysis_run_id=?" if analysis_run_id else "")
            args = [self.owner_id] + ([analysis_run_id] if analysis_run_id else [])
            total = conn.execute(f"SELECT count(*) FROM practice_sets WHERE {where}", args).fetchone()[0]
            rows = conn.execute(f"SELECT id FROM practice_sets WHERE {where} ORDER BY created_at DESC,id LIMIT ? OFFSET ?", (*args, limit, offset))
            return b4.Page[b4.PracticeSetView](items=[self._set_view(conn, x[0]) for x in rows], total=total, offset=offset, limit=limit)

    def _insert_revision(self, conn, practice, *, version, snapshot, constraints, draft_items, title):
        revision_id = uuid.uuid4().hex
        input_hash = canonical_hash(dict(snapshot=snapshot, constraints=constraints, draftItems=draft_items))
        conn.execute("INSERT INTO practice_revisions(id,practice_set_id,version,input_hash,selection_snapshot_json,constraints_json,draft_items_json,title_snapshot,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (revision_id, practice, version, input_hash, encode(snapshot), encode(constraints), encode(draft_items), title, now_iso()))
        conn.execute("UPDATE practice_sets SET current_revision_id=? WHERE id=?", (revision_id, practice))
        return revision_id

    def create_practice(self, body):
        command = self._command("practice.create", body)
        replay = self._replay(command)
        if replay:
            return b4.PracticeSetView.model_validate(replay)
        self._constraints(body.constraints)
        report = self.analysis.read_ready_report(body.analysis_run_id, owner_id=self.owner_id)
        points = {x["knowledgePointId"]: x for x in report["knowledgePoints"]}
        unique(body.target_knowledge_point_ids, "targetKnowledgePointIds")
        if not set(body.target_knowledge_point_ids) <= set(points):
            raise invalid("目标知识点必须属于就绪报告。", "targetKnowledgePointIds")
        snapshot = dict(targetKnowledgePoints=[points[x] for x in sorted(body.target_knowledge_point_ids)], analysisInputHash=report["inputHash"])
        def apply(conn):
            set_id = uuid.uuid4().hex
            conn.execute("INSERT INTO practice_sets(id,owner_id,analysis_run_id,subject_id,title,created_at) VALUES(?,?,?,?,?,?)",
                (set_id, self.owner_id, body.analysis_run_id, report["subjectId"], body.title, now_iso()))
            self._insert_revision(conn, set_id, version=1, snapshot=snapshot, constraints=body.constraints.model_dump(by_alias=True), draft_items=[], title=body.title)
            return self._set_view(conn, set_id).model_dump(by_alias=True, mode="json")
        outcome = execute_command(catalog=self.catalog, command=command, apply=apply)
        return b4.PracticeSetView.model_validate(dict(outcome.result, replayed=outcome.replayed))

    def suggestions(self, set_id, body):
        self._constraints(body.constraints)
        practice = self.get_practice(set_id)
        if practice.revision != body.expected_revision:
            raise stale(practice.revision)
        report = self.analysis.read_ready_report(practice.analysis_run_id, owner_id=self.owner_id)
        targets = {x.knowledge_point_id for x in practice.current_revision.target_knowledge_points}
        original_ids = set(report.get("originalQuestionRevisionIds", []))
        originals = original_surfaces(report.get("originalQuestionContents", []))
        if body.constraints.exclude_original and "originalQuestionContents" not in report:
            raise AppError("报告原题排除依据未装配。", code="PRACTICE_SOURCE_UNAVAILABLE", status_code=503)
        candidates = []
        for question in self.questions.list_confirmed(subject_id=practice.subject_id, owner_id=self.question_owner_id):
            coverage = targets & {x["knowledge_point_id"] for x in question.knowledge_links}
            difficulty = question.metadata.get("difficulty") or "unspecified"
            if not coverage or question.question_status != "confirmed":
                continue
            if body.constraints.question_types and question.content["type"] not in body.constraints.question_types:
                continue
            if difficulty == "unspecified" and not body.constraints.include_unknown_difficulty:
                continue
            if body.constraints.difficulties and difficulty not in body.constraints.difficulties:
                continue
            fingerprint = surface(question)
            if body.constraints.exclude_original and (question.question_revision_id in original_ids or fingerprint in originals):
                continue
            candidates.append((question, coverage, fingerprint))
        chosen, seen = [], set()
        uncovered = set(targets)
        coverage_count = {x: 0 for x in sorted(targets)}
        while candidates and len(chosen) < body.constraints.count:
            candidates.sort(key=lambda x: (-len(x[1] & uncovered), x[0].question_id, x[0].question_revision_id))
            question, coverage, fingerprint = candidates.pop(0)
            if body.constraints.deduplicate and fingerprint in seen:
                continue
            seen.add(fingerprint)
            uncovered -= coverage
            for point in coverage:
                coverage_count[point] += 1
            chosen.append(b4.PracticeSuggestion(questionId=question.question_id, questionRevisionId=question.question_revision_id,
                content=as_rich(question), knowledgePoints=[dict(knowledgePointId=x["knowledge_point_id"], knowledgeRevisionId=x["knowledge_revision_id"], name=x["name_snapshot"], role=x["role"]) for x in question.knowledge_links],
                questionType=question.content["type"], difficulty=question.metadata.get("difficulty"), reason="符合教师约束；覆盖目标知识点："+"、".join(sorted(coverage)), answerState=question.answer_state))
        gaps = ["目标知识点无符合约束的题目："+x for x in sorted(uncovered)]
        if len(chosen) < body.constraints.count:
            gaps.append(f"题量缺口：{body.constraints.count-len(chosen)}；请显式补题审核或调整约束。")
        return b4.PracticeSuggestions(items=chosen, requestedCount=body.constraints.count, selectedCount=len(chosen), coverage=coverage_count, gaps=gaps)

    def _prepared(self, items, subject):
        unique([x.item_key for x in items], "itemKey")
        unique([x.ordinal for x in items], "ordinal")
        unique([x.question_revision_id for x in items], "questionRevisionId")
        numbers=[n.question_no for item in items for n in item.item_structure.nodes]
        unique(numbers,"questionNo")
        if any(not x.strip() for x in numbers):
            raise invalid("完整题号不能为空。","questionNo")
        prepared = []
        for item in sorted(items, key=lambda x: x.ordinal):
            question = self.questions.read_revision(item.question_revision_id, owner_id=self.question_owner_id)
            if question.question_status != "confirmed" or question.subject_id != subject:
                raise invalid("题目须同学科且未归档。", "questionRevisionId")
            prepared.append(prepare(item, question, read_asset=self.read_question_asset, assets=self.assets))
        return prepared

    def _store_items(self, conn, revision_id, prepared):
        conn.execute("DELETE FROM practice_item_knowledge WHERE practice_revision_id=?", (revision_id,))
        conn.execute("DELETE FROM practice_items WHERE practice_revision_id=?", (revision_id,))
        conn.execute("DELETE FROM practice_selections WHERE practice_revision_id=?", (revision_id,))
        ordinal = 0
        for entry in prepared:
            item, question = entry["item"], entry["question"]
            selection_id = uuid.uuid4().hex
            conn.execute("INSERT INTO practice_selections VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                selection_id, revision_id, item.item_key, item.ordinal, question.question_id, question.question_revision_id, question.content_hash,
                encode(entry["rich"]), encode(question.metadata), encode(entry["rich"]["assets"]), encode({"reason":"教师明确选题并复核计分结构"}),
                encode({"origin":entry["rich"]["origin"], "locators":list(question.source_locators)}), question.answer_state))
            node_ids = {x["node"].node_key: uuid.uuid4().hex for x in entry["nodes"]}
            for node_entry in entry["nodes"]:
                node = node_entry["node"]
                ordinal += 1
                question_no = node.question_no
                source = dict(questionRevisionId=question.question_revision_id, itemKey=item.item_key, nodeKey=node.node_key,
                              originalQuestionNo=node.question_no, sourceBlockIds=node.source_block_ids, origin=entry["rich"]["origin"])
                conn.execute("INSERT INTO practice_items VALUES(?,?,?,?,?,?,?,?,?,?,?)", (node_ids[node.node_key], revision_id,
                    selection_id, node.node_key, node_ids.get(node.parent_node_key), question_no, ordinal, int(node.is_scored),
                    node_entry["units"], encode(node_entry["content"]), encode(source)))
                for link in node_entry["links"]:
                    conn.execute("INSERT INTO practice_item_knowledge VALUES(?,?,?,?,?,?,?)", (node_ids[node.node_key], revision_id,
                        link["knowledge_point_id"], link["knowledge_revision_id"], link["name_snapshot"], link["subject_id_snapshot"], link["role"]))

    def save_draft(self, set_id, body):
        # The original command, including its original CAS, identifies a save.
        # A committed receipt remains valid after later edits or reference changes.
        command = make_command(operation="practice.draft:"+set_id, submission_id=body.submission_id,
            payload=body.model_dump(by_alias=True, mode="json", exclude={"submission_id"}), owner_id=self.owner_id)
        replay = self._replay(command)
        if replay:
            return b4.PracticeSetView.model_validate(replay)
        # Receipt and CAS/state must describe one teaching snapshot. Otherwise a
        # same-command commit between two reads can be mistaken for a stale edit.
        with self.catalog.read_connection() as conn:
            replay = self._replay_in(conn, command)
            if replay:
                return b4.PracticeSetView.model_validate(replay)
            self._constraints(body.constraints)
            practice = self._set_view(conn, set_id)
            if practice.revision != body.expected_revision:
                raise stale(practice.revision)
            if practice.current_revision.state != "draft":
                raise AppError("审核版不可修改，请建立新草稿。", code="PRACTICE_NOT_EDITABLE", status_code=409)
        # Question/asset reads and preparation remain outside transactions and
        # publication. An already committed identical receipt wins over a later
        # preparation failure; a missing receipt retains the original exception.
        try:
            prepared = self._prepared(body.items, practice.subject_id)
        except Exception:
            with self.coordinator.publication(operation="practice.draft.preparation_error"):
                replay = self._replay(command)
                if replay:
                    return b4.PracticeSetView.model_validate(replay)
            raise
        def apply(conn):
            current = self.repo.set_in(conn, set_id, self.owner_id)
            if current["revision"] != body.expected_revision:
                raise stale(current["revision"])
            revision = self.repo.revision_in(conn, set_id, current["current_revision_id"], self.owner_id)
            if revision["state"] != "draft":
                raise AppError("审核版不可修改，请建立新草稿。", code="PRACTICE_NOT_EDITABLE", status_code=409)
            self._store_items(conn, revision["id"], prepared)
            draft_items = [x.model_dump(by_alias=True, mode="json") for x in body.items]
            constraints = body.constraints.model_dump(by_alias=True)
            identity = dict(selectionSnapshot=decode(revision["selection_snapshot_json"]), draftItems=draft_items,
                            constraints=constraints, contentHashes=[x["question"].content_hash for x in prepared])
            conn.execute("UPDATE practice_revisions SET draft_items_json=?,constraints_json=?,input_hash=?,total_score_units=? WHERE id=?",
                (encode(draft_items), encode(constraints), canonical_hash(identity), sum(x["total"] for x in prepared), revision["id"]))
            conn.execute("UPDATE practice_sets SET revision=revision+1 WHERE id=?", (set_id,))
            return self._set_view(conn, set_id).model_dump(by_alias=True, mode="json")
        with self.coordinator.publication(operation="practice.draft"):
            replay = self._replay(command)
            if replay:
                return b4.PracticeSetView.model_validate(replay)
            self._active_refs(prepared, practice.subject_id)
            outcome = execute_command(catalog=self.catalog, command=command, apply=apply)
        return b4.PracticeSetView.model_validate(dict(outcome.result, replayed=outcome.replayed))

    def _active_refs(self, entries, subject):
        refs = []
        for entry in entries:
            question = self.questions.read_revision(entry["question"].question_revision_id, owner_id=self.question_owner_id)
            if question.question_status != "confirmed" or question.content_hash != entry["question"].content_hash or question.subject_id != subject:
                raise AppError("题目审核身份已改变或已归档。", code="PRACTICE_REFERENCE_CHANGED", status_code=409)
            used={x for node in entry["nodes"] for x in node["node"].knowledge_point_ids}
            refs.extend(KnowledgeReference(x["knowledge_point_id"], x["knowledge_revision_id"]) for x in question.knowledge_links if x["knowledge_point_id"] in used)
        require_active_knowledge_references(self.knowledge, refs, expected_subject_id=subject)

    def review(self, set_id, body):
        command = self._command("practice.review:"+set_id, body)
        replay = self._replay(command)
        if replay:
            return b4.PracticeSetView.model_validate(replay)
        practice = self.get_practice(set_id)
        if practice.revision != body.expected_revision:
            raise stale(practice.revision)
        draft = practice.current_revision
        prepared = self._prepared(draft.draft_items, practice.subject_id)
        if not prepared:
            raise invalid("必须明确选择题目与计分结构。")
        self._constraints(draft.constraints)
        report = self.analysis.read_ready_report(practice.analysis_run_id, owner_id=self.owner_id)
        originals = original_surfaces(report.get("originalQuestionContents", []))
        original_ids = set(report.get("originalQuestionRevisionIds", []))
        if draft.constraints.exclude_original and "originalQuestionContents" not in report:
            raise AppError("报告原题排除依据未装配。", code="PRACTICE_SOURCE_UNAVAILABLE", status_code=503)
        targets = {x.knowledge_point_id for x in draft.target_knowledge_points}
        coverage, seen = set(), set()
        for entry in prepared:
            question = entry["question"]
            difficulty = question.metadata.get("difficulty") or "unspecified"
            fingerprint = surface(question)
            if ((draft.constraints.question_types and question.content["type"] not in draft.constraints.question_types)
                or (difficulty == "unspecified" and not draft.constraints.include_unknown_difficulty)
                or (draft.constraints.difficulties and difficulty not in draft.constraints.difficulties)
                or (draft.constraints.exclude_original and (question.question_revision_id in original_ids or fingerprint in originals))
                or (draft.constraints.deduplicate and fingerprint in seen)):
                raise invalid("已选题目不满足教师约束，请显式调整约束或补题。", "constraints")
            seen.add(fingerprint)
            coverage.update(k["knowledge_point_id"] for node in entry["nodes"] if node["units"] for k in node["links"])
        if len(prepared) != draft.constraints.count or not targets <= coverage:
            raise invalid("题量或目标覆盖仍有缺口，请明确补题或调整目标与题量。", "items", "PRACTICE_COVERAGE_GAP")
        def apply(conn):
            current = self.repo.set_in(conn, set_id, self.owner_id)
            if current["revision"] != body.expected_revision:
                raise stale(current["revision"])
            revision = self.repo.revision_in(conn, set_id, current["current_revision_id"], self.owner_id)
            if revision["state"] != "draft" or revision["input_hash"] != draft.input_hash:
                raise stale(current["revision"])
            self._store_items(conn, revision["id"], prepared)
            conn.execute("UPDATE practice_revisions SET state='reviewed',reviewed_at=? WHERE id=?", (now_iso(), revision["id"]))
            conn.execute("UPDATE practice_sets SET revision=revision+1 WHERE id=?", (set_id,))
            return self._set_view(conn, set_id).model_dump(by_alias=True, mode="json")
        with self.coordinator.publication(operation="practice.review"):
            replay = self._replay(command)
            if replay:
                return b4.PracticeSetView.model_validate(replay)
            self._active_refs(prepared, practice.subject_id)
            outcome = execute_command(catalog=self.catalog, command=command, apply=apply)
        return b4.PracticeSetView.model_validate(dict(outcome.result, replayed=outcome.replayed))

    def new_revision(self, set_id, body):
        command = self._command("practice.revision:"+set_id, body)
        def apply(conn):
            practice = self.repo.set_in(conn, set_id, self.owner_id)
            source = self.repo.revision_in(conn, set_id, body.source_revision_id, self.owner_id)
            if source["state"] != "reviewed":
                raise invalid("新草稿只能复制已审核修订。", "sourceRevisionId")
            version = conn.execute("SELECT max(version)+1 FROM practice_revisions WHERE practice_set_id=?", (set_id,)).fetchone()[0]
            target_id = self._insert_revision(conn, set_id, version=version, snapshot=decode(source["selection_snapshot_json"]),
                constraints=decode(source["constraints_json"]), draft_items=decode(source["draft_items_json"], list), title=source["title_snapshot"])
            selections = {x["id"]: uuid.uuid4().hex for x in self.repo.selections_in(conn, source["id"])}
            items = self.repo.items_in(conn, source["id"])
            nodes = {x["id"]: uuid.uuid4().hex for x in items}
            for old, new in selections.items():
                conn.execute("INSERT INTO practice_selections SELECT ?,?,item_key,ordinal,question_id,question_revision_id,question_content_hash,content_snapshot_json,metadata_snapshot_json,rich_assets_json,reason_json,source_snapshot_json,answer_state FROM practice_selections WHERE id=?", (new, target_id, old))
            for item in items:
                conn.execute("INSERT INTO practice_items VALUES(?,?,?,?,?,?,?,?,?,?,?)", (nodes[item["id"]],target_id,selections[item["selection_id"]],item["node_key"],nodes.get(item["parent_item_id"]),item["question_no"],item["ordinal"],item["is_scored"],item["max_score_units"],item["content_json"],item["source_locator_json"]))
                conn.execute("INSERT INTO practice_item_knowledge SELECT ?,?,knowledge_point_id,knowledge_revision_id,name_snapshot,subject_snapshot,role FROM practice_item_knowledge WHERE item_id=?", (nodes[item["id"]],target_id,item["id"]))
            conn.execute("UPDATE practice_revisions SET total_score_units=? WHERE id=?", (source["total_score_units"],target_id))
            conn.execute("UPDATE practice_sets SET revision=revision+1 WHERE id=?", (set_id,))
            return self._set_view(conn, set_id).model_dump(by_alias=True, mode="json")
        outcome = execute_command(catalog=self.catalog, command=command, apply=apply)
        return b4.PracticeSetView.model_validate(dict(outcome.result, replayed=outcome.replayed))

    def convert(self, set_id, revision_id, body):
        command = self._command("practice.assessment:"+revision_id, body)
        replay = self._replay(command)
        if replay:
            # Scope must still belong to this requested set, even for replay.
            self.get_revision(set_id, revision_id)
            return b4.PracticeConversionReceipt.model_validate(replay)
        view = self.get_revision(set_id, revision_id)
        if view.state != "reviewed":
            raise invalid("只能转换审核版。", "practiceRevisionId", "PRACTICE_NOT_REVIEWED")
        # Verify frozen images outside SQL and publication; no current question substitution.
        asset_sizes = {}
        for item in view.items:
            for asset in item.content.assets:
                data = self.assets.read("blobs/"+asset.sha256)
                if len(data) == 0:
                    raise invalid("图片数据为空。", "assets")
                asset_sizes[asset.sha256] = len(data)
        with self.coordinator.publication(operation="practice.assessment"):
            replay = self._replay(command)
            if replay:
                return b4.PracticeConversionReceipt.model_validate(replay)
            refs = [KnowledgeReference(k.knowledge_point_id, k.knowledge_revision_id) for item in view.items for k in item.knowledge_points]
            require_active_knowledge_references(self.knowledge, refs, expected_subject_id=view.subject_id)
            def apply(conn):
                practice = self.repo.set_in(conn, set_id, self.owner_id)
                revision = self.repo.revision_in(conn, set_id, revision_id, self.owner_id)
                return convert_in(self, conn, practice, revision, body, asset_sizes=asset_sizes)
            outcome = execute_command(catalog=self.catalog, command=command, apply=apply)
        return b4.PracticeConversionReceipt.model_validate(dict(outcome.result, replayed=outcome.replayed))

    def register_job_executors(self, registry):
        registry.register("teaching", "export", uses_model=False, factory=lambda record: self._export_executor)

    def _accept_export(self, set_id, revision_id, body):
        command = self._command("practice.export:"+revision_id, body)
        replay = self._replay(command)
        if replay:
            self.get_revision(set_id, revision_id)
            return replay
        if self.engine is None:
            raise AppError("导出任务引擎未装配。", code="SERVICE_UNAVAILABLE", status_code=503)
        store = self.engine.store("teaching")
        def apply(conn):
            practice = self.repo.set_in(conn, set_id, self.owner_id)
            revision = self.repo.revision_in(conn, set_id, revision_id, self.owner_id)
            if revision["state"] != "reviewed":
                raise invalid("只能导出审核版。", "practiceRevisionId", "PRACTICE_NOT_REVIEWED")
            selections = [dict(rich=decode(x["content_snapshot_json"]), answerState=x["answer_state"], ordinal=x["ordinal"],
                nodes=[dict(questionNo=i["question_no"],isScored=bool(i["is_scored"]),maxScoreUnits=i["max_score_units"]) for i in self.repo.items_in(conn,revision_id) if i["selection_id"]==x["id"]],
                maxScoreUnits=sum(i["max_score_units"] or 0 for i in self.repo.items_in(conn, revision_id) if i["selection_id"]==x["id"]))
                for x in self.repo.selections_in(conn, revision_id)]
            frozen = dict(practiceRevisionId=revision_id, variant=body.variant, assessmentId=body.assessment_id,
                          title=revision["title_snapshot"], reviewedInputHash=revision["input_hash"], selections=selections, ruleCode="practice_export_v1")
            if body.variant == "score_template":
                conversion = conn.execute("SELECT * FROM practice_conversions WHERE assessment_id=? AND practice_revision_id=? AND owner_id=?", (body.assessment_id, revision_id, self.owner_id)).fetchone()
                if conversion is None:
                    raise invalid("施测不属于此固定练习转换。", "assessmentId", "PRACTICE_ASSESSMENT_MISMATCH")
                participants = AssessmentRepository(self.catalog).list_participants_in(conn, body.assessment_id)
                leaves = conn.execute("SELECT id,question_no,max_score_units FROM paper_items WHERE paper_revision_id=? AND is_scored=1 ORDER BY ordinal", (conversion["paper_revision_id"],)).fetchall()
                frozen.update(paperRevisionId=conversion["paper_revision_id"], participants=[x.view().model_dump(by_alias=True) for x in participants],
                    leaves=[dict(itemId=x["id"], questionNo=x["question_no"], maxScoreUnits=x["max_score_units"]) for x in leaves])
            input_hash = canonical_hash(frozen)
            existing = conn.execute("SELECT * FROM practice_exports WHERE owner_id=? AND input_hash=?", (self.owner_id, input_hash)).fetchone()
            if existing:
                job = store.get(existing["job_id"])
                return dict(exportId=existing["id"], practiceRevisionId=revision_id, inputHash=input_hash, job=job.view().model_dump(by_alias=True), replayed=False, reused=True)
            job = store.create_in(conn, kind="export", frozen_input=frozen, owner_id=self.owner_id)
            export_id = uuid.uuid4().hex
            conn.execute("INSERT INTO practice_exports VALUES(?,?,?,?,?,?,?,?,?)", (export_id, self.owner_id, revision_id, body.variant, body.assessment_id, input_hash, encode(frozen), job.job_id, now_iso()))
            return dict(exportId=export_id, practiceRevisionId=revision_id, inputHash=input_hash, job=job.view().model_dump(by_alias=True), replayed=False, reused=False)
        outcome = execute_command(catalog=self.catalog, command=command, apply=apply)
        return dict(outcome.result, replayed=outcome.replayed)

    async def create_export(self, set_id, revision_id, body):
        receipt = b4.ExportReceipt.model_validate(await anyio.to_thread.run_sync(lambda: self._accept_export(set_id, revision_id, body)))
        if not receipt.replayed and not receipt.reused:
            self.engine.schedule("teaching", receipt.job.job_id, self._export_executor, uses_model=False)
        return receipt

    async def _export_executor(self, frozen_job, context):
        with self.catalog.read_connection() as conn:
            row = conn.execute("SELECT * FROM practice_exports WHERE job_id=? AND owner_id=?", (frozen_job.job_id, self.owner_id)).fetchone()
        if row is None:
            raise AppError("导出任务元数据损坏。", code="PRACTICE_DATA_CORRUPT", status_code=500)
        frozen = decode(row["frozen_input_json"])
        if frozen_job.input != frozen:
            raise AppError("导出任务冻结输入不符。", code="PRACTICE_DATA_CORRUPT", status_code=500)
        payload, media, filename = await asyncio.to_thread(render, dict(frozen, frozenAt=row["created_at"]), self.assets)
        if await context.cancellation_requested():
            return JobOutcome(result={})
        stored = await asyncio.to_thread(self.assets.store_original, payload, media_type=media, original_name=filename)
        artifact_id, asset_id = uuid.uuid4().hex, uuid.uuid4().hex
        result = dict(exportId=row["id"], artifactId=artifact_id, practiceRevisionId=row["practice_revision_id"], variant=row["variant"], assessmentId=row["assessment_id"])
        def publish(conn):
            self.file_assets.create_in(conn, kind="export", blob_key=stored.blob_key, sha256=stored.sha256, media_type=media,
                byte_size=stored.byte_size, original_name=filename, owner_id=self.owner_id, asset_id=asset_id)
            conn.execute("INSERT INTO export_artifacts VALUES(?,?,?,?,?,?,?,?,?,?)", (artifact_id, row["id"], self.owner_id, row["practice_revision_id"], asset_id, filename, media, stored.sha256, stored.byte_size, now_iso()))
        return JobOutcome(result=result, publish=publish)

    def list_exports(self, set_id, revision_id, *, offset=0, limit=50):
        page(offset, limit)
        self.get_revision(set_id, revision_id)
        with self.catalog.read_connection() as conn:
            total = conn.execute("SELECT count(*) FROM export_artifacts WHERE owner_id=? AND practice_revision_id=?", (self.owner_id, revision_id)).fetchone()[0]
            rows = conn.execute("SELECT a.*,e.variant,e.assessment_id FROM export_artifacts a JOIN practice_exports e ON e.id=a.export_id WHERE a.owner_id=? AND a.practice_revision_id=? ORDER BY a.created_at DESC,a.id LIMIT ? OFFSET ?", (self.owner_id, revision_id, limit, offset)).fetchall()
        return b4.Page[b4.ExportArtifact](items=[dict(artifactId=x["id"], exportId=x["export_id"], practiceRevisionId=revision_id,
            variant=x["variant"], assessmentId=x["assessment_id"], fileAssetId=x["file_asset_id"], filename=x["filename"], mediaType=x["media_type"],
            sha256=x["sha256"], byteSize=x["byte_size"], downloadUrl="/api/v1/export-artifacts/"+x["id"]+"/download", createdAt=x["created_at"]) for x in rows], total=total, offset=offset, limit=limit)

    def get_asset(self, set_id, revision_id, sha):
        view = self.get_revision(set_id, revision_id)
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise invalid("资产散列非法。", "sha")
        for item in view.items:
            for asset in item.content.assets:
                if asset.sha256 == sha:
                    return self.assets.read("blobs/"+sha), asset.media_type
        raise AppError("此固定练习未引用该图片。", code="PRACTICE_ASSET_NOT_FOUND", status_code=404)
