"""Read-only checks of this batch's closed isolated backend stores."""
import json
import sqlite3
import tempfile
from pathlib import Path

batch = Path.cwd() / 'docs/qa/TEACHING-LOOP-G1-B4-20261002'
root = Path((batch / 'root/browser-data.txt').read_text(encoding='utf-8-sig').strip()).resolve()
assert root.is_relative_to(Path(tempfile.gettempdir()).resolve())
assert root.name == 'data' and root.parent.name.startswith('zqky-g1-browser-')
checks = []
for relative in ('textbooks/catalog.sqlite3', 'question-bank/question-bank.sqlite3', 'knowledge/knowledge.sqlite3', 'teaching/teaching.sqlite3'):
    path = root / relative
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as conn:
        integrity = conn.execute('PRAGMA integrity_check').fetchall()
        foreign_keys = conn.execute('PRAGMA foreign_key_check').fetchall()
        checks.append({'path': relative, 'integrityRows': integrity, 'foreignKeyRows': foreign_keys})
        assert integrity == [('ok',)] and foreign_keys == []
with sqlite3.connect((root / 'teaching/teaching.sqlite3').as_uri() + '?mode=ro', uri=True) as conn:
    revision = conn.execute("SELECT id, state FROM score_revisions WHERE assessment_id = ?", ('6b855beb49c54c1daf44564939a9abf3',)).fetchall()
    matrix = conn.execute('SELECT status, score_units FROM student_item_scores WHERE score_revision_id = ? ORDER BY item_id', ('bbe7c4fadbe74bbc8fce13aa3c3274e9',)).fetchall()
    assert revision == [('bbe7c4fadbe74bbc8fce13aa3c3274e9', 'confirmed')]
    assert sorted(matrix) == [('recorded', 100), ('recorded', 200), ('recorded', 500)]
payload = {'dataRoot': str(root), 'readOnly': True, 'checks': checks, 'revision': revision, 'matrix': matrix, 'totalUnits': sum(row[1] for row in matrix)}
(batch / 'root/closed-data-check.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'fourStoresIntegrity': 'ok', 'foreignKeyRows': 0, 'revisionCount': len(revision), 'totalUnits': payload['totalUnits']}))
