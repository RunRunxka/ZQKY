"""Owned real FastAPI for G3 UI probes. No provider, formal roots or credentials."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--port', type=int, default=8001)
args = parser.parse_args()
assert args.label.replace('-', '').isalnum() and args.port == 8001
receipt = OUT / (args.label + '-service.json')
stop_file = OUT / (args.label + '.stop')
seed_file = OUT / (args.label + '-seed.json')
assert not any(p.exists() for p in (receipt, stop_file, seed_file))
sample = Path(tempfile.mkdtemp(prefix='zqky-g3-runtime-' + args.label + '-')).resolve()
(sample / 'empty-textbooks').mkdir()
isolated = dict(ZQKY_DATA_DIR=str(sample / 'data'), ZQKY_ENV='test', PYTHONUTF8='1',
    PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1', ZQKY_KEEP_TEST_DATA='1',
    ZQKY_TEXTBOOK_SOURCE_DIR=str(sample / 'empty-textbooks'),
    ZQKY_QDRANT_URL='http://127.0.0.1:16333', ZQKY_EMBEDDING_BASE_URL='http://127.0.0.1:9',
    ZQKY_ALLOWED_ORIGINS='http://127.0.0.1:5174')
os.environ.update(isolated)
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'apps/api'))
record = dict(label=args.label, pid=os.getpid(), command=[sys.executable, *sys.argv],
    createdAt=datetime.now(timezone.utc).isoformat(), host='127.0.0.1', port=args.port,
    sampleRoot=str(sample), env=isolated, sampleRetained=True, settingsCredentialsFile=None,
    stopFile=str(stop_file), seedFile=str(seed_file), status='starting',
    runnerSHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    explicitEnvEstablishedBeforeAppMain=True, providerCalls=0)
save = lambda: receipt.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
save()
started = time.monotonic()
try:
    from app.core.config import Settings
    assert Settings.from_env().credentials_file is None
    from app.main import app
    assert app.state.settings.credentials_file is None
    record.update(appMainImported=True, standardCreateApp=True, status='constructed')
    save()
    seed_file.write_text(json.dumps(dict(schemaVersion=1, apiOrigin='http://127.0.0.1:8001',
        isolationDataRoot=str(sample / 'data'), buildId=(ROOT / 'apps/web/.next/BUILD_ID').read_text().strip(),
        classCode='G3-V00-20261004', className='G3独立隔离班'), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port, log_level='info'))

    async def watch_stop():
        while not server.should_exit:
            if stop_file.exists():
                record['stopRequestedAt'] = datetime.now(timezone.utc).isoformat()
                save()
                server.should_exit = True
                return
            await asyncio.sleep(0.2)

    async def run():
        watcher = asyncio.create_task(watch_stop())
        try:
            record['status'] = 'serving'
            save()
            await server.serve()
        finally:
            watcher.cancel()
            try:
                await watcher
            except asyncio.CancelledError:
                pass

    asyncio.run(run())
    record.update(status='closed', standardLifespanClosed=True)
except BaseException as error:
    record.update(status='failed', errorType=type(error).__name__, error=str(error))
    raise
finally:
    record.update(finishedAt=datetime.now(timezone.utc).isoformat(), elapsedMs=round((time.monotonic() - started) * 1000, 3))
    save()
