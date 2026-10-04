"""Derive B5 runner, preserving the completed G2 tool byte for byte."""
from pathlib import Path

OUT=Path(__file__).resolve().parent
source=(OUT/"run_api.py").read_text(encoding="utf-8")
substitutions=[
    ('parser.add_argument(\'--candidate\', required=True)', 'parser.add_argument(\'--candidate\')\nparser.add_argument(\'--source\', action=\'append\', default=[])'),
    ("prefix='zqky-g2-ctrl-'", "prefix='zqky-b5-ctrl-'"),
    ("candidate_path = ROOT/args.candidate\ncandidate = json.loads(candidate_path.read_text(encoding='utf-8'))\nsource_hashes = lambda: {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in candidate['sourceFiles']}",
     "candidate_path = ROOT/args.candidate if args.candidate else None\ncandidate = json.loads(candidate_path.read_text(encoding='utf-8')) if candidate_path else None\nnames = set(args.source) | (set(candidate['sourceFiles']) if candidate else set())\nassert names, 'explicit private sources or stable candidate required'\nsource_hashes = lambda: {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(names)}"),
    ("candidateSHA=hashlib.sha256(candidate_path.read_bytes()).hexdigest()", "candidateSHA=hashlib.sha256(candidate_path.read_bytes()).hexdigest() if candidate_path else None"),
]
for before,after in substitutions:
    assert before in source,before
    source=source.replace(before,after)
with (OUT/"run_b5_api.py").open("x",encoding="utf-8",newline="\n") as stream:stream.write(source)
print("run_b5_api.py created; original run_api.py unchanged")
