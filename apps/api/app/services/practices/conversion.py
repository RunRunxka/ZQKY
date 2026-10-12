"""One teaching transaction creates paper, T30 assessment and true provenance."""
import uuid
from app.contracts.assessments import AssessmentCreateRequest
from app.core.sqlite import now_iso
from app.repositories.teaching.papers import PaperRepository, ItemKnowledgeRecord
from .common import encode, invalid


def convert_in(service, conn, practice, revision, body, *, asset_sizes):
    papers = PaperRepository(service.catalog)
    paper = papers.create_paper_in(conn, subject_id=practice["subject_id"], title=body.title, owner_id=service.owner_id)
    paper_revision = papers.create_revision_in(conn, paper_id=paper.paper_id, version=1, source_file_id=None,
        source_practice_revision_id=revision["id"], total_score_units=revision["total_score_units"], title_snapshot=body.title)
    items = service.repo.items_in(conn, revision["id"])
    identifiers = {x["id"]: uuid.uuid4().hex for x in items}
    for item in items:
        content = service.json(item["content_json"])
        for asset in content["assets"]:
            existing = conn.execute("SELECT owner_id,sha256,media_type,blob_key,byte_size,kind FROM file_assets WHERE id=?", (asset["assetId"],)).fetchone()
            if existing is None:
                service.file_assets.create_in(conn, kind="attachment", blob_key="blobs/"+asset["sha256"], sha256=asset["sha256"],
                    media_type=asset["mediaType"], byte_size=asset_sizes[asset["sha256"]], original_name="练习固定图片", owner_id=service.owner_id, asset_id=asset["assetId"])
            elif (existing["owner_id"] != service.owner_id or existing["sha256"] != asset["sha256"] or existing["media_type"] != asset["mediaType"]
                  or existing["blob_key"] != "blobs/"+asset["sha256"] or existing["byte_size"] != asset_sizes[asset["sha256"]] or existing["kind"] != "attachment"):
                raise invalid("练习图片资产归属或声明冲突。", "assets")
        papers.insert_items_in(conn, paper_revision_id=paper_revision.revision_id, items=[dict(
            item_id=identifiers[item["id"]], parent_item_id=identifiers.get(item["parent_item_id"]),
            question_no=item["question_no"], ordinal=item["ordinal"], is_scored=bool(item["is_scored"]),
            max_score_units=item["max_score_units"], content=content, source_locator=dict(service.json(item["source_locator_json"]), practiceItemId=item["id"], practiceRevisionId=revision["id"]))])
        # The reviewed JSON itself is the source identity, including key order.
        conn.execute("UPDATE paper_items SET content_json=? WHERE id=?", (item["content_json"], identifiers[item["id"]]))
        conn.execute("UPDATE paper_items SET question_revision_id=? WHERE id=?", (item["question_revision_id"], identifiers[item["id"]]))
        knowledge = [ItemKnowledgeRecord(x["knowledge_point_id"], x["knowledge_revision_id"], x["name_snapshot"], x["role"], "bank_confirmed")
                     for x in service.repo.knowledge_in(conn, item["id"])]
        papers.insert_item_knowledge_in(conn, item_id=identifiers[item["id"]], paper_revision_id=paper_revision.revision_id, knowledge=knowledge)
        # Persist the actual reviewed rich source blocks, including common material and images.
        block_sets = [content["stemBlocks"], *content["optionBlocks"].values(), content["answerBlocks"], content["explanationBlocks"], *[m["blocks"] for m in content["sharedMaterials"]]]
        for blocks in block_sets:
            for block in blocks:
                block_id = f"{identifiers[item['id']]}:{block['id']}"
                ordinal = conn.execute("SELECT count(*)+1 FROM paper_source_blocks WHERE paper_revision_id=?", (paper_revision.revision_id,)).fetchone()[0]
                conn.execute("INSERT INTO paper_source_blocks(id,paper_revision_id,ordinal,kind,block_json,locator_json,disposition,item_id) VALUES(?,?,?,?,?,?,'item',?)",
                    (block_id, paper_revision.revision_id, ordinal, block["kind"], encode(block), item["source_locator_json"], identifiers[item["id"]]))
        if item["is_scored"] and not (content["stemBlocks"] or content["optionBlocks"]):
            raise invalid("练习来源计分叶题面不完整。", "items")
    papers.confirm_revision_in(conn, paper_revision.revision_id)
    papers.set_current_revision_in(conn, paper.paper_id, paper_revision.revision_id)
    result = service.assessment_service.create_in(conn, AssessmentCreateRequest(
        submissionId=body.submission_id, paperRevisionId=paper_revision.revision_id, title=body.title,
        assessmentType="practice", heldOn=body.held_on, classIds=body.class_ids, participants=body.participants))
    assessment_id = result["assessment"]["assessmentId"]
    conversion_id = uuid.uuid4().hex
    conn.execute("INSERT INTO practice_conversions(id,owner_id,practice_revision_id,paper_revision_id,assessment_id,input_hash,participant_snapshot_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (conversion_id, service.owner_id, revision["id"], paper_revision.revision_id, assessment_id,
         service.hash(dict(practiceRevisionId=revision["id"], paperRevisionId=paper_revision.revision_id, participants=result["participants"])), encode(result["participants"]), now_iso()))
    for item in items:
        conn.execute("INSERT INTO practice_paper_item_mappings VALUES(?,?,?,?,?)", (conversion_id, revision["id"], item["id"], identifiers[item["id"]], paper_revision.revision_id))
    return dict(conversionId=conversion_id, paperId=paper.paper_id, paperRevisionId=paper_revision.revision_id,
                assessmentId=assessment_id, practiceRevisionId=revision["id"], replayed=False)
