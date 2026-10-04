import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { pathToFileURL } from 'node:url';
import crypto from 'node:crypto';
import ts from 'typescript';

const qa = path.resolve('docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002');
const read = name => JSON.parse(fs.readFileSync(path.join(qa, name), 'utf8').replace(/^\uFEFF/, ''));
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const candidate = read('CANDIDATE-g1-resume-r1.json');
const baseline = read('BASELINE.json');
const playwrightModule = import.meta.resolve('@playwright/test');

function configModule(filename, originalUrl) {
  let source = fs.readFileSync(filename, 'utf8');
  source = source.replace("'@playwright/test'", JSON.stringify(playwrightModule));
  if (originalUrl) {
    source = source.replace("'../../../playwright.config'", JSON.stringify(originalUrl));
    source = source.replaceAll('import.meta.url', JSON.stringify(pathToFileURL(filename).href));
  }
  const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
  return `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`;
}
const originalUrl = configModule(path.resolve('playwright.config.ts'));
const original = (await import(originalUrl)).default;
const external = (await import(configModule(path.join(qa, 'e2e.external.config.ts'), originalUrl))).default;
const permittedOverrides = new Set(['testDir', 'webServer', 'outputDir', 'reporter']);
const inheritedKeys = Object.keys(original).filter(key => !permittedOverrides.has(key));
for (const key of inheritedKeys) assert.deepEqual(external[key], original[key], `Inherited config changed: ${key}`);
for (const key of Object.keys(external)) assert(Object.hasOwn(original, key) || permittedOverrides.has(key), `Unregistered config key: ${key}`);
assert.equal(external.webServer, undefined);
assert.equal(external.testDir, path.resolve('tests/e2e'));
assert.equal(external.workers, 1);
assert.equal(external.fullyParallel, false);
assert.equal(external.timeout, 45000);
assert.equal(external.expect.timeout, 10000);
assert.equal(external.use.baseURL, 'http://127.0.0.1:5174');
assert.deepEqual(external.use.viewport, { width:1440, height:900 });
assert.equal(external.use.trace, 'retain-on-failure');
assert.equal(external.outputDir, path.join(qa, 'e2e-artifacts'));
assert.deepEqual(external.reporter, [['list'], ['json', {outputFile:path.join(qa,'full-e2e-results.json')}], ['junit', {outputFile:path.join(qa,'full-e2e-results.xml')}]]);

const specNames = ['assessments', 'question-bank-real'];
const unchangedTopLevel = [];
for (const name of specNames) {
  const beforePath = path.join(qa,'adapt-e2e',`${name}.before.ts`);
  const currentPath = path.resolve(`tests/e2e/${name}.spec.ts`);
  const before = ts.createSourceFile(beforePath, fs.readFileSync(beforePath,'utf8'),ts.ScriptTarget.Latest,true);
  const after = ts.createSourceFile(currentPath, fs.readFileSync(currentPath,'utf8'),ts.ScriptTarget.Latest,true);
  const stableStatements = tree => tree.statements.filter(node => !((ts.isInterfaceDeclaration(node) && node.name.text === 'Backend') || (ts.isFunctionDeclaration(node) && ['startBackend','stopBackend'].includes(node.name?.text)))).map(node => node.getText(tree));
  assert.deepEqual(stableStatements(after), stableStatements(before), `${name} changed a non-lifecycle top-level statement`);
  const fn = tree => tree.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'startBackend');
  const localDeclarations = tree => {
    const found = {};
    function visit(node) {
      if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) found[node.name.text] = node.getText(tree);
      ts.forEachChild(node, visit);
    }
    visit(fn(tree));
    return found;
  };
  const oldDeclarations = localDeclarations(before), newDeclarations = localDeclarations(after);
  const stableLocals = name === 'assessments' ? ['port','tmpRoot','dataDir','logFile','env','seedScript','seed','paper','logStream','child','origin'] : ['tmpRoot','dataDir','env','child','logStream'];
  for (const local of stableLocals) assert.equal(newDeclarations[local], oldDeclarations[local], `${name} changed startup business value ${local}`);
  unchangedTopLevel.push({spec:name, statements:stableStatements(after).length, startupBusinessLocals:stableLocals, result:'unchanged'});
}

const receipt = read('adapt-e2e/resource-receipts.json');
const command = read('adapt-e2e/resource-second-command.json');
const created = read('adapt-e2e/created-roots.json').roots;
const finalResources = read('adapt-e2e/resources-final.json');
const log = fs.readFileSync(path.join(qa,'adapt-e2e/resource-second.log'),'utf8').replace(/^\uFEFF/,'');
assert.equal(receipt.cases, 4); assert.equal(receipt.passed, 4); assert.equal(receipt.failed, 0);
assert.equal(command.exitCode, 0);
assert(receipt.elapsedMs > 0);
assert.equal(receipt.receipts.length, 4);
assert.equal(created.length, 4);
assert(log.includes(`RESULT 4 passed, 0 failed, ${receipt.elapsedMs}ms`));
const seen = new Set();
const retained = log.split(/\r?\n/).filter(line => line.startsWith('[ZQKY_TEST_DATA_RETAINED] ')).map(line => JSON.parse(line.slice('[ZQKY_TEST_DATA_RETAINED] '.length)));
assert.equal(retained.length, 2);
for (const source of receipt.source) {
  const file = `tests/e2e/${source.name}.spec.ts`;
  assert.equal(source.beforeSha256, baseline.sourceFiles[file]);
  assert.equal(source.afterSha256, candidate.files[file]);
  assert.equal(source.afterSha256, sha(fs.readFileSync(file)));
  assert.equal(source.businessCallbacksUnchanged, true);
  assert.equal(source.nonLifecycleFunctionsUnchanged, true);
}
for (const value of receipt.receipts) {
  const key = `${value.spec}:${value.mode}`;
  assert(!seen.has(key)); seen.add(key);
  assert(specNames.includes(value.spec)); assert(['keep','default'].includes(value.mode));
  assert.equal(value.childClosed,true); assert.equal(value.logClosed,true); assert.equal(value.logContainsStdoutAndStderrTail,true);
  assert.equal(value.result,'passed'); assert(value.elapsedMs > 0);
  const own = created.find(root => root.spec===value.spec && root.mode===value.mode);
  assert(own && own.createdByThisHarness);
  assert.equal(own.tmpRoot,value.tmpRoot);
  assert.equal(value.apiLog,path.join(value.tmpRoot,'api.log'));
  const relative = path.relative(path.resolve(os.tmpdir()),path.resolve(value.tmpRoot));
  assert(relative && !relative.startsWith('..') && !path.isAbsolute(relative));
  assert(path.basename(value.tmpRoot).startsWith(value.spec==='assessments'?'zqky-f20i-':'zqky-f10-real-'));
  const keep = value.mode==='keep';
  assert.equal(value.retained,keep); assert.equal(value.deletedOwnNewRoot,!keep);
  assert.deepEqual(value.order,keep?['child-close','log-close']:['child-close','log-close','rm-own-root']);
  assert(log.includes(`PASS ${value.spec} ${value.mode} ${value.elapsedMs}ms`));
  if (keep) {
    const record = retained.find(item => item.spec===value.spec);
    assert.deepEqual(record,{spec:value.spec,tmpRoot:value.tmpRoot,dataDir:own.dataDir,apiLog:value.apiLog,pid:value.pid,childClosed:true,logClosed:true});
  }
}
assert.deepEqual([...seen].sort(),['assessments:default','assessments:keep','question-bank-real:default','question-bank-real:keep']);
assert.deepEqual(finalResources.matchingOwnedChildren,[]);
for (const field of ['noApiImports','noNetworkListeners','ownedChildrenClosed','ownedLogStreamsClosed','oldDirectoriesUntouched','frontendUntouched']) assert.equal(receipt.resources[field],true);
const evidence = ['resource-harness.mjs','resource-first-source.mjs','resource-first.log','resource-first-command.json','resource-second.log','resource-second-command.json','resource-receipts.json','created-roots-first.json','created-roots.json','resources-final.json'];
const evidenceSha = Object.fromEntries(evidence.map(name=>[name,sha(fs.readFileSync(path.join(qa,'adapt-e2e',name)))]));
const report = {
  capturedAt:new Date().toISOString(),
  config:{inheritedKeys,webServerAbsent:true,testDir:external.testDir,workers:external.workers,fullyParallel:external.fullyParallel,timeout:external.timeout,expect:external.expect,use:external.use,reporter:external.reporter,permittedOverrides:[...permittedOverrides],actualTestCollectionRun:false},
  unchangedTopLevel,
  resourceEvidence:{recordsValidated:4,harnessReportedPassed:4,harnessElapsedMs:receipt.elapsedMs,actualHarnessRunByAuditor:false,sourceMatchesCandidate:true,firstFailurePreserved:true,finalOwnedChildReceiptEmpty:true,evidenceSha},
  limits:'Loads configuration only, no test callback or resource harness, service, browser or app execution. Validates receipts against frozen source and captured logs; does not substitute browser/full E2E gates.'
};
fs.writeFileSync(path.join(qa,'audit/config-resource-audit.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
