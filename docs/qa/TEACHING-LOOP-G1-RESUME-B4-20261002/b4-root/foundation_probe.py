import os
import tempfile
import json
from pathlib import Path

sample = Path(tempfile.mkdtemp(prefix='zqky-b4-foundation-'))
os.environ.update(ZQKY_DATA_DIR=str(sample/'data'), ZQKY_ENV='test', PYTHONUTF8='1', ZQKY_QDRANT_URL='http://127.0.0.1:16333')
from app.repositories.teaching.catalog import TeachingCatalog
from app.core.migrations.teaching import MIGRATIONS
from app.contracts.b4 import AnalysisCreateRequest

print(json.dumps({'sample':str(sample),'migrations':{m.id:m.sha256 for m in MIGRATIONS}},ensure_ascii=False),flush=True)
catalog = TeachingCatalog(sample/'teaching.sqlite3')
catalog.migrate()
catalog.migrate()
with catalog.read_connection() as conn:
    assert list(conn.execute('PRAGMA foreign_key_check')) == []
    assert [r[0] for r in conn.execute('PRAGMA integrity_check')] == ['ok']
    assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    print(json.dumps({'tables':[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")], 'fk':0,'integrity':'ok'},ensure_ascii=False))
print('foundation new database migrated twice successfully')
