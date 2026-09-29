"""用「同 Embedding 身份、新清洗策略」重建一个新索引代并原子切换（RAG-QUALITY v1.1）。

- 复用 `IndexService.begin_rebuild` / `run_rebuild`：租约、写入闸门、断点恢复、
  对账与**单指针发布**全部沿用既有机制，不另写一套重建。
- 新旧代并存：旧 collection 不删、旧原文不改；切换只改 `active_generation_id`。
- 与 API 争用同一数据根：本 CLI 持排他数据锁（API 在跑时会明确失败）。

用法::

    uv run --directory apps/api python ../../scripts/rag/rebuild_index.py --dry-run
    uv run --directory apps/api python ../../scripts/rag/rebuild_index.py
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from app.core.config import Settings  # noqa: E402
from app.providers.embeddings.ollama_embedding import OllamaEmbeddingProvider  # noqa: E402
from app.repositories.textbook_catalog.catalog import TextbookCatalog  # noqa: E402
from app.repositories.vector_store.qdrant import HttpQdrantStore  # noqa: E402
from app.services.document_parsing.chunking import (  # noqa: E402
    DEFAULT_CHUNK_POLICY,
    chunk_policy_json,
)
from app.services.textbook_index.service import IndexService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="同模型新清洗策略重建索引代")
    parser.add_argument("--data-dir", help="数据根目录（默认正式 .local-data）")
    parser.add_argument("--qdrant", help="Qdrant 地址（默认正式 6333）")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要发生什么，不做任何写入")
    args = parser.parse_args()

    settings = Settings.from_env()
    if args.data_dir:
        settings = settings.__class__(**{**settings.__dict__, "data_dir": Path(args.data_dir)})
    if args.qdrant:
        settings = settings.__class__(**{**settings.__dict__, "qdrant_url": args.qdrant})

    policy = chunk_policy_json(DEFAULT_CHUNK_POLICY)
    print(f"新代分块策略：{policy}")

    if args.dry_run:
        catalog = TextbookCatalog(settings.textbooks_root / "catalog.sqlite3")
        try:
            catalog.open_existing()
        except Exception as exc:
            raise SystemExit(f"教材目录不可只读打开：{exc}")
        state = catalog.catalog_state()
        generation = catalog.get_generation(state.active_generation_id)
        profile = catalog.get_embedding_profile(generation.profile_id) if generation else None
        print(f"当前活动代：{state.active_generation_id}（{generation.chunk_policy_json if generation else '无'}）")
        print(f"当前 Embedding：{profile.model_name if profile else '无'} / {profile.model_manifest_digest if profile else ''}")
        print(f"将新建一代并逐册重建；完成前 active_generation_id 不变。")
        catalog.close()
        return 0

    from app.core.data_lock import acquire_data_lock

    with acquire_data_lock(settings.data_dir, exclusive=True, label="rag-rebuild"):
        catalog = TextbookCatalog(settings.textbooks_root / "catalog.sqlite3")
        catalog.migrate()
        provider = OllamaEmbeddingProvider(settings.embedding_base_url)
        vectors = HttpQdrantStore(settings.qdrant_url)
        if not vectors.ping():
            raise SystemExit(f"Qdrant 不可达：{settings.qdrant_url}")
        index = IndexService(catalog, provider, vectors, settings)

        status = index.status()
        if status.activeGenerationId is None:
            raise SystemExit("没有活动索引代，先完成一次入库或空库首启。")
        profile_id = status.activeProfileId
        if not profile_id:
            raise SystemExit("当前代没有 Embedding 配置，拒绝重建。")

        # 先恢复/续跑被中断的重建：worker 被强杀会留下 running + 过期租约，
        # 闸门仍指向它；API 的 /rebuilds 路由也是先 recover 再 begin（同一顺序）。
        begin = time.monotonic()
        resumed = index.recover_pending_jobs()
        if resumed:
            print(f"已续跑被中断的重建任务 {resumed} 个")
        if index.status().rebuildJob is not None:
            finished = index.status().rebuildJob
            print(f"重建仍在进行：{finished.jobId} state={finished.state}")
            print(f"用时 {round(time.monotonic() - begin, 1)}s")
        else:
            submission = f"rag-quality-v1-rebuild-{int(time.time())}"
            job = index.begin_rebuild(profile_id=profile_id, submission_id=submission)
            print(f"已创建重建任务 {job.jobId}（目标代 {job.targetGenerationId}）")
            finished = index.run_rebuild(job.jobId)
            print(f"重建结束：state={finished.state} error={finished.errorCode} 用时 {round(time.monotonic() - begin, 1)}s")
        final = index.status()
        print(f"新活动代：{final.activeGenerationId}")
        print(f"新代块数：{final.generation.chunkTotal if final.generation else 0} / 教材 {final.generation.documentTotal if final.generation else 0} 册")
        catalog.close()
        return 0 if finished.state == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
