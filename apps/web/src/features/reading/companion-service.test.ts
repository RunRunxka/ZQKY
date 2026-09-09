import { describe, expect, it } from 'vitest';
import {
  composeCompanionReply,
  createReadingCompanionService,
  type CompanionServiceRequest,
} from './companion-service';
import type { ChatServiceEvent } from '@/features/chat/model/chat-service';

function makeRequest(overrides?: Partial<CompanionServiceRequest>): CompanionServiceRequest {
  return {
    sessionId: 'rss-1',
    turnId: 'rturn-1',
    materialTitle: '分数是什么（演示材料）',
    userText: '什么是约分？',
    signal: new AbortController().signal,
    ...overrides,
  };
}

/** 收集事件直至 end/error/abort */
async function collect(request: CompanionServiceRequest): Promise<ChatServiceEvent[]> {
  const service = createReadingCompanionService({ chunkDelayMs: 0 });
  const events: ChatServiceEvent[] = [];
  await service.run(request, (event) => events.push(event));
  return events;
}

describe('reading companion service（R32.1）', () => {
  it('回复以显式模拟标注并携带材料与选区', () => {
    const reply = composeCompanionReply({ materialTitle: '分数是什么', userText: '问题', quote: '分数表示整体的一部分' });
    expect(reply).toContain('【模拟回复】');
    expect(reply).toContain('《分数是什么》');
    expect(reply).toContain('分数表示整体的一部分');
  });

  it('按统一事件模型流式输出：turn-start → process/stage → 多段 text → usage → end', async () => {
    const events = await collect(makeRequest());
    const types = events.map((event) => event.type);
    expect(types[0]).toBe('turn-start');
    expect(types).toContain('process');
    expect(types).toContain('stage');
    expect(types[types.length - 1]).toBe('end');
    // 正文为多个增量块（非一次性字符串）
    const textEvents = events.filter((event) => event.type === 'text');
    expect(textEvents.length).toBeGreaterThan(3);
    const full = textEvents.map((event) => (event as { delta: string }).delta).join('');
    expect(full).toContain('【模拟回复】');
    expect(full).toContain('伴生助手尚未接入模型服务');
    // 全部事件归属同一会话/轮次
    for (const event of events) {
      expect(event.sessionId).toBe('rss-1');
      expect(event.turnId).toBe('rturn-1');
    }
  });

  it('armFailure：下一轮以可重试错误收尾，重试轮正常完成', async () => {
    const service = createReadingCompanionService({ chunkDelayMs: 0 });
    const failed: ChatServiceEvent[] = [];
    service.armFailure();
    await service.run(makeRequest({ turnId: 'rturn-fail' }), (event) => failed.push(event));
    const error = failed.find((event) => event.type === 'error');
    expect(error && error.type === 'error' && error.error.retryable).toBe(true);
    // 重试轮：不再失败，正常 end
    const retried: ChatServiceEvent[] = [];
    await service.run(makeRequest({ turnId: 'rturn-retry' }), (event) => retried.push(event));
    expect(retried[retried.length - 1]?.type).toBe('end');
  });

  it('取消（AbortSignal）：中断后不再有新事件，已生成的增量可保留', async () => {
    const controller = new AbortController();
    const service = createReadingCompanionService({ chunkDelayMs: 30 });
    const events: ChatServiceEvent[] = [];
    let sawText = false;
    const run = service.run(makeRequest({ signal: controller.signal }), (event) => {
      events.push(event);
      if (event.type === 'text' && !sawText) {
        sawText = true;
        controller.abort();
      }
    });
    await expect(run).rejects.toMatchObject({ name: 'AbortError' });
    const countAfterAbort = events.length;
    await new Promise((resolve) => setTimeout(resolve, 80));
    // 中止后不再有新事件
    expect(events.length).toBe(countAfterAbort);
    expect(events.some((event) => event.type === 'text')).toBe(true);
  });
});
