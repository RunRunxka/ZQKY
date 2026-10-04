import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const qa = path.resolve('docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const result = fs.readFileSync(path.join(qa,'adapt-e2e/RESULT.md'),'utf8');
assert(!result.includes('](lint-first.log)'));
assert(!result.includes('](typecheck-first.log)'));
const records = [];
for (const name of ['lint','typecheck']) {
  const receiptPath = path.join(qa,`adapt-e2e/${name}-receipt-r2.json`);
  const receipt = JSON.parse(fs.readFileSync(receiptPath,'utf8').replace(/^\uFEFF/,''));
  const first = JSON.parse(fs.readFileSync(path.join(qa,`adapt-e2e/${name}-first-command.json`),'utf8').replace(/^\uFEFF/,''));
  assert.equal(receipt.command,first.command);
  assert.equal(receipt.exitCode,0);
  assert(receipt.elapsedMs > 0);
  assert.equal(receipt.stdout,''); assert.equal(receipt.stderr,'');
  assert.equal(receipt.stdoutBytes,0); assert.equal(receipt.stderrBytes,0);
  const files = [receipt.stdoutFile,receipt.stderrFile,receipt.logFile];
  for (const file of files) {
    const relative = path.relative(path.join(qa,'adapt-e2e'),file);
    assert(relative && !relative.startsWith('..') && !path.isAbsolute(relative));
    assert(fs.existsSync(file));
  }
  assert.equal(fs.statSync(receipt.stdoutFile).size,0);
  assert.equal(fs.statSync(receipt.stderrFile).size,0);
  records.push({name,command:receipt.command,exitCode:receipt.exitCode,elapsedMs:receipt.elapsedMs,stdoutBytes:0,stderrBytes:0,receiptSHA256:hash(fs.readFileSync(receiptPath)),files:files.map(file=>({file,size:fs.statSync(file).size,sha256:hash(fs.readFileSync(file))}))});
}
const report = {capturedAt:new Date().toISOString(),recordsValidated:2,issue:'Initial RESULT linked nonexistent first lint/typecheck logs and first receipts omitted duration/streams',resolution:'Original missing evidence now explicitly recorded; real repeated targeted commands have physical receipts and captured zero-byte output files. No first-run logs or times were fabricated.',records};
fs.writeFileSync(path.join(qa,'audit/receipt-supplement-audit.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
