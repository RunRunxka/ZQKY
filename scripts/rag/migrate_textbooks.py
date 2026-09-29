"""把只读原始教材目录（人教版 markdown 副本）迁移进正式教材目录与向量索引。

设计要点：
- 复用真实入库链路（``IngestService``）：封存不可变修订 → 分块 → 本地 Embedding →
  Qdrant 写入 → 原子发布。不另写一套"迁移专用"入库逻辑。
- 幂等：同一文件重复执行不产生重复书册；命中既有书册时走**更新**路径
  （新增修订并发布），旧修订与其历史引用保留可读。
- 只读源目录：原件由入库链路复制进受管 blobs，源目录一个字节都不写。
- 失败逐册记录，不中断整批；报告写入 ``_work`` 或指定路径。

用法（在仓库根目录）::

    uv run --directory apps/api python ../../scripts/rag/migrate_textbooks.py --limit 1
    uv run --directory apps/api python ../../scripts/rag/migrate_textbooks.py

或直接用仓库脚本 ``npm run rag:migrate -- --limit 1``。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from app.core.config import Settings  # noqa: E402
from app.providers.embeddings.ollama_embedding import OllamaEmbeddingProvider  # noqa: E402
from app.repositories.textbook_catalog.catalog import TextbookCatalog  # noqa: E402
from app.repositories.vector_store.qdrant import HttpQdrantStore  # noqa: E402
from app.services.document_parsing.chunking import chunk_document  # noqa: E402
from app.services.document_parsing.parser import parse_document  # noqa: E402
from app.services.textbook_index.service import IndexService  # noqa: E402
from app.services.textbook_ingest.service import IngestService  # noqa: E402

OWNER_ID = "system"

#: 顶层目录名 → (学科 id, 版本 id)。与 `app/services/textbook_ingest/taxonomy.py` 的字典一致。
SUBJECT_DIRS: dict[str, tuple[str, str]] = {
    "人教A版高中数学【电子课本】": ("math", "renjiao-a"),
    "人教B版高中数学【电子课本】": ("math", "renjiao-b"),
    "人教版高中语文【电子课本】": ("chinese", "renjiao"),
    "人教版高中英语【电子课本】": ("english", "renjiao"),
    "人教版高中物理【电子课本】": ("physics", "renjiao"),
    "人教版高中化学【电子课本】": ("chemistry", "renjiao"),
    "人教版高中生物【电子课本】": ("biology", "renjiao"),
    "人教版高中历史【电子课本】": ("history", "renjiao"),
    "人教版高中地理【电子课本】": ("geography", "renjiao"),
    "人教版高中政治【电子课本】": ("politics", "renjiao"),
}

#: 年级归属是**推断**（必修→高一、选修/选择性必修→高二），由教师在教材管理页确认后修正。
GRADE_BY_KEYWORD: tuple[tuple[str, str], ...] = (
    ("选择性必修", "senior-2"),
    ("选修", "senior-2"),
    ("必修", "senior-1"),
)

SPECIAL_BOOKS = {"人教版高中政治【学生读本】.pdf": ("senior-2", "学生读本")}

#: id → 中文标签，与 `app/services/textbook_ingest/taxonomy.py` 一致。
#: 逻辑库显示名用标签而不是内部 id，教师看到的是「高一 · 数学 · 人教A版」。
GRADE_LABELS = {"senior-1": "高一", "senior-2": "高二", "senior-3": "高三"}
SUBJECT_LABELS = {
    "chinese": "语文",
    "math": "数学",
    "english": "英语",
    "physics": "物理",
    "chemistry": "化学",
    "biology": "生物",
    "history": "历史",
    "geography": "地理",
    "politics": "思想政治",
}
EDITION_LABELS = {"renjiao-a": "人教A版", "renjiao-b": "人教B版", "renjiao": "人教版"}


def library_display_name(grade_id: str, subject_id: str, edition_id: str) -> str:
    grade = GRADE_LABELS.get(grade_id, grade_id)
    subject = SUBJECT_LABELS.get(subject_id, subject_id)
    edition = EDITION_LABELS.get(edition_id, edition_id)
    return f"{grade} · {subject} · {edition}"


@dataclass
class BookTask:
    subject_id: str
    edition_id: str
    grade_id: str
    title: str
    volume_label: str
    source: Path


@dataclass
class BookResult:
    title: str
    subject_id: str
    grade_id: str
    edition_id: str
    status: str
    document_id: str | None = None
    revision_id: str | None = None
    chunk_count: int = 0
    char_count: int = 0
    job_state: str | None = None
    error: str | None = None
    seconds: float = 0.0
    notes: list[str] = field(default_factory=list)


def normalize_book_name(raw: str) -> str:
    """把带 uuid 后缀的电子课本目录名还原成可读书名（去掉 .pdf-<uuid> 与冗余后缀）。"""
    text = re.sub(r"\.pdf-[0-9a-f-]{8,}$", "", raw)
    text = text.replace("【高清教材】", "").replace("【电子课本】", "")
    return text.strip()


def grade_of(name: str) -> str:
    for keyword, grade in GRADE_BY_KEYWORD:
        if keyword in name:
            return grade
    return "senior-1"


def volume_of(name: str) -> str:
    for mark in ("第一册", "第二册", "第三册", "第四册", "上册", "中册", "下册"):
        if mark in name:
            return mark
    # 先判「选择性必修」，否则「选择性必修1」会被「必修」规则误吃成「必修1」
    match = re.search(r"选择性必修\s*(\d+)", name)
    if match:
        return f"选择性必修{match.group(1)}"
    match = re.search(r"(?<!性)必修\s*(\d+)", name)
    if match:
        return f"必修{match.group(1)}"
    match = re.search(r"选修\s*(\d+)", name)
    if match:
        return f"选修{match.group(1)}"
    return ""


def discover_books(source_root: Path) -> tuple[list[BookTask], list[str]]:
    """枚举源目录里的每册教材；返回 (任务列表, 跳过说明)。"""
    tasks: list[BookTask] = []
    skipped: list[str] = []
    for directory in sorted(source_root.iterdir()):
        if not directory.is_dir():
            continue
        mapping = SUBJECT_DIRS.get(directory.name)
        if mapping is None:
            skipped.append(f"{directory.name}：未登记的学科目录")
            continue
        subject_id, edition_id = mapping
        for path in sorted(directory.rglob("*.md")):
            stem = path.parent.name if path.parent != directory else path.stem
            raw_name = stem.split(".pdf-")[0]
            title = normalize_book_name(raw_name)
            special = SPECIAL_BOOKS.get(f"{raw_name}.pdf")
            grade_id, volume_label = (
                special if special else (grade_of(title), volume_of(title))
            )
            tasks.append(
                BookTask(
                    subject_id=subject_id,
                    edition_id=edition_id,
                    grade_id=grade_id,
                    title=title,
                    volume_label=volume_label,
                    source=path,
                )
            )
    return tasks, skipped


def ensure_profile_and_generation(index: IndexService, *, model_name: str):
    """登记（或复用）Embedding 配置并保证存在一个可写索引代。"""
    probe = index.probe(model_name=model_name)
    listed = index.list_profiles()
    active = next(
        (item for item in listed.profiles if item.modelName == probe.modelName), None
    )
    if active is None:
        active = index.create_profile(model_name=model_name)
    current = index.status()
    if current.activeGenerationId is None:
        index.ensure_empty_generation(active.profileId)
        current = index.status()
    return active, current


def stage_from_zip(zip_path: Path, staging: Path) -> Path:
    """把归档里的 ``markdown/`` 树解到临时目录，返回可作为 source_root 的路径。

    原始归档（`F:\\人教版教材.zip`）与 `F:\\人教版教材\\markdown` 都只读；解压只写 `_work`。
    归档里 markdown 只占很小一部分，这里只解 `.md`，避免把 1.4 GB 的图片一起展开。
    **调用方必须传本次运行独占的目录**：两次迁移并发时共用同一个暂存目录会互相截断文件
    （实测 58 册在共用目录下会瞬时只剩 56 册）。
    """
    import zipfile

    staging.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        members = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".md") and "/markdown/" in name.replace("\\", "/")
        ]
        if not members:
            raise SystemExit(f"归档里没有 markdown：{zip_path}")
        for name in members:
            relative = name.replace("\\", "/").split("/markdown/", 1)[1]
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, target.open("wb") as destination:
                destination.write(source.read())
    return staging


def migrate(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if args.source:
        settings = settings.__class__(**{**settings.__dict__, "textbook_source_dir": Path(args.source)})
    if args.data_dir:
        settings = settings.__class__(**{**settings.__dict__, "data_dir": Path(args.data_dir)})

    if args.source_zip:
        # 源目录被外部流程清空后，归档是唯一可复现来源；解压到本次运行独占的暂存目录再走同一流程
        staging_root = (
            Path(args.staging)
            if args.staging
            else REPO_ROOT / "_work" / "rag-rebuild-v1" / f"source-md-{os.getpid()}"
        )
        staged = stage_from_zip(Path(args.source_zip), staging_root)
        settings = settings.__class__(
            **{**settings.__dict__, "textbook_source_dir": staged}
        )
        print(f"已从归档解出 markdown → {staged}")
    source_root = Path(settings.textbook_source_dir)
    if not source_root.is_dir():
        print(f"来源教材目录不可用：{source_root}", file=sys.stderr)
        return 2
    tasks, skipped = discover_books(source_root)
    if args.only:
        wanted = set(args.only.split(","))
        tasks = [task for task in tasks if task.subject_id in wanted]
    if args.limit:
        tasks = tasks[: args.limit]
    if not tasks:
        print("没有可迁移的教材。", file=sys.stderr)
        return 2
    if args.dry_run:
        print(f"来源目录：{source_root}")
        print(f"识别教材 {len(tasks)} 册" + (f"；跳过目录：{skipped}" if skipped else ""))
        for index_no, task in enumerate(tasks, start=1):
            print(
                f"  {index_no:>3}. [{task.subject_id}/{task.edition_id}/{task.grade_id}] "
                f"{task.title}（{task.volume_label or '未标册次'}）"
            )
        return 0

    # 写数据的 CLI 与 API 持同一把数据根排他锁：API 在跑时迁移会明确失败，
    # 而不是两个写入者同时改同一个数据根（见 docs/PLAN.md §5.2）。
    from app.core.data_lock import acquire_data_lock

    data_lock = acquire_data_lock(settings.data_dir, exclusive=True, label="rag-migrate")
    data_lock.__enter__()
    try:
        return _migrate_locked(args, settings, tasks=tasks, skipped=skipped)
    finally:
        data_lock.__exit__(None, None, None)


def _migrate_locked(args, settings, *, tasks: list[BookTask], skipped: list[str]) -> int:
    import tempfile

    # 本次运行独占的源文件副本目录：源目录只读，绝不移动/删除源文件
    stage_dir = Path(tempfile.mkdtemp(prefix="rag-migrate-src-"))
    print(f"源文件副本目录：{stage_dir}（源目录只读）")
    catalog = TextbookCatalog(settings.textbooks_root / "catalog.sqlite3")
    catalog.migrate()
    provider = OllamaEmbeddingProvider(settings.embedding_base_url)
    vectors = HttpQdrantStore(settings.qdrant_url)
    if not vectors.ping():
        print(f"Qdrant 不可达：{settings.qdrant_url}", file=sys.stderr)
        return 3
    ingest = IngestService(
        catalog, parse_document, chunk_document, provider, vectors, settings
    )
    index = IndexService(catalog, provider, vectors, settings)

    profile, status = ensure_profile_and_generation(index, model_name=args.model)
    generation_id = status.activeGenerationId
    print(f"Embedding 配置：{profile.modelName}（{profile.dimensions} 维，{profile.profileId}）")
    print(f"当前索引代：{generation_id}")
    print(f"待迁移教材：{len(tasks)} 册；可检索正文块总量会随分块结果增长\n")

    libraries: dict[tuple[str, str, str], str] = {}
    results: list[BookResult] = []
    started = time.monotonic()

    for index_no, task in enumerate(tasks, start=1):
        label = f"[{index_no}/{len(tasks)}] {task.title}"
        begin = time.monotonic()
        result = BookResult(
            title=task.title,
            subject_id=task.subject_id,
            grade_id=task.grade_id,
            edition_id=task.edition_id,
            status="pending",
        )
        try:
            key = (task.grade_id, task.subject_id, task.edition_id)
            library_id = libraries.get(key)
            if library_id is None:
                existing = [
                    item
                    for item in catalog.list_libraries(
                        grade_id=task.grade_id,
                        subject_id=task.subject_id,
                        edition_id=task.edition_id,
                    )
                    if item.kind == "base"
                ]
                if existing:
                    library_id = existing[0].library_id
                    readable = library_display_name(
                        task.grade_id, task.subject_id, task.edition_id
                    )
                    if existing[0].display_name != readable:
                        # 早期迁移写过内部 id（senior-1 · math · renjiao-a），这里顺手修正成教师可读的名字
                        catalog.update_library(
                            library_id,
                            expected_revision=existing[0].revision,
                            display_name=readable,
                        )
                else:
                    record = catalog.create_library(
                        kind="base",
                        owner_id=OWNER_ID,
                        display_name=library_display_name(
                            task.grade_id, task.subject_id, task.edition_id
                        ),
                        grade_id=task.grade_id,
                        subject_id=task.subject_id,
                        edition_id=task.edition_id,
                    )
                    library_id = record.library_id
                libraries[key] = library_id

            same_title = [
                item
                for item in catalog.list_documents(
                    subject_id=task.subject_id, edition_id=task.edition_id
                )
                if item.title == task.title
            ]
            target = same_title[0] if same_title else None
            if target is not None:
                result.document_id = target.document_id
                result.notes.append("命中既有书册，按更新路径追加修订")

            # 入库链路对"上传暂存文件"是**移动**语义（浏览器上传后临时文件即可丢弃）。
            # 源教材必须保持不动，因此先复制到本次运行独占的暂存目录，再把副本交给入库。
            staged_copy = stage_dir / f"{abs(hash(str(task.source))):x}{task.source.suffix}"
            shutil.copy2(task.source, staged_copy)

            metadata = {
                "title": task.title,
                "stageId": "senior",
                "gradeIds": [task.grade_id],
                "subjectId": task.subject_id,
                "editionId": task.edition_id,
                "publicationLabel": "人教版",
                "volumeLabel": task.volume_label,
            }
            draft = ingest.create_import_from_path(
                file_name=task.source.name,
                staged_path=staged_copy,
                metadata=metadata,
                target_document_id=target.document_id if target else None,
                expected_current_revision_id=(
                    target.current_revision_id if target else None
                ),
                confirm_metadata=True,
                owner_id=OWNER_ID,
            )
            job = ingest.commit_import(
                draft.importId,
                expected_revision=draft.revision,
                submission_id=f"migrate-{task.subject_id}-{task.edition_id}-{abs(hash(task.title)):x}",
                library_ids=[library_id],
                acknowledge_warnings=True,
            )
            finished = ingest.run_ingest_job(job.jobId)
            result.job_state = finished.state
            if finished.state != "succeeded":
                result.status = "failed"
                result.error = f"{finished.errorCode}: {finished.errorMessage}"
            else:
                document = catalog.get_document(finished.documentId or "")
                revision_id = document.current_revision_id if document else None
                result.revision_id = revision_id
                if revision_id:
                    record = catalog.get_revision(revision_id)
                    result.char_count = record.char_count if record else 0
                    result.chunk_count = next(
                        (
                            item.expected_chunk_count
                            for item in catalog.list_generation_revisions(generation_id)
                            if item.document_revision_id == revision_id
                        ),
                        0,
                    )
                result.status = "migrated"
        except Exception as exc:  # 逐册失败不中断整批
            result.status = "failed"
            result.error = f"{type(exc).__name__}: {exc}"
        result.seconds = round(time.monotonic() - begin, 1)
        results.append(result)
        mark = "OK " if result.status == "migrated" else "FAIL"
        print(
            f"{mark} {label} — {result.char_count} 字符 / {result.chunk_count} 块 "
            f"/ {result.seconds}s" + (f" — {result.error}" if result.error else "")
        )

    elapsed = round(time.monotonic() - started, 1)
    final = index.status()
    report = {
        "sourceRoot": str(settings.textbook_source_dir),
        "model": profile.modelName,
        "dimensions": profile.dimensions,
        "profileId": profile.profileId,
        "generationId": generation_id,
        "generationChunkTotal": final.generation.chunkTotal if final.generation else 0,
        "elapsedSeconds": elapsed,
        "books": [result.__dict__ for result in results],
        "skippedDirectories": skipped,
        "requestedSource": args.source or None,
        "requestedSourceZip": args.source_zip or None,
    }
    report_path = Path(args.report) if args.report else (
        REPO_ROOT / "_work" / "rag-rebuild-v1" / "migration-report.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    migrated = sum(1 for item in results if item.status == "migrated")
    failed = len(results) - migrated
    print(f"\n完成：{migrated} 册已迁移 / {failed} 册失败；用时 {elapsed}s")
    print(f"索引代块数：{report['generationChunkTotal']}")
    print(f"报告：{report_path}")
    vectors.close()
    catalog.close()
    ingest.close()
    index.close()
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移人教版 markdown 教材进正式教材目录与索引")
    parser.add_argument("--source", help="原始教材目录（默认取 ZQKY_TEXTBOOK_SOURCE_DIR）")
    parser.add_argument(
        "--source-zip",
        help="从归档读取 markdown（源目录不可用时的可复现来源，例如 F:/人教版教材.zip）",
    )
    parser.add_argument(
        "--staging",
        help="从归档解压 markdown 的暂存目录（默认每次运行独占，避免并发互相截断）",
    )
    parser.add_argument("--data-dir", help="数据根目录（默认 .local-data）")
    parser.add_argument("--model", default="bge-m3", help="本机 Ollama Embedding 模型名")
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 册（试跑用）")
    parser.add_argument(
        "--dry-run", action="store_true", help="只识别与列出教材，不写任何数据"
    )
    parser.add_argument("--only", help="逗号分隔的学科 id，只迁移这些学科")
    parser.add_argument("--report", help="报告输出路径")
    return migrate(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
