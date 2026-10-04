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
    matrix = conn.execute('SELECT participant_id, item_id, status, score_units FROM student_item_scores WHERE score_revision_id = ? ORDER BY participant_id, item_id', ('bbe7c4fadbe74bbc8fce13aa3c3274e9',)).fetchall()
    assert revision == [('bbe7c4fadbe74bbc8fce13aa3c3274e9', 'confirmed')]
    frozen = json.loads(conn.execute('SELECT participant_snapshot_json FROM score_revisions WHERE id = ?', (revision[0][0],)).fetchone()[0])
    expected_by_suffix = {'甲': [100, 200, 500], '丙': [0, 300, 500], '丁': [200, 300, 500]}
    participant_totals = {}
    assert len(matrix) == 9 and len(frozen) == 3
    for participant in frozen:
        expected = expected_by_suffix[participant['name'][-1]]
        cells = [row for row in matrix if row[0] == participant['participantId']]
        assert [row[1] for row in cells] == ['it-g1browser-1', 'it-g1browser-2', 'it-g1browser-3']
        assert [row[2] for row in cells] == ['recorded'] * 3
        assert [row[3] for row in cells] == expected
        participant_totals[participant['name'][-1]] = sum(expected)
payload = {'dataRoot': str(root), 'readOnly': True, 'checks': checks, 'revision': revision, 'matrix': matrix, 'participantTotals': participant_totals}
(batch / 'root/closed-data-check.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'fourStoresIntegrity': 'ok', 'foreignKeyRows': 0, 'revisionCount': len(revision), 'matrixCellCount': len(matrix), 'participantTotals': participant_totals}, ensure_ascii=False))
