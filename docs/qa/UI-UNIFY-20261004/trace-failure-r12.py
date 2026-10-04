"""Read intact local entries from the failed, incompletely finalized trace ZIP."""
import hashlib
import json
import pathlib
import struct
import zlib

root = pathlib.Path(__file__).resolve().parent
trace = next((root / 'e2e-full-r12').glob('lesson-plan-无面包屑*/trace.zip'))
raw = trace.read_bytes()
pos = 0
records = []
while raw[pos:pos + 4] == b'PK\x03\x04':
    _, flag, method, _, _, _, compressed, _, name_len, extra_len = struct.unpack_from('<5H3I2H', raw, pos + 4)
    name = raw[pos + 30:pos + 30 + name_len].decode()
    start = pos + 30 + name_len + extra_len
    if method == 8:
        decompressor = zlib.decompressobj(-15)
        data = decompressor.decompress(raw[start:])
        pos = start + len(raw[start:]) - len(decompressor.unused_data) + (16 if flag & 8 else 0)
    else:
        data = raw[start:start + compressed]
        pos = start + compressed
    if name.endswith(('.trace', '.network')):
        for line in data.decode().splitlines():
            row = json.loads(line)
            if (row.get('type') == 'after' and row.get('error')) or row.get('type') == 'console' or (row.get('type') == 'event' and row.get('method') == 'pageError') or 'ERR_NO_BUFFER_SPACE' in line:
                records.append({'entry': name, 'record': row})
    if pos >= len(raw):
        break

output = {'trace': str(trace.relative_to(root)), 'sha256': hashlib.sha256(raw).hexdigest(), 'note': 'Normal ZIP directory could not be read; only intact local ZIP entries were extracted.', 'records': records}
(root / 'browser-failure-r12.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'records': len(records), 'traceSha256': output['sha256']}, indent=2))
