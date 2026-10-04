"""Preserve prepared v1 probes and derive new v2 labels, never overwrite results."""
from pathlib import Path
import json

OUT=Path(__file__).resolve().parent
changes=[]
for source_name,target_name,substitutions in (
    ("b5_contract_probe.py","b5_contract_probe_v2.py",[("-v1.json","-v2.json"),("modelFingerprint=\"7\"*64","modelFingerprint=\"sha256:\"+\"7\"*64")]),
    ("b5_ddl_probe.py","b5_ddl_probe_v2.py",[("B5-DDL-PROBE-v1.json","B5-DDL-PROBE-v2.json")]),
):
    source=OUT/source_name
    snapshot=OUT/(source_name+".prepared-v1.bin")
    with snapshot.open("xb") as stream: stream.write(source.read_bytes())
    text=source.read_text(encoding="utf-8")
    for before,after in substitutions:
        assert before in text,before
        text=text.replace(before,after)
    with (OUT/target_name).open("x",encoding="utf-8",newline="\n") as stream: stream.write(text)
    changes.append(dict(original=source_name,preserved=snapshot.name,new=target_name))
print(json.dumps(changes))
