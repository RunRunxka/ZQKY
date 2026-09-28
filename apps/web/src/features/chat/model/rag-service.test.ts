import { afterEach, describe, expect, it, vi } from 'vitest';
import { createRealChatService, type ChatServiceEvent } from './chat-service';
import { streamRag } from './rag-service';

const request = () => ({ sessionId: 's1', turnId: 't1', messages: [{ role: 'user' as const, content: '求函数定义域' }], signal: new AbortController().signal });
const frame = (id: number, name: string, body = {}) => `id: ${id}\nevent: ${name}\ndata: ${JSON.stringify({ sessionId: 's1', turnId: 't1', ...body })}\n\n`;
function serve(text: string) {
  const fetcher = vi.fn().mockResolvedValue(new Response(text, { headers: { 'content-type': 'text/event-stream' } }));
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}
afterEach(() => vi.unstubAllGlobals());

describe('真实本地教材通道', () => {
  it('RAG 与追问澄清走专用通道，不携带云模型/普通历史', async () => {
    const chat = vi.fn();
    const fetcher = serve(frame(1, 'message.start') + frame(2, 'text.delta', { text: '教材引用' }) + frame(3, 'message.end', { finishReason: 'stop' }));
    const events: ChatServiceEvent[] = [];
    await createRealChatService({ stream: chat }).run({ ...request(), modelProfileId: 'cloud-secret-profile', extensions: { mcps: [], skills: [], capability: { value: 'ask_questions', label: '追问澄清' } } }, (e) => events.push(e));
    expect(chat).not.toHaveBeenCalled();
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/rag/stream');
    const body = JSON.parse(fetcher.mock.calls[0][1].body);
    expect(body).toMatchObject({ question: '求函数定义域', sessionId: 's1', turnId: 't1' });
    expect(body.modelProfileId).toBeUndefined();
    expect(body.messages).toBeUndefined();
    expect(events.map((e) => [e.type, e.eventId])).toEqual([['turn-start', 1], ['text', 2], ['end', 3]]);
  });

  it('普通对话仍只调用既有聊天通道', async () => {
    const chat = vi.fn().mockResolvedValue(undefined);
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    await createRealChatService({ stream: chat }).run({ ...request(), modelProfileId: 'p1' }, vi.fn());
    expect(chat).toHaveBeenCalledOnce();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('同轮重连传持久化游标，重复片段不追加，等待与提交确认有序恢复', async () => {
    const card = { interactionId: 'i1', status: 'waiting', questions: [{ questionId: 'q1', prompt: '请补充条件', allowFreeText: true }] };
    const answers = [{ questionId: 'q1', labels: [], freeText: 'x>0' }];
    const fetcher = serve(frame(2, 'text.delta', { text: '旧文本' }) + frame(3, 'wait-user', { interaction: card }) + frame(4, 'reply.accepted', { interactionId: 'i1', submissionId: 'a1', answers }) + frame(5, 'message.end'));
    const events: ChatServiceEvent[] = [];
    await streamRag({ ...request(), rag: { sessionId: 's1', turnId: 't1', question: '原题', lastEventId: 2, status: 'interrupted' } }, (e) => events.push(e));
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toMatchObject({ question: '原题', afterEventId: 2 });
    expect(events.map((e) => e.type)).toEqual(['wait-user', 'reply-accepted', 'end']);
  });

  it('未收到明确结束事件的断流不能当作完成', async () => {
    serve(frame(1, 'message.start') + frame(2, 'text.delta', { text: '部分内容' }));
    const events: ChatServiceEvent[] = [];
    await expect(streamRag(request(), (e) => events.push(e))).rejects.toMatchObject({ code: 'RAG_DISCONNECTED' });
    expect(events.some((e) => e.type === 'end')).toBe(false);
  });

  it('游标缺口与串轮事件明确失败，不显示不完整或别轮结果', async () => {
    serve(frame(2, 'text.delta', { text: '缺首事件' }));
    await expect(streamRag(request(), vi.fn())).rejects.toMatchObject({ code: 'RAG_PROTOCOL_ERROR' });
    serve(frame(1, 'text.delta', { text: '另一轮', turnId: 'other' }));
    await expect(streamRag(request(), vi.fn())).rejects.toMatchObject({ code: 'RAG_PROTOCOL_ERROR' });
  });

  it('恢复过期显示后端原因，不重建原轮或请求普通聊天', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ code: 'RAG_TURN_EXPIRED', message: '本轮已过期，请重新提问。' }), { status: 410 }));
    vi.stubGlobal('fetch', fetcher);
    await expect(streamRag(request(), vi.fn())).rejects.toMatchObject({ code: 'RAG_TURN_EXPIRED', message: '本轮已过期，请重新提问。' });
    expect(fetcher).toHaveBeenCalledOnce();
  });
});
