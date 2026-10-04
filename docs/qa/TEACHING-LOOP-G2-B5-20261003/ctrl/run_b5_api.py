"""A new full API run: isolated before app imports, owned removal paths retained."""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import inspect
import json
import locale
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding='utf-8')
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--candidate')
parser.add_argument('--source', action='append', default=[])
parser.add_argument('files', nargs='*')
args = parser.parse_args()
assert args.label.replace('-', '').isalnum()
log, receipt, xml = [OUT/(args.label+suffix) for suffix in ('.log','-command.json','.xml')]
assert not any(path.exists() for path in (log, receipt, xml))
sample = Path(tempfile.mkdtemp(prefix='zqky-b5-ctrl-' + args.label + '-')).resolve()
for folder in ('tmp','data','empty-textbooks','_retained_removals'): (sample/folder).mkdir()
isolated = dict(ZQKY_DATA_DIR=str(sample/'data'), ZQKY_ENV='test', PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
    PYTHONDONTWRITEBYTECODE='1', ZQKY_QDRANT_URL='http://127.0.0.1:16333', ZQKY_EMBEDDING_BASE_URL='http://127.0.0.1:9',
    ZQKY_TEXTBOOK_SOURCE_DIR=str(sample/'empty-textbooks'), ZQKY_KEEP_TEST_DATA='1')
os.environ.update(isolated)
tempfile.tempdir = str(sample/'tmp')
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'apps/api'))
candidate_path = ROOT/args.candidate if args.candidate else None
candidate = json.loads(candidate_path.read_text(encoding='utf-8')) if candidate_path else None
names = set(args.source) | (set(candidate['sourceFiles']) if candidate else set())
assert names, 'explicit private sources or stable candidate required'
source_hashes = lambda: {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(names)}
record = dict(label=args.label, command=[sys.executable,*sys.argv], cwd=str(ROOT), pid=os.getpid(), env=isolated,
    sampleRoot=str(sample), sampleRetained=True, candidate=args.candidate, candidateSHA=hashlib.sha256(candidate_path.read_bytes()).hexdigest() if candidate_path else None,
    sourceBefore=source_hashes(), startedAtUtc=datetime.now(timezone.utc).isoformat(), status='running',
    settingsCredentialsFile=None, tcpServerStarted=False, retainedCleanup=[], semanticRemovalSnapshots=[],
    parentUtf8Mode=sys.flags.utf8_mode, parentPreferredEncoding=locale.getpreferredencoding(False))
save = lambda: receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save()
original_rmtree = shutil.rmtree

def guarded_cleanup(path, *positional, **keywords):
    target = Path(path).resolve()
    if target != sample and sample not in target.parents:
        raise RuntimeError('Refusing any recursive cleanup outside the new owned root: '+str(target))
    # Session lifecycle cleanup is retained. An intentional fault-injection removal
    # still runs against a verified owned path after preserving its full prior bytes.
    caller = inspect.stack()[1]
    if Path(caller.filename).name == 'conftest.py':
        record['retainedCleanup'].append(str(target)); return
    if target == sample or sample/'_retained_removals' == target or sample/'_retained_removals' in target.parents:
        raise RuntimeError('Cannot remove the evidence root or its preservation area')
    if target.exists():
        snapshot = sample/'_retained_removals'/str(len(record['semanticRemovalSnapshots']))
        shutil.copytree(target,snapshot)
        hashes = {str(item.relative_to(snapshot)): hashlib.sha256(item.read_bytes()).hexdigest() for item in snapshot.rglob('*') if item.is_file()}
        record['semanticRemovalSnapshots'].append(dict(target=str(target),snapshot=str(snapshot),caller=str(caller.filename),line=caller.lineno,files=hashes))
    return original_rmtree(target,*positional,**keywords)

class Tee:
    def __init__(self,a,b): self.a,self.b=a,b
    def write(self,value): self.a.write(value); self.b.write(value); self.flush(); return len(value)
    def flush(self): self.a.flush(); self.b.flush()
    def isatty(self): return False

started=time.perf_counter(); code=None
try:
    with log.open('x',encoding='utf-8') as stream:
        with contextlib.redirect_stdout(Tee(sys.stdout,stream)), contextlib.redirect_stderr(Tee(sys.stderr,stream)):
            shutil.rmtree=guarded_cleanup
            from app.core.config import Settings
            assert Settings.from_env().credentials_file is None
            original_init=Settings.__init__
            signature=inspect.signature(original_init)
            def isolated_settings(self,*positional,**kwargs):
                bound=signature.bind_partial(self,*positional,**kwargs)
                defaults=dict(credentials_file=None,textbook_source_dir=sample/'empty-textbooks',qdrant_url='http://127.0.0.1:16333',embedding_base_url='http://127.0.0.1:9')
                for key,value in defaults.items():
                    if key not in bound.arguments: kwargs[key]=value
                original_init(self,*positional,**kwargs)
            Settings.__init__=isolated_settings
            import pytest
            code=int(pytest.main(['-c','apps/api/pyproject.toml',*(args.files or ['apps/api/tests']), '--basetemp='+str(sample/'pytest'), '--junitxml='+str(xml)]))
finally:
    shutil.rmtree=original_rmtree
    if 'original_init' in globals(): Settings.__init__=original_init
    record.update(status='complete' if code is not None else 'runner_error',exitCode=code,elapsedMs=round((time.perf_counter()-started)*1000,3),
        finishedAtUtc=datetime.now(timezone.utc).isoformat(),sourceAfter=source_hashes(),logsClosed=True,
        logSHA=hashlib.sha256(log.read_bytes()).hexdigest() if log.exists() else None)
    record['sourceDrift']=[name for name,digest in record['sourceBefore'].items() if record['sourceAfter'].get(name)!=digest]
    if xml.exists(): record['junit']=[dict(suite.attrib) for suite in ET.parse(xml).getroot().iter('testsuite')]
    save()
print(json.dumps({key:record.get(key) for key in ('label','pid','exitCode','elapsedMs','sourceDrift','junit','sampleRoot')},ensure_ascii=False))
raise SystemExit(code if code is not None else 1)
