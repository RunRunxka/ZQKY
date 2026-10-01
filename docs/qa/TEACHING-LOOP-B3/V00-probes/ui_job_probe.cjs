/**
 * Read-only diagnostics for B2 knowledge task hooks.
 * From repository root:
 *   node --no-experimental-webstorage docs/qa/TEACHING-LOOP-B2-REVIEW-20261001/probes/ui_job_probe.cjs
 * Exit 0 means the diagnostic ran; inspect bugReproduced, not exit status, for defects.
 * Loads the actual hooks.ts through the installed esbuild. Only API boundaries are mocked.
 * Does not modify product files, start services, or call real models.
 */
const fs = require('node:fs');
const path = require('node:path');
const { Module, createRequire } = require('node:module');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '../../../..');
const rootRequire = createRequire(path.join(root, 'package.json'));
const { JSDOM } = rootRequire('jsdom');
const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: 'http://localhost',
});
global.window = dom.window;
global.document = dom.window.document;
Object.defineProperty(global, 'navigator', {
  value: dom.window.navigator,
  configurable: true,
});
const React = rootRequire('react');
const { render, fireEvent, act, cleanup } = rootRequire('@testing-library/react');
const hookPath = path.join(root, 'apps/web/src/features/knowledge-points/hooks.ts');

function loadActualHook(api) {
  const compiled = rootRequire('esbuild').transformSync(fs.readFileSync(hookPath, 'utf8'), {
    loader: 'ts',
    format: 'cjs',
  }).code;
  const loaded = new Module(hookPath, module);
  loaded.filename = hookPath;
  loaded.paths = Module._nodeModulePaths(root);
  loaded.require = (id) => {
    if (id === '@/services/api-client') return { ApiError: class ApiError extends Error {} };
    if (id === '@/contracts/teaching-loop') {
      return {
        isJobTerminal: (state) => ['succeeded', 'failed', 'cancelled', 'interrupted'].includes(state),
      };
    }
    if (id === '@/services/workflow-jobs-api') return api;
    return rootRequire(id);
  };
  loaded._compile(compiled, hookPath);
  return loaded.exports.useKnowledgeJob;
}

async function main() {
  const useKnowledgeJob = loadActualHook({
    observeJob: async () => null,
    retryJob: async () => undefined,
    cancelJob: async () => undefined,
  });
  const strictResults = [];
  let terminalCalls = 0;
  function StrictHarness() {
    const job = useKnowledgeJob({ onTerminal: () => { terminalCalls += 1; } });
    return React.createElement('button', {
      onClick: () => job.adopt({ jobId: 'strict-probe', attempt: 1, state: 'succeeded' }),
    }, job.view?.state ?? 'null');
  }
  for (const strict of [false, true]) {
    terminalCalls = 0;
    const component = React.createElement(StrictHarness);
    const ui = render(strict ? React.createElement(React.StrictMode, null, component) : component);
    fireEvent.click(ui.getByRole('button'));
    strictResults.push({ strict, view: ui.getByRole('button').textContent, terminalCalls });
    cleanup();
  }
  assert.equal(strictResults[0].view, 'succeeded', 'ordinary-mode control must work');
  assert.equal(strictResults[0].terminalCalls, 1, 'ordinary-mode terminal callback control');

  let releaseRetry;
  const useRaceJob = loadActualHook({
    observeJob: () => new Promise(() => {}),
    retryJob: () => new Promise((resolve) => { releaseRetry = resolve; }),
    cancelJob: async () => undefined,
  });
  let controller;
  function RaceHarness() {
    controller = useRaceJob();
    return React.createElement('div', null, controller.view?.jobId ?? 'null');
  }
  const ui = render(React.createElement(RaceHarness));
  await act(async () => controller.adopt({ jobId: 'old-A', attempt: 1, state: 'failed' }));
  await act(async () => controller.retry());
  assert.equal(typeof releaseRetry, 'function', 'retry request must be in flight');
  await act(async () => {
    controller.reset();
    controller.adopt({ jobId: 'new-B', attempt: 1, state: 'queued' });
  });
  const beforeLateRetry = ui.container.textContent;
  assert.equal(beforeLateRetry, 'new-B', 'new task must be active before late response');
  await act(async () => releaseRetry({ jobId: 'old-A', attempt: 2, state: 'queued' }));
  const afterLateRetry = ui.container.textContent;
  cleanup();
  dom.window.close();

  console.log(JSON.stringify({
    probe: 'B2 UI task hook review',
    source: path.relative(root, hookPath).replaceAll('\\', '/'),
    strictMode: {
      actual: strictResults,
      expected: { strict: true, view: 'succeeded', terminalCalls: 1 },
      bugReproduced: strictResults[1].view !== 'succeeded' || strictResults[1].terminalCalls !== 1,
    },
    lateRetry: {
      beforeLateRetry,
      afterLateRetry,
      expectedAfterLateRetry: 'new-B',
      bugReproduced: afterLateRetry !== 'new-B',
    },
    executionSucceeded: true,
  }, null, 2));
}

main().catch((error) => {
  cleanup();
  dom.window.close();
  console.error(error);
  process.exitCode = 1;
});
