"""Pure fixed-content projections and explicit scored-node validation."""
import copy
import re
import hashlib
from app.contracts.teaching_loop import RichContentV2, canonical_hash
from app.services.question_bank.fingerprint import duplicate_content_fingerprint
from app.services.question_bank.rich import image_media_type
from app.schemas.question_bank import QuestionType
from typing import get_args
from .common import invalid, unique, units


def _markdown_blocks(text, prefix):
    if re.search(r"!\[[^\]]*\]\(|^\s*\|.*\|\s*$|<[^>]+>", text, re.M):
        raise invalid("此旧题含尚未定位的图表或 HTML，请先明确校对为富题。", "questionRevisionId", "PRACTICE_RICH_REVIEW_REQUIRED")
    pattern = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$|(?<![\\$])\$(?!\$)(.+?)(?<!\\)\$(?!\$)", re.S)
    blocks, cursor = [], 0
    for match in pattern.finditer(text):
        if match.start() > cursor:
            blocks.append(dict(id=f"{prefix}:{len(blocks)}", kind="paragraph", text=text[cursor:match.start()]))
        blocks.append(dict(id=f"{prefix}:{len(blocks)}", kind="formula", latex=match.group(1) or match.group(2)))
        cursor = match.end()
    if cursor < len(text) or not blocks:
        blocks.append(dict(id=f"{prefix}:{len(blocks)}", kind="paragraph", text=text[cursor:]))
    return blocks


def as_rich(question) -> dict:
    rich = question.content.get("richContent")
    if rich is not None:
        rich=RichContentV2.model_validate(rich).model_dump(by_alias=True)
        blocks=[*[b for m in rich["sharedMaterials"] for b in m["blocks"]],*rich["stemBlocks"],*[b for v in rich["optionBlocks"].values() for b in v],*rich["answerBlocks"],*rich["explanationBlocks"]]
        unique([b["id"] for b in blocks],"content.richContent.blockId")
        unique([m["id"] for m in rich["sharedMaterials"]],"content.richContent.materialId")
        unique([a["assetId"] for a in rich["assets"]],"content.richContent.assetId")
        if {a["assetId"] for a in rich["assets"]}!={b["assetId"] for b in blocks if b["kind"]=="image"}:
            raise invalid("图片声明必须与完整固定富题的引用相符。","assets")
        return rich
    content = question.content
    rich = dict(version=2, sharedMaterials=[], stemBlocks=_markdown_blocks(content["stemMarkdown"], "stem"),
        optionBlocks={x["key"]: _markdown_blocks(x["textMarkdown"], "option:"+x["key"]) for x in content.get("options", [])},
        answerBlocks=[], explanationBlocks=[], assets=[],
        origin=dict(originalAssetId="question-revision:"+question.question_revision_id,
                    originalSha256=canonical_hash(content), sourceLocator={"questionRevisionId": question.question_revision_id}))
    if content.get("assetIds"):
        raise invalid("此旧题图片缺少富内容位置与声明，请先在题库明确校对为富题。", "questionRevisionId", "PRACTICE_RICH_REVIEW_REQUIRED")
    answer = content.get("answer")
    if answer:
        text = answer.get("textMarkdown") or ", ".join(answer.get("choiceKeys", []))
        if not text and answer.get("accepted") is not None:
            text = "true" if answer["accepted"] else "false"
        if text:
            rich["answerBlocks"] = _markdown_blocks(text, "answer")
    if content.get("explanationMarkdown"):
        rich["explanationBlocks"] = _markdown_blocks(content["explanationMarkdown"], "explanation")
    return RichContentV2.model_validate(rich).model_dump(by_alias=True)


def surface(question) -> str:
    return duplicate_content_fingerprint(question.content)


def original_surfaces(contents):
    """Unknown original type matches candidates without rewriting original facts."""
    result = set()
    for content in contents:
        types = (content["type"],) if content.get("type") else get_args(QuestionType)
        for question_type in types:
            result.add(duplicate_content_fingerprint(dict(content, type=question_type)))
    return result


def prepare(item, question, *, read_asset, assets):
    rich = as_rich(question)
    for asset in rich["assets"]:
        data, media = read_asset(asset["assetId"])
        if media != image_media_type(data) or media == "application/octet-stream":
            raise invalid("题目图片类型不符合真实字节。", "assets", "PRACTICE_ASSET_MISMATCH")
        if hashlib.sha256(data).hexdigest() != asset["sha256"] or media != asset["mediaType"]:
            raise invalid("题目图片声明与真实字节不一致。", "assets", "PRACTICE_ASSET_MISMATCH")
        stored = assets.store_original(data, media_type=media, original_name="practice-image")
        if stored.sha256 != asset["sha256"] or media != asset["mediaType"]:
            raise invalid("题目图片声明与真实字节不一致。", "assets", "PRACTICE_ASSET_MISMATCH")
    return validate_structure(item, question, rich)


def validate_structure(item, question, rich):
    links = {x["knowledge_point_id"]: x for x in question.knowledge_links}
    unique(item.selected_knowledge_point_ids, "selectedKnowledgePointIds")
    if not set(item.selected_knowledge_point_ids) <= set(links):
        raise invalid("知识点必须来自固定正式题的关联。", "selectedKnowledgePointIds")
    blocks = {x["id"]: x for x in rich["stemBlocks"]}
    blocks.update({x["id"]: x for v in rich["optionBlocks"].values() for x in v})
    nodes = item.item_structure.nodes
    unique([x.node_key for x in nodes], "nodeKey")
    unique([x.ordinal for x in nodes], "ordinal")
    unique([x.question_no for x in nodes], "questionNo")
    node_map = {x.node_key: x for x in nodes}
    children = {x.parent_node_key for x in nodes if x.parent_node_key}
    leaf_total = 0
    assigned = set()
    result = []
    for node in sorted(nodes, key=lambda x: x.ordinal):
        seen = {node.node_key}
        parent = node.parent_node_key
        while parent is not None:
            if parent not in node_map or parent in seen:
                raise invalid("父子计分结构缺节点或有环。", "parentNodeKey")
            seen.add(parent)
            parent = node_map[parent].parent_node_key
        unique(node.source_block_ids, "sourceBlockIds")
        unique(node.knowledge_point_ids, "knowledgePointIds")
        if not set(node.source_block_ids) <= set(blocks):
            raise invalid("题面来源块不属于所选固定题。", "sourceBlockIds")
        assigned.update(node.source_block_ids)
        if not set(node.knowledge_point_ids) <= set(item.selected_knowledge_point_ids):
            raise invalid("节点知识点不在教师选择的正式关联内。", "knowledgePointIds")
        score = None
        if node.is_scored:
            if node.node_key in children or not node.max_score or not node.knowledge_point_ids or not node.source_block_ids:
                raise invalid("计分节点必须是正分、有知识点与实质题面的叶。", "itemStructure")
            score = units(node.max_score)
            leaf_total += score
        elif node.max_score is not None:
            raise invalid("容器与非计分节点不能有满分。", "maxScore")
        node_rich = copy.deepcopy(rich)
        selected=set(node.source_block_ids)
        node_rich["stemBlocks"] = [x for x in rich["stemBlocks"] if x["id"] in selected]
        node_rich["optionBlocks"] = {k:[x for x in v if x["id"] in selected] for k,v in rich["optionBlocks"].items() if any(x["id"] in selected for x in v)}
        source_blocks=[*node_rich["stemBlocks"],*[x for v in node_rich["optionBlocks"].values() for x in v]]
        if node.is_scored and not any(x.get("text", "").strip() or x["kind"] != "paragraph" for x in source_blocks):
            raise invalid("计分叶题面为空。", "sourceBlockIds")
        result.append(dict(node=node, content=node_rich, units=score, links=[links[k] for k in node.knowledge_point_ids]))
    if not any(x["units"] for x in result) or leaf_total != units(item.max_score):
        raise invalid("整题满分必须等于计分叶合计。", "maxScore")
    if assigned != set(blocks):
        raise invalid("全部题干与选项来源块必须明确分配，不能丢失。", "sourceBlockIds")
    return dict(item=item, question=question, rich=rich, nodes=result, total=leaf_total)
