"""ROOT-only current action refresh; save exact before and declared document delta."""
import argparse
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import re

R=Path(__file__).resolve().parents[4]
O=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
p.add_argument('--label',required=True)
p.add_argument('--message-file',required=True)
a=p.parse_args()
assert a.label.replace('-','').isalnum()
before=O/('CURRENT-before-'+a.label+'.md')
delta=O/('CURRENT-'+a.label+'-delta.json')
assert not before.exists() and not delta.exists()
target=R/'docs/CURRENT_STATUS.md'
raw=target.read_bytes()
message=(R/a.message_file).read_text(encoding='utf-8').strip()
at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
replacement='## 1. 当前任务与下一动作\r\n\r\n'+at+'：'+message+'\r\n\r\n'
pattern=rb'## 1\. \xe5\xbd\x93\xe5\x89\x8d\xe4\xbb\xbb\xe5\x8a\xa1\xe4\xb8\x8e\xe4\xb8\x8b\xe4\xb8\x80\xe5\x8a\xa8\xe4\xbd\x9c\r?\n.*?(?=### 1\.1 )'
new,n=re.subn(pattern,replacement.encode('utf-8'),raw,count=1,flags=re.S)
assert n==1
before.write_bytes(raw)
target.write_bytes(new)
sha=lambda b:hashlib.sha256(b).hexdigest()
delta.write_text(json.dumps(dict(at=at,path='docs/CURRENT_STATUS.md',beforeSHA=sha(raw),afterSHA=sha(new),
 before=before.relative_to(R).as_posix(),onlyLiveSectionUpdated=True,historicalBlocksUnchanged=True,
 message=a.message_file),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(at=at,delta=delta.relative_to(R).as_posix()),ensure_ascii=False))
