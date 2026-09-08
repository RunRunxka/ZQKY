import type { ModelTestResult } from '@/contracts/model-settings';

export function TestResult({
  test,
}: {
  test: { running: boolean; result?: ModelTestResult; stream: boolean };
}) {
  if (test.running)
    return (
      <p className="model-test-result" role="status">
        {test.stream ? '正在测试流式输出…' : '正在测试连接…'}
      </p>
    );
  const result = test.result;
  if (!result) return null;
  return (
    <p className={`model-test-result ${result.ok ? 'success' : 'error'}`} role="status">
      {result.ok
        ? `${test.stream ? '流式协议通过' : '连接成功'} · ${result.latencyMs} ms${result.stream ? ` · ${result.stream.chunks} 个文本分块 · 首段 ${result.stream.firstTextMs ?? '未知'} ms${result.stream.chunks < 2 ? '（仅收到单块，尚不能证明持续增量输出）' : ''}` : ''}`
        : `${result.error.message}（${result.error.code}）`}
    </p>
  );
}
