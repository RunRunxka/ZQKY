import { cleanup, render } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { Message } from '@/features/chat/Message';
import { createChatStore } from './model/store';
import { createMemoryChatRepository } from '@/services/chat-repository';

/**
 * R25 轮级耗时终态回归（自 _work/review-s2-s3-20260908/timing.test.tsx 迁入正式回归）：
 * - 正文/推理出现后耗时仍可见且只渲染一处（原缺陷：正文开始后耗时从状态行消失）；
 * - 全部结束路径（end/error/停止/断流/异常兜底）写入 finishedAt，终态不再计时
 *   （原缺陷：服务 Promise 抛错后 finishedAt 缺失，标题区继续计时）；
 * - 刷新恢复路径：中断轮次以会话最后保存时间冻结耗时，旧历史缺失 finishedAt 时补齐，
 *   不把离线经过时间当推理耗时，多次载入冻结值稳定（复核报告要求的独立回归）。
 */
afterEach(cleanup);

it('R25 正文流式阶段耗时保持可见且只渲染一处', () => {
  const { container } = render(
    <Message
      message={{
        id: 'a',
        role: 'assistant',
        status: 'streaming',
        content: 'first streamed chunk',
        startedAt: new Date().toISOString(),
      }}
      copied={false}
      onCopy={() => {}}
      onReuse={() => {}}
    />,
  );
  expect(container.querySelectorAll('.chat-turn-duration')).toHaveLength(1);
});

it('R25 等待占位（无正文无推理）同样只渲染一处耗时', () => {
  const { container } = render(
    <Message
      message={{
        id: 'b',
        role: 'assistant',
        status: 'streaming',
        content: '',
        startedAt: new Date().toISOString(),
      }}
      copied={false}
      onCopy={() => {}}
      onReuse={() => {}}
    />,
  );
  expect(container.querySelectorAll('.chat-turn-duration')).toHaveLength(1);
});

it('R25 服务 Promise 抛错后终态冻结耗时（finishedAt 必须写入）', async () => {
  const store = createChatStore({
    repository: createMemoryChatRepository(),
    services: {
      real: {
        kind: 'real',
        run: async () => {
          throw new Error('offline');
        },
      },
    },
  });
  try {
    await store.getState().init();
    await store.getState().send('question', { id: 'fixture', modelLabel: 'fixture' });
    expect(store.getState().messages.at(-1)?.status).toBe('error');
    expect(store.getState().messages.at(-1)?.finishedAt).toBeTruthy();
  } finally {
    store.getState().dispose();
  }
});

it('R25 刷新恢复：中断轮次以会话最后保存时间冻结耗时，旧历史缺失 finishedAt 时补齐', async () => {
  const repo = createMemoryChatRepository();
  await repo.save({
    id: 'restore',
    title: '恢复',
    createdAt: '2026-09-08T00:00:00.000Z',
    updatedAt: '2026-09-08T00:01:00.000Z',
    messages: [
      {
        id: 'a1',
        role: 'assistant',
        content: '旧历史终态（无 finishedAt）',
        status: 'done',
        startedAt: '2026-09-08T00:00:10.000Z',
      },
      {
        id: 'a2',
        role: 'assistant',
        content: '进行中',
        status: 'streaming',
        startedAt: '2026-09-08T00:00:30.000Z',
      },
    ],
  });
  const store = createChatStore({ repository: repo });
  try {
    await store.getState().init();
    const messages = store.getState().messages;
    expect(messages[0]?.status).toBe('done');
    expect(messages[0]?.finishedAt).toBe('2026-09-08T00:01:00.000Z');
    expect(messages[1]?.status).toBe('stopped');
    expect(messages[1]?.finishReason).toBe('disconnected');
    expect(messages[1]?.finishedAt).toBe('2026-09-08T00:01:00.000Z');
    // 再次选择同一会话：恢复语义一致，冻结值不随载入时间增长
    await store.getState().selectConversation('restore');
    expect(store.getState().messages[1]?.finishedAt).toBe('2026-09-08T00:01:00.000Z');
  } finally {
    store.getState().dispose();
  }
});
