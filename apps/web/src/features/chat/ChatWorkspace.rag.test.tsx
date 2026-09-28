import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ChatWorkspace } from './ChatWorkspace';
import { NavigationPreference } from '@/components/layout/NavigationPreference';

vi.mock('@/features/chat/vendor/thinking-orbs', () => ({ ThinkingOrb: () => null }));
vi.mock('next/navigation', () => ({ usePathname: () => '/chat', useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@/features/model-settings/useModelCatalog', () => ({ useModelCatalog: () => ({ catalog: null, loading: false, error: '没有云模型配置', refresh: vi.fn() }) }));
vi.mock('@/services/chat-repository', async (original) => {
  const actual = await original<typeof import('@/services/chat-repository')>();
  return { ...actual, createIdbChatRepository: () => actual.createMemoryChatRepository() };
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

async function openRag() {
  window.matchMedia = vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() });
  render(<NavigationPreference><ChatWorkspace /></NavigationPreference>);
  fireEvent.click(screen.getByRole('button', { name: /^选择业务能力，当前：/ }));
  fireEvent.click(screen.getByRole('button', { name: /^RAG 模式/ }));
  const input = screen.getByRole('textbox', { name: '输入问题' });
  await waitFor(() => expect(input).not.toBeDisabled());
  return input;
}

describe('教材入口与真实追问界面', () => {
  it('无云模型仍能发起教材请求、填写真实卡片并在同轮看到续答', async () => {
    let sink!: ReadableStreamDefaultController<Uint8Array>;
    let turn: { sessionId: string; turnId: string };
    let seq = 0;
    const push = (name: string, payload: object = {}) => sink.enqueue(new TextEncoder().encode(`id: ${++seq}\nevent: ${name}\ndata: ${JSON.stringify({ ...turn, ...payload })}\n\n`));
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === '/api/v1/rag/status') return Response.json({ available: true, detail: '本地就绪' });
      if (url === '/api/v1/rag/stream') {
        turn = JSON.parse(String(init?.body));
        const body = new ReadableStream<Uint8Array>({ start(controller) { sink = controller; } });
        push('message.start');
        push('text.delta', { text: '已核验教材原文与行号。' });
        push('wait-user', { interaction: { interactionId: 'i1', status: 'waiting', questions: [{ questionId: 'q1', prompt: '补充题目条件', allowFreeText: true }] } });
        return new Response(body, { headers: { 'content-type': 'text/event-stream' } });
      }
      if (url === '/api/v1/rag/reply') {
        const reply = JSON.parse(String(init?.body));
        push('reply.accepted', { interactionId: reply.interactionId, submissionId: reply.submissionId, answers: reply.answers });
        push('text.delta', { text: '这是补充条件后的教材续答。' });
        push('message.end', { finishReason: 'stop' }); sink.close();
        return Response.json({ accepted: true });
      }
      throw new Error(`不应调用 ${url}`);
    });
    vi.stubGlobal('fetch', fetcher);
    const input = await openRag();
    fireEvent.change(input, { target: { value: '求函数定义域' } });
    expect(screen.getByRole('button', { name: '发送' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
    await screen.findByText('教材追问');
    expect(screen.queryByText('追问（本地模拟）')).not.toBeInTheDocument();
    expect(screen.queryByText(/无法读取模型配置/)).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole('textbox', { name: '补充题目条件（自由输入）' }), { target: { value: 'x 大于零' } });
    fireEvent.click(screen.getByRole('button', { name: '提交' }));
    await screen.findByText('这是补充条件后的教材续答。');
    expect(screen.getByText(/教材追问.*已回答/)).toBeInTheDocument();
    expect(fetcher.mock.calls.filter(([url]) => url === '/api/v1/rag/stream')).toHaveLength(1);
    expect(fetcher.mock.calls.some(([url]) => url === '/api/v1/chat/stream')).toBe(false);
  });

  it('教材服务不可用显示真实原因并保留输入，不切换普通聊天', async () => {
    const fetcher = vi.fn(async (url: string) => { expect(url).toBe('/api/v1/rag/status'); return Response.json({ available: false, detail: '本地模型未启动' }); });
    vi.stubGlobal('fetch', fetcher);
    const input = await openRag();
    fireEvent.change(input, { target: { value: '需要保留的题目' } });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));
    await screen.findByText(/本地模型未启动.*输入已保留/);
    expect(input).toHaveValue('需要保留的题目');
    expect(fetcher.mock.calls.every(([url]) => url === '/api/v1/rag/status')).toBe(true);
  });
});
