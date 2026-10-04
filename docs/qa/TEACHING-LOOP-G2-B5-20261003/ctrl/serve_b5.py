"""Owned isolated standard B5 TCP runtime; complete log and retained seed/wires."""
from datetime import datetime, timezone
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
label, candidate_name = sys.argv[1:3]
assert label.replace('-', '').isalnum()
receipt, seed, stop, log = [OUT/(label+suffix) for suffix in ('-service.json', '-seed.json', '.stop', '.log')]
assert not any(path.exists() for path in (receipt, seed, stop, log))
with socket.socket() as probe:
    probe.bind(('127.0.0.1', 8001))
candidate_path = ROOT/candidate_name
candidate = json.loads(candidate_path.read_text(encoding='utf-8'))
hash_sources = lambda: {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in candidate['sourceFiles']}
assert hash_sources() == candidate['sourceFiles'], 'Stable candidate source required'
sample = Path(tempfile.mkdtemp(prefix='zqky-b5-runtime-'+label+'-'))
(sample/'empty-textbooks').mkdir()
isolated = dict(ZQKY_DATA_DIR=str(sample/'data'), ZQKY_ENV='test', PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
    PYTHONDONTWRITEBYTECODE='1', ZQKY_API_PORT='8001', ZQKY_KEEP_TEST_DATA='1',
    ZQKY_QDRANT_URL='http://127.0.0.1:16333', ZQKY_EMBEDDING_BASE_URL='http://127.0.0.1:9',
    ZQKY_TEXTBOOK_SOURCE_DIR=str(sample/'empty-textbooks'))
os.environ.update(isolated)
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'apps/api'))
sys.stdout.reconfigure(encoding='utf-8')
record = dict(label=label, pid=os.getpid(), command=[sys.executable, *sys.argv], env=isolated,
    host='127.0.0.1', port=8001, credentialsFile=None, sampleRoot=str(sample), sampleRetained=True,
    candidate=candidate_name, candidateSHA=hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
    sourceBefore=hash_sources(), startedAtUtc=datetime.now(timezone.utc).isoformat(),
    status='initializing', stopFile=str(stop), seedFile=str(seed), logFile=str(log), serverStarted=False)
save = lambda: receipt.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
save()
fixture = server = None
try:
    with log.open('x', encoding='utf-8', newline='\n') as stream:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            from app.core.config import Settings
            from app.core.secrets import SecretStore
            from app.main import create_app
            settings = Settings(host='127.0.0.1', port=8001, allowed_origins=frozenset({'http://127.0.0.1:5174'}),
                env='test', data_dir=sample/'data', credentials_file=None, textbook_source_dir=sample/'empty-textbooks',
                qdrant_url='http://127.0.0.1:16333', embedding_base_url='http://127.0.0.1:9')
            # Fixture-only memory credentials survive the seed lifespan; no formal env is read.
            memory_secrets = SecretStore()
            seed_app = create_app(settings, secret_store=memory_secrets)
            spec = importlib.util.spec_from_file_location('b5_browser_seed', OUT.parent/'b5-v00/v3/browser/seed_runtime.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _, fixture = module.seed_for_browser(seed_app, seed, tag=label)
            record['seedClientClosed'] = True
            app = create_app(settings, secret_store=memory_secrets)
            assert app.state.settings.credentials_file is None
            assert app.state.job_executors.has('teaching', 'lesson_generation')
            fixture.install()
            record['transportInstalled'] = True
            import uvicorn
            server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8001, log_level='info'))
            record.update(status='serving', seedSHA=hashlib.sha256(seed.read_bytes()).hexdigest(), serverStarted=True)
            save()
            def watch():
                while not server.should_exit:
                    if stop.exists():
                        server.should_exit = True
                        return
                    time.sleep(.2)
            watcher = threading.Thread(target=watch, daemon=True)
            watcher.start()
            server.run()
            watcher.join(timeout=2)
            record.update(status='closed', serverClosed=True, watcherClosed=not watcher.is_alive())
finally:
    if fixture is not None:
        fixture.restore()
        record['transportRestored'] = not fixture.originals
    record.update(finishedAtUtc=datetime.now(timezone.utc).isoformat(), stopRequested=stop.exists(),
                  sampleRetained=sample.exists(), sourceAfter=hash_sources(), logClosed=True)
    record['sourceDrift'] = [name for name, sha in record['sourceBefore'].items() if record['sourceAfter'].get(name) != sha]
    if server is None:
        record['status'] = 'initialization_failed'
    if log.exists():
        record['logSHA'] = hashlib.sha256(log.read_bytes()).hexdigest()
    save()
