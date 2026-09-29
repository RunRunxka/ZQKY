"""检索命中率测量（top-k / MRR）——标签由**文档结构**自动给出，不依赖人工判分。

标签来源：把每个 Markdown 小节标题（如「1.2 空间向量基本定理」）当作查询，
正确结果定义为「该小节自己的正文块」。命中判据 = 前 k 个融合候选里
存在同一修订、且 `chapter_path` 叶子相同的块。因此这个指标衡量的是
**小节可定位性**，不是「答案是否正确」。

必须如实说明的偏差（写进输出与报告）：
- 查询与目标共享词面（甚至只差编号），所以**这是真实提问命中率的上界**，
  比学生口语化提问容易得多；不能用它替代金标集评测。
- 只覆盖**结构化标题**能命中的范围；表格、公式、习题区的定位质量不在其中。
- 走的是产品同一条检索路径（范围核验 → 稠密 50 + BM25 50 + RRF k=60），
  不是另写一套"评测专用"检索。

用法::

    uv run --directory apps/api python ../../scripts/rag/measure_hit_rate.py --sample 400
    uv run --directory apps/api python ../../scripts/rag/measure_hit_rate.py --all
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from app.core.config import Settings  # noqa: E402
from app.providers.embeddings.ollama_embedding import OllamaEmbeddingProvider  # noqa: E402
from app.repositories.textbook_catalog.catalog import TextbookCatalog  # noqa: E402
from app.repositories.vector_store.qdrant import HttpQdrantStore  # noqa: E402
from app.services.rag_v2.retrieval import HybridRetriever  # noqa: E402
from app.services.rag_v2.scope import resolve_scope, verify_scope  # noqa: E402
from app.schemas.textbook import TextbookSelection  # noqa: E402

#: 不作为可检索小节的叶子标题（目录、导引、排版残留等）
STOP_LEAVES = {
    "", "目录", "探究", "思考", "练习", "习题", "前言", "小结", "本册导引",
    "阅读与思考", "阅读", "问题", "提示", "归纳", "归纳总结", "例题", "答案",
    "复习参考题", "章末", "本章小结", "后记", "版权", "致谢", "● ●", "◆ ◆",
    "图像", "表格", "栏目", "说明",
}
LEADING_NUMBER = re.compile(r"^[第]?[\d一二三四五六七八九十百零]+\s*[章节讲单元课.]*[\s\d.、]*")
MIN_LEAF_CHARS = 4
MAX_LEAF_CHARS = 30
#: 练习/活动指令行——它们是任务说明而不是知识点小节，作为查询无区分度
INSTRUCTION_PATTERN = re.compile(
    r"^\s*\d*\s*(complete|listen|answer|exchange|work|discuss|read|write|look|choose|fill|"
    r"match|translate|talk|watch|use|make|share|prepare|review|check|study|tell|think|summar)",
    re.IGNORECASE,
)
#: 只有册次/单元/目录这类通用词，检索上没有唯一目标
GENERIC_ONLY = re.compile(r"^(unit|section|part|contents?|appendix|glossary)\s*\d*$", re.IGNORECASE)
MIN_SECTION_CHUNKS = 2
#: 教材「栏目」名——它们是版式标签（侧栏/活动栏），不是可检索的知识点小节。
#: 作为查询没有唯一目标，留在集合里只会把检索质量算低。
COLUMN_KEYWORDS = (
    "学习聚焦", "本节聚焦", "聚焦", "资料卡片", "结果与讨论", "研究样例", "尝试与发现",
    "思考与讨论", "活动主题", "史料阅读", "问题探究", "拓展应用", "概念检测", "思考",
    "探究", "阅读与思考", "相关信息", "提示", "注意", "方法导引", "科学史话", "科学技术社会",
    "练习与应用", "复习与提高", "单元小结", "REFLECTING", "PROJECT", "VIDEO TIME",
    "In this unit", "WORD STUDY", "Listening", "Speaking", "Reading and Thinking",
)


def collect_sections(catalog: TextbookCatalog, generation_id: str):
    """返回 [(document_revision_id, title, 叶子, 块 ordinals, subject_id)]。"""
    sections = []
    for link in catalog.list_generation_revisions(generation_id):
        if link.state != "ready":
            continue
        revision = catalog.get_revision(link.document_revision_id)
        if revision is None:
            continue
        document = catalog.get_document(revision.document_id)
        if document is None or document.deleted_at:
            continue
        metadata = catalog.current_metadata_revision(document.document_id)
        chunks = [c for c in catalog.list_chunks(link.chunk_set_id) if c.region == "body"]
        grouped: dict[str, list] = defaultdict(list)
        for chunk in chunks:
            leaf = (chunk.chapter_path[-1] if chunk.chapter_path else "").strip()
            grouped[leaf].append(chunk)
        for leaf, items in grouped.items():
            bare = LEADING_NUMBER.sub("", leaf).strip()
            if leaf in STOP_LEAVES or len(bare) < MIN_LEAF_CHARS:
                continue
            if len(bare) > MAX_LEAF_CHARS:
                continue
            if bare in STOP_LEAVES:
                continue
            if INSTRUCTION_PATTERN.match(bare) or GENERIC_ONLY.match(bare):
                continue
            if any(keyword.lower() in bare.lower() for keyword in COLUMN_KEYWORDS):
                continue
            if not any(ch.isalpha() for ch in bare):
                continue
            # 只保留有实质正文的小节：至少 MIN_SECTION_CHUNKS 个正文块
            if len(items) < MIN_SECTION_CHUNKS:
                continue
            sections.append(
                {
                    "revisionId": revision.revision_id,
                    "documentId": document.document_id,
                    "documentTitle": document.title,
                    "subjectId": metadata.subject_id,
                    "gradeId": metadata.grade_ids[0] if metadata.grade_ids else "",
                    "editionId": metadata.edition_id,
                    "leaf": leaf,
                    "path": tuple(items[0].chapter_path) if items[0].chapter_path else (),
                    "ordinals": sorted(item.ordinal for item in items),
                    "chunkSetId": link.chunk_set_id,
                }
            )
    return sections


def main() -> int:
    parser = argparse.ArgumentParser(description="检索命中率测量（小节可定位性，非教学质量）")
    parser.add_argument("--data-dir", help="数据根目录（默认正式 .local-data）")
    parser.add_argument("--qdrant", help="Qdrant 地址（默认正式 6333）")
    parser.add_argument("--sample", type=int, default=0, help="随机抽样多少个查询（0=全部）")
    parser.add_argument("--all", action="store_true", help="跑全部查询")
    parser.add_argument("--seed", type=int, default=20260928)
    parser.add_argument("--report", help="报告输出路径")
    args = parser.parse_args()

    settings = Settings.from_env()
    if args.data_dir:
        settings = settings.__class__(**{**settings.__dict__, "data_dir": Path(args.data_dir)})
    if args.qdrant:
        settings = settings.__class__(**{**settings.__dict__, "qdrant_url": args.qdrant})

    # 只读测量：不动正式库结构、不建空库（PLAN §6.2）
    catalog_path = settings.textbooks_root / "catalog.sqlite3"
    if not catalog_path.is_file():
        raise SystemExit(f"教材目录不存在，拒绝创建空库：{catalog_path}")
    catalog = TextbookCatalog(catalog_path)
    provider = OllamaEmbeddingProvider(settings.embedding_base_url)
    vectors = HttpQdrantStore(settings.qdrant_url)
    generation_id = catalog.catalog_state().active_generation_id
    if not generation_id:
        print("没有已发布的索引代。", file=sys.stderr)
        return 2
    generation = catalog.get_generation(generation_id)
    profile = catalog.get_embedding_profile(generation.profile_id)
    print(f"索引代 {generation_id} / 模型 {profile.model_name}（{profile.dimensions} 维）")

    # 范围 = 全部可用书册（最难的"全库搜"设置，与产品一样先解析再冻结）
    documents = [
        item
        for item in catalog.list_documents()
        if item.current_revision_id
    ]
    by_key = defaultdict(list)
    for item in documents:
        metadata = catalog.current_metadata_revision(item.document_id)
        by_key[(metadata.grade_ids[0] if metadata.grade_ids else "", metadata.subject_id, metadata.edition_id)].append(item.document_id)

    sections = collect_sections(catalog, generation_id)
    print(f"可评测小节 {len(sections)} 个（来自 {len(documents)} 册）")
    if not sections:
        return 2
    if args.sample and not args.all:
        random.Random(args.seed).shuffle(sections)
        sections = sections[: args.sample]
        print(f"抽样 {len(sections)} 个查询（seed={args.seed}）")

    retriever = HybridRetriever(catalog, vectors, provider)
    hits = {1: 0, 3: 0, 5: 0, 10: 0}
    chapter_hits = {1: 0, 3: 0, 5: 0, 10: 0}
    rr_sum = 0.0
    chapter_rr = 0.0
    per_subject = defaultdict(
        lambda: {"n": 0, "h1": 0, "h5": 0, "h10": 0, "c1": 0, "c5": 0, "c10": 0}
    )
    failures = []
    started = time.monotonic()

    # 按 (年级,学科,版本) 分组，一次性冻结范围并复用（同一范围内 BM25 缓存可复用）
    buckets: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for item in sections:
        buckets[(item["gradeId"], item["subjectId"], item["editionId"])].append(item)

    done = 0
    for key, items in buckets.items():
        grade_id, subject_id, edition_id = key
        document_ids = by_key.get(key) or []
        if not document_ids:
            continue
        selection = TextbookSelection(
            gradeId=grade_id,
            subjectId=subject_id,
            editionId=edition_id,
            documentIds=document_ids,
        )
        scope = verify_scope(catalog, resolve_scope(catalog, selection))
        for item in items:
            query = LEADING_NUMBER.sub("", item["leaf"]).strip() or item["leaf"]
            try:
                candidates = retriever.retrieve(
                    question=query, scope=scope, profile=profile, generation=generation
                )
            except Exception as exc:  # 检索失败如实计入，不跳过
                failures.append({"leaf": item["leaf"], "error": f"{type(exc).__name__}: {exc}"})
                per_subject[subject_id]["n"] += 1
                done += 1
                continue
            rank = None
            chapter_rank = None
            target_chapter = item["path"][0] if item["path"] else ""
            for position, candidate in enumerate(candidates[:10], start=1):
                if candidate.document_revision_id != item["revisionId"]:
                    continue
                parts = [part.strip() for part in candidate.chapter_path]
                # 叶子级（严格）：被查小节标题出现在候选的章节路径里
                if rank is None and item["leaf"] in parts:
                    rank = position
                # 同章级（宽松，接近旧项目的"节级"口径）：与目标属于同一顶层章节
                if (
                    chapter_rank is None
                    and target_chapter
                    and parts
                    and parts[0] == target_chapter
                ):
                    chapter_rank = position
                if rank is not None and chapter_rank is not None:
                    break
            for k in hits:
                if rank is not None and rank <= k:
                    hits[k] += 1
                if chapter_rank is not None and chapter_rank <= k:
                    chapter_hits[k] += 1
            rr_sum += 1.0 / rank if rank else 0.0
            chapter_rr += 1.0 / chapter_rank if chapter_rank else 0.0
            stats = per_subject[subject_id]
            stats["n"] += 1
            if rank == 1:
                stats["h1"] += 1
            if rank is not None and rank <= 5:
                stats["h5"] += 1
            if rank is not None and rank <= 10:
                stats["h10"] += 1
            if chapter_rank == 1:
                stats["c1"] += 1
            if chapter_rank is not None and chapter_rank <= 5:
                stats["c5"] += 1
            if chapter_rank is not None and chapter_rank <= 10:
                stats["c10"] += 1
            if rank is None and len(failures) < 40:
                failures.append(
                    {
                        "leaf": item["leaf"],
                        "book": item["documentTitle"],
                        "top3": [
                            "/".join(c.chapter_path)[:60] for c in candidates[:3]
                        ],
                    }
                )
            done += 1
            if done % 50 == 0:
                print(
                    f"  …{done}/{len(sections)}  "
                    f"Hit@1={hits[1]/done:.3f} Hit@5={hits[5]/done:.3f} Hit@10={hits[10]/done:.3f}",
                    flush=True,
                )

    total = sum(stat["n"] for stat in per_subject.values()) or 1
    report = {
        "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "indexGenerationId": generation_id,
        "model": profile.model_name,
        "dimensions": profile.dimensions,
        "scope": "全部已就绪书册（全库竞争）",
        "labelSource": "文档结构：小节标题 → 该小节自己的正文块",
        "meaning": "小节可定位性（不是答案正确率，也不是教学质量）",
        "bias": "查询与目标共享词面，是真实提问命中率的上界；不能替代金标集评测",
        "queries": total,
        "leafLevel": {
            "hitAt1": round(hits[1] / total, 4),
            "hitAt3": round(hits[3] / total, 4),
            "hitAt5": round(hits[5] / total, 4),
            "hitAt10": round(hits[10] / total, 4),
            "mrrAt10": round(rr_sum / total, 4),
        },
        "chapterLevel": {
            "hitAt1": round(chapter_hits[1] / total, 4),
            "hitAt3": round(chapter_hits[3] / total, 4),
            "hitAt5": round(chapter_hits[5] / total, 4),
            "hitAt10": round(chapter_hits[10] / total, 4),
            "mrrAt10": round(chapter_rr / total, 4),
        },
        "perSubject": {
            name: {
                "queries": stat["n"],
                "leafHitAt1": round(stat["h1"] / stat["n"], 4) if stat["n"] else None,
                "leafHitAt5": round(stat["h5"] / stat["n"], 4) if stat["n"] else None,
                "leafHitAt10": round(stat["h10"] / stat["n"], 4) if stat["n"] else None,
                "chapterHitAt1": round(stat["c1"] / stat["n"], 4) if stat["n"] else None,
                "chapterHitAt5": round(stat["c5"] / stat["n"], 4) if stat["n"] else None,
                "chapterHitAt10": round(stat["c10"] / stat["n"], 4) if stat["n"] else None,
            }
            for name, stat in sorted(per_subject.items())
        },
        "perSubjectGranularity": "leafHit*=叶子级严格；chapterHit*=同章级宽松",
        "elapsedSeconds": round(time.monotonic() - started, 1),
        "failures": failures[:40],
    }
    out = Path(args.report) if args.report else (
        REPO_ROOT / "_work" / "rag-rebuild-v1" / "hit-rate.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    leaf, chapter = report["leafLevel"], report["chapterLevel"]
    print(
        f"\n查询 {total} 条\n"
        f"  叶子级（严格）：Hit@1 {leaf['hitAt1']:.3f} / Hit@3 {leaf['hitAt3']:.3f} "
        f"/ Hit@5 {leaf['hitAt5']:.3f} / Hit@10 {leaf['hitAt10']:.3f} / MRR@10 {leaf['mrrAt10']:.3f}\n"
        f"  同章级（宽松）：Hit@1 {chapter['hitAt1']:.3f} / Hit@3 {chapter['hitAt3']:.3f} "
        f"/ Hit@5 {chapter['hitAt5']:.3f} / Hit@10 {chapter['hitAt10']:.3f} / MRR@10 {chapter['mrrAt10']:.3f}"
    )
    print(f"用时 {report['elapsedSeconds']}s，报告 {out}")
    catalog.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
