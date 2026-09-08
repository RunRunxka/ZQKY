import { it, expect } from 'vitest';
import { createChatStore } from './store';
import { createMemoryChatRepository } from '@/services/chat-repository';
import type { ChatStreamHandlers } from '@/services/chat-stream';
const profile = { id: 'p', modelLabel: 'model' };
it('新建会话停止旧流，晚到分块不串写，停止内容可恢复', async () => {
  let handlers!: ChatStreamHandlers, finish!: () => void;
  const repo = createMemoryChatRepository();
  const store = createChatStore({
    repository: repo,
    stream: async (_input, h) => {
      handlers = h;
      h.onText?.('已收到');
      await new Promise<void>((r) => {
        finish = r;
      });
    },
  });
  await store.getState().init();
  const run = store.getState().send('问题', profile);
  const old = store.getState().activeId!;
  store.getState().newConversation();
  handlers.onText?.('晚到文本');
  finish();
  await run;
  expect(store.getState().messages).toHaveLength(0);
  expect((await repo.load(old))?.messages[1]).toMatchObject({
    content: '已收到',
    status: 'stopped',
  });
});
it('重试部分回答保留原文，但不把旧尝试再发给模型', async () => {
  let calls = 0;
  const sent: string[][] = [];
  const store = createChatStore({
    repository: createMemoryChatRepository(),
    stream: async (input, h) => {
      sent.push(input.messages.map((m) => m.content));
      calls++;
      h.onText?.(calls === 1 ? '部分回答' : '完整回答');
      if (calls === 1) h.onError?.({ code: 'ERROR', message: '错误' });
      else h.onEnd?.('stop');
    },
  });
  await store.getState().init();
  await store.getState().send('问题', profile);
  await store.getState().retryLast(profile);
  expect(store.getState().messages.map((m) => m.content)).toEqual(['问题', '部分回答', '完整回答']);
  expect(sent[1]).toEqual(['问题']);
});
it('刷新恢复输入草稿与会话模型，未结束生成恢复为中断', async () => {
  const repo = createMemoryChatRepository();
  const store = createChatStore({ repository: repo });
  await store.getState().init();
  store.getState().setDraft('尚未发送');
  store.getState().setModel('specific');
  await store.getState().flush();
  const next = createChatStore({ repository: repo });
  await next.getState().init();
  expect(next.getState()).toMatchObject({ draft: '尚未发送', modelProfileId: 'specific' });
});
it('存储失败保留编辑内容并允许备份，重试成功后清除提示', async () => {
  const repo = createMemoryChatRepository();
  let fail = true;
  const store = createChatStore({
    repository: {
      ...repo,
      save: async (...args) => {
        if (fail) throw new Error('存储空间不足');
        return repo.save(...args);
      },
    },
  });
  await store.getState().init();
  store.getState().setDraft('不能丢失');
  expect(await store.getState().flush()).toBe(false);
  expect(store.getState().storageWarning).toBe('存储空间不足');
  expect(store.getState().exportActive()).toContain('不能丢失');
  fail = false;
  expect(await store.getState().flush()).toBe(true);
  expect(store.getState().storageWarning).toBeNull();
});
it('恢复进行中的回答时保留部分文本并标记中断', async () => {
  const repo = createMemoryChatRepository();
  await repo.save({
    id: 'interrupted',
    title: '中断',
    createdAt: '2026-09-06',
    updatedAt: '2026-09-06',
    messages: [{ id: 'a', role: 'assistant', content: '部分文本', status: 'streaming' }],
  });
  const store = createChatStore({ repository: repo });
  await store.getState().init();
  expect(store.getState().messages[0].content).toBe('部分文本');
  expect(store.getState().messages[0].status).not.toBe('streaming');
  expect(store.getState().sending).toBe(false);
});
