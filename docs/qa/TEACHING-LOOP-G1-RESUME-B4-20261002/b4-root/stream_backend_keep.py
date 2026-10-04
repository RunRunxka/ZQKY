"""Execute the original stream fixture with outer isolation and retained owned samples.

Does not start a frontend or change any HTTP/upstream implementation.
The caller owns and records this process, the new data root, and ports 8001/8002.
"""
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
data = Path(os.environ['ZQKY_DATA_DIR']).resolve()
assert os.environ['ZQKY_ENV'] == 'test'
assert data.is_relative_to(Path(tempfile.gettempdir()).resolve())
assert data.parent.name.startswith('zqky-b4-')
assert os.environ['ZQKY_QDRANT_URL'] == 'http://127.0.0.1:16333'
assert os.environ['ZQKY_EMBEDDING_BASE_URL'] == 'http://127.0.0.1:9'

original_temporary_directory = tempfile.TemporaryDirectory

class RetainedOwnedTemporaryDirectory:
    def __init__(self, *args, **kwargs):
        # The original fixture only constructs this once with a prefix.
        assert not args and set(kwargs) == {'prefix'}
        self.name = tempfile.mkdtemp(prefix=kwargs['prefix'], dir=data.parent)
        print(json.dumps({'ownedStreamModelSample': self.name, 'retained': True}), flush=True)

    def cleanup(self):
        print(json.dumps({'ownedStreamModelSample': self.name, 'cleanup': 'retained'}), flush=True)

def fixture_temporary_directory(*args, **kwargs):
    if not args and kwargs == {'prefix': 'zqky-chat-test-'}:
        return RetainedOwnedTemporaryDirectory(**kwargs)
    return original_temporary_directory(*args, **kwargs)

tempfile.TemporaryDirectory = fixture_temporary_directory
try:
    root = Path(__file__).resolve().parents[4]
    runpy.run_path(str(root / 'tests/fixtures/stream_backend.py'), run_name='__main__')
finally:
    tempfile.TemporaryDirectory = original_temporary_directory
