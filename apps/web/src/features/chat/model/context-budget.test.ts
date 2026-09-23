import { describe, expect, it } from 'vitest';
import {
  conversationProjection,
  projectRequestHistory,
  selectMessagesForRequest,
  takeNewestMessages,
} from './context-budget';
import type { ChatMessage } from '@/contracts/chat';

function message(
  role: ChatMessage['role'],
  content: string,
  status: ChatMessage['status'] = 'done',
): ChatMessage {
  return { id: `m-${Math.random().toString(36).slice(2)}`, role, content, status };
}

/**
 * R12 投影 + 历史裁剪：CHAT-CONTEXT-BUDGET v1 起，产品路径的历史裁剪由
 * `buildChatRequest`（request-budget.ts）统一完成；这里断言共用内核
 * （`projectRequestHistory` / `takeNewestMessages`）与兼容入口的**整条取舍**语义。
 */
describe('上下文预算', () => {
  it('预算充足时保留全部消息', () => {
    const messages = [
      message('user', '第一问'),
      message('assistant', '第一答'),
      message('user', '第二问'),
    ];
    const selected = selectMessagesForRequest(messages, 1000);
    expect(selected).toHaveLength(3);
    expect(selected.at(-1)?.content).toBe('第二问');
  });

  it('超预算时从最旧开始丢弃，保留最近消息与其回复', () => {
    const messages = [
      message('user', '旧'.repeat(600)),
      message('assistant', '答'.repeat(600)),
      message('user', '新问题'),
    ];
    const selected = selectMessagesForRequest(messages, 800);
    // 最后一条用户消息 + 预算内最近的助手回复
    expect(selected).toHaveLength(2);
    expect(selected[0]?.content).toBe('答'.repeat(600));
    expect(selected[1]?.content).toBe('新问题');
  });

  it('失败或流式中的空 assistant 占位不发送', () => {
    const messages = [
      message('user', '问题'),
      message('assistant', '', 'error'),
      message('user', '换个问法'),
    ];
    const selected = selectMessagesForRequest(messages, 1000);
    expect(selected).toHaveLength(2);
    expect(selected.every((item) => item.content.length > 0)).toBe(true);
  });

  it('放不下的整条消息直接丢弃，绝不截断半条（当前问题放不下必须由构建器明确失败）', () => {
    const messages = [message('user', '超'.repeat(5000))];
    // 旧实现的「最后一条用户消息即使超预算也保留」会让超限内容进入请求；
    // 新语义整条取舍，是否可发送由 buildChatRequest 判定并显式失败。
    expect(selectMessagesForRequest(messages, 100)).toEqual([]);
    expect(selectMessagesForRequest(messages, 5000)).toHaveLength(1);
  });

  it('takeNewestMessages：字符、条数与单条上限任一不满足即整条停止，并如实计数', () => {
    const entries = projectRequestHistory([
      message('user', '最旧的问题'),
      message('assistant', '旧的回答'),
      message('assistant', '过长的回答'.repeat(9)), // 45 字符：超过单条上限时不得发送
      message('user', '最新的问题'),
    ]);
    const droppedByChars = takeNewestMessages(entries, {
      chars: 20,
      count: 99,
      maxChars: 999,
    });
    expect(droppedByChars.messages.map((m) => m.content)).toEqual(['最新的问题']);
    expect(droppedByChars.dropped).toBe(3);

    const droppedByCount = takeNewestMessages(entries, { chars: 999, count: 1, maxChars: 999 });
    expect(droppedByCount.messages.map((m) => m.content)).toEqual(['最新的问题']);
    expect(droppedByCount.dropped).toBe(3);

    const droppedBySingleLimit = takeNewestMessages(entries, {
      chars: 999,
      count: 99,
      maxChars: 40,
    });
    // 第 3 条（45 字符）超过单条上限：整条停止，其后更旧的一并丢弃（连续近期上下文）
    expect(droppedBySingleLimit.messages.map((m) => m.content)).toEqual(['最新的问题']);
    expect(droppedBySingleLimit.dropped).toBe(3);
  });

  it('projectRequestHistory：助手消息按对话投影计入，无正文占位不进入请求', () => {
    const withAsk: ChatMessage = {
      id: 'a',
      role: 'assistant',
      content: '正文',
      status: 'done',
      asks: [
        {
          interactionId: 'ask-1',
          questions: [{ questionId: 'q1', prompt: '偏好' }],
          status: 'answered',
          drafts: {},
          answers: [{ questionId: 'q1', labels: ['选项A'], freeText: '' }],
          followUp: '续写内容',
        },
      ],
    };
    const entries = projectRequestHistory([withAsk, message('assistant', '', 'error')]);
    expect(entries).toHaveLength(1);
    expect(entries[0]?.content).toBe(conversationProjection(withAsk));
    expect(entries[0]?.content).toContain('选项A');
    expect(entries[0]?.content).toContain('续写内容');
  });
});
