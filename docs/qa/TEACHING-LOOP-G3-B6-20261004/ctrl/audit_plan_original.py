"""Only remove this batch's additive markers in memory, then compare original bytes."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re

R=Path(__file__).resolve().parents[4]
O=Path(__file__).resolve().parent
p=argparse.ArgumentParser(); p.add_argument('--label',required=True); a=p.parse_args()
assert a.label.replace('-','').isalnum()
out=O/(a.label+'.json'); assert not out.exists()
name='docs/design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md'
old=(O/'opening-documents'/name).read_bytes(); raw=(R/name).read_bytes()
stripped,n=re.subn(rb'\n<!-- (G3|B6)-CHECKPOINT:([^\r\n]+) -->\r?\n.*?<!-- /\1-CHECKPOINT:\2 -->\r?\n\r?\n',b'',raw,flags=re.S)
stripped,m=re.subn(rb'<!-- PLAN-STATUS-SNAPSHOT:2026-10-04-OPENING -->\r?\n.*?<!-- END-PLAN-STATUS-SNAPSHOT:2026-10-04-OPENING -->\r?\n\r?\n',b'',stripped,flags=re.S)
sha=lambda b:hashlib.sha256(b).hexdigest()
record=dict(at=datetime.now(timezone.utc).isoformat(),path=name,originalBytes=len(old),
 originalSHA=sha(old),currentSHA=sha(raw),strippedBytes=len(stripped),strippedSHA=sha(stripped),
 checkpointBlocks=n,openingStatusBlocks=m,exactOriginalPreserved=old==stripped,
 fileWritten=False,originalTasksAndPseudocodeEdited=False)
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record,ensure_ascii=False))
assert old==stripped
