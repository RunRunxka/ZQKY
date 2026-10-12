"""Read complete confirmed facts from one SQLite read snapshot."""
from app.contracts.b4 import FrozenParticipant
from app.core.exceptions import AppError
from app.repositories.teaching.papers import PaperRepository
from app.repositories.teaching.scores import ScoreRepository
from app.services.papers.reader import ConfirmedPaperReaderAdapter
from .aggregate import STATES


def corrupt(message):
    return AppError(message, code="ANALYSIS_SOURCE_CORRUPT", status_code=500)


def selection_error(index, code, message):
    return AppError(message, code="ANALYSIS_SELECTION_INVALID", status_code=422,
                    details={"issues": [{"field": f"selectedParticipantIds[{index}]", "row": index,
                                         "code": code, "message": message}]})


def read_facts(catalog, assessment_id, payload, owner_id):
    papers, scores = PaperRepository(catalog), ScoreRepository(catalog)
    with catalog.read_connection() as conn:
        assessment = conn.execute("SELECT * FROM assessments WHERE id=? AND owner_id=?",
                                  (assessment_id, owner_id)).fetchone()
        if assessment is None:
            raise AppError("施测不存在。", code="ASSESSMENT_NOT_FOUND", status_code=404)
        score = scores.require_revision_in(conn, payload.score_revision_id)
        if score.assessment_id != assessment_id:
            raise AppError("成绩修订不属于此施测。", code="SCORE_REVISION_NOT_FOUND", status_code=404)
        if score.state != "confirmed":
            raise AppError("分析只能使用已确认成绩。", code="ANALYSIS_SCORE_NOT_CONFIRMED", status_code=422)
        paper = ConfirmedPaperReaderAdapter(catalog).read_in(conn, score.paper_revision_id)
        all_items = papers.list_items_in(conn, paper.paper_revision_id)
        blocks = papers.list_blocks_in(conn, paper.paper_revision_id)
        available = {p.participant_id: p for p in score.participant_snapshot}
        if len(available) != len(score.participant_snapshot):
            raise corrupt("成绩人次快照存在重复。")
        seen, students, selected = set(), set(), []
        for index, pid in enumerate(payload.selected_participant_ids):
            if pid in seen:
                raise selection_error(index, "DUPLICATE_PARTICIPANT", "参测人次不能重复。")
            if pid not in available:
                raise selection_error(index, "PARTICIPANT_NOT_IN_REVISION", "人次不属于固定成绩修订。")
            participant = available[pid]
            if participant.student_id in students:
                raise selection_error(index, "DUPLICATE_STUDENT_ATTEMPT", "同学生只能选择一个人次。")
            seen.add(pid)
            students.add(participant.student_id)
            selected.append(FrozenParticipant.model_validate(participant.model_dump(by_alias=True)).model_dump(by_alias=True))
        selected.sort(key=lambda p: p["participantId"])
        leaf_map = {item.item_id: item for item in paper.scored_leaves}
        fixed_items = {item.item_id: item for item in score.item_snapshot}
        if len(fixed_items) != len(score.item_snapshot) or set(fixed_items) != set(leaf_map):
            raise corrupt("成绩计分叶快照与固定原卷不一致。")
        source_blocks = [{"blockId": b.block_id, "ordinal": b.ordinal, "block": b.block,
                          "sourceLocator": b.locator, "disposition": b.disposition,
                          "itemId": b.item_id, "excludeReason": b.exclude_reason} for b in blocks]
        mappings = {row["paper_item_id"]: dict(row) for row in conn.execute(
            "SELECT m.paper_item_id,m.practice_item_id,m.practice_revision_id,s.question_revision_id "
            "FROM practice_paper_item_mappings m JOIN practice_items i "
            "ON i.id=m.practice_item_id AND i.practice_revision_id=m.practice_revision_id "
            "JOIN practice_selections s ON s.id=i.selection_id AND s.practice_revision_id=i.practice_revision_id "
            "JOIN practice_conversions c ON c.id=m.conversion_id AND c.paper_revision_id=m.paper_revision_id "
            "AND c.practice_revision_id=m.practice_revision_id "
            "WHERE m.paper_revision_id=? AND c.owner_id=?",
            (paper.paper_revision_id, owner_id))}
        items, knowledge = [], {}
        original_contents = []
        for item in all_items:
            rich = item.content.get("richContent") or item.content
            if "stemBlocks" in rich or "stemMarkdown" in item.content:
                compatible = {k: v for k, v in item.content.items() if k in
                              ("type", "stemMarkdown", "options", "answer", "explanationMarkdown", "assetIds", "richContent")}
                compatible.setdefault("stemMarkdown", "\n\n".join(
                    str(b.get("text") or b.get("latex") or "") for b in rich.get("stemBlocks", [])))
                if "stemBlocks" in rich:
                    compatible["richContent"] = rich
                    compatible.setdefault("options", [{"key": key, "textMarkdown": "\n\n".join(
                        str(b.get("text") or b.get("latex") or "") for b in val)}
                        for key, val in rich.get("optionBlocks", {}).items()])
                original_contents.append(compatible)
            if item.item_id not in leaf_map:
                continue
            fixed = fixed_items[item.item_id]
            if fixed.max_score_units != item.max_score_units or fixed.max_score_units <= 0:
                raise corrupt("成绩计分叶满分与固定原卷不一致。")
            links = []
            for k in item.knowledge:
                kp = {"knowledgePointId": k.knowledge_point_id, "knowledgeRevisionId": k.knowledge_revision_id,
                      "name": k.knowledge_name_snapshot, "role": k.role}
                previous = knowledge.get(k.knowledge_point_id)
                if previous and (previous["knowledgeRevisionId"], previous["name"]) != (kp["knowledgeRevisionId"], kp["name"]):
                    raise corrupt("同知识点存在不一致固定修订或名称。")
                if previous is None or kp["role"] == "primary":
                    knowledge[k.knowledge_point_id] = kp
                links.append(kp)
            content = dict(item.content)
            content["sourceBlocks"] = source_blocks
            lineage = mappings.get(item.item_id, {})
            items.append({"itemId": item.item_id, "itemPath": fixed.item_path,
                          "maxScoreUnits": fixed.max_score_units, "knowledgePoints": links,
                          "content": content, "sharedMaterials": rich.get("sharedMaterials", []),
                          "sourceLocator": item.source_locator, "assets": rich.get("assets", []),
                          "practiceRevisionId": lineage.get("practice_revision_id"),
                          "practiceItemId": lineage.get("practice_item_id")})
        cells = scores.matrix_cells_in(conn, score.revision_id)
        expected = {(pid, iid) for pid in available for iid in fixed_items}
        actual = {(cell.participant_id, cell.item_id) for cell in cells}
        if actual != expected or len(cells) != len(expected):
            raise corrupt("固定成绩全矩阵缺格或存在额外单元格。")
        counts, selected_cells = dict.fromkeys(STATES, 0), []
        for cell in cells:
            if cell.status == "recorded" and cell.score_units > fixed_items[cell.item_id].max_score_units:
                raise corrupt("固定成绩单元格超过满分。")
            if cell.participant_id in seen:
                counts[cell.status] += 1
                selected_cells.append({"participantId": cell.participant_id, "itemId": cell.item_id,
                                       "status": cell.status, "scoreUnits": cell.score_units})
        return {"assessmentId": assessment_id, "subjectId": paper.subject_id,
                "scoreRevisionId": score.revision_id, "paperRevisionId": paper.paper_revision_id,
                "paperTitle": paper.title, "ruleCode": payload.rule_code,
                "participants": selected, "items": items, "cells": selected_cells,
                "knowledgePoints": [knowledge[k] for k in sorted(knowledge)],
                "selectionSnapshot": {"selectedParticipantIds": sorted(seen), "uniqueStudentCount": len(students),
                                      "participantCount": len(selected), "leafCount": len(items), "stateCounts": counts},
                "originalQuestionRevisionIds": sorted({m["question_revision_id"] for m in mappings.values()}),
                "originalQuestionContents": original_contents}
