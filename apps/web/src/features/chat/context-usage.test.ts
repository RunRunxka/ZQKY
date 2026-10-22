import { describe, expect, it } from 'vitest';
import type { ChatMessage } from '@/contracts/chat';
import { computeContextUsage, estimateTokens } from './context-usage';

function message(overrides: Partial<ChatMessage>): ChatMessage {
  return {
    id: 'm1',
    role: 'assistant',
    content: '',
    status: 'done',
    ...overrides,
  };
}

describe('context-usage', () => {
  it('估算口径：中文约 0.6 token/字，英文约 0.3 token/字符', () => {
    expect(estimateTokens('')).toBe(0);
    expect(estimateTokens('x'.repeat(200))).toBe(60);
    expect(estimateTokens('中'.repeat(100))).toBe(60);
    // 50 中文 + 100 英文 = 30 + 30 = 60
    expect(estimateTokens(`${'中'.repeat(50)}${'x'.repeat(100)}`)).toBe(60);
  });

  it('有真实 usage 时：真实 input + 之后新增消息 + 草稿', () => {
    const messages: ChatMessage[] = [
      message({ id: 'u1', role: 'user', content: '你好' }),
      message({
        id: 'a1',
        content: '回答',
        modelProfileId: 'p1',
        usage: { inputTokens: 1200, outputTokens: 80, cachedInputTokens: 300 },
      }),
      message({ id: 'u2', role: 'user', content: '再问一句'.repeat(10) }),
    ];
    const usage = computeContextUsage(messages, 'x'.repeat(100), 'p1');
    expect(usage.source).toBe('provider');
    expect(usage.baselineMessageId).toBe('a1');
    expect(usage.baselineTokens).toBe(1200);
    // 40 个中文 ≈ 24 tokens
    expect(usage.tailTokens).toBe(estimateTokens('再问一句'.repeat(10)));
    expect(usage.draftTokens).toBe(30);
    expect(usage.usedTokens).toBe(1200 + usage.tailTokens + 30);
    expect(usage.outputTokens).toBe(80);
    expect(usage.cachedInputTokens).toBe(300);
  });

  it('切换模型后不拿另一个模型的真实值当基准，整体回退估算', () => {
    const messages: ChatMessage[] = [
      message({
        id: 'a1',
        content: '旧模型回答',
        modelProfileId: 'old-model',
        usage: { inputTokens: 9999, outputTokens: 100 },
      }),
    ];
    const usage = computeContextUsage(messages, 'x'.repeat(100), 'new-model');
    expect(usage.source).toBe('estimate');
    expect(usage.baselineMessageId).toBeNull();
    expect(usage.usedTokens).toBe(estimateTokens('旧模型回答') + 30);
  });

  it('没有真实 usage 时按可见消息 + 草稿估算', () => {
    const messages: ChatMessage[] = [
      message({ id: 'u1', role: 'user', content: 'x'.repeat(100) }),
      message({ id: 'a1', content: '中'.repeat(50) }),
    ];
    const usage = computeContextUsage(messages, 'x'.repeat(100), 'p1');
    expect(usage.source).toBe('estimate');
    // 100 ASCII=30 + 50 中文=30 + 草稿 30
    expect(usage.usedTokens).toBe(90);
    expect(usage.outputTokens).toBeNull();
  });
});
