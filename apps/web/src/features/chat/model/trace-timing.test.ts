import { describe, expect, it, vi } from 'vitest';
import { createMemoryChatRepository } from '@/services/chat-repository';
import { formatTurnDuration, turnDurationSeconds } from './trace-timing';
import { createScriptedChatStore as createChatStore } from '../../../../../../tests/fixtures/scripted-chat-store';

describe('轮级耗时格式（对照参考 formatTurnDuration）', () => {
  it('秒/分秒/时分格式', () => {
    expect(formatTurnDuration(0)).toBe('0s');
    expect(formatTurnDuration(7.4)).toBe('7s');
    expect(formatTurnDuration(60)).toBe('1m'); // 先取整再格式化（同参考）
    expect(formatTurnDuration(60)).toBe('1m');
    expect(formatTurnDuration(83)).toBe('1m 23s');
    expect(formatTurnDuration(3600)).toBe('1h');
    expect(formatTurnDuration(3720)).toBe('1h 2m');
    expect(formatTurnDuration(-5)).toBe('0s');
  });

  it('时长计算：进行中按当前时间滴答，结束后冻结', () => {
    const start = '2026-09-07T12:00:00.000Z';
    expect(turnDurationSeconds(start, '2026-09-07T12:00:03.500Z')).toBeCloseTo(3.5, 5);
    expect(turnDurationSeconds(start, undefined, Date.parse(start) + 2000)).toBe(2);
    expect(turnDurationSeconds('bad-date', '2026-09-07T12:00:00.000Z')).toBe(0);
  });
});

describe('轮级时间戳（S3：startedAt/finishedAt 随消息记录）', () => {
  it('正常结束：startedAt 在占位创建时记录，finishedAt 在 end 收尾记录', async () => {
    const store = createChatStore({
      repository: createMemoryChatRepository(),
      services: {
        real: {
          kind: 'real',
          run: async (request, emit) => {
            emit({
              sessionId: request.sessionId,
              turnId: request.turnId,
              type: 'end',
              finishReason: 'stop',
            });
          },
        },
      },
    });
    await store.getState().init();
    await store.getState().send('问题', { id: 'p', modelLabel: '测试' });
    const message = store.getState().messages[1]!;
    expect(message.startedAt).toBeTruthy();
    expect(message.finishedAt).toBeTruthy();
    expect(message.status).toBe('done');
    store.getState().dispose();
  });

  it('取消收尾同样记录 finishedAt', async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    const store = createChatStore({
      repository: createMemoryChatRepository(),
      services: {
        real: {
          kind: 'real',
          run: async () => {
            await gate;
          },
        },
      },
    });
    await store.getState().init();
    const run = store.getState().send('问题', { id: 'p', modelLabel: '测试' });
    await vi.waitFor(() => expect(store.getState().sending).toBe(true));
    store.getState().stop();
    release();
    await run;
    const message = store.getState().messages[1]!;
    expect(message.status).toBe('stopped');
    expect(message.finishedAt).toBeTruthy();
    store.getState().dispose();
  });
});
