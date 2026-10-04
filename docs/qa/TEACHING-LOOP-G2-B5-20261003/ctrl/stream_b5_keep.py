"""Original three-protocol fixture, isolated and gracefully stopped by CTRL."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[4]; OUT=Path(__file__).resolve().parent
label=sys.argv[1]
assert label.replace('-','').isalnum()
receipt=OUT/(label+'-service.json');stop=OUT/(label+'.stop')
assert not receipt.exists() and not stop.exists()
sample=Path(tempfile.mkdtemp(prefix='zqky-b5-stream-'+label+'-'))
(sample/'empty-textbooks').mkdir()
isolated=dict(ZQKY_DATA_DIR=str(sample/'data'),ZQKY_ENV='test',PYTHONUTF8='1',PYTHONIOENCODING='utf-8',
    PYTHONDONTWRITEBYTECODE='1',ZQKY_QDRANT_URL='http://127.0.0.1:16333',ZQKY_EMBEDDING_BASE_URL='http://127.0.0.1:9',
    ZQKY_TEXTBOOK_SOURCE_DIR=str(sample/'empty-textbooks'))
os.environ.update(isolated); sys.dont_write_bytecode=True
sys.stdout.reconfigure(encoding='utf-8')
record=dict(label=label,pid=os.getpid(),command=[sys.executable,*sys.argv],startedAtUtc=datetime.now(timezone.utc).isoformat(),
    env=isolated,sampleRoot=str(sample),ports=[8001,8002],stopFile=str(stop),credentialsFile=None,status='initializing')
save=lambda:receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save()
original_temp=tempfile.TemporaryDirectory
class Retained:
    def __init__(self,prefix):
        self.name=tempfile.mkdtemp(prefix=prefix,dir=sample)
        record['fixtureModelSample']=self.name; save()
    def cleanup(self): record['fixtureSampleRetained']=True;save()
def owned_temp(*args,**kwargs):
    if not args and kwargs=={'prefix':'zqky-chat-test-'}: return Retained(**kwargs)
    return original_temp(*args,**kwargs)
tempfile.TemporaryDirectory=owned_temp
import uvicorn
original_run=uvicorn.run
def managed_run(app,**kwargs):
    assert kwargs.get('host')=='127.0.0.1' and kwargs.get('port')==8001
    server=uvicorn.Server(uvicorn.Config(app,**kwargs))
    record['status']='serving';save()
    def watch():
        while not server.should_exit:
            if stop.exists(): server.should_exit=True;return
            time.sleep(.2)
    thread=threading.Thread(target=watch,daemon=True);thread.start()
    server.run();thread.join(timeout=2)
    record.update(serverClosed=True,watcherClosed=not thread.is_alive());save()
uvicorn.run=managed_run
try:
    runpy.run_path(str(ROOT/'tests/fixtures/stream_backend.py'),run_name='__main__')
    record['status']='closed'
finally:
    uvicorn.run=original_run;tempfile.TemporaryDirectory=original_temp
    record.update(finishedAtUtc=datetime.now(timezone.utc).isoformat(),stopRequested=stop.exists(),sampleRetained=sample.exists())
    save()
