"""ROOT current indexes only, preserve exact before snapshots and deltas."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
R=Path(__file__).resolve().parents[4];B=R/'docs/qa/TEACHING-LOOP-G3-B6-20261004'
before=B/'ctrl/B6-FINAL-INDEX-before-v1';delta=B/'ctrl/B6-FINAL-INDEX-delta-v1.json'
assert not before.exists() and not delta.exists() and (B/'B6-CLOSE-v1.json').exists()
at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();sha=lambda b:hashlib.sha256(b).hexdigest()
targets={
 'docs/README.md':('qa/TEACHING-LOOP-G3-B6-20261004/', 'CURRENT_STATUS.md'),
 'docs/qa/README.md':('TEACHING-LOOP-G3-B6-20261004/', '../CURRENT_STATUS.md'),
 'docs/design/teaching-loop-v1/README.md':('../../qa/TEACHING-LOOP-G3-B6-20261004/', '../../CURRENT_STATUS.md')}
changes=[]
for name,(prefix,current) in targets.items():
 p=R/name;raw=p.read_bytes();saved=before/name;saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(raw)
 text=(f'\n<!-- B6-FINAL-INDEX:20261004 -->\r\n{at}：G3独立技术关闭；本批限定B6技术集成与教学质量验收准备已完成，'
       f'见[最终矩阵]({prefix}B6-CLOSE-MATRIX-v1.md)、[收据]({prefix}B6-CLOSE-v1.json)、'
       f'[教师试用]({prefix}b6-exports/TEACHER-TRIAL-v1.md)。1286/check、真实五字段、四视口14、原完整153及独立技术签收完成；最终文档后验单列；'
       f'真实模型待输入、教师评价待验、Word/WPS排版not_run、RAG-REL OPEN，原B6/B7整体未关闭。'
       f'以下开工和10-03文字保留历史时点；唯一当前入口仍为[CURRENT_STATUS]({current})。本批停止，无Git或部署。'
       '\r\n<!-- /B6-FINAL-INDEX:20261004 -->\r\n\r\n').encode('utf-8')
 pos=raw.index(b'\n')+1;new=raw[:pos]+text+raw[pos:];assert new[:pos]+new[pos+len(text):]==raw
 p.write_bytes(new);changes.append(dict(path=name,beforeSHA=sha(raw),afterSHA=sha(new),additiveOnly=True,before=saved.relative_to(R).as_posix()))
name='docs/qa/TEACHING-LOOP-G3-B6-20261004/README.md';p=R/name;raw=p.read_bytes();saved=before/name;saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(raw)
addition=(f'\n{at}：本批完成并停止：[限定B6最终矩阵](B6-CLOSE-MATRIX-v1.md)、[关闭收据](B6-CLOSE-v1.json)、'
 '[质量样例与人审入口](b6-quality/README.md)、[质量次数勘误](b6-quality/RESULT-CORRIGENDUM-v1.md)、'
 '[四类实际DOCX/PDF及教师试用](b6-exports/TEACHER-TRIAL-v1.md)。原计划B6/B7整体、真人/live/WordWPS/RAG-REL待验边界保持；以下是此前历史状态。\n\n').encode('utf-8')
pos=raw.index(b'\n')+1;new=raw[:pos]+addition+raw[pos:];p.write_bytes(new)
changes.append(dict(path=name,beforeSHA=sha(raw),afterSHA=sha(new),additiveOnly=True,before=saved.relative_to(R).as_posix()))
delta.write_text(json.dumps(dict(at=at,changes=changes,originalTasksEdited=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(at=at,path=delta.relative_to(R).as_posix(),files=len(changes)),ensure_ascii=False))
