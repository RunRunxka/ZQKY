"""Add-only current status with correct repository-relative links for the plan."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

R=Path(__file__).resolve().parents[4];O=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--message-file',required=True)
a=p.parse_args();assert a.label.replace('-','').isalnum()
message=(R/a.message_file).read_text(encoding='utf-8').strip()
at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
before=O/('B6-'+a.label+'-DOC-before');delta=O/('B6-'+a.label+'-DOC-delta.json')
assert not before.exists() and not delta.exists()
sha=lambda b:hashlib.sha256(b).hexdigest();changes=[]
for name in ['docs/CURRENT_STATUS.md','docs/NEXT_SESSION_START.md',
             'docs/design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md']:
 local=re.sub(r'(?<=\]\()qa/', '../../qa/',message) if '/design/' in name else message
 block=('\n<!-- B6-CHECKPOINT:'+a.label+' -->\r\n'+at+'：'+local+
        '\r\n<!-- /B6-CHECKPOINT:'+a.label+' -->\r\n\r\n').encode('utf-8')
 target=R/name;raw=target.read_bytes();saved=before/name
 saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(raw)
 pos=raw.index(b'\n')+1;new=raw[:pos]+block+raw[pos:]
 assert new[:pos]+new[pos+len(block):]==raw
 target.write_bytes(new)
 changes.append(dict(path=name,beforeSHA=sha(raw),afterSHA=sha(new),additiveOnly=True,
 originalBefore=saved.relative_to(R).as_posix(),planRelativeLinksCorrectedOnlyInNewBlock='/design/' in name))
delta.write_text(json.dumps(dict(at=at,label=a.label,changes=changes,originalTasksEdited=False),
 ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(at=at,delta=delta.relative_to(R).as_posix()),ensure_ascii=False))
