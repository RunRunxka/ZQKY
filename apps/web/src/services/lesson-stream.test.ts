/**
 * 教案生成流客户端：归档 SSE 事件协议（message.start / module.* / message.end / error）。
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { streamLessonModules, type LessonStreamHandlers } from './lesson-stream';
import { ApiError } from './api-client';

function sseResponse(chunks: string[], contentType = 'text/event-stream'): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return {
    ok: true,
    status: 200,
    body: stream,
    headers: new Headers({ 'content-type': contentType }),
    json: async () => ({}),
  } as unknown as Response;
}

function record(): { handlers: LessonStreamHandlers; log: string[] } {
  const log: string[] = [];
  return {
    log,
    handlers: {
      onStart: (info) => log.push(`start:${info.modules.join(',')}`),
      onModuleStart: (module, label) => log.push(`module-start:${module}:${label}`),
      onModuleDelta: (module, delta) => log.push(`delta:${module}:${delta}`),
      onModuleError: (module, message) => log.push(`module-error:${module}:${message}`),
      onModuleDone: (module) => log.push(`module-done:${module}`),
      onEnd: (reason) => log.push(`end:${reason}`),
      onError: (error) => log.push(`error:${error.code}`),
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('streamLessonModules', () => {
  it('按归档协议分发事件，并在 message.end 后结束', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        sseResponse([
          'event: message.start\ndata: {"requestId":"r1","modules":["analysis","reflection"]}\n\n',
          'event: module.start\ndata: {"module":"analysis","label":"教学分析"}\n\n',
          'event: module.delta\ndata: {"module":"analysis","text":"【学情分析】A"}\n\n',
          'event: module.delta\ndata: {"module":"analysis","text":"【教材分析】B"}\n\n',
          'event: module.done\ndata: {"module":"analysis"}\n\n',
          'event: module.error\ndata: {"module":"reflection","message":"模型未返回正文"}\n\n',
          'event: message.end\ndata: {"finishReason":"stop"}\n\n',
        ]),
      ),
    );
    vi.stubGlobal('fetch', fetchMock);
    const { handlers, log } = record();
    await streamLessonModules(
      { requestId: 'r1', modelProfileId: 'profile-1', courseName: '荷塘月色', modules: ['analysis', 'reflection'] },
      handlers,
    );
    expect(log).toEqual([
      'start:analysis,reflection',
      'module-start:analysis:教学分析',
      'delta:analysis:【学情分析】A',
      'delta:analysis:【教材分析】B',
      'module-done:analysis',
      'module-error:reflection:模型未返回正文',
      'end:stop',
    ]);
    const body = JSON.parse(String((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body));
    expect(body).toMatchObject({ requestId: 'r1', modelProfileId: 'profile-1', courseName: '荷塘月色' });
    expect(body.analysisRunId).toBeUndefined();
    expect(body.sourceAssetRef).toBeUndefined();
  });

  it('把可选来源与知识点带进请求体（上传学情文件为追加字段）', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(sseResponse(['event: message.end\ndata: {}\n\n'])));
    vi.stubGlobal('fetch', fetchMock);
    const { handlers } = record();
    await streamLessonModules(
      {
        requestId: 'r2',
        modelProfileId: 'p',
        courseName: '课',
        requirements: '突出对比',
        analysisRunId: 'run-1',
        sourceAssetRef: 'asset-1',
        selectedKnowledgePointIds: ['kp-1', 'kp-2'],
      },
      handlers,
    );
    const body = JSON.parse(String((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body));
    expect(body).toMatchObject({
      requirements: '突出对比',
      analysisRunId: 'run-1',
      sourceAssetRef: 'asset-1',
      selectedKnowledgePointIds: ['kp-1', 'kp-2'],
    });
  });

  it('流开始前失败按 HTTP 错误抛出（含 code/message）', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 503,
          json: async () => ({ code: 'SERVICE_UNAVAILABLE', message: '模型解析器未装配', retryable: true }),
          headers: new Headers({ 'content-type': 'application/json' }),
        } as unknown as Response),
      ),
    );
    await expect(
      streamLessonModules({ requestId: 'r', modelProfileId: 'p', courseName: 'c' }, record().handlers),
    ).rejects.toMatchObject({ code: 'SERVICE_UNAVAILABLE', status: 503, retryable: true });
  });

  it('非 SSE 响应视为失败（不当作正常流）', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(sseResponse(['{}'], 'application/json'))));
    await expect(
      streamLessonModules({ requestId: 'r', modelProfileId: 'p', courseName: 'c' }, record().handlers),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it('流中断（缺少 message.end）抛出 STREAM_INTERRUPTED，已收到的增量仍已分发', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(sseResponse(['event: module.delta\ndata: {"module":"analysis","text":"半段"}\n\n']))),
    );
    const { handlers, log } = record();
    await expect(
      streamLessonModules({ requestId: 'r', modelProfileId: 'p', courseName: 'c' }, handlers),
    ).rejects.toMatchObject({ code: 'STREAM_INTERRUPTED' });
    expect(log).toContain('delta:analysis:半段');
  });

  it('error 事件终结流并回调原因', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(sseResponse(['event: error\ndata: {"code":"UPSTREAM_ERROR","message":"上游断开","retryable":true}\n\n'])),
      ),
    );
    const { handlers, log } = record();
    await streamLessonModules({ requestId: 'r', modelProfileId: 'p', courseName: 'c' }, handlers);
    expect(log).toContain('error:UPSTREAM_ERROR');
  });
});
