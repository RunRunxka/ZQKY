import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { InfoPanel } from './InfoPanel';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const selection = { gradeId: 'g1', subjectId: 's1', editionId: 'e1', documentIds: ['d1'] };

function ragStatusPayload(over: Record<string, unknown> = {}) {
  return {
    retrieval: {
      denseLimit: 50,
      lexicalLimit: 50,
      rrfK: 60,
      vectorStore: true,
      queryEmbedding: true,
      available: true,
      reason: null,
    },
    summarization: {
      available: true,
      reason: null,
      model: 'qwen2.5:7b',
      providerUrl: 'http://127.0.0.1:11434',
    },
    sourceAccess: { available: true, reason: null, verifiesHash: true },
    scope: { ready: true, reason: null, selection },
    generation: null,
    humanQuality: 'not_run',
    ...over,
  };
}

function capabilitiesPayload(rag: { status: string; detail: string }) {
  return {
    service: 'zhiqikeyuan-api',
    apiVersion: 'v1',
    generatedAt: '2026-09-28T00:00:00.000Z',
    capabilities: [
      { feature: 'model_settings', label: '模型设置', status: 'ready', detail: '已实现。' },
      { feature: 'rag', label: '教材检索（RAG）', status: rag.status, detail: rag.detail },
      { feature: 'mcp', label: 'MCP', status: 'planned', detail: '外部 MCP 连接管理未实现。' },
      { feature: 'skills', label: 'Skills', status: 'planned', detail: '技能定义与执行未实现。' },
    ],
  };
}

const RAG_UNAVAILABLE_DETAIL = '本地教材运行时状态由 /rag/status 检查；人工教学质量验收尚未完成。';

function installFetch(options: {
  caps?: () => Response | Promise<Response>;
  rag?: () => Response | Promise<Response>;
}) {
  const fetcher = vi.fn(async (url: string) => {
    if (String(url).includes('/capabilities'))
      return options.caps
        ? await options.caps()
        : Response.json(capabilitiesPayload({ status: 'ready', detail: RAG_UNAVAILABLE_DETAIL }));
    if (String(url).includes('/rag/status'))
      return options.rag ? await options.rag() : Response.json(ragStatusPayload());
    throw new Error(`不应调用 ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

function renderPanel() {
  return render(
    <InfoPanel profile={null} conversations={[]} activeId={null} messageCount={0} />,
  );
}

function ragRow(): HTMLElement {
  const row = document.querySelector('[data-capability="rag"]');
  if (!row) throw new Error('未渲染 RAG 能力行');
  return row as HTMLElement;
}

describe('对话能力边界（A1 r1 D6 修复）', () => {
  it('rag=unavailable 时显示真实原因，RAG 行不再出现「规划中」', async () => {
    installFetch({
      caps: () =>
        Response.json(
          capabilitiesPayload({ status: 'unavailable', detail: RAG_UNAVAILABLE_DETAIL }),
        ),
      rag: () =>
        Response.json(
          ragStatusPayload({
            retrieval: {
              denseLimit: 50,
              lexicalLimit: 50,
              rrfK: 60,
              vectorStore: true,
              queryEmbedding: true,
              available: false,
              reason: '当前没有已发布的教材索引代。',
            },
          }),
        ),
    });
    renderPanel();
    await waitFor(() =>
      expect(ragRow().querySelector('.chat-info-state')).toHaveTextContent('已实现 · 检索不可用'),
    );
    expect(ragRow()).toHaveTextContent('检索：不可用（当前没有已发布的教材索引代。）');
    expect(ragRow()).toHaveTextContent('人工教学质量：尚未验收');
    expect(ragRow()).not.toHaveTextContent('规划中');
    expect(ragRow()).not.toHaveTextContent('已实现 · 就绪');
  });

  it('rag=ready 但检索不可用（无索引代）时显示检索原因，不显示为可用', async () => {
    installFetch({
      caps: () =>
        Response.json(capabilitiesPayload({ status: 'ready', detail: RAG_UNAVAILABLE_DETAIL })),
      rag: () =>
        Response.json(
          ragStatusPayload({
            retrieval: {
              denseLimit: 50,
              lexicalLimit: 50,
              rrfK: 60,
              vectorStore: true,
              queryEmbedding: true,
              available: false,
              reason: '当前没有已发布的教材索引代。',
            },
            summarization: { available: false, reason: '本地概括未启动。', model: null, providerUrl: null },
          }),
        ),
    });
    renderPanel();
    await waitFor(() =>
      expect(ragRow().querySelector('.chat-info-state')).toHaveTextContent('已实现 · 检索不可用'),
    );
    expect(ragRow()).toHaveTextContent('检索：不可用（当前没有已发布的教材索引代。）');
    expect(ragRow()).toHaveTextContent('本地概括：不可用（本地概括未启动。）');
    expect(ragRow().querySelector('.chat-info-state')?.textContent).not.toBe('已实现 · 就绪');
  });

  it('真实就绪时显示分项可用，并始终保留「人工教学质量尚未验收」', async () => {
    installFetch({});
    renderPanel();
    await waitFor(() =>
      expect(ragRow().querySelector('.chat-info-state')).toHaveTextContent('已实现 · 就绪'),
    );
    expect(ragRow()).toHaveTextContent('检索：可用（向量 + 词法）');
    expect(ragRow()).toHaveTextContent('本地概括：可用（qwen2.5:7b）');
    expect(ragRow()).toHaveTextContent('原文访问：可用（核验规范化文本散列）');
    expect(ragRow()).toHaveTextContent('任教范围：已就绪');
    expect(ragRow()).toHaveTextContent('人工教学质量：尚未验收');
    expect(ragRow()).not.toHaveTextContent('规划中');
  });

  it('接口读取失败显示「状态未知 / 读取失败」，不出现「规划中」也不出现「可用」', async () => {
    const fetcher = installFetch({
      caps: () =>
        Response.json({ code: 'SERVICE_UNAVAILABLE', message: '状态读取失败' }, { status: 503 }),
      rag: () =>
        Response.json({ code: 'SERVICE_UNAVAILABLE', message: '状态读取失败' }, { status: 503 }),
    });
    renderPanel();
    await waitFor(() =>
      expect(ragRow().querySelector('.chat-info-state')).toHaveTextContent('状态未知'),
    );
    const panel = document.querySelector('.chat-info-inner') as HTMLElement;
    expect(panel).toHaveTextContent('读取失败');
    // 失败态不出现任何未实现的硬编码标签，也不出现任何可用性结论
    expect(panel).not.toHaveTextContent('规划中');
    expect(panel).not.toHaveTextContent('可用');
    expect(panel).not.toHaveTextContent('已实现');
    // 可重试：点击后重新读取两个接口
    const before = fetcher.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: '重新读取状态' }));
    await waitFor(() => expect(fetcher.mock.calls.length).toBeGreaterThan(before));
    expect(ragRow().querySelector('.chat-info-state')).toHaveTextContent('状态未知');
  });

  it('MCP / Skills 按能力清单状态显示；附件解析无接口可判定，标注「暂未接入」', async () => {
    installFetch({});
    renderPanel();
    await waitFor(() =>
      expect(document.querySelector('[data-capability="mcp"]')).not.toBeNull(),
    );
    const mcp = document.querySelector('[data-capability="mcp"]') as HTMLElement;
    const skills = document.querySelector('[data-capability="skills"]') as HTMLElement;
    const attachments = document.querySelector('[data-capability="attachments"]') as HTMLElement;
    expect(mcp.querySelector('.chat-info-state')).toHaveTextContent('未接入');
    expect(mcp).toHaveTextContent('外部 MCP 连接管理未实现。');
    expect(skills.querySelector('.chat-info-state')).toHaveTextContent('未接入');
    expect(attachments.querySelector('.chat-info-state')).toHaveTextContent('暂未接入');
    expect(attachments).not.toHaveTextContent('已实现');
  });
});
