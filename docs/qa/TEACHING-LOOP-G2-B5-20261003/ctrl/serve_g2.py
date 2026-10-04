"""CTRL-owned 8001; isolated real four-DB browser seed, graceful stop marker."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
label=sys.argv[1]
if not label.replace('-','').isalnum(): raise ValueError('invalid immutable service label')
receipt=OUT/(label+'-service.json'); seed=OUT/(label+'-seed.json'); stop=OUT/(label+'.stop')
if any(path.exists() for path in (receipt,seed,stop)): raise FileExistsError('Never reuse a service identity')
sample=Path(tempfile.mkdtemp(prefix='zqky-g2-runtime-'+label+'-'))
(sample/'empty-textbooks').mkdir()
isolated=dict(ZQKY_DATA_DIR=str(sample/'data'),ZQKY_ENV='test',PYTHONUTF8='1',PYTHONIOENCODING='utf-8',
    PYTHONDONTWRITEBYTECODE='1',ZQKY_API_PORT='8001',ZQKY_QDRANT_URL='http://127.0.0.1:16333',
    ZQKY_EMBEDDING_BASE_URL='http://127.0.0.1:9',ZQKY_TEXTBOOK_SOURCE_DIR=str(sample/'empty-textbooks'))
os.environ.update(isolated);sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'apps/api'))
sys.stdout.reconfigure(encoding='utf-8')
record=dict(label=label,pid=os.getpid(),command=[sys.executable,*sys.argv],startedAtUtc=datetime.now(timezone.utc).isoformat(),
    port=8001,host='127.0.0.1',env=isolated,sampleRoot=str(sample),sampleRetained=True,credentialsFile=None,
    status='initializing',stopFile=str(stop),seedFile=str(seed),serverStarted=False)
save=lambda:receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save()
server=None
try:
    from app.core.config import Settings
    settings=Settings(host='127.0.0.1',port=8001,allowed_origins=frozenset({'http://127.0.0.1:5174'}),env='test',
        data_dir=sample/'data',credentials_file=None,textbook_source_dir=sample/'empty-textbooks',
        qdrant_url='http://127.0.0.1:16333',embedding_base_url='http://127.0.0.1:9')
    from app.main import create_app
    spec=importlib.util.spec_from_file_location('g2_browser_seed',OUT.parent/'g2-v00/browser/seed_runtime.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    seed_app=create_app(settings)
    module.seed_for_browser(seed_app,seed)
    # TestClient seeding has closed its lifespan. Serve a fresh application over
    # those exact isolated fixed rows, with fresh runtime clients and engine.
    app=create_app(settings)
    assert app.state.settings.credentials_file is None
    import uvicorn
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8001,log_level='info'))
    record.update(status='serving',seedSHA=hashlib.sha256(seed.read_bytes()).hexdigest(),serverStarted=True)
    save()
    def watch():
        while not server.should_exit:
            if stop.exists(): server.should_exit=True;return
            time.sleep(.2)
    watcher=threading.Thread(target=watch,daemon=True);watcher.start()
    server.run()
    watcher.join(timeout=2)
    record.update(status='closed',serverClosed=True,watcherClosed=not watcher.is_alive())
finally:
    record.update(finishedAtUtc=datetime.now(timezone.utc).isoformat(),stopRequested=stop.exists(),sampleRetained=sample.exists())
    if server is None: record['status']='initialization_failed'
    save()
