import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import ts from 'typescript';

const qa = 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002';
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
function extract(file) {
  const bytes = fs.readFileSync(file);
  const source = ts.createSourceFile(file, bytes.toString('utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const businessTests = [], hooks = [], functions = {}, imports = [];
  function walk(node) {
    if (ts.isCallExpression(node)) {
      const callee = node.expression.getText(source);
      if (callee === 'test' || callee === 'test.only' || callee === 'test.skip' || callee === 'test.fixme') {
        const name = node.arguments[0]?.getText(source);
        businessTests.push({name, sha256:hash(node.getText(source)), text:node.getText(source)});
      }
      if (callee === 'test.afterAll' || callee === 'test.beforeAll') hooks.push({name:callee,text:node.getText(source)});
    }
    if (ts.isFunctionDeclaration(node) && node.name) functions[node.name.text] = node.getText(source);
    if (ts.isImportDeclaration(node)) imports.push(node.getText(source));
    ts.forEachChild(node,walk);
  }
  walk(source);
  return {file, sha256:hash(bytes), businessTests, functions, hooks, imports,
    parseDiagnostics:source.parseDiagnostics.map(d=>ts.flattenDiagnosticMessageText(d.messageText,'\n'))};
}
const specs = [['assessments','tests/e2e/assessments.spec.ts'],['question-bank-real','tests/e2e/question-bank-real.spec.ts']];
const reports = [];
for (const [name,currentPath] of specs) {
  const before = extract(`${qa}/adapt-e2e/${name}.before.ts`), after = extract(currentPath);
  const oldTests = before.businessTests.map(t=>({name:t.name,sha256:t.sha256}));
  const newTests = after.businessTests.map(t=>({name:t.name,sha256:t.sha256}));
  const changedFunctions = Object.keys(before.functions).filter(n=>before.functions[n]!==after.functions[n]);
  const unchangedBusinessFunctions = Object.keys(before.functions).filter(n=>!['startBackend','stopBackend'].includes(n));
  reports.push({name,beforeSha256:before.sha256,currentSha256:after.sha256,
    originalTestCount:oldTests.length,currentTestCount:newTests.length,
    originalBusinessTests:oldTests,currentBusinessTests:newTests,
    businessTestBodiesExactlyUnchanged:JSON.stringify(oldTests)===JSON.stringify(newTests),
    unchangedBusinessFunctions:unchangedBusinessFunctions.map(n=>({name:n,exactlyUnchanged:before.functions[n]===after.functions[n]})),
    changedOriginalFunctions:changedFunctions,
    addedFunctions:Object.keys(after.functions).filter(n=>!before.functions[n]),
    importsExactlyUnchanged:JSON.stringify(before.imports)===JSON.stringify(after.imports),
    parseDiagnostics:after.parseDiagnostics});
  const lifecycle = {before:{startBackend:before.functions.startBackend,stopBackend:before.functions.stopBackend,hooks:before.hooks},
                     after:{startBackend:after.functions.startBackend,stopBackend:after.functions.stopBackend,hooks:after.hooks}};
  fs.writeFileSync(`${qa}/audit/${name}-lifecycle.json`,JSON.stringify(lifecycle,null,2));
}
fs.writeFileSync(`${qa}/audit/business-set-audit.json`,JSON.stringify(reports,null,2));
console.log(JSON.stringify(reports.map(r=>({...r,originalBusinessTests:undefined,currentBusinessTests:undefined})),null,2));
if (reports.some(r=>!r.businessTestBodiesExactlyUnchanged||r.unchangedBusinessFunctions.some(f=>!f.exactlyUnchanged)||!r.importsExactlyUnchanged||r.parseDiagnostics.length)) process.exitCode=1;
