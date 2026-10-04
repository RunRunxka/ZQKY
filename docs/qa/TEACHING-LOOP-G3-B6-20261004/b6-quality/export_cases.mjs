// Executes the existing production exporter and template, without another renderer.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const own = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(own, '../../../..');
const require = createRequire(path.join(root, 'package.json'));
const esbuild = require('esbuild');
const label = process.argv[2];
if (!label || !/^[a-z0-9-]+$/.test(label)) throw Error('Explicit immutable input label required');
const input = path.join(own, 'runs', label);
const output = path.join(own, 'exports', label);
if (fs.existsSync(output)) throw Error('Do not overwrite previous DOCX evidence');
fs.mkdirSync(output, { recursive: true });
const bundle = path.join(process.env.ZQKY_DATA_DIR, '..', 'existing-lesson-exporter.cjs');
// Bundle exact repository implementation, not a copied flattening algorithm.
esbuild.buildSync({ entryPoints: [path.join(root, 'apps/web/src/features/lesson-plan/services/export.ts')],
  bundle: true, platform: 'node', format: 'cjs', outfile: bundle, logLevel: 'warning' });
const { buildDocx } = require(bundle);
const templatePath = path.join(root, 'apps/web/public/templates/lesson-plan-template.docx');
const template = fs.readFileSync(templatePath);
const originalFetch = globalThis.fetch;
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
globalThis.fetch = async url => {
  if (url !== '/templates/lesson-plan-template.docx') throw Error('Exporter network is not authorized');
  return new Response(template, { status: 200 });
};
const records = [];
try {
  const summary = JSON.parse(fs.readFileSync(path.join(input, 'SUMMARY.json'), 'utf8'));
  for (const entry of summary.results) {
    const sourceFile = path.join(input, 'quality-cases', entry.caseId, 'fixed-export-input.json');
    const sourceBytes = fs.readFileSync(sourceFile);
    const fixed = JSON.parse(sourceBytes.toString('utf8'));
    const blob = await buildDocx(fixed.data);
    const bytes = Buffer.from(await blob.arrayBuffer());
    const file = path.join(output, entry.caseId + '.docx');
    fs.writeFileSync(file, bytes, { flag: 'wx' });
    records.push({ caseId: entry.caseId, file, fileSHA: sha(bytes), byteSize: bytes.length,
      fixedExportInputSHA: sha(sourceBytes), revisionId: fixed.revisionId, sourceLabel: fixed.sourceLabel,
      templateSHA: sha(template), exporterSourceSHA: sha(fs.readFileSync(path.join(root, 'apps/web/src/features/lesson-plan/services/export.ts'))),
      renderedStatus: 'not_run_structure_only', teacherReview: 'teacher_review_pending' });
  }
  fs.writeFileSync(path.join(output, 'DOCX-MANIFEST.json'), JSON.stringify({ task: 'B6-QUALITY-v1',
    pid: process.pid, nodeVersion: process.version, caseCount: records.length, templatePath, templateSHA: sha(template),
    existingExporter: 'apps/web/src/features/lesson-plan/services/export.ts#buildDocx', records,
    layoutAcceptance: 'not_run; separate exports lane owns actual PDF/layout samples' }, null, 2) + '\n', { flag: 'wx' });
  if (records.length !== 15) throw Error('Expected 15 current fixed lesson DOCX artifacts');
  console.log(JSON.stringify({ caseCount: records.length, existingExporter: true, layoutAcceptance: 'not_run' }));
} finally { globalThis.fetch = originalFetch; }
