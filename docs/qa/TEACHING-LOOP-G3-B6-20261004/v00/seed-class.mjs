import { request } from '@playwright/test';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
const [source, output] = process.argv.slice(2);
if (!source || !output || existsSync(output)) throw new Error('Require ROOT runtime source and a fresh output path');
const raw = readFileSync(source), seed = JSON.parse(raw.toString('utf8'));
if (seed.schemaVersion !== 1 || seed.apiOrigin !== 'http://127.0.0.1:8001' || !seed.isolationDataRoot || !seed.classCode) throw new Error('Invalid isolated ROOT seed');
const context = await request.newContext(); const startedAt = new Date().toISOString(), started = performance.now();
try {
  const body = { code: seed.classCode, name: seed.className, schoolYear: '2026-2027', gradeId: 'senior-1' };
  const response = await context.post(seed.apiOrigin + '/api/v1/classes', { data: body });
  const result = await response.json(); if (response.status() !== 201 || !result.classId) throw new Error('Class creation failed: ' + JSON.stringify({ status: response.status(), result }));
  writeFileSync(output, JSON.stringify({ ...seed, classId: result.classId,
    apiSeedBinding: { source, sha256: createHash('sha256').update(raw).digest('hex'), buildBindingState: 'old-build-at-runtime-seed-creation; ROOT must bind new stable candidate before browser' },
    seedCommand: { command: process.argv, pid: process.pid, startedAt, endedAt: new Date().toISOString(), durationMs: performance.now() - started, method: 'POST', businessPath: '/api/v1/classes', body, status: response.status(), result } }, null, 2) + '\n');
  process.stdout.write(JSON.stringify({ output, classId: result.classId, status: response.status() }) + '\n');
} finally { await context.dispose(); }
