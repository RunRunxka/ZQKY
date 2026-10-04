"""Diagnostic of an existing immutable reader's same-process cache semantics.

This is a boundary observation, not an assertion that cached verified bytes are
untrusted or that B5 must re-read the disk on every fixed-source use.
"""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile

here = Path(__file__).resolve().parent
repo = here.parents[3]
temporary = Path(tempfile.mkdtemp(prefix="zqky-b5-generation-cache-review-"))
os.environ.update(ZQKY_DATA_DIR=str(temporary / "data"), ZQKY_ENV="test", PYTHONUTF8="1")
sys.path.insert(0, str(repo / "apps" / "api"))
from app.core.exceptions import AppError
from app.services.rag_v2.source_text import ImmutableSource
from tests.lesson_generation_support import Scene


async def main():
    scene = await Scene.create(temporary / "scene")
    try:
        prepared = scene.prepare()
        revision = scene.rag_env.catalog.get_revision(prepared.frozen_input["evidenceRefs"][0]["documentRevisionId"])
        path = scene.rag_env.blobs.path_of("normalized", revision.normalized_blob_id).resolve()
        assert path.is_relative_to(temporary.resolve())
        original = path.read_bytes()
        path.write_bytes(b"fixture corrupted only inside review TEMP")
        # Normal B5 path uses the exact RAG reader that verified the span at
        # preparation. Its previously checked bytes are cached in memory.
        warm = await scene.run(scene.job(prepared))
        record = dict(tempRoot=str(temporary), changedPath=str(path),
                      warmJobState=warm.state, warmError=warm.error_code,
                      modelCalls=scene.calls, proposals=scene.count("lesson_ai_proposals"),
                      sameProcessCachedBytesAreOriginal=True)
        scene.rag.texts = ImmutableSource(catalog=scene.rag_env.catalog, blob_store=scene.rag_env.blobs)
        try:
            scene.rag.verify_selected_evidence(prepared.frozen_input["scopeSnapshot"], prepared.frozen_input["evidenceRefs"])
            record["coldReaderAccepted"] = True
        except AppError as exc:
            record.update(coldReaderAccepted=False, coldReaderError=exc.code)
        path.write_bytes(original)
        record["temporaryBlobRestored"] = path.read_bytes() == original
        # A legitimate catalog deletion is a different boundary. Acceptance
        # was already frozen while the document was live; deletion must stop
        # provider execution even if its old checked text is still cached.
        pending = scene.job(prepared)
        document = scene.rag_env.catalog.get_document(revision.document_id)
        scene.rag_env.catalog.delete_document(document.document_id, expected_revision=document.revision)
        before_calls = scene.calls
        deleted = await scene.run(pending)
        record.update(legitimateDeletedDocumentJobState=deleted.state,
                      legitimateDeletedDocumentError=deleted.error_code,
                      legitimateDeletedDocumentProviderCalls=scene.calls-before_calls)
        assert deleted.state == "failed" and scene.calls == before_calls
        (here / "warm-source-cache-v2.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(record,ensure_ascii=False))
    finally:
        await scene.close()

asyncio.run(main())
