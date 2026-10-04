"""ROOT-only additive timestamped state; immutable before/delta evidence."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--label', required=True)
p.add_argument('--message-file', required=True)
args = p.parse_args()
assert args.label.replace('-', '').isalnum()
message = (ROOT / args.message_file).read_text(encoding='utf-8').strip()
stamp = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
block = ('\n<!-- B6-CHECKPOINT:' + args.label + ' -->\r\n' + stamp + '：' + message +
         '\r\n<!-- /B6-CHECKPOINT:' + args.label + ' -->\r\n\r\n')
sha = lambda b: hashlib.sha256(b).hexdigest()
names = ['docs/CURRENT_STATUS.md', 'docs/NEXT_SESSION_START.md',
         'docs/design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md']
before = OUT / ('B6-' + args.label + '-DOC-before')
delta = OUT / ('B6-' + args.label + '-DOC-delta.json')
assert not before.exists() and not delta.exists()
changes = []
for name in names:
    target = ROOT / name
    raw = target.read_bytes()
    saved = before / name
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_bytes(raw)
    idx = raw.index(b'\n') + 1
    new = raw[:idx] + block.encode('utf-8') + raw[idx:]
    target.write_bytes(new)
    changes.append(dict(path=name, beforeSHA=sha(raw), afterSHA=sha(new),
                        additiveOnly=True, originalBefore=str(saved.relative_to(ROOT))))
delta.write_text(json.dumps(dict(timestamp=stamp, label=args.label, changes=changes,
    messageSource=args.message_file, originalTasksEdited=False), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(dict(timestamp=stamp, delta=str(delta.relative_to(ROOT))), ensure_ascii=False))
