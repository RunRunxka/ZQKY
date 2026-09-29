"""固定质量集运行器（RAG-QUALITY v1.1）：自然问法 + 语料校验过的锚点标签。

与 `measure_hit_rate.py` 的区别（独立验收 Q8 点名的口径问题）：
- 问题用**自然问法**，不拿章节标题充当问题；
- 正向标签 = 目标书册 + **锚点短语**，且锚点先对**该册封存规范化原文**校验存在，
  不存在即整份数据集失败——不允许"自生成的标签自己打分"；
- 走产品同一条检索与首答链路，报告状态、原因码、长度预算、图片清洗与不重复展示。

用法（**只读打开正式数据，不建库、不改任教设置**）::

    uv run --directory apps/api python ../../scripts/rag/run_quality_set.py
    uv run --directory apps/api python ../../scripts/rag/run_quality_set.py --data-dir <隔离目录>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from app.core.config import Settings  # noqa: E402
from app.core.rag_budget import (  # noqa: E402
    EVIDENCE_TOTAL_RAW_MAX_CHARS,
    FIRST_ANSWER_EVIDENCE_MAX_ITEMS,
    SUMMARY_MAX_POINTS,
    SUMMARY_MAX_TOTAL_CHARS,
)
from app.providers.embeddings.ollama_embedding import OllamaEmbeddingProvider  # noqa: E402
from app.repositories.textbook_catalog.catalog import TextbookCatalog  # noqa: E402
from app.repositories.vector_store.qdrant import HttpQdrantStore  # noqa: E402
from app.services.rag_v2.retrieval import HybridRetriever  # noqa: E402
from app.services.rag_v2.service import RagV2Service  # noqa: E402
from app.services.rag_v2.summary import KnowledgeSummarizer  # noqa: E402
from app.services.rag_v2.requests import RagStreamRequestV2  # noqa: E402

IMAGE_SYNTAX = re.compile(r"!\[[^\]]*\]\(|<img\b")
LONG_EVIDENCE_ID = re.compile(r"ev-[0-9a-f]{8,}")


def load_set(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_text_of(catalog: TextbookCatalog, blobs, revision_id: str) -> str:
    revision = catalog.get_revision(revision_id)
    return blobs.read_text(area="normalized", blob_id=revision.normalized_blob_id)


async def ask(service: RagV2Service, question: str, selection: dict) -> dict:
    body = RagStreamRequestV2(
        requestId=uuid.uuid4().hex,
        sessionId=uuid.uuid4().hex,
        turnId=uuid.uuid4().hex,
        question=question,
        scope={"kind": "selection", "selection": selection},
    )
    begin = time.monotonic()
    turn = service.start(body)
    result = None
    body_text = ""
    try:
        async for event in service.events(turn):
            if event is None:
                continue
            if event["event"] == "rag.result":
                result = event["data"]["result"]
            elif event["event"] == "text.delta":
                body_text = event["data"].get("text", "")
            elif event["event"] == "error":
                return {
                    "status": "error",
                    "code": event["data"].get("code"),
                    "message": event["data"].get("message"),
                    "seconds": round(time.monotonic() - begin, 2),
                }
            elif event["event"] in ("wait-user", "message.end"):
                break
    finally:
        try:
            service.cancel(turn.session_id, turn.turn_id)
        except Exception:
            pass
    return {
        "status": (result or {}).get("status"),
        "reasonCode": (result or {}).get("reasonCode"),
        "reason": (result or {}).get("reason"),
        "points": (result or {}).get("points") or [],
        "evidence": (result or {}).get("evidence") or [],
        "presentation": (result or {}).get("presentation"),
        "bodyText": body_text,
        "seconds": round(time.monotonic() - begin, 2),
    }


async def main_async(args: argparse.Namespace) -> int:
    from app.services.textbook_ingest.blobs import BlobStore  # 局部导入，避免顶层副作用

    settings = Settings.from_env()
    if args.data_dir:
        settings = settings.__class__(**{**settings.__dict__, "data_dir": Path(args.data_dir)})
    if args.qdrant:
        settings = settings.__class__(**{**settings.__dict__, "qdrant_url": args.qdrant})

    catalog = TextbookCatalog(settings.textbooks_root / "catalog.sqlite3")
    try:
        catalog.open_existing()
    except Exception as exc:
        raise SystemExit(f"教材目录不可只读打开：{exc}")
    blobs = BlobStore(settings.textbooks_root)

    spec = load_set(Path(args.set))
    groups = {group["id"]: group for group in spec["groups"]}

    # 范围：按分组解析允许书册（只读；不写任教设置）
    scopes: dict[str, dict] = {}
    for group_id, group in groups.items():
        documents = [
            item
            for item in catalog.list_documents(
                grade_id=group["gradeId"],
                subject_id=group["subjectId"],
                edition_id=group["editionId"],
            )
            if item.current_revision_id
        ]
        if not documents:
            raise SystemExit(f"分组没有可用书册：{group_id}")
        scopes[group_id] = {
            "gradeId": group["gradeId"],
            "subjectId": group["subjectId"],
            "editionId": group["editionId"],
            "documentIds": [item.document_id for item in documents],
        }

    # 标签自检：锚点必须真实存在于该分组的语料里，否则整份数据集失败
    label_failures: list[str] = []
    for item in spec["questions"]:
        if item["kind"] != "positive":
            continue
        group = groups[item["group"]]
        haystacks = []
        for document_id in scopes[item["group"]]["documentIds"]:
            document = catalog.get_document(document_id)
            haystacks.append(
                normalized_text_of(catalog, blobs, document.current_revision_id).lower()
            )
        for anchor in item["anchors"]:
            if not any(anchor.lower() in text for text in haystacks):
                label_failures.append(f"{item['id']} 锚点不存在于 {group['id']} 语料：{anchor}")
    if label_failures:
        print("标签自检失败（锚点不是真实语料内容，拒绝用自造标签打分）：", file=sys.stderr)
        for problem in label_failures:
            print("  -", problem, file=sys.stderr)
        return 2
    print(f"标签自检通过：{sum(1 for q in spec['questions'] if q['kind'] == 'positive')} 个正向问题的锚点均存在于对应语料\n")

    provider = OllamaEmbeddingProvider(settings.embedding_base_url)
    service = RagV2Service(
        catalog=catalog,
        retrieval=HybridRetriever(catalog, HttpQdrantStore(settings.qdrant_url), provider),
        summarizer=KnowledgeSummarizer(settings.embedding_base_url),
        explainer=None,
    )

    results = []
    for item in spec["questions"]:
        outcome = await ask(service, item["question"], scopes[item["group"]])
        evidence = outcome.get("evidence") or []
        joined = "\n".join(entry["text"] for entry in evidence)
        readable_joined = "\n".join((entry.get("readable") or {}).get("text", "") for entry in evidence)
        points = outcome.get("points") or []
        body_chars = sum(len(point["title"]) + len(point["summary"]) for point in points)
        entry = {
            "id": item["id"],
            "group": item["group"],
            "kind": item["kind"],
            "question": item["question"],
            "status": outcome.get("status"),
            "reasonCode": outcome.get("reasonCode"),
            "reason": outcome.get("reason"),
            "points": len(points),
            "bodyChars": body_chars,
            "evidenceCount": len(evidence),
            "evidenceRawChars": sum(len(item2["text"]) for item2 in evidence),
            "seconds": outcome.get("seconds"),
            "anchorHitAt5": (
                any(anchor.lower() in "\n".join(e["text"] for e in evidence[:5]).lower()
                    for anchor in item["anchors"])
                if item["kind"] == "positive" and item["anchors"]
                else None
            ),
            "rawHasImageSyntax": bool(IMAGE_SYNTAX.search(joined)),
            "readableHasImageSyntax": bool(IMAGE_SYNTAX.search(readable_joined)),
            "bodyHasExcerptBlock": "> " in (outcome.get("bodyText") or ""),
            "bodyHasLongEvidenceId": bool(LONG_EVIDENCE_ID.search(outcome.get("bodyText") or "")),
            "budgetOk": (
                len(points) <= SUMMARY_MAX_POINTS
                and body_chars <= SUMMARY_MAX_TOTAL_CHARS
                and len(evidence) <= FIRST_ANSWER_EVIDENCE_MAX_ITEMS
                and sum(len(e["text"]) for e in evidence) <= EVIDENCE_TOTAL_RAW_MAX_CHARS
            ),
        }
        results.append(entry)
        print(
            f"{entry['id']:4s} {entry['status']:12s} 原因码={str(entry['reasonCode']):20s} "
            f"点={entry['points']} 正文={entry['bodyChars']}字 证据={entry['evidenceCount']}条 "
            f"锚点命中={entry['anchorHitAt5']} {entry['seconds']}s"
        )

    positives = [item for item in results if item["kind"] == "positive"]
    boundaries = [item for item in results if item["kind"] == "boundary"]
    summary = {
        "questionCount": len(results),
        "positive": len(positives),
        "boundary": len(boundaries),
        "okCount": sum(1 for item in results if item["status"] == "ok"),
        "positiveOkCount": sum(1 for item in positives if item["status"] == "ok"),
        "positiveAnchorHitAt5": sum(1 for item in positives if item["anchorHitAt5"]),
        "reasonCodeCounts": {},
        "budgetViolations": [item["id"] for item in results if not item["budgetOk"]],
        "rawImageSyntaxLeak": [item["id"] for item in results if item["rawHasImageSyntax"]],
        "readableImageSyntaxLeak": [item["id"] for item in results if item["readableHasImageSyntax"]],
        "bodyExcerptBlockLeak": [item["id"] for item in results if item["bodyHasExcerptBlock"]],
        "bodyLongIdLeak": [item["id"] for item in results if item["bodyHasLongEvidenceId"]],
        "boundaryStatuses": [
            {"id": item["id"], "status": item["status"], "reasonCode": item["reasonCode"]}
            for item in boundaries
        ],
        "elapsedSeconds": round(sum(item["seconds"] or 0 for item in results), 1),
    }
    for item in results:
        key = item["reasonCode"] or "(none)"
        summary["reasonCodeCounts"][key] = summary["reasonCodeCounts"].get(key, 0) + 1
    report = {
        "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "dataDir": str(settings.data_dir),
        "setPath": str(Path(args.set)),
        "note": "锚点标签先对语料校验存在；正向问题用自然问法；人工教学质量不在本报告范围",
        "summary": summary,
        "results": results,
    }
    out = Path(args.report) if args.report else REPO_ROOT / "_work" / "rag-quality-v1" / "quality-set.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"总分：{summary['okCount']}/{summary['questionCount']} ok；"
          f"正向 {summary['positiveOkCount']}/{summary['positive']} ok；"
          f"正向锚点 Hit@5 {summary['positiveAnchorHitAt5']}/{summary['positive']}")
    print(f"原因码分布：{summary['reasonCodeCounts']}")
    print(f"预算越界：{summary['budgetViolations'] or '无'}")
    print(f"原文含图片语法（预期，封存切片不改）：{len(summary['rawImageSyntaxLeak'])} 条")
    print(f"清洗后仍含图片语法（应为 0）：{summary['readableImageSyntaxLeak'] or '无'}")
    print(f"正文含原文块（应为空）：{summary['bodyExcerptBlockLeak'] or '无'}；含长 ev-id（应为空）：{summary['bodyLongIdLeak'] or '无'}")
    print(f"边界问题状态：{summary['boundaryStatuses']}")
    print(f"报告：{out}")
    await service.close()
    catalog.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="固定质量集运行器（只读，不建库不改任教设置）")
    parser.add_argument("--set", default=str(REPO_ROOT / "tests" / "fixtures" / "rag-quality-set.json"))
    parser.add_argument("--data-dir", help="数据根目录（默认正式 .local-data，只读打开）")
    parser.add_argument("--qdrant", help="Qdrant 地址")
    parser.add_argument("--report", help="报告输出路径")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
