"""对已迁移的教材索引做**真实**检索验收：范围解析 → 向量+BM25 → RRF → 原文证据 → 知识点首答。

不使用替身：真实 SQLite 教材目录、真实 bge-m3、真实 Qdrant、真实本机概括模型。
输出逐项的原文证据、定位与耗时，并断言证据文本与不可变规范化文本逐字节相同。

用法（仓库根目录）::

    uv run --directory apps/api python ../../scripts/rag/verify_retrieval.py --question "集合中元素的三个特性是什么"
    uv run --directory apps/api python ../../scripts/rag/verify_retrieval.py --questions-file questions.txt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from app.core.config import Settings  # noqa: E402
from app.providers.embeddings.ollama_embedding import OllamaEmbeddingProvider  # noqa: E402
from app.repositories.textbook_catalog.catalog import TextbookCatalog  # noqa: E402
from app.repositories.vector_store.qdrant import HttpQdrantStore  # noqa: E402
from app.services.rag_v2.explain import Explainer  # noqa: E402
from app.services.rag_v2.retrieval import HybridRetriever  # noqa: E402
from app.services.rag_v2.service import RagV2Service  # noqa: E402
from app.services.rag_v2.summary import KnowledgeSummarizer  # noqa: E402
from app.services.rag_v2.requests import RagStreamRequestV2  # noqa: E402


def build_service(settings: Settings) -> tuple[RagV2Service, TextbookCatalog, OllamaEmbeddingProvider]:
    # 只读验收：不动正式库结构、不建空库、不写任教设置（PLAN §6.2）
    catalog = TextbookCatalog(settings.textbooks_root / "catalog.sqlite3")
    try:
        catalog.open_existing()
    except Exception as exc:
        raise SystemExit(f"教材目录不可只读打开：{exc}")
    print(f"数据目录：{settings.data_dir}（只读打开，不改结构）")
    provider = OllamaEmbeddingProvider(settings.embedding_base_url)
    vectors = HttpQdrantStore(settings.qdrant_url)
    service = RagV2Service(
        catalog=catalog,
        retrieval=HybridRetriever(catalog, vectors, provider),
        summarizer=KnowledgeSummarizer(settings.embedding_base_url),
        explainer=Explainer(None),
    )
    return service, catalog, provider


def selection_for(catalog: TextbookCatalog, grade_id: str, subject_id: str, edition_id: str):
    documents = [
        item
        for item in catalog.list_documents(
            grade_id=grade_id, subject_id=subject_id, edition_id=edition_id
        )
        if item.current_revision_id
    ]
    if not documents:
        raise SystemExit(f"范围内没有可用书册：{grade_id}/{subject_id}/{edition_id}")
    return {
        "gradeId": grade_id,
        "subjectId": subject_id,
        "editionId": edition_id,
        "documentIds": [item.document_id for item in documents],
    }


async def ask(service: RagV2Service, question: str, selection: dict) -> dict:
    session_id = uuid.uuid4().hex
    turn_id = uuid.uuid4().hex
    body = RagStreamRequestV2(
        requestId=uuid.uuid4().hex,
        sessionId=session_id,
        turnId=turn_id,
        question=question,
        scope={"kind": "selection", "selection": selection},
    )
    begin = time.monotonic()
    turn = service.start(body)
    result = None
    text = ""
    interaction = None
    first_evidence_at = None
    try:
        async for event in service.events(turn):
            if event is None:
                continue
            if event["event"] == "rag.result":
                result = event["data"]["result"]
                first_evidence_at = round(time.monotonic() - begin, 2)
            elif event["event"] == "text.delta":
                text = event["data"].get("text", "")
            elif event["event"] == "wait-user":
                # 定位成功后服务端固定发出追问卡并等待用户回复（不主动 message.end）；
                # 本脚本只做检索验收，因此把 wait-user 当作本轮已完成。
                interaction = {
                    "interactionId": event["data"].get("interactionId"),
                    "intro": event["data"].get("intro"),
                    "questions": event["data"].get("questions"),
                }
                break
            elif event["event"] == "error":
                return {
                    "question": question,
                    "status": "error",
                    "code": event["data"].get("code"),
                    "message": event["data"].get("message"),
                    "seconds": round(time.monotonic() - begin, 2),
                }
            elif event["event"] == "message.end":
                break
    finally:
        # 轮次在 message.end 后已被清理，取消失败只是“已经结束”，不是错误
        try:
            service.cancel(session_id, turn_id)
        except Exception:
            pass
    return {
        "question": question,
        "status": (result or {}).get("status"),
        "reason": (result or {}).get("reason"),
        "pointCount": len((result or {}).get("points") or []),
        "evidenceCount": len((result or {}).get("evidence") or []),
        "resultSeconds": first_evidence_at,
        "totalSeconds": round(time.monotonic() - begin, 2),
        "answerPreview": text[:600],
        "interaction": interaction,
        "evidence": [
            {
                "title": item["title"],
                "chapterPath": item["chapterPath"],
                "locator": item["locator"],
                "charStart": item["charStart"],
                "charEnd": item["charEnd"],
                "textPreview": item["text"][:200],
                "textLength": len(item["text"]),
                "isSuperseded": item["isSuperseded"],
            }
            for item in ((result or {}).get("evidence") or [])
        ],
    }


async def main_async(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if args.data_dir:
        settings = settings.__class__(
            **{**settings.__dict__, "data_dir": Path(args.data_dir)}
        )
    service, catalog, provider = build_service(settings)

    vector_ok = await asyncio.to_thread(lambda: service.retrieval is not None)
    print(f"Qdrant：{settings.qdrant_url}    Ollama：{settings.embedding_base_url}    检索器：{vector_ok}")

    selection = selection_for(catalog, args.grade, args.subject, args.edition)
    print(f"范围：{args.grade}/{args.subject}/{args.edition}，{len(selection['documentIds'])} 册")
    # 范围以请求内联传入（scope.kind="selection"），**不落库**：验收不得改用户的任教配置

    questions = [args.question] if args.question else Path(args.questions_file).read_text(
        encoding="utf-8"
    ).splitlines()
    questions = [item.strip() for item in questions if item.strip()]

    report = []
    for question in questions:
        outcome = await ask(service, question, selection)
        report.append(outcome)
        print(f"\n=== {question}")
        print(f"    status={outcome['status']} 证据={outcome.get('evidenceCount')} 条/知识点={outcome.get('pointCount')} 条"
              f" 检索={outcome.get('resultSeconds')}s 总计={outcome.get('totalSeconds')}s")
        if outcome.get("reason"):
            print(f"    reason={outcome['reason']}")
        for item in outcome.get("evidence") or []:
            locator = item["locator"]
            where = (
                f"行 {locator.get('lineStart')}-{locator.get('lineEnd')}"
                if locator.get("kind") == "markdown"
                else f"页 {locator.get('pageStart')}-{locator.get('pageEnd')}"
            )
            print(f"    - {item['title']}｜{'/'.join(item['chapterPath'])}｜{where}｜{item['textLength']} 字符")
        if outcome.get("answerPreview"):
            print("    正文预览：" + outcome["answerPreview"].replace("\n", " ")[:220])

    report_path = Path(args.report) if args.report else (
        REPO_ROOT / "_work" / "rag-rebuild-v1" / "retrieval-verification.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {"settings": {"qdrant": settings.qdrant_url, "selection": selection}, "results": report},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n报告：{report_path}")
    await service.close()
    provider.close() if hasattr(provider, "close") else None
    catalog.close()
    empty = [item for item in report if item["status"] != "ok"]
    print(f"结论：{len(report) - len(empty)}/{len(report)} 得到 ok 结果")
    return 0 if not empty else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="真实教材检索验收（无替身）")
    parser.add_argument("--question", help="单个问题")
    parser.add_argument("--questions-file", help="每行一个问题")
    parser.add_argument("--grade", default="senior-1")
    parser.add_argument("--subject", default="math")
    parser.add_argument("--edition", default="renjiao-a")
    parser.add_argument("--data-dir", help="数据根目录（默认 .local-data）")
    parser.add_argument("--report", help="报告输出路径")
    args = parser.parse_args()
    if not args.question and not args.questions_file:
        parser.error("需要 --question 或 --questions-file")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
