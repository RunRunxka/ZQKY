"""Prepare fixed non-production paper for G1 browser verification."""
import json
import os
import sys
import tempfile
from pathlib import Path

root = Path(os.environ['ZQKY_DATA_DIR']).resolve()
assert os.environ['ZQKY_ENV'] == 'test'
assert root.is_relative_to(Path(tempfile.gettempdir()).resolve())
assert root.name == 'data'
repo = Path.cwd().resolve()
sys.path.insert(0, str(repo / 'apps/api'))
sys.path.insert(0, str(repo / 'tests/fixtures'))
from tests.scores_support import ScoresHarness
from teaching_loop_docx import build_complete_paper

with ScoresHarness(root.parent) as harness:
    paper = harness.seed_confirmed_paper(tag='g1browser', leaves=(('Q1', 200), ('Q2', 300), ('Q3', 500)), title='G1 固定验证卷')
    metadata = {'dataDir': str(root), 'paperId': paper.paper_id, 'paperRevisionId': paper.revision_id, 'title': paper.title}
(root.parent / 'g1-rich-paper.docx').write_bytes(build_complete_paper())
(repo / 'docs/qa/TEACHING-LOOP-G1-B4-20261002/root/browser-seed.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(metadata, ensure_ascii=False))
