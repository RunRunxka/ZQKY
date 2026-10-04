"""Retain first diagnostic inputs, verifying each copy against recorded command SHA."""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
for label in ['f30-lint-r1', 'f30-types-r1']:
    record = json.loads((OUT / f'{label}-command.json').read_text(encoding='utf-8'))
    for name, expected in record['sourceBefore'].items():
        raw = (ROOT / name).read_bytes()
        if label == 'f30-types-r1' and name.endswith('useLessonOperation.ts'):
            text = raw.decode('utf-8').replace('const currentIdentity = contextKey; const failure: { error: ApiError | null } = { error: null };', 'const currentIdentity = contextKey; let failure: ApiError | null = null;').replace('failure.error', 'failure')
            raw = text.encode('utf-8')
        if label == 'f30-types-r1' and name.endswith('useServerPersistence.ts'):
            text = raw.decode('utf-8').replace("setSyncState('saving'); setError(null); const failure: { error: ApiError | null } = { error: null };", "setSyncState('saving'); setError(null); let failure: ApiError | null = null;").replace('failure.error', 'failure')
            raw = text.encode('utf-8')
        if hashlib.sha256(raw).hexdigest() != expected: raise ValueError(f'Input SHA mismatch: {label}/{name}')
        target = OUT / f'{label}-source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream: stream.write(raw)
    print(f'{label}: {len(record["sourceBefore"])} original diagnostic inputs retained and verified')
