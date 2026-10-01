/**
 * V00 · RV09/RV10 前端探针（自建；只读加载真实 TS 模块，仅替换 API 边界）。
 *
 * 覆盖：
 *   A. StrictMode（普通 + React.StrictMode 双 setup）下 adopt(终态) 生效、onTerminal 恰一次（RV09）；
 *   B. 真实 `observeJob` 的观察窗口：重试收据 N 接受 [N, N+1]，N+2 视为被接管返回 null；
 *      精确窗口（adopt）不接受更早/更晚 attempt（RV01 观察语义 + RV10）；
 *   C. 迟到 retry 响应：reset/adopt 新任务后不写状态、不污染（RV10）；
 *   D. 迟到 cancel 响应：同上；
 *   E. 迟到失败响应：不写 actionError；
 *   F. 观察代次：旧任务的 onUpdate 迟到到达不覆盖新任务；
 *   G. StrictMode 下观察更新仍生效。
 *
 * 运行（仓库根）：node --no-experimental-webstorage <abs>/p09_frontend_hooks.cjs
 * 退出码 0 = 全部断言通过；1 = 存在失败（`failures` 数组给出首败）。
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { Module, createRequire } = require('node:module');

const root = path.resolve(__dirname, '../../../..');
const rootRequire = createRequire(path.join(root, 'package.json'));
const { JSDOM } = require(rootRequire.resolve('jsdom'));
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost' });
global.window = dom.window;
global.document = dom.window.document;
Object.defineProperty(global, 'navigator', { value: dom.window.navigator, configurable: true });
global.HTMLElement = dom.window.HTMLElement;
global.DOMException = dom.window.DOMException;

const React = rootRequire('react');
const { render, fireEvent, act, cleanup, waitFor } = rootRequire('@testing-library/react');
const esbuild = rootRequire('esbuild');

const WEB_SRC = path.join(root, 'apps', 'web', 'src');
const CONTRACTS = path.join(WEB_SRC, 'contracts', 'teaching-loop.ts');
const JOBS_API = path.join(WEB_SRC, 'services', 'workflow-jobs-api.ts');
const HOOKS = path.join(WEB_SRC, 'features', 'knowledge-points', 'hooks.ts');

function compile(file) {
  return esbuild.transformSync(fs.readFileSync(file, 'utf8'), { loader: 'ts', format: 'cjs' }).code;
}

function loadModule(file, resolver) {
  const loaded = new Module(file, module);
  loaded.filename = file;
  loaded.paths = Module._nodeModulePaths(root);
  loaded.require = resolver;
  loaded._compile(compile(file), file);
  return loaded.exports;
}

class ApiError extends Error {
  constructor(code, message, status = 0, retryable = false) {
    super(message);
    this.code = code;
    this.status = status;
    this.retryable = retryable;
  }
}

const contracts = loadModule(CONTRACTS, (id) => rootRequire(id));

function makeJobView(overrides) {
  return {
    jobId: 'job-1',
    domain: 'knowledge',
    kind: 'suggestion',
    attempt: 1,
    state: 'queued',
    result: null,
    error: null,
    ...overrides,
  };
}

const results = { failures: [] };
function check(name, condition, detail) {
  results[name] = { ok: Boolean(condition), detail };
  if (!condition) results.failures.push(`${name}: ${JSON.stringify(detail)}`);
}

async function checkObserveWindow() {
  // 真实 workflow-jobs-api 的 observeJob + 受控 apiRequest
  const responses = [];
  const requests = [];
  const apiClient = {
    apiRequest: async (url, options) => {
      requests.push(url);
      if (!responses.length) throw new Error('no scripted response left');
      const next = responses.shift();
      if (next instanceof Error) throw next;
      return next;
    },
  };
  const jobsApi = loadModule(JOBS_API, (id) => {
    if (id === '@/services/api-client') return apiClient;
    if (id === '@/contracts/teaching-loop') return contracts;
    return rootRequire(id);
  });
  const sleep = async () => {};

  // 重试窗口 [N, N+1]：N(queued) → N+1(succeeded) 接受；N+2 拒绝
  responses.push(makeJobView({ attempt: 2, state: 'queued' }));
  responses.push(makeJobView({ attempt: 3, state: 'succeeded' }));
  const updates = [];
  const accepted = await jobsApi.observeJob('knowledge', 'job-1', {
    ...jobsApi.retryObservationWindow({ attempt: 2 }),
    onUpdate: (view) => updates.push(view.attempt),
    sleep,
  });
  check('window_accept_N_and_N1', accepted && accepted.attempt === 3 && updates.join(',') === '2,3', {
    accepted: accepted && accepted.attempt, updates,
  });

  responses.push(makeJobView({ attempt: 5, state: 'succeeded' }));
  const rejected = await jobsApi.observeJob('knowledge', 'job-1', {
    ...jobsApi.retryObservationWindow({ attempt: 2 }),
    sleep,
  });
  check('window_reject_N2', rejected === null, { rejected });

  responses.push(makeJobView({ attempt: 1, state: 'succeeded' }));
  const older = await jobsApi.observeJob('knowledge', 'job-1', {
    ...jobsApi.retryObservationWindow({ attempt: 2 }),
    sleep,
  });
  check('window_reject_older', older === null, { older });

  responses.push(makeJobView({ attempt: 1, state: 'succeeded' }));
  const exactRejected = await jobsApi.observeJob('knowledge', 'job-1', {
    expectedAttempt: 2,
    sleep,
  });
  check('window_exact_rejects_other_attempt', exactRejected === null, { exactRejected });

  // 终态返回：观察在终态停止（不再发请求）
  responses.push(makeJobView({ attempt: 4, state: 'failed' }));
  const before = requests.length;
  const terminal = await jobsApi.observeJob('knowledge', 'job-1', {
    minAttempt: 4, maxAttempt: 4, sleep,
  });
  check('terminal_stops_observation', terminal.state === 'failed' && requests.length === before + 1, {
    state: terminal.state, requestsDelta: requests.length - before,
  });

  // Abort：返回 null
  const controller = new AbortController();
  controller.abort();
  const aborted = await jobsApi.observeJob('knowledge', 'job-1', { signal: controller.signal, sleep });
  check('abort_returns_null', aborted === null, { aborted });
}

function loadHook(apiBoundary) {
  return loadModule(HOOKS, (id) => {
    if (id === '@/services/api-client') return { ApiError };
    if (id === '@/contracts/teaching-loop') return contracts;
    if (id === '@/services/workflow-jobs-api') return apiBoundary;
    return rootRequire(id);
  }).useKnowledgeJob;
}

function deferred() {
  let resolve; let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

async function checkStrictMode() {
  const useKnowledgeJob = loadHook({
    observeJob: () => new Promise(() => {}),
    retryJob: async () => makeJobView({ state: 'succeeded' }),
    cancelJob: async () => makeJobView({ state: 'succeeded' }),
    retryObservationWindow: (view) => ({ minAttempt: view.attempt, maxAttempt: view.attempt + 1 }),
  });
  for (const strict of [false, true]) {
    let terminalCalls = 0;
    function Harness() {
      const job = useKnowledgeJob({ onTerminal: () => { terminalCalls += 1; } });
      return React.createElement(
        'button',
        { onClick: () => job.adopt(makeJobView({ state: 'succeeded', attempt: 1 })) },
        job.view ? `${job.view.state}:${job.view.attempt}` : 'null',
      );
    }
    const element = strict
      ? React.createElement(React.StrictMode, null, React.createElement(Harness))
      : React.createElement(Harness);
    const ui = render(element);
    await act(async () => { fireEvent.click(ui.getByRole('button')); });
    const label = ui.getByRole('button').textContent;
    check(`strictmode_${strict ? 'on' : 'off'}`, label === 'succeeded:1' && terminalCalls === 1, {
      label, terminalCalls,
    });
    cleanup();
  }
}

async function checkLateRetryAndCancel() {
  const retryDeferred = deferred();
  const cancelDeferred = deferred();
  const useKnowledgeJob = loadHook({
    observeJob: () => new Promise(() => {}),
    retryJob: () => retryDeferred.promise,
    cancelJob: () => cancelDeferred.promise,
    retryObservationWindow: (view) => ({ minAttempt: view.attempt, maxAttempt: view.attempt + 1 }),
  });
  const terminals = [];
  let controller = null;
  function Harness() {
    controller = useKnowledgeJob({ onTerminal: (view) => terminals.push(view.jobId) });
    return React.createElement(
      'div',
      null,
      React.createElement('button', {
        'data-testid': 'adopt-a',
        onClick: () => controller.adopt(makeJobView({ jobId: 'A', state: 'failed', attempt: 1 })),
      }, 'adoptA'),
      React.createElement('button', {
        'data-testid': 'retry',
        onClick: () => controller.retry(),
      }, 'retry'),
      React.createElement('button', {
        'data-testid': 'reset',
        onClick: () => controller.reset(),
      }, 'reset'),
      React.createElement('button', {
        'data-testid': 'adopt-b',
        onClick: () => controller.adopt(makeJobView({ jobId: 'B', state: 'succeeded', attempt: 3 })),
      }, 'adoptB'),
      React.createElement('button', {
        'data-testid': 'cancel',
        onClick: () => controller.cancel(),
      }, 'cancel'),
      React.createElement('span', { 'data-testid': 'state' },
        controller.view ? `${controller.view.jobId}:${controller.view.state}:${controller.view.attempt}` : 'null'),
      React.createElement('span', { 'data-testid': 'pending' },
        controller.pending || 'none'),
    );
  }
  const ui = render(React.createElement(Harness));
  const click = async (testId) => { await act(async () => { fireEvent.click(ui.getByTestId(testId)); }); };

  // 迟到 retry：A 在途 → reset → 接管 B → 释放 A 响应
  await click('adopt-a');
  await click('retry');
  const pendingDuringRetry = ui.getByTestId('pending').textContent;
  await click('reset');
  const pendingAfterReset = ui.getByTestId('pending').textContent;
  await click('adopt-b');
  const stateAfterAdoptB = ui.getByTestId('state').textContent;
  await act(async () => {
    retryDeferred.resolve(makeJobView({ jobId: 'A', state: 'succeeded', attempt: 2 }));
    await Promise.resolve();
  });
  const stateAfterLateRetry = ui.getByTestId('state').textContent;
  check('late_retry_response_ignored', stateAfterLateRetry === stateAfterAdoptB && stateAfterAdoptB === 'B:succeeded:3', {
    pendingDuringRetry, pendingAfterReset, stateAfterAdoptB, stateAfterLateRetry,
  });

  // 迟到 cancel：A 在途 → reset → 接管 B → 释放 A 响应
  await click('reset');
  await click('adopt-a');
  await click('cancel');
  await click('reset');
  await click('adopt-b');
  const beforeLateCancel = ui.getByTestId('state').textContent;
  await act(async () => {
    cancelDeferred.resolve(makeJobView({ jobId: 'A', state: 'cancelled', attempt: 2 }));
    await Promise.resolve();
  });
  const afterLateCancel = ui.getByTestId('state').textContent;
  check('late_cancel_response_ignored', afterLateCancel === beforeLateCancel && afterLateCancel === 'B:succeeded:3', {
    beforeLateCancel, afterLateCancel,
  });

  cleanup();  // 先卸载上一棵组件树，避免重复 testid

  // 迟到失败：不写 actionError、不污染视图
  const failing = deferred();
  const useFailing = loadHook({
    observeJob: () => new Promise(() => {}),
    retryJob: () => failing.promise,
    cancelJob: () => new Promise(() => {}),
    retryObservationWindow: (view) => ({ minAttempt: view.attempt, maxAttempt: view.attempt + 1 }),
  });
  let c2 = null;
  function Harness2() {
    c2 = useFailing();
    return React.createElement(
      'div',
      null,
      React.createElement('button', { 'data-testid': 'adopt-a', onClick: () => c2.adopt(makeJobView({ jobId: 'A', state: 'failed', attempt: 1 })) }, 'a'),
      React.createElement('button', { 'data-testid': 'retry', onClick: () => c2.retry() }, 'r'),
      React.createElement('button', { 'data-testid': 'reset', onClick: () => c2.reset() }, 'x'),
      React.createElement('button', { 'data-testid': 'adopt-b', onClick: () => c2.adopt(makeJobView({ jobId: 'B', state: 'succeeded', attempt: 1 })) }, 'b'),
      React.createElement('span', { 'data-testid': 'state' }, c2.view ? `${c2.view.jobId}:${c2.view.state}` : 'null'),
      React.createElement('span', { 'data-testid': 'err' }, c2.actionError ? c2.actionError.code : 'none'),
    );
  }
  const ui2 = render(React.createElement(Harness2));
  await act(async () => { fireEvent.click(ui2.getByTestId('adopt-a')); });
  await act(async () => { fireEvent.click(ui2.getByTestId('retry')); });
  await act(async () => { fireEvent.click(ui2.getByTestId('reset')); });
  await act(async () => { fireEvent.click(ui2.getByTestId('adopt-b')); });
  await act(async () => { failing.reject(new Error('late failure')); await Promise.resolve(); });
  check('late_failure_ignored', ui2.getByTestId('state').textContent === 'B:succeeded'
    && ui2.getByTestId('err').textContent === 'none', {
    state: ui2.getByTestId('state').textContent, error: ui2.getByTestId('err').textContent,
  });
  cleanup();
}

async function checkObservationEpoch() {
  // 旧任务的观察回调迟到：不覆盖新任务
  const observers = [];
  const useKnowledgeJob = loadHook({
    observeJob: (domain, jobId, options) => {
      const record = { jobId, options };
      observers.push(record);
      return new Promise((resolve) => { record.resolve = resolve; });
    },
    retryJob: async () => makeJobView({ state: 'succeeded' }),
    cancelJob: async () => makeJobView({ state: 'succeeded' }),
    retryObservationWindow: (view) => ({ minAttempt: view.attempt, maxAttempt: view.attempt + 1 }),
  });
  let c = null;
  const terminals = [];
  function Harness() {
    c = useKnowledgeJob({ onTerminal: (view) => terminals.push(view.jobId) });
    return React.createElement(
      'div',
      null,
      React.createElement('button', { 'data-testid': 'adopt-a', onClick: () => c.adopt(makeJobView({ jobId: 'A', state: 'running', attempt: 1 })) }, 'a'),
      React.createElement('button', { 'data-testid': 'adopt-b', onClick: () => c.adopt(makeJobView({ jobId: 'B', state: 'running', attempt: 5 })) }, 'b'),
      React.createElement('span', { 'data-testid': 'state' }, c.view ? `${c.view.jobId}:${c.view.attempt}` : 'null'),
    );
  }
  const ui = render(React.createElement(Harness));
  await act(async () => { fireEvent.click(ui.getByTestId('adopt-a')); });
  await act(async () => { fireEvent.click(ui.getByTestId('adopt-b')); });
  const firstObserver = observers[0];
  await act(async () => {
    firstObserver.options.onUpdate(makeJobView({ jobId: 'A', state: 'interrupted', attempt: 1 }));
    await Promise.resolve();
  });
  check('observation_epoch_guards_stale_update',
    ui.getByTestId('state').textContent === 'B:5' && terminals.length === 0, {
      state: ui.getByTestId('state').textContent, terminals,
    });
  cleanup();
}

async function main() {
  await checkObserveWindow();
  await checkStrictMode();
  await checkLateRetryAndCancel();
  await checkObservationEpoch();
  results.verdict = results.failures.length ? 'fail' : 'pass';
  const out = path.join(__dirname, 'p09_frontend_hooks.json');
  fs.writeFileSync(out, JSON.stringify(results, null, 2) + '\n', 'utf8');
  console.log(JSON.stringify({ verdict: results.verdict, failures: results.failures }, null, 2));
  for (const [key, value] of Object.entries(results)) {
    if (key === 'failures' || key === 'verdict') continue;
    console.log(key, JSON.stringify(value.detail));
  }
  process.exit(results.failures.length ? 1 : 0);
}

main().catch((error) => {
  console.error(error);
  process.exit(2);
});
