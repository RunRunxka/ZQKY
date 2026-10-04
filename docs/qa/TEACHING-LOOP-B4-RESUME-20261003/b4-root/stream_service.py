"""Own one isolated original stream fixture, retained samples and graceful stopfile."""
import argparse
import contextlib
import hashlib
import json
import os
import runpy
import socket
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--candidate', required=True)
args = parser.parse_args()
assert args.label.replace('-', '').isalnum()
root = Path(__file__).resolve().parents[4]
out = Path(__file__).resolve().parent
receipt, log = out / f'stream-{args.label}.json', out / f'stream-{args.label}.log'
assert not receipt.exists() and not log.exists(), 'Never replace an earlier lifecycle or first failure'
for port in (8001, 8002):
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', port)) != 0, 'Refuse occupied test ports'
sample = Path(tempfile.mkdtemp(prefix=f'zqky-b4-stream-20261003-{args.label}-'))
data, stop = sample / 'data', sample / 'ctrl-stop-stream'
(sample / 'empty-textbooks').mkdir()
isolated = dict(ZQKY_DATA_DIR=str(data), ZQKY_ENV='test', PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
                ZQKY_QDRANT_URL='http://127.0.0.1:16333', ZQKY_EMBEDDING_BASE_URL='http://127.0.0.1:9',
                ZQKY_TEXTBOOK_SOURCE_DIR=str(sample / 'empty-textbooks'), PYTHONPATH=str(root / 'apps/api'))
os.environ.update(isolated)
sys.path.insert(0, str(root / 'apps/api'))
candidate_path = root / args.candidate
value = dict(status='starting', pid=os.getpid(), label=args.label, cwd=str(root),
             command=[sys.executable, *sys.argv], env=isolated, sampleRoot=str(sample), dataDir=str(data),
             stopFile=str(stop), candidate=args.candidate, candidateSHA256=hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
             startedAt=datetime.now(timezone.utc).isoformat(), originalFixture='tests/fixtures/stream_backend.py',
             originalFixtureSHA256=hashlib.sha256((root / 'tests/fixtures/stream_backend.py').read_bytes()).hexdigest(),
             settingsCredentialsFile=None, noFrontendLifecycle=True)

def save():
    receipt.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

save()
print(json.dumps(dict(pid=value['pid'], sampleRoot=str(sample), stopFile=str(stop), receipt=str(receipt)), ensure_ascii=False), flush=True)
tick = time.perf_counter()
try:
    with log.open('x', encoding='utf-8', buffering=1) as output, contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        from app.core.config import Settings
        settings = Settings.from_env()
        assert settings.credentials_file is None and settings.data_dir.resolve() == data.resolve()
        value['outerIsolationVerifiedBeforeMainImport'] = True
        import uvicorn
        original_run = uvicorn.run

        def owned_run(app, *positional, **kwargs):
            assert not positional and kwargs == dict(host='127.0.0.1', port=8001, log_level='warning')
            server = uvicorn.Server(uvicorn.Config(app, **kwargs))
            value.update(serverEnteredAt=datetime.now(timezone.utc).isoformat(), originalUvicornArguments=kwargs)
            save()
            print('OWNED_STREAM_SERVER_ENTER', json.dumps(kwargs), flush=True)

            def monitor():
                while not stop.exists() and not server.should_exit:
                    time.sleep(.2)
                if stop.exists():
                    server.should_exit = True

            watcher = threading.Thread(target=monitor, daemon=True)
            watcher.start()
            server.run()
            print('OWNED_STREAM_SERVER_RETURN', datetime.now(timezone.utc).isoformat(), flush=True)

        uvicorn.run = owned_run
        try:
            runpy.run_path(str(out / 'stream_backend_keep.py'), run_name='__main__')
            value['originalFixtureFinallyReturned'] = True
            print('ORIGINAL_STREAM_FIXTURE_FINALLY_RETURNED', flush=True)
        finally:
            uvicorn.run = original_run
    value['exit'] = 0
except BaseException as exc:
    value.update(exit=1, error=repr(exc))
    raise
finally:
    value.update(status='complete', stoppedAt=datetime.now(timezone.utc).isoformat(),
                 elapsedMs=round((time.perf_counter() - tick) * 1000, 3), gracefulStopRequested=stop.exists(),
                 logsClosed=True, sampleRetained=sample.exists(),
                 logSHA256=hashlib.sha256(log.read_bytes()).hexdigest() if log.exists() else None)
    save()
print(json.dumps(dict(pid=value['pid'], exit=value['exit'], status=value['status'])), flush=True)
