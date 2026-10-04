"""Generate the reviewed TS mirror from B4 declarations without app imports."""
import ast
from pathlib import Path

root = Path.cwd()
source = root / 'apps/api/app/contracts/b4.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
request_types = {'AnalysisCreateRequest', 'NoteRequest', 'PracticeConstraints', 'PracticeCreateRequest', 'PracticeNode', 'PracticeStructure', 'PracticeDraftItem', 'PracticeDraftPatch', 'PracticeSuggestionsRequest', 'PracticeReviewRequest', 'PracticeRevisionRequest', 'ExportRequest', 'PracticeConversionRequest'}

def typ(node):
    if isinstance(node, ast.Name):
        return {'str':'string', 'int':'number', 'float':'number', 'bool':'boolean', 'Any':'unknown'}.get(node.id, node.id)
    if isinstance(node, ast.Constant):
        if node.value is None:
            return 'null'
        return repr(node.value)
    if isinstance(node, ast.BinOp):
        return typ(node.left)+' | '+typ(node.right)
    if isinstance(node, ast.Subscript):
        name = node.value.id
        if name == 'list':
            return 'Array<'+typ(node.slice)+'>'
        if name == 'dict':
            return 'Record<'+', '.join(typ(n) for n in node.slice.elts)+'>'
        if name == 'Literal':
            return ' | '.join(typ(n) for n in (node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]))
        return name+'<'+typ(node.slice)+'>'
    raise ValueError(ast.dump(node))

lines = ["/** B4 v1 shared wire contract; mirrored from app/contracts/b4.py. */", "import type { JobView, RichContentV2, ScoreStatus, Observation } from './teaching-loop';", "import type { AssessmentParticipantInput } from './assessments';", '']
for cls in tree.body:
    if not isinstance(cls, ast.ClassDef) or cls.name == 'Frozen':
        continue
    lines.append('export interface '+cls.name+('<T>' if cls.name == 'Page' else '')+' {')
    for field in cls.body:
        if not isinstance(field, ast.AnnAssign):
            continue
        alias = field.target.id
        default = field.value is not None and not isinstance(field.value, ast.Call)
        if isinstance(field.value, ast.Call):
            for kw in field.value.keywords:
                if kw.arg == 'alias':
                    alias = kw.value.value
                if kw.arg in ('default', 'default_factory'):
                    default = True
        optional = '?' if default and cls.name in request_types else ''
        lines.append('  '+alias+optional+': '+typ(field.annotation)+';')
    lines.extend(['}', ''])
(root / 'apps/web/src/contracts/b4.ts').write_text('\n'.join(lines), encoding='utf-8')
print('mirrored', len([n for n in tree.body if isinstance(n, ast.ClassDef)])-1, 'models')
