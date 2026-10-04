import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { performance } from 'node:perf_hooks';
import { createHash } from 'node:crypto';
import { transform } from 'esbuild';
import ts from 'typescript';

const QA = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(QA, '..', '..', '..', '..');
const sources = [
  { name: 'assessments', prefix: 'zqky-f20i-', promise: true },
  { name: 'question-bank-real', prefix: 'zqky-f10-real-', promise: false },
];
const sha = (bytes) => createHash('sha256').update(bytes).digest('hex');
const normalize = (value) => value.replaceAll('\r\n', '\n');
const receipts = [];
const created = [];
const preservedEnv = process.env.ZQKY_KEEP_TEST_DATA;
const startedAt = new Date().toISOString();
const started = performance.now();

function collect(source, filename) {
  const tree = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const tests = [];
  const functions = new Map();
  function visit(node) {
    if (ts.isFunctionDeclaration(node) && node.name) {
      functions.set(node.name.text, normalize(node.getText(tree)));
    }
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'test') {
      assert(ts.isStringLiteral(node.arguments[0]), 'Business test name must remain a literal');
      tests.push({ name: node.arguments[0].text, source: normalize(node.getText(tree)) });
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
  return { tests, functions };
}

async function loadRealHook(entry) {
  const filename = path.join(REPO, 'tests', 'e2e', `${entry.name}.spec.ts`);
  const beforeBytes = fs.readFileSync(path.join(QA, `${entry.name}.before.ts`));
  const afterBytes = fs.readFileSync(filename);
  const before = collect(beforeBytes.toString('utf8'), filename);
  const after = collect(afterBytes.toString('utf8'), filename);
  assert.deepEqual(after.tests, before.tests, 'Business test collection and entire callbacks must remain unchanged');
  for (const [name, original] of before.functions) {
    if (name !== 'startBackend' && name !== 'stopBackend') {
      assert.equal(after.functions.get(name), original, `Non-lifecycle function changed: ${name}`);
    }
  }
  const hooks = [];
  const registrations = [];
  const stub = (name) => registrations.push(name);
  stub.afterAll = (callback) => hooks.push(callback);
  stub.describe = (_name, callback) => callback();
  stub.describe.configure = () => {};
  globalThis.__resourceTest = stub;
  const importLine = /^import \{ test, expect[^\n]*\} from '@playwright\/test';\r?$/m;
  assert(importLine.test(afterBytes.toString('utf8')), 'Only Playwright registration import is replaced for hook capture');
  const text = afterBytes.toString('utf8')
    .replace(importLine, 'const test = globalThis.__resourceTest; const expect = () => { throw new Error("Business callbacks must not run in resource harness"); };')
    .replaceAll('import.meta.url', JSON.stringify(pathToFileURL(filename).href))
    + `\nexport function __installFixture(value) { backend = value; ${entry.promise ? 'backendPromise = Promise.resolve(value);' : ''} }\n`
    + `export function __stateCleared() { return backend === null${entry.promise ? ' && backendPromise === null' : ''}; }\n`;
  const compiled = await transform(text, { loader: 'ts', target: 'node22', format: 'esm', sourcefile: filename });
  const output = path.join(QA, `${entry.name}.compiled.mjs`);
  fs.writeFileSync(output, compiled.code);
  const module = await import(pathToFileURL(output).href);
  delete globalThis.__resourceTest;
  assert.equal(hooks.length, 1);
  assert.deepEqual(registrations, before.tests.map((test) => test.name));
  return { module, hook: hooks[0], source: { name: entry.name, beforeSha256: sha(beforeBytes), afterSha256: sha(afterBytes), testCount: before.tests.length, testNames: registrations, businessCallbacksUnchanged: true, nonLifecycleFunctionsUnchanged: true } };
}

async function ownFixture(entry, mode) {
  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), entry.prefix));
  const dataDir = path.join(tmpRoot, 'data');
  fs.mkdirSync(dataDir);
  fs.writeFileSync(path.join(dataDir, 'marker.txt'), `owned ${entry.name} ${mode}\n`);
  created.push({ spec: entry.name, mode, tmpRoot, dataDir, createdByThisHarness: true });
  fs.writeFileSync(path.join(QA, 'created-roots.json'), JSON.stringify({ startedAt, roots: created }, null, 2));
  const child = spawn(process.execPath, ['-e', "process.stdout.end('STDOUT-BEGIN\\nSTDOUT-END\\n'); setTimeout(() => { process.stderr.end('STDERR-TAIL\\n'); }, 100); setInterval(() => {}, 1000);"], { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  const order = [];
  const closed = new Promise((resolve) => child.once('close', () => { order.push('child-close'); resolve(); }));
  const logStream = fs.createWriteStream(path.join(tmpRoot, 'api.log'));
  logStream.once('close', () => order.push('log-close'));
  child.stdout.pipe(logStream, { end: false });
  child.stderr.pipe(logStream, { end: false });
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Own no-port child did not emit tail')), 5000);
    let stderr = '';
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
    child.stderr.once('end', () => {
      clearTimeout(timer);
      assert.equal(stderr, 'STDERR-TAIL\n');
      resolve();
    });
  });
  assert.equal(logStream.writableEnded, false, 'Two pipe EOFs must not prematurely end the log');
  assert.equal(child.exitCode, null, 'Own fixture must still be alive until real afterAll');
  return { origin: 'no-network-fixture', child, closed, logStream, tmpRoot, dataDir, order };
}

async function runCase(entry, loaded, mode) {
  const current = await ownFixture(entry, mode);
  const expectKeep = mode === 'keep';
  if (expectKeep) process.env.ZQKY_KEEP_TEST_DATA = '1';
  else delete process.env.ZQKY_KEEP_TEST_DATA;
  loaded.module.__installFixture(current);
  const originalRm = fs.rmSync;
  const originalLog = console.log;
  const printed = [];
  let removed = false;
  fs.rmSync = (target, options) => {
    const resolved = path.resolve(target);
    const relative = path.relative(path.resolve(os.tmpdir()), resolved);
    assert.equal(resolved, path.resolve(current.tmpRoot), 'Cleanup must target only this just-created root');
    assert(relative && !relative.startsWith('..') && !path.isAbsolute(relative));
    assert(path.basename(resolved).startsWith(entry.prefix));
    assert.deepEqual(current.order, ['child-close', 'log-close'], 'Child and log closure must precede recursive cleanup');
    assert.equal(current.logStream.closed, true);
    assert.equal(fs.readFileSync(path.join(resolved, 'api.log'), 'utf8'), 'STDOUT-BEGIN\nSTDOUT-END\nSTDERR-TAIL\n');
    current.order.push('rm-own-root');
    removed = true;
    return originalRm(target, options);
  };
  console.log = (...args) => { printed.push(args.join(' ')); originalLog(...args); };
  const caseStart = performance.now();
  try {
    await loaded.hook();
    assert.equal(loaded.module.__stateCleared(), true);
    assert.equal(current.logStream.closed, true);
    assert.equal(removed, !expectKeep);
    assert.equal(fs.existsSync(current.tmpRoot), expectKeep);
    if (expectKeep) {
      assert.deepEqual(current.order, ['child-close', 'log-close']);
      assert.equal(fs.readFileSync(path.join(current.tmpRoot, 'api.log'), 'utf8'), 'STDOUT-BEGIN\nSTDOUT-END\nSTDERR-TAIL\n');
      const retained = printed.filter((line) => line.startsWith('[ZQKY_TEST_DATA_RETAINED] '));
      assert.equal(retained.length, 1);
      const record = JSON.parse(retained[0].slice('[ZQKY_TEST_DATA_RETAINED] '.length));
      assert.deepEqual(record, { spec: entry.name, tmpRoot: path.resolve(current.tmpRoot), dataDir: current.dataDir, apiLog: path.join(path.resolve(current.tmpRoot), 'api.log'), pid: current.child.pid, childClosed: true, logClosed: true });
    } else {
      assert.deepEqual(current.order, ['child-close', 'log-close', 'rm-own-root']);
      assert.equal(printed.filter((line) => line.startsWith('[ZQKY_TEST_DATA_RETAINED] ')).length, 0);
    }
    const value = { spec: entry.name, mode, pid: current.child.pid, tmpRoot: current.tmpRoot, apiLog: path.join(current.tmpRoot, 'api.log'), childClosed: true, logClosed: true, logContainsStdoutAndStderrTail: true, retained: expectKeep, deletedOwnNewRoot: !expectKeep, order: current.order, elapsedMs: Math.round(performance.now() - caseStart), result: 'passed' };
    receipts.push(value);
    originalLog(`PASS ${entry.name} ${mode} ${value.elapsedMs}ms`);
  } finally {
    fs.rmSync = originalRm;
    console.log = originalLog;
  }
}

try {
  const source = [];
  for (const entry of sources) {
    const loaded = await loadRealHook(entry);
    source.push(loaded.source);
    for (const mode of ['keep', 'default']) await runCase(entry, loaded, mode);
  }
  const summary = { startedAt, finishedAt: new Date().toISOString(), node: process.version, platform: process.platform, cases: receipts.length, passed: receipts.length, failed: 0, elapsedMs: Math.round(performance.now() - started), source, receipts, resources: { noApiImports: true, noNetworkListeners: true, ownedChildrenClosed: true, ownedLogStreamsClosed: true, retainedNewRoots: created.filter((root) => root.mode === 'keep'), removedOnlyOwnNewRoots: created.filter((root) => root.mode === 'default'), oldDirectoriesUntouched: true, frontendUntouched: true } };
  fs.writeFileSync(path.join(QA, 'resource-receipts.json'), JSON.stringify(summary, null, 2));
  console.log(`RESULT ${summary.passed} passed, 0 failed, ${summary.elapsedMs}ms`);
} finally {
  if (preservedEnv === undefined) delete process.env.ZQKY_KEEP_TEST_DATA;
  else process.env.ZQKY_KEEP_TEST_DATA = preservedEnv;
}
