import { afterEach, describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { AskUserDraft, AskUserInteraction } from '@/contracts/chat';
import { AskUserCard } from './AskUserCard';

afterEach(cleanup);

function card(over: Partial<AskUserInteraction> = {}): AskUserInteraction {
  return {
    interactionId: 'i1',
    status: 'waiting',
    intro: '可继续追问细节，或跳过结束本轮。',
    questions: [
      {
        questionId: 'q1',
        header: '继续追问',
        prompt: '定位是否符合题意？',
        options: [{ label: '细讲解题思路' }, { label: '重新核对知识点' }],
        multiSelect: false,
        allowFreeText: true,
        placeholder: '补充说明',
      },
      {
        questionId: 'q2',
        header: '补充',
        prompt: '还需要补充什么？',
        options: [{ label: '补充条件' }],
        multiSelect: false,
        allowFreeText: false,
      },
    ],
    drafts: {},
    ...over,
  };
}

/** 受控包装：草稿与聚焦题都回流到组件（贴近聊天页的真实用法） */
function Harness({
  interaction,
  onContinue = vi.fn(),
  onSkip = vi.fn(),
  submitting = false,
  active = true,
}: {
  interaction: AskUserInteraction;
  onContinue?: (id: string) => void;
  onSkip?: (id: string) => void;
  submitting?: boolean;
  active?: boolean;
}) {
  const [drafts, setDrafts] = useState(interaction.drafts);
  const [focus, setFocus] = useState<string | null>(interaction.questions[0]!.questionId);
  return (
    <AskUserCard
      interaction={{ ...interaction, drafts }}
      active={active}
      submitting={submitting}
      focusQuestionId={focus}
      onDraft={(id, questionId, draft) => setDrafts((current) => ({ ...current, [questionId]: draft }))}
      onFocusChange={(id, questionId) => setFocus(questionId)}
      onContinue={onContinue}
      onSkip={onSkip}
    />
  );
}

function option(label: string) {
  return screen.getByRole('button', { name: new RegExp(label) });
}

describe('追问卡 v2（§7.2/§7.3）', () => {
  it('单选选中不自动跳题；页码与草稿保持在当前题', () => {
    const onContinue = vi.fn();
    render(<Harness interaction={card()} onContinue={onContinue} />);
    expect(screen.getByText('第 1 / 2 题')).toBeInTheDocument();
    fireEvent.click(option('细讲解题思路'));
    expect(option('细讲解题思路')).toHaveAttribute('aria-pressed', 'true');
    // 不自动翻页、不提交
    expect(screen.getByText('第 1 / 2 题')).toBeInTheDocument();
    expect(onContinue).not.toHaveBeenCalled();
    expect(screen.getByRole('textbox', { name: /自由输入/ })).toHaveValue('');
  });

  it('箭头只浏览：切题不清空已填草稿，也不确认、不提交', () => {
    const onContinue = vi.fn();
    render(<Harness interaction={card()} onContinue={onContinue} />);
    fireEvent.change(screen.getByRole('textbox', { name: /自由输入/ }), {
      target: { value: '补充：定义域 x>0' },
    });
    fireEvent.click(screen.getByRole('button', { name: '下一题' }));
    expect(screen.getByText('第 2 / 2 题')).toBeInTheDocument();
    expect(onContinue).not.toHaveBeenCalled();
    // 回到第一题：草稿仍在
    fireEvent.click(screen.getByRole('button', { name: '上一题' }));
    expect(screen.getByText('第 1 / 2 题')).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /自由输入/ })).toHaveValue('补充：定义域 x>0');
  });

  it('「忽略」只提交当前题的跳过动作（由 store 决定前进/提交）', () => {
    const onSkip = vi.fn();
    render(<Harness interaction={card()} onSkip={onSkip} />);
    fireEvent.click(screen.getByRole('button', { name: '忽略' }));
    expect(onSkip).toHaveBeenCalledWith('i1');
  });

  it('pendingSubmission：改选、输入与忽略全部锁定，只允许精确重试', () => {
    const onContinue = vi.fn();
    render(
      <Harness
        interaction={card({
          pendingSubmission: {
            submissionId: 'sub-1',
            answers: [{ questionId: 'q1', labels: [], freeText: 'x>0' }],
          },
          drafts: { q1: { labels: [], freeText: 'x>0', disposition: 'unanswered' } },
        })}
        onContinue={onContinue}
      />,
    );
    expect(option('细讲解题思路')).toBeDisabled();
    expect(screen.getByRole('textbox', { name: /自由输入/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: '忽略' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /重试提交/ }));
    expect(onContinue).toHaveBeenCalledWith('i1');
  });

  it('方向键只在选项列表内移动焦点，不改选择、不进入输入框', () => {
    render(<Harness interaction={card()} />);
    const first = option('细讲解题思路');
    const second = option('重新核对知识点');
    first.focus();
    fireEvent.keyDown(first, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(second);
    fireEvent.keyDown(second, { key: 'ArrowUp' });
    expect(document.activeElement).toBe(first);
    expect(first).toHaveAttribute('aria-pressed', 'false');
    // 输入框中的方向键不移动选项焦点（保持文本光标语义）
    const textarea = screen.getByRole('textbox', { name: /自由输入/ });
    textarea.focus();
    fireEvent.keyDown(textarea, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(textarea);
  });

  it('中文输入法组合期间 Enter 不触发确认；组合结束后 Enter 才继续', () => {
    const onContinue = vi.fn();
    render(<Harness interaction={card()} onContinue={onContinue} />);
    const textarea = screen.getByRole('textbox', { name: /自由输入/ });
    fireEvent.compositionStart(textarea);
    fireEvent.change(textarea, { target: { value: '定义域' } });
    fireEvent.keyDown(textarea, { key: 'Enter', isComposing: true });
    expect(onContinue).not.toHaveBeenCalled();
    fireEvent.compositionEnd(textarea);
    fireEvent.keyDown(textarea, { key: 'Enter' });
    expect(onContinue).toHaveBeenCalledWith('i1');
  });

  it('历史多选卡只读：不可编辑、不可提交，并给出说明', () => {
    const onContinue = vi.fn();
    render(
      <Harness
        interaction={card({
          questions: [
            {
              questionId: 'q1',
              prompt: '历史多选',
              options: [{ label: 'A' }, { label: 'B' }],
              multiSelect: true,
              allowFreeText: true,
            },
          ],
        })}
        onContinue={onContinue}
      />,
    );
    expect(screen.getByText(/历史多选卡：仅按原记录只读展示/)).toBeInTheDocument();
    expect(option('A')).toBeDisabled();
    expect(screen.getByRole('textbox', { name: /自由输入/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: '忽略' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '继续' })).toBeDisabled();
  });

  it('未确认提示与已答摘要按原样呈现', () => {
    const draft: AskUserDraft = { labels: ['细讲解题思路'], freeText: '' };
    const ui = render(
      <Harness
        interaction={card({
          status: 'answered',
          drafts: { q1: draft },
          answers: [{ questionId: 'q1', labels: ['细讲解题思路'], freeText: '' }],
        })}
        active={false}
      />,
    );
    expect(ui.container.querySelector('.chat-ask-summary')?.textContent).toContain('细讲解题思路');
  });

  it('RAG-QUALITY v1.1 精简：普通状态不再渲染独立卡标题，标签与分页合并到顶行', () => {
    const { container } = render(<Harness interaction={card()} />);
    // 顶行（标签 + 分页）只有一处；旧的独立卡标题（.chat-ask-head）在普通状态不再渲染
    expect(container.querySelectorAll('.chat-ask-pager')).toHaveLength(1);
    expect(container.querySelectorAll('.chat-ask-pager .chat-ask-kind')).toHaveLength(1);
    expect(container.querySelectorAll('.chat-ask-head')).toHaveLength(0);
    expect(screen.getAllByText('教材追问')).toHaveLength(1);
    // 题干（prompt）只出现一次，题干标签与题目含义不同时保留一个题干标签
    expect(screen.getAllByText('定位是否符合题意？')).toHaveLength(1);
    expect(container.querySelectorAll('.chat-ask-pager .chat-ask-label')).toHaveLength(1);
  });

  it('RAG-QUALITY v1.1 精简：与题干/标签同义的 intro 不再重复显示', () => {
    const { container } = render(
      <Harness
        interaction={card({
          intro: '继续追问',
          questions: [
            {
              questionId: 'q1',
              header: '继续追问',
              prompt: '继续追问',
              options: [{ label: '细讲解题思路' }],
              multiSelect: false,
              allowFreeText: false,
            },
          ],
        })}
      />,
    );
    // 题干标签与题干同义 → 不重复渲染题干标签；intro 与题干相同 → 不重复渲染
    expect(container.querySelector('.chat-ask-pager .chat-ask-label')).toBeNull();
    expect(container.querySelectorAll('.chat-ask-intro')).toHaveLength(0);
    expect(screen.getAllByText('继续追问')).toHaveLength(1);
  });

  it('RAG-QUALITY v1.1 精简：有信息量的 intro 仍显示一次，异常状态保留必要说明', () => {
    const { container } = render(<Harness interaction={card()} />);
    expect(container.querySelectorAll('.chat-ask-intro')).toHaveLength(1);
    cleanup();
    const pending = render(
      <Harness
        interaction={card({
          pendingSubmission: {
            submissionId: 'sub-1',
            answers: [{ questionId: 'q1', labels: [], freeText: 'x>0' }],
          },
          drafts: { q1: { labels: [], freeText: 'x>0', disposition: 'unanswered' } },
        })}
      />,
    );
    expect(pending.container.querySelector('.chat-ask-note')?.textContent).toContain(
      '上次提交结果尚未确认',
    );
    expect(pending.container.querySelector('.chat-ask-foot .chat-ask-hint')?.textContent).toContain(
      '结果未确认：仅可重试原提交',
    );
  });
});
