import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import type { ChatMessage } from '@/contracts/chat';
import { Message } from './Message';
import type { RagResultV2, ScopeSnapshot, TextbookEvidence } from './model/rag-v2';

vi.mock('./vendor/thinking-orbs', () => ({ ThinkingOrb: () => null }));
afterEach(cleanup);

const scope: ScopeSnapshot = {
  schemaVersion: 2,
  selection: { gradeId: 'g1', subjectId: 's1', editionId: 'e1', documentIds: ['d1'] },
  documents: [{ documentId: 'd1', documentRevisionId: 'r1', metadataRevisionId: 'm1' }],
  embeddingGenerationId: 'gen-1',
  scopeHash: 'a'.repeat(64),
};

function evidence(over: Partial<TextbookEvidence> = {}): TextbookEvidence {
  return {
    evidenceId: 'ev-1',
    documentRevisionId: 'r1',
    normalizedTextSha256: 'b'.repeat(64),
    charStart: 0,
    charEnd: 12,
    documentId: 'd1',
    title: '高中数学 必修一',
    editionLabel: '人教A版',
    subjectLabel: '数学',
    chapterPath: ['第一章', '1.1 集合'],
    text: '集合的表示方法：列举法与描述法。',
    originalFileSha256: 'c'.repeat(64),
    locator: {
      kind: 'markdown',
      lineStart: 10,
      lineEnd: 12,
      pageStart: null,
      pageEnd: null,
      blockStart: null,
      blockEnd: null,
    },
    isSuperseded: false,
    ...over,
  };
}

function result(over: Partial<RagResultV2> = {}): RagResultV2 {
  return {
    contractVersion: 2,
    resultId: 'res-1',
    status: 'ok',
    scopeSnapshot: scope,
    points: [{ pointId: 'p1', title: '集合表示', summary: '两种表示法。', evidenceIds: ['ev-1'] }],
    evidence: [evidence()],
    reason: null,
    ...over,
  };
}

function message(over: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: 'a1',
    role: 'assistant',
    content: '教材知识点与原文摘录。',
    status: 'done',
    modelLabel: '本地教材引擎',
    ...over,
  };
}

const scopeLabelFor = () => '高一 · 数学 · 人教A版 · 2 册';
const noop = () => undefined;

describe('教材证据与范围展示', () => {
  it('按 evidence[] 渲染标题、版本、学科、章节、可读定位与原文，并显示本轮范围', () => {
    render(
      <Message
        message={message({ ragResult: result(), ragEvidence: [evidence()], ragScope: scope })}
        copied={false}
        onCopy={noop}
        onReuse={noop}
        scopeLabelFor={scopeLabelFor}
      />,
    );
    expect(screen.getByText('教材依据')).toBeInTheDocument();
    expect(screen.getByText(/本轮范围：高一 · 数学 · 人教A版 · 2 册/)).toBeInTheDocument();
    expect(screen.getByText('高中数学 必修一')).toBeInTheDocument();
    expect(screen.getByText(/人教A版 · 数学 · 第一章 → 1\.1 集合 · 第 10–12 行/)).toBeInTheDocument();
    expect(screen.getByText('[ev-1]')).toBeInTheDocument();
    expect(screen.getByText('集合的表示方法：列举法与描述法。')).toBeInTheDocument();
    expect(screen.getByText('集合表示')).toBeInTheDocument();
  });

  it('isSuperseded 明确标注历史修订，不隐藏也不冒充有效', () => {
    render(
      <Message
        message={message({
          ragResult: result({ evidence: [evidence({ isSuperseded: true })] }),
          ragEvidence: [evidence({ isSuperseded: true })],
        })}
        copied={false}
        onCopy={noop}
        onReuse={noop}
      />,
    );
    expect(screen.getByText(/教材已更新，此引用为历史修订/)).toBeInTheDocument();
    expect(screen.getByText('集合的表示方法：列举法与描述法。')).toBeInTheDocument();
  });

  it('后端未给证据就不显示证据区（旧消息与空结果都不猜造引用）', () => {
    const ui = render(
      <Message message={message()} copied={false} onCopy={noop} onReuse={noop} />,
    );
    expect(ui.container.querySelector('.chat-rag-evidence')).toBeNull();
    cleanup();
    // 只有结果、没有证据：保留状态与范围，但不渲染任何证据条目
    const ui2 = render(
      <Message
        message={message({
          ragResult: result({ evidence: [], points: [] }),
          ragEvidence: [],
          ragScope: scope,
        })}
        copied={false}
        onCopy={noop}
        onReuse={noop}
        scopeLabelFor={scopeLabelFor}
      />,
    );
    expect(ui2.container.querySelector('.chat-rag-evidence')).not.toBeNull();
    expect(ui2.container.querySelectorAll('.chat-rag-list li')).toHaveLength(0);
    cleanup();
    // 旧 v1 形状（citations/explanations）只读可渲染，不伪造证据区
    const ui3 = render(
      <Message
        message={message({
          content: '旧 v1 正文',
          rag: {
            sessionId: 's',
            turnId: 't',
            question: '旧题',
            lastEventId: 4,
            status: 'terminal',
            ...({ subject: '数学', citations: [{ citation_id: 'c1' }] } as object),
          } as ChatMessage['rag'],
        })}
        copied={false}
        onCopy={noop}
        onReuse={noop}
      />,
    );
    expect(screen.getByText('旧 v1 正文')).toBeInTheDocument();
    expect(ui3.container.querySelector('.chat-rag-evidence')).toBeNull();
  });

  it('no_evidence 显示如实原因与补充提示，不出现详解引导', () => {
    const ui = render(
      <Message
        message={message({
          content: '当前教材范围没有找到足够依据。',
          ragResult: result({ status: 'no_evidence', points: [], evidence: [], reason: '没有匹配的教材片段。' }),
        })}
        copied={false}
        onCopy={noop}
        onReuse={noop}
      />,
    );
    expect(screen.getByText('没有匹配的教材片段。')).toBeInTheDocument();
    expect(
      screen.getByText(/当前范围内没有找到足够依据，回答未包含教材外推内容/),
    ).toBeInTheDocument();
    expect(ui.container.querySelector('.chat-ask-card.guidance')).toBeNull();
  });

  it('详解引导卡按一般追问卡渲染（顶部标签为「教材详解」），由 store 决定派发', () => {
    render(
      <Message
        message={message({
          asks: [
            {
              interactionId: 'guidance-res-1',
              status: 'waiting',
              kind: 'guidance',
              intro: '本轮定位已结束。',
              questions: [
                {
                  questionId: 'explain-direction',
                  header: '详解方向',
                  prompt: '希望进一步理解哪一步？',
                  options: [{ label: '细讲解题思路' }],
                  multiSelect: false,
                  allowFreeText: true,
                },
              ],
              drafts: {},
              guidance: {},
            },
          ],
        })}
        copied={false}
        onCopy={noop}
        onReuse={noop}
        ask={{
          waitingId: null,
          submitting: false,
          focus: { interactionId: 'guidance-res-1', questionId: 'explain-direction' },
          notice: null,
          onDraft: noop,
          onFocusChange: noop,
          onContinue: noop,
          onSkip: noop,
        }}
      />,
    );
    expect(screen.getByText('教材详解')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /细讲解题思路/ })).toBeEnabled();
    expect(screen.getByRole('button', { name: /继续详解/ })).toBeEnabled();
  });
});
