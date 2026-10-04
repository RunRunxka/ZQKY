"""F30-L scoped checks with immutable source-bound labels; no services or real storage."""
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
MODULE = ROOT / 'apps/web/src/features/lesson-plan'

def sources():
    paths = [p for p in MODULE.rglob('*') if p.suffix in {'.ts', '.tsx', '.css', '.json'}]
    paths += [ROOT / p for p in ['apps/web/src/features/assessments/hooks.ts', 'apps/web/src/services/navigation-guard.tsx', 'apps/web/src/contracts/lesson-plans.ts', 'apps/web/src/services/lesson-plans-api.ts', 'apps/web/src/services/lesson-plan-sources-api.ts', 'apps/web/src/services/use-workflow-job.ts']]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}

def main():
    label, mode = sys.argv[1:3]
    if not label.replace('-', '').isalnum() or mode not in {'unit', 'types', 'lint'}:
        raise ValueError('invalid label/mode')
    log, receipt, result = [OUT / f'{label}{suffix}' for suffix in ['.log', '-command.json', '-results.json']]
    if any(p.exists() for p in [log, receipt, result]): raise FileExistsError(label)
    temp = tempfile.mkdtemp(prefix=f'zqky-b5-fe-{label}-')
    env = dict(os.environ, NODE_OPTIONS='--no-experimental-webstorage', PYTHONUTF8='1', PYTHONIOENCODING='utf-8', ZQKY_ENV='test', ZQKY_DATA_DIR=str(Path(temp) / 'data'))
    scope = [str(p) for p in sorted(MODULE.rglob('*')) if p.suffix in {'.ts', '.tsx'} and p.name != 'types.ts']
    if mode == 'types':
        config = OUT / f'{label}-tsconfig.json'
        with config.open('x', encoding='utf-8') as stream: json.dump({'extends': str(ROOT / 'apps/web/tsconfig.json'), 'compilerOptions': {'incremental': False, 'noEmit': True}, 'include': scope + [str(ROOT / 'tests/setup.ts')], 'exclude': ['node_modules']}, stream, indent=2)
        argv = [str(NODE), str(ROOT / 'node_modules/typescript/bin/tsc'), '--project', str(config)]
    elif mode == 'lint': argv = [str(NODE), str(ROOT / 'node_modules/eslint/bin/eslint.js'), '--max-warnings=0', *scope]
    else: argv = [str(NODE), str(ROOT / 'node_modules/vitest/vitest.mjs'), 'run', '--config', 'vitest.config.ts', 'apps/web/src/features/lesson-plan', '--maxWorkers=1', '--no-file-parallelism', '--reporter=default', '--reporter=json', f'--outputFile.json={result}']
    before = sources()
    snapshot = OUT / f'{label}-source'
    for name in before:
        target = snapshot / name; target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream: stream.write((ROOT / name).read_bytes())
    started = dt.datetime.now(dt.timezone.utc).isoformat(); tick = time.perf_counter()
    with log.open('xb') as stream:
        child = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        code = child.wait()
    after = sources(); raw = log.read_text(encoding='utf-8')
    record = {'label': label, 'mode': mode, 'argv': argv, 'cwd': str(ROOT), 'environment': {k: env[k] for k in ['NODE_OPTIONS', 'PYTHONUTF8', 'PYTHONIOENCODING', 'ZQKY_ENV', 'ZQKY_DATA_DIR']}, 'pid': child.pid, 'exitCode': code, 'elapsedMs': round((time.perf_counter()-tick)*1000, 3), 'startedAtUtc': started, 'finishedAtUtc': dt.datetime.now(dt.timezone.utc).isoformat(), 'sourceBefore': before, 'sourceAfter': after, 'changedSources': [k for k in before if before[k] != after.get(k)], 'sampleRoot': temp, 'sampleRetained': True, 'childClosed': child.poll() is not None, 'logClosed': True, 'logSha256': hashlib.sha256(log.read_bytes()).hexdigest(), 'uncaughtExceptionRecords': raw.count('Uncaught Exception'), 'firstFailurePreservedIn': str(log) if code else None}
    if result.exists():
        actual = json.loads(result.read_text(encoding='utf-8')); record['actual'] = {k: actual.get(k) for k in ['numTotalTests', 'numPassedTests', 'numFailedTests', 'numPendingTests', 'success']}; record['failedCases'] = [{'name': case.get('fullName'), 'messages': case.get('failureMessages')} for suite in actual.get('testResults', []) for case in suite.get('assertionResults', []) if case.get('status') == 'failed']; record['resultSha256'] = hashlib.sha256(result.read_bytes()).hexdigest()
    with receipt.open('x', encoding='utf-8') as stream: json.dump(record, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k: record.get(k) for k in ['label', 'pid', 'exitCode', 'elapsedMs', 'changedSources', 'actual', 'sampleRoot']}, ensure_ascii=False))
    return code

if __name__ == '__main__': raise SystemExit(main())
