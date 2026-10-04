"""Scoped front-end author checks; immutable labels, no services or business data imports."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
NODE = Path('C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
SCOPE = [
    'apps/web/src/features/practices/PracticeEditor.tsx',
    'apps/web/src/features/practices/PracticesWorkspace.tsx',
    'apps/web/src/features/practices/session.ts',
    'apps/web/src/features/practices/styles.css',
    'apps/web/src/features/practices/g2-session.test.tsx',
    'apps/web/src/features/practices/PracticesWorkspace.test.tsx',
    'apps/web/src/features/learning-analysis/LearningAnalysisWorkspace.tsx',
    'apps/web/src/features/learning-analysis/LearningAnalysisWorkspace.test.tsx',
    'apps/web/src/features/assessments/hooks.ts',
    'apps/web/src/services/navigation-guard.tsx',
    'apps/web/src/contracts/b4.ts',
]


def shas():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SCOPE}


def main():
    label = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else 'unit'
    if not label.replace('-', '').isalnum():
        raise ValueError('invalid immutable label')
    receipt = OUT / f'{label}-command.json'
    logfile = OUT / f'{label}.log'
    result = OUT / f'{label}-results.json'
    for target in (receipt, logfile, result):
        if target.exists():
            raise FileExistsError(target)
    temp = tempfile.mkdtemp(prefix=f'zqky-g2-fe-{label}-')
    env = dict(os.environ)
    env.update({'NODE_OPTIONS': '--no-experimental-webstorage', 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8', 'ZQKY_ENV': 'test', 'ZQKY_DATA_DIR': str(Path(temp) / 'data')})
    command = [str(NODE), str(ROOT / 'node_modules/vitest/vitest.mjs'), 'run', '--config', 'vitest.config.ts',
               'apps/web/src/features/practices/g2-session.test.tsx', 'apps/web/src/features/practices/PracticesWorkspace.test.tsx',
               'apps/web/src/features/learning-analysis/LearningAnalysisWorkspace.test.tsx', '--maxWorkers=1', '--no-file-parallelism',
               '--reporter=default', '--reporter=json', f'--outputFile.json={result}']
    if mode == 'lint':
        command = [str(NODE), str(ROOT / 'node_modules/eslint/bin/eslint.js'), '--max-warnings=0', *[name for name in SCOPE[:8] if not name.endswith('.css')]]
    elif mode == 'types':
        config = OUT / f'{label}-tsconfig.json'
        with config.open('x', encoding='utf-8') as stream:
            json.dump({'extends': str(ROOT / 'apps/web/tsconfig.json'), 'compilerOptions': {'noEmit': True, 'incremental': False},
                       'include': [str(ROOT / name) for name in SCOPE[:8] if not name.endswith('.css')] + [str(ROOT / 'tests/setup.ts')], 'exclude': ['node_modules']}, stream, indent=2)
        command = [str(NODE), str(ROOT / 'node_modules/typescript/bin/tsc'), '--project', str(config)]
    elif mode != 'unit':
        raise ValueError('unknown limited mode')
    before = shas()
    start = dt.datetime.now(dt.timezone.utc).isoformat()
    clock = time.perf_counter()
    with logfile.open('xb') as stream:
        child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        exit_code = child.wait()
    ms = (time.perf_counter() - clock) * 1000
    after = shas()
    record = {'label': label, 'mode': mode, 'command': command, 'cwd': str(ROOT), 'env': {key: env[key] for key in ('NODE_OPTIONS', 'PYTHONUTF8', 'PYTHONIOENCODING', 'ZQKY_ENV', 'ZQKY_DATA_DIR')},
              'startedAtUtc': start, 'finishedAtUtc': dt.datetime.now(dt.timezone.utc).isoformat(), 'pid': child.pid, 'exitCode': exit_code, 'elapsedMs': round(ms, 3),
              'childClosed': child.poll() is not None, 'logClosed': True, 'sampleRoot': temp, 'sampleRetained': True, 'sourceBefore': before, 'sourceAfter': after,
              'changedSources': [key for key in before if before[key] != after[key]], 'logSha256': hashlib.sha256(logfile.read_bytes()).hexdigest()}
    record['uncaughtExceptionRecords'] = logfile.read_text(encoding='utf-8', errors='strict').count('Uncaught Exception')
    if result.exists():
        actual = json.loads(result.read_text(encoding='utf-8'))
        record['actual'] = {key: actual.get(key) for key in ('numTotalTests', 'numPassedTests', 'numFailedTests', 'numPendingTests', 'success')}
        record['resultSha256'] = hashlib.sha256(result.read_bytes()).hexdigest()
    with receipt.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
    print(json.dumps({key: record.get(key) for key in ('label', 'pid', 'exitCode', 'elapsedMs', 'changedSources', 'actual', 'sampleRoot')}, ensure_ascii=False))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
