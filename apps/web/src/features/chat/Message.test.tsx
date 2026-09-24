import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Message } from './Message';

vi.mock('./vendor/thinking-orbs', () => ({ ThinkingOrb: () => null }));
import type { ChatMessage } from '@/contracts/chat';

afterEach(cleanup);

function message(content: string, status: ChatMessage['status'] = 'streaming'): ChatMessage {
  return {
    id: 'assistant-math',
    role: 'assistant',
    content,
    status,
    modelLabel: 'synthetic model',
  };
}

describe('助手 message.content 数学展示', () => {
  it('正文流式中闭合公式可见、未闭合尾段保持原文且不改写 message.content', () => {
    const source = String.raw`已闭合 $x^2$ 与 \(y^2\)。` + '\n\n' + '尾段 $a+b';
    const ui = render(
      <Message message={message(source)} copied={false} onCopy={() => {}} onReuse={() => {}} />,
    );
    const bubble = ui.container.querySelector('.chat-bubble.assistant')!;
    const body = bubble.querySelector('.chat-answer-content')!;
    expect(body.querySelectorAll('.katex')).toHaveLength(2);
    expect(body.querySelector('.katex-error')).toBeNull();
    expect(body.querySelector('.chat-answer-raw')?.textContent).toContain('$a+b');
    expect(body.textContent).toContain('已闭合');
    expect(
      (ui.container.querySelector('.chat-bubble.assistant') as HTMLElement).textContent,
    ).toContain('已闭合');
    expect(message(source).content).toBe(source);
  });

  it('终态正文使用 AnswerMarkdown，刷新恢复仍解析同一原文', () => {
    const source = String.raw`答案 $E=mc^2$`;
    const ui = render(
      <Message
        message={message(source, 'done')}
        copied={false}
        onCopy={() => {}}
        onReuse={() => {}}
      />,
    );
    const bubble = ui.container.querySelector('.chat-bubble.assistant')!;
    expect(bubble.querySelector('.chat-answer-content > .answer-markdown .katex')).not.toBeNull();
    expect(bubble.querySelector('.katex-error')).toBeNull();
    expect(message(source, 'done').content).toBe(source);
  });
});
