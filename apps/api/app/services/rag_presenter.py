"""Preserve verified citations while keeping internal paths and failed evidence off the UI."""

from __future__ import annotations

from copy import deepcopy
from pathlib import PurePosixPath, PureWindowsPath
import re

from app.core.exceptions import AppError


def public_result(raw: dict) -> dict:
    status = raw.get("status")
    if status in {"model_unavailable", "unavailable", "cancelled", "budget_exceeded", "error"}:
        raise AppError(
            "本地教材模型或索引当前不可用，请检查本机服务后重试。",
            code="RAG_MODEL_UNAVAILABLE", status_code=503, retryable=True,
        )
    if status not in {"ok", "partial", "uncertain", "no_evidence"}:
        raise AppError("教材定位未得到可展示的有效结果。", code="RAG_INVALID_RESULT", status_code=502)
    result = {
        "contract_version": raw.get("contract_version"),
        "status": status,
        "subject": raw.get("subject"),
        "evidence": [], "citations": [], "explanations": [],
        "uncertain_reason": None,
    }
    if status not in {"ok", "partial"}:
        # Diagnostic retrieval candidates are not demonstrated teaching evidence.
        result["uncertain_reason"] = "现有教材证据不足以支持可靠讲解，请补充完整题干、学科或具体疑问。"
        return result
    evidence = deepcopy(raw.get("evidence") or [])
    citations = deepcopy(raw.get("citations") or [])
    explanations = deepcopy(raw.get("explanations") or [])
    if not evidence or not citations or not explanations:
        if status == "partial":
            raise AppError("本地教材依据核验未完成，请稍后重试。", code="RAG_REVIEW_UNAVAILABLE", status_code=503, retryable=True)
        raise AppError("教材结果缺少原文、引用或讲解，已停止展示。", code="RAG_INVALID_RESULT", status_code=502)
    known = {}
    try:
        if len(evidence) > 20 or len(citations) > 20 or len(explanations) > 20:
            raise ValueError("result item limit")
        if sum(len(item["text"]) for item in evidence) > 40000:
            raise ValueError("result text limit")
        for item in evidence:
            key = item["citation_id"]
            path = item["file"]
            if key in known or PureWindowsPath(path).is_absolute() or PurePosixPath(path).is_absolute():
                raise ValueError("invalid source identity")
            if ".." in PurePosixPath(path.replace("\\", "/")).parts:
                raise ValueError("invalid relative source")
            if item["char_span"][0] < 0 or not item["text"] or item["char_span"][1] - item["char_span"][0] != len(item["text"]):
                raise ValueError("source substring mismatch")
            if not re.fullmatch(r"[0-9a-f]{64}", item["source_sha256"]):
                raise ValueError("invalid source fingerprint")
            if item["line_span"][0] < 1 or item["line_span"][1] < item["line_span"][0]:
                raise ValueError("invalid lines")
            known[key] = item
        cited = set()
        for citation in citations:
            ref = known[citation["citation_id"]]
            for field in ("file", "source_sha256", "char_span", "line_span", "text"):
                if citation[field] != ref[field]:
                    raise ValueError("citation mismatch")
            cited.add(citation["citation_id"])
        for explanation in explanations:
            if not explanation["explanation"].strip() or not explanation["citation_ids"]:
                raise ValueError("unsupported explanation")
            if len(explanation["explanation"]) > 12000 or len(explanation["point"]) > 2000:
                raise ValueError("explanation text limit")
            if not set(explanation["citation_ids"]).issubset(cited):
                raise ValueError("dangling citation")
            supplement = explanation.get("supplement")
            if supplement and supplement.get("is_external") is not True:
                raise ValueError("unmarked supplement")
            if supplement and len(supplement["text"]) > 12000:
                raise ValueError("supplement text limit")
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        raise AppError("教材引用未通过一致性检查，已停止展示。", code="RAG_INVALID_RESULT", status_code=502) from exc
    # Include only stable, public source fields. Ranking/expansion metadata stays server-side.
    fields = ("citation_id", "file", "book", "path", "source_sha256", "char_span", "line_span", "text")
    result.update(
        evidence=[{key: item[key] for key in fields} for item in evidence],
        citations=[{key: item[key] for key in fields} for item in citations],
        explanations=explanations,
    )
    if raw.get("provenance", {}).get("grounding_review", {}).get("output_mode") == "textbook_excerpt":
        result["answerMode"] = "textbook_excerpt"
    if status == "partial":
        result["uncertain_reason"] = "以下仅展示已通过依据核验的部分讲解；其余内容证据不足，暂不提供。"
    return result


def render_result(result: dict) -> str:
    if result["status"] not in {"ok", "partial"}:
        return "\n\n" + result["uncertain_reason"] + "\n\n"
    excerpt = result.get("answerMode") == "textbook_excerpt"
    blocks = ["\n\n### 教材定位与原文讲解\n" if excerpt else "\n\n### 教材定位与讲解\n"]
    if result["status"] == "partial":
        blocks.append(result["uncertain_reason"] + "\n")
    for citation in result["citations"]:
        location = " → ".join([citation["book"], *citation["path"]])
        first, last = citation["line_span"]
        blocks.append(f"**[{citation['citation_id']}] {location} · 第 {first}–{last} 行**\n")
        blocks.append("\n".join("> " + line for line in citation["text"].split("\n")) + "\n")
    for explanation in ([] if excerpt else result["explanations"]):
        refs = "、".join(f"[{item}]" for item in explanation["citation_ids"])
        blocks.append(f"**{explanation['point']}** {refs}\n\n{explanation['explanation']}\n")
        if explanation.get("supplement"):
            blocks.append(f"**教材外补充**：{explanation['supplement']['text']}\n")
    if excerpt:
        blocks.append("以上为相关教材原文摘录，供核对题目知识点；本轮未提供独立解题推导。\n")
    else:
        blocks.append("教材定位与解释供核对参考；人工教学质量验收尚未完成。\n")
    return "\n".join(blocks)
