import { request } from '@playwright/test';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
const [source, originalFailure, output] = process.argv.slice(2);
if (!source || !originalFailure || !output || existsSync(output)) throw new Error('Fresh seed output and preserved first failure required');
const raw = readFileSync(source), seed = JSON.parse(raw.toString('utf8')), failure = JSON.parse(readFileSync(originalFailure, 'utf8'));
if (seed.apiOrigin !== 'http://127.0.0.1:8001' || !seed.isolationDataRoot || failure.actualBusinessStatus !== 201 || !failure.actualBusinessResponse.id) throw new Error('Invalid committed isolated business seed');
const context = await request.newContext(), startedAt = new Date().toISOString(), started = performance.now();
try {
  const path = '/api/v1/classes/' + failure.actualBusinessResponse.id;
  const response = await context.get(seed.apiOrigin + path), result = await response.json();
  if (response.status() !== 200 || JSON.stringify(result) !== JSON.stringify(failure.actualBusinessResponse)) throw new Error('Created class readback drift');
  writeFileSync(output, JSON.stringify({ ...seed, classId: result.id, apiSeedBinding: { source, sha256: createHash('sha256').update(raw).digest('hex'), buildBindingState: 'old-build-at-runtime-seed-creation; ROOT must bind new stable candidate before browser' },
    seedCommand: { command: process.argv, pid: process.pid, startedAt, endedAt: new Date().toISOString(), durationMs: performance.now() - started, method: 'GET', businessPath: path, status: response.status(), result, firstFailedQaReceipt: originalFailure } }, null, 2) + '\n');
  process.stdout.write(JSON.stringify({ output, classId: result.id, status: response.status() }) + '\n');
} finally { await context.dispose(); }
