import ts from 'typescript';
import { readdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import path from 'node:path';
const root = 'docs/qa/TEACHING-LOOP-G3-B6-20261004/v00';
const output = process.argv[2]; if (!output || existsSync(output)) throw new Error('Fresh preparation receipt path required');
const startedAt = new Date().toISOString(), started = performance.now(), results = [];
for (const dir of ['unit', 'browser']) for (const file of readdirSync(path.join(root, dir)).filter((file) => /\.tsx?$/.test(file))) {
  const filename = path.join(root, dir, file), source = readFileSync(filename, 'utf8');
  const parsed = ts.transpileModule(source, { fileName: filename, reportDiagnostics: true,
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
  results.push({ file: filename, diagnostics: (parsed.diagnostics ?? []).map((d) => ({ code: d.code, text: ts.flattenDiagnosticMessageText(d.messageText, '\n') })) });
}
const result = { task: 'G3-V00-v1 preparation only', command: process.argv, pid: process.pid, startedAt,
  endedAt: new Date().toISOString(), durationMs: performance.now() - started, results,
  productTestsRun: false, servicesStarted: false, checks: 'TypeScript parser/transpile syntax only, not typechecking or behavior acceptance' };
writeFileSync(output, JSON.stringify(result, null, 2) + '\n');
const errors = results.reduce((count, item) => count + item.diagnostics.length, 0); process.stdout.write(JSON.stringify({ files: results.length, errors, output }) + '\n'); process.exitCode = errors ? 1 : 0;
