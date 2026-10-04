"""Independent artifact audit: immutable exports only; no network or product imports."""
from pathlib import Path
from zipfile import ZipFile
import hashlib, json, logging, os, posixpath, re, runpy, subprocess, sys, time
from lxml import etree as ET
import pdfplumber

logging.getLogger('pdfminer').setLevel(logging.ERROR)
OUT = Path(__file__).resolve().parent
ROOT = Path.cwd()
RUNTIME = Path('C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies')
POPPLER = RUNTIME / 'native/poppler/Library/bin'
RENDERER = Path('C:/Users/96022/.codex/plugins/cache/openai-primary-runtime/documents/26.904.11930/skills/documents/render_docx.py')
TEMPLATE = ROOT / 'apps/web/public/templates/lesson-plan-template.docx'
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
sha = lambda b: hashlib.sha256(b).hexdigest()
compact = lambda s: re.sub(r'\s', '', s or '')
write = lambda p, v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
started = time.perf_counter()
receipt = {'command': [sys.executable, str(Path(__file__).resolve())], 'pid': os.getpid(), 'sourceBeforeSHA': sha(Path(__file__).read_bytes()), 'startedAtEpoch': time.time(), 'samples': [], 'subcommands': [], 'network': False}

def run_command(args):
    start = time.perf_counter()
    child = subprocess.Popen([str(x) for x in args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf8')
    stdout, stderr = child.communicate(timeout=60)
    record = {'command': [str(x) for x in args], 'pid': child.pid, 'exitCode': child.returncode, 'durationMs': (time.perf_counter() - start) * 1000, 'stdout': stdout, 'stderr': stderr}
    receipt['subcommands'].append(record)
    assert child.returncode == 0, record
    return record

def parse_xml(content):
    return ET.fromstring(content, parser=ET.XMLParser(resolve_entities=False, no_network=True))

def package_check(path, expected):
    with ZipFile(path) as z, ZipFile(TEMPLATE) as template:
        assert z.testzip() is None
        names = set(z.namelist())
        parsed = {n: parse_xml(z.read(n)) for n in names if n.endswith('.xml') or n.endswith('.rels')}
        relations = []
        for n, doc in parsed.items():
            if not n.endswith('.rels'):
                continue
            base = '' if n == '_rels/.rels' else posixpath.dirname(posixpath.dirname(n))
            for rel in doc:
                target = rel.get('Target')
                external = rel.get('TargetMode') == 'External'
                resolved = None if external else posixpath.normpath(posixpath.join(base, target)).lstrip('/')
                if not external:
                    assert resolved in names, (n, target, resolved)
                relations.append({'part': n, 'target': target, 'resolved': resolved, 'external': external})
        doc = parsed['word/document.xml']
        source = parse_xml(template.read('word/document.xml'))
        rows = doc.xpath('//w:tr', namespaces=NS)
        assert len(rows) == 11
        cells = [row.xpath('./w:tc', namespaces=NS) for row in rows]
        text = lambda cell: ''.join(cell.xpath('.//w:t/text()', namespaces=NS))
        actual = {'title': text(cells[0][1]), 'totalLessons': text(cells[0][3]), 'currentLessonNo': text(cells[0][5]), 'lessonTypesText': text(cells[1][1]), 'coreCompetencies': text(cells[2][1]), 'keyPoints': text(cells[3][1]), 'teachingDesign': text(cells[4][1]), 'firstDesign': text(cells[6][1]), 'firstSecondary': text(cells[6][2]), 'restDesign': text(cells[8][1]), 'restSecondary': text(cells[8][2]), 'exercises': text(cells[9][1]), 'reflection': text(cells[10][1])}
        for name in ('title', 'totalLessons', 'coreCompetencies', 'keyPoints', 'teachingDesign', 'exercises', 'reflection'):
            assert actual[name] == expected[name], ('DOCX complete scalar', name)
        assert actual['currentLessonNo'] == '第' + expected['currentLessonNo'] + '课时'
        types = [('new', '新课'), ('review', '复习课'), ('exercise', '试题讲评课'), ('experiment', '实验课'), ('other', '其它')]
        expected_types = '  '.join(('☑' if key in expected['lessonTypes'] else '□') + label + ('（' + expected['otherTypeText'] + '）' if key == 'other' and key in expected['lessonTypes'] else '') for key, label in types)
        assert actual['lessonTypesText'] == expected_types
        for scope, processes in (('first', expected['process'][:2]), ('rest', expected['process'][2:])):
            for field, suffix in (('design', 'Design'), ('secondary', 'Secondary')):
                wanted = ''.join(p['stage'] + p[field] for p in processes)
                assert actual[scope + suffix] == wanted, ('DOCX whole process', scope, field)
        c14n = lambda elem: ET.tostring(elem, method='c14n')
        properties = {}
        for name, xp in {'table': '//w:tblPr', 'cell': '//w:tcPr', 'row': '//w:trPr', 'section': '//w:sectPr'}.items():
            got, baseline = doc.xpath(xp, namespaces=NS), source.xpath(xp, namespaces=NS)
            assert [c14n(x) for x in got] == [c14n(x) for x in baseline], ('template properties', name)
            properties[name] = {'count': len(got), 'SHA': sha(b''.join(c14n(x) for x in got))}
        fonts = lambda doc: sorted({tuple(sorted(x.attrib.items())) for x in doc.xpath('//w:rFonts', namespaces=NS)})
        assert fonts(doc) == fonts(source)
        assert z.read('word/styles.xml') == template.read('word/styles.xml')
        heights = [dict(x.attrib) for x in doc.xpath('//w:trHeight', namespaces=NS)]
        assert all(x.get('{'+NS['w']+'}hRule') != 'exact' for x in doc.xpath('//w:trHeight', namespaces=NS))
        all_text = ''.join(doc.xpath('//w:t/text()', namespaces=NS))
        assert not re.search(r'\{(?:title|coreCompetencies|firstDesign|restDesign|firstSecondary|restSecondary|reflection)\}', all_text)
        return {'status': 'actualpass', 'zipCRC': 'all_members_valid', 'xmlParts': len(parsed), 'relations': relations, 'all11FieldProof': actual, 'properties': properties, 'fonts': fonts(doc), 'rowHeights': heights, 'gridSpanCount': len(doc.xpath('//w:gridSpan', namespaces=NS)), 'verticalMergeCount': len(doc.xpath('//w:vMerge', namespaces=NS)), 'fixedTemplateRows': 11, 'longContent': 'Full field and process text retained; inherited table/cell/row/section properties and non-exact height verified; Word pagination not claimed.'}

def pdf_check(path, manifest):
    expected = manifest['fullData']
    field_labels = {'核心素养目标': 'coreCompetencies', '教学重、难点': 'keyPoints', '教学设计': 'teachingDesign', '课堂练习及作业布置': 'exercises', '教学反思': 'reflection'}
    values = {field: '' for field in field_labels.values()}
    designs, secondary, stages, pages = '', '', [], []
    with pdfplumber.open(path) as pdf:
        assert len(pdf.pages) == manifest['printRecord']['paperCount']
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            assert manifest['saved']['currentRevisionId'] in text
            assert '后台固定 v2' in text
            assert 590 < page.width < 600 and 838 < page.height < 845
            tables = page.extract_tables()
            process_active = False
            for table in tables:
                for row in table:
                    label = compact(row[0]).replace('（续）', '')
                    if label in field_labels:
                        process_active = False
                        values[field_labels[label]] += compact(row[1])
                    elif label == '课题':
                        assert compact(row[1]) == compact(expected['title'])
                        assert compact(row[3]) == compact(expected['totalLessons'])
                        assert compact(row[5]) == '第'+expected['currentLessonNo']+'课时'
                    elif label == '课型':
                        assert compact(expected['otherTypeText']) in compact(row[1])
                    elif label == '教学过程' or (not label and process_active):
                        process_active = True
                        main, sec = compact(row[1]), compact(row[-1])
                        if main.startswith('教学设计'):
                            main = main[len('教学设计'):]
                        if sec.startswith('二次备课'):
                            sec = sec[len('二次备课'):]
                        for process in expected['process']:
                            stage = compact(process['stage'])
                            if main.startswith(stage):
                                stages.append(stage)
                                main = main[len(stage):]
                                if main.startswith('（续）'):
                                    main = main[len('（续）'):]
                                break
                        designs += main
                        secondary += sec
            pages.append({'page': i+1, 'width': page.width, 'height': page.height, 'text': text, 'tables': tables})
        for name, value in values.items():
            assert value == compact(expected[name]), ('Actual PDF full field', name, len(value), len(compact(expected[name])))
        assert designs == compact(''.join(p['design'] for p in expected['process'])), 'Actual PDF complete process designs'
        assert secondary == compact(''.join(p['secondary'] for p in expected['process'])), 'Actual PDF complete process secondary'
        sequence = [stage for i, stage in enumerate(stages) if i == 0 or stage != stages[i-1]]
        assert sequence == [compact(p['stage']) for p in expected['process']], 'Actual PDF every stage in order'
    return {'status': 'actualpass', 'pages': pages, 'fullFieldReconstruction': values, 'allProcessDesign': designs, 'allProcessSecondary': secondary, 'processStageSequence': sequence, 'sourceOnEveryPage': True, 'extractionNote': 'Only line-wrap whitespace normalized; actual PDF table cells, complete scalar and every process design/secondary reconstructed. No product pagination called.'}

try:
    # Bundled-only dependency preflight. Never invokes user desktop Office/WPS.
    previous_path = os.environ.get('PATH', '')
    restricted_path = os.pathsep.join(str(x) for x in (RUNTIME/'python', RUNTIME/'node/bin', RUNTIME/'bin/override', RUNTIME/'bin/fallback', POPPLER))
    os.environ['PATH'] = restricted_path
    diagnostic_start = time.perf_counter()
    try:
        module = runpy.run_path(str(RENDERER))
        soffice = module['_resolve_soffice']()
        receipt['docxRender'] = {'status': 'ready', 'resolved': soffice}
    except FileNotFoundError as error:
        receipt['docxRender'] = {'status': 'not_run', 'reason': str(error), 'bundledOnlyPATH': restricted_path, 'renderer': str(RENDERER), 'rendererSHA': sha(RENDERER.read_bytes()), 'durationMs': (time.perf_counter()-diagnostic_start)*1000, 'desktopOfficeInvoked': False}
    finally:
        os.environ['PATH'] = previous_path
    assert receipt['docxRender']['status'] == 'not_run', 'Unexpected bundled LO requires actual rendering before conclusion.'
    for case in ('short', 'long', 'multi', 'symbols'):
        directory = OUT/'samples-r3'/case
        manifest = json.loads((directory/'manifest.json').read_text('utf8'))
        assert sha((directory/(case+'.docx')).read_bytes()) == manifest['docx']['SHA']
        assert sha((directory/(case+'.pdf')).read_bytes()) == manifest['pdf']['SHA']
        assert manifest['before'] == manifest['after'] and manifest['browserPATCH'] == []
        assert sha(manifest['source'].encode()) == manifest['sourceSHA']
        assert sha(TEMPLATE.read_bytes()) == manifest['templateSHA']
        with ZipFile(directory/'trace.zip') as trace:
            assert trace.testzip() is None
        docx_result = package_check(directory/(case+'.docx'), manifest['fullData'])
        pdf_result = pdf_check(directory/(case+'.pdf'), manifest)
        render = directory/'pdf-pages'
        render.mkdir()
        cmd = run_command([POPPLER/'pdftoppm.exe', '-png', '-r', '110', directory/(case+'.pdf'), render/'page'])
        pngs = sorted(render.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
        assert len(pngs) == len(pdf_result['pages'])
        pdf_result['pagePNGs'] = [{'path': str(p.resolve()), 'SHA': sha(p.read_bytes())} for p in pngs]
        write(directory/'offline-structure-and-pdf.json', {'docx': docx_result, 'pdf': pdf_result, 'docxRender': receipt['docxRender']})
        receipt['samples'].append({'caseId': case, 'status': 'actualpass', 'docxStructure': 'actualpass', 'actualPDFFullTextAndSource': 'actualpass', 'pageCount': len(pngs), 'renderPID': cmd['pid'], 'structureResultSHA': sha((directory/'offline-structure-and-pdf.json').read_bytes()), 'visualReview': 'pending_actual_view', 'docxLayout': 'not_run'})
        print(json.dumps({'case': case, 'status': 'actualpass', 'PDFpages': len(pngs), 'docxLayout': 'not_run'}))
    receipt['exitCode'] = 0
except Exception as error:
    receipt['exitCode'] = 1
    receipt['failure'] = {'type': type(error).__name__, 'message': str(error)}
    import traceback
    traceback.print_exc()
finally:
    receipt['durationMs'] = (time.perf_counter() - started)*1000
    receipt['sourceAfterSHA'] = sha(Path(__file__).read_bytes())
    write(OUT/'offline-r1-command.json', receipt)
sys.exit(receipt['exitCode'])
