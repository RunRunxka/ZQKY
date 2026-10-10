import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from './api-client';
import { streamAgent } from './agent-stream';

function sseResponse(frames: string): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(frames));
      controller.close();
    },
  });
  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'content-type': 'text/event-stream' }),
    body: stream,
  } as unknown as Response;
}

function errorEnvelope(status: number, body: unknown): Response {
  return {
    ok: false,
    status,
    json: async () => body,
    headers: new Headers({ 'content-type': 'application/json' }),
  } as unknown as Response;
}

function stubFetch(impl: (url: string, init?: RequestInit) => Promise<Response>) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    impl(typeof input === 'string' ? input : input.toString(), init),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

const BASE_INPUT = {
  requestId: 'r1',
  threadId: 't1',
  message: '你好',
  modelProfileId: 'p1',
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('agent-stream', () => {
  it('按序分发 text/tool/wait-confirm/end 事件', async () => {
    const frames =
      'event: message.start\ndata: {"requestId":"r1","messageId":"r1","threadId":"t1","modelProfileId":"p1"}\n\n' +
      'event: text.delta\ndata: {"messageId":"r1","text":"你好"}\n\n' +
      'event: text.delta\ndata: {"messageId":"r1","text":"，老师"}\n\n' +
      'event: tool.call\ndata: {"messageId":"r1","name":"list_capabilities","args":{},"callId":"c1"}\n\n' +
      'event: tool.result\ndata: {"messageId":"r1","name":"list_capabilities","callId":"c1","output":"已装配"}\n\n' +
      'event: wait-confirm\ndata: {"requestId":"r1","messageId":"r1","confirmId":"k1","payload":{"action":"apply"}}\n\n' +
      'event: message.end\ndata: {"messageId":"r1","finishReason":"stop"}\n\n';
    stubFetch(async () => sseResponse(frames));

    const seen: string[] = [];
    const texts: string[] = [];
    let confirm: { confirmId: string } | null = null;
    await streamAgent(BASE_INPUT, {
      onStart: () => seen.push('start'),
      onText: (d) => texts.push(d),
      onToolCall: (c) => seen.push(`call:${c.name}`),
      onToolResult: (r) => seen.push(`result:${r.name}`),
      onWaitConfirm: (c) => {
        confirm = c;
        seen.push('wait-confirm');
      },
      onEnd: (r) => seen.push(`end:${r}`),
    });

    expect(texts.join('')).toBe('你好，老师');
    expect(seen).toEqual([
      'start',
      'call:list_capabilities',
      'result:list_capabilities',
      'wait-confirm',
      'end:stop',
    ]);
    expect(confirm).not.toBeNull();
    expect((confirm as { confirmId: string } | null)?.confirmId).toBe('k1');
  });

  it('流开始前模型缺失：抛 404 信封错误而不进入事件流', async () => {
    stubFetch(async () =>
      errorEnvelope(404, { code: 'MODEL_PROFILE_NOT_FOUND', message: '模型配置不存在。' }),
    );
    let started = false;
    const err = await streamAgent(BASE_INPUT, { onStart: () => (started = true) }).then(
      () => null,
      (e) => e as ApiError,
    );
    expect(err).not.toBeNull();
    expect(err).toBeInstanceOf(ApiError);
    expect(err?.code).toBe('MODEL_PROFILE_NOT_FOUND');
    expect(started).toBe(false);
  });

  it('error 事件后终止并不再分发后续帧', async () => {
    const frames =
      'event: message.start\ndata: {"requestId":"r1","messageId":"r1","threadId":"t1","modelProfileId":"p1"}\n\n' +
      'event: error\ndata: {"requestId":"r1","code":"UPSTREAM_ERROR","message":"上游异常","retryable":false}\n\n' +
      'event: text.delta\ndata: {"messageId":"r1","text":"不应到达"}\n\n';
    stubFetch(async () => sseResponse(frames));
    const texts: string[] = [];
    let errCode = '';
    await streamAgent(BASE_INPUT, {
      onText: (d) => texts.push(d),
      onError: (e) => (errCode = e.code),
    });
    expect(errCode).toBe('UPSTREAM_ERROR');
    expect(texts).toEqual([]);
  });

  it('未知事件被忽略（前向兼容）', async () => {
    const frames =
      'event: message.start\ndata: {"requestId":"r1","messageId":"r1","threadId":"t1","modelProfileId":"p1"}\n\n' +
      'event: future.event\ndata: {"x":1}\n\n' +
      'event: text.delta\ndata: {"messageId":"r1","text":"ok"}\n\n' +
      'event: message.end\ndata: {"messageId":"r1","finishReason":"stop"}\n\n';
    stubFetch(async () => sseResponse(frames));
    const texts: string[] = [];
    let ended = '';
    await streamAgent(BASE_INPUT, {
      onText: (d) => texts.push(d),
      onEnd: (r) => (ended = r),
    });
    expect(texts.join('')).toBe('ok');
    expect(ended).toBe('stop');
  });

  it('连接中断（无 terminal 事件）抛 STREAM_INTERRUPTED', async () => {
    const frames =
      'event: message.start\ndata: {"requestId":"r1","messageId":"r1","threadId":"t1","modelProfileId":"p1"}\n\n' +
      'event: text.delta\ndata: {"messageId":"r1","text":"半截"}\n\n';
    stubFetch(async () => sseResponse(frames));
    const err = await streamAgent(BASE_INPUT, {}).then(() => null, (e) => e as ApiError);
    expect(err?.code).toBe('STREAM_INTERRUPTED');
  });
});
