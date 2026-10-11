'use client';
import { useRef } from 'react';
import { ChevronLeft, ChevronRight, LoaderCircle, MessageCircleQuestion } from 'lucide-react';
import type {
  AskUserDraft,
  AskUserInteraction,
  AskUserQuestion,
} from '@/contracts/chat';

const EMPTY_DRAFT: AskUserDraft = { labels: [], freeText: '' };

/**
 * 对话内追问/确认卡（骨架版）：Agent 中断（wait-user）与对话追问共用同一卡片。
 *
 * - 顶部：标签、左右箭头、页码；箭头**只浏览**（不确认、不提交）；
 * - 中部：编号选项 + 可选自由输入；单选选中**不自动跳题**；
 * - 底部：「忽略」与「继续」；键盘：↑↓ 选项、Enter 选中、Enter 继续、
 *   Shift+Enter 换行；中文输入法组合期间不触发确认。
 */
export function AskUserCard({
  interaction,
  active,
  submitting,
  focusQuestionId,
  notice,
  onDraft,
  onFocusChange,
  onContinue,
  onSkip,
}: {
  interaction: AskUserInteraction;
  active: boolean;
  submitting: boolean;
  focusQuestionId?: string | null;
  notice?: string | null;
  onDraft(interactionId: string, questionId: string, draft: AskUserDraft): void;
  onFocusChange(interactionId: string, questionId: string): void;
  onContinue(interactionId: string): void;
  onSkip(interactionId: string): void;
}) {
  const composingRef = useRef(false);
  const optionsRef = useRef<HTMLDivElement>(null);
  const total = interaction.questions.length;
  const requested = interaction.questions.findIndex((q) => q.questionId === focusQuestionId);
  const activeIndex = Math.min(Math.max(requested, 0), Math.max(total - 1, 0));
  const question: AskUserQuestion | undefined = interaction.questions[activeIndex];
  const pendingRetry = !!interaction.pendingSubmission;
  const locked = interaction.status === 'submitting' || (submitting && active);
  const answerable =
    (interaction.status === 'waiting' || interaction.status === 'failed') && active && !locked;
  const editable = answerable && !pendingRetry;
  const canRetry = pendingRetry && answerable;
  const answered = interaction.status === 'answered';

  const draftOf = (q: AskUserQuestion): AskUserDraft => interaction.drafts[q.questionId] ?? EMPTY_DRAFT;
  const isComposing = (event: React.KeyboardEvent) =>
    event.nativeEvent.isComposing || composingRef.current;

  function pickOption(q: AskUserQuestion, label: string) {
    if (!editable) return;
    onDraft(interaction.interactionId, q.questionId, { labels: [label], freeText: '' });
  }
  function updateFreeText(q: AskUserQuestion, text: string) {
    if (!editable) return;
    const current = draftOf(q);
    onDraft(interaction.interactionId, q.questionId, {
      labels: text.trim() ? [] : current.labels,
      freeText: text,
    });
  }
  function moveOptionFocus(event: React.KeyboardEvent, position: number) {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    const buttons = optionsRef.current?.querySelectorAll<HTMLButtonElement>('button[data-option]');
    if (!buttons?.length) return;
    event.preventDefault();
    const next =
      event.key === 'ArrowDown'
        ? Math.min(position + 1, buttons.length - 1)
        : Math.max(position - 1, 0);
    buttons[next]?.focus();
  }
  function browse(delta: -1 | 1) {
    if (total <= 1) return;
    const next = Math.min(total - 1, Math.max(0, activeIndex + delta));
    const target = interaction.questions[next];
    if (target) onFocusChange(interaction.interactionId, target.questionId);
  }
  function summaryLine(q: AskUserQuestion): string {
    const answer = interaction.answers?.find((a) => a.questionId === q.questionId);
    if (!answer || (!answer.labels.length && !answer.freeText?.trim())) return '（已跳过）';
    const parts: string[] = [];
    if (answer.labels.length) parts.push(answer.labels.join('、'));
    if (answer.freeText?.trim()) parts.push(answer.freeText.trim());
    return parts.join('；') || '（已跳过）';
  }

  const interrupted = interaction.status === 'interrupted' || (interaction.status === 'waiting' && !active);
  const answerableState =
    interaction.status === 'waiting' || interaction.status === 'submitting' || interaction.status === 'failed';
  const introText = interaction.intro?.trim() ?? '';

  return (
    <div
      className={`chat-ask-card ${interaction.status}${active ? ' active' : ''}`}
      data-status={interaction.status}
    >
      {(!answerableState || !question) && (
        <p className="chat-ask-head">
          <MessageCircleQuestion size={14} aria-hidden="true" />
          <span>
            对话追问
            {interaction.status === 'submitting' && ' · 提交中'}
            {answered && ' · 已回答'}
            {interrupted && ' · 已失效'}
          </span>
        </p>
      )}
      {introText && <p className="chat-ask-intro">{introText}</p>}
      {pendingRetry && (
        <p className="chat-ask-note" role="status">
          上次提交结果尚未确认：改选、输入与忽略已锁定，只能按原答案精确重试（不会重复处理）。
        </p>
      )}

      {interrupted && !answered && (
        <p className="chat-ask-note" role="status">
          本轮等待已失效（取消或刷新后上下文不再可用），此卡不可提交；可重新发送问题开启新的尝试。
        </p>
      )}

      {(interaction.status === 'waiting' ||
        interaction.status === 'submitting' ||
        interaction.status === 'failed') &&
        question && (
          <>
            <header className="chat-ask-pager">
              <span className="chat-ask-kind">
                <MessageCircleQuestion size={14} aria-hidden="true" />
                <span>对话追问{interaction.status === 'submitting' && ' · 提交中'}</span>
              </span>
              {total > 1 && (
                <>
                  <span className="chat-flex-spacer" />
                  <button
                    type="button"
                    className="chat-ask-arrow"
                    aria-label="上一题"
                    disabled={activeIndex === 0}
                    onClick={() => browse(-1)}
                  >
                    <ChevronLeft size={14} />
                  </button>
                  <span className="chat-ask-page" aria-live="polite">
                    第 {activeIndex + 1} / {total} 题
                  </span>
                  <button
                    type="button"
                    className="chat-ask-arrow"
                    aria-label="下一题"
                    disabled={activeIndex >= total - 1}
                    onClick={() => browse(1)}
                  >
                    <ChevronRight size={14} />
                  </button>
                </>
              )}
            </header>
            <section className="chat-ask-question" aria-label={`追问 ${activeIndex + 1}/${total}`}>
              <p className="chat-ask-prompt">{question.prompt}</p>
              <div ref={optionsRef} className="chat-ask-options" role="group" aria-label={question.prompt}>
                {(question.options ?? []).map((option, position) => {
                  const picked = draftOf(question).labels.includes(option.label);
                  return (
                    <button
                      key={option.label}
                      type="button"
                      data-option={position}
                      aria-pressed={picked}
                      disabled={!editable}
                      onKeyDown={(event) => {
                        if (isComposing(event)) {
                          if (event.key === 'Enter') event.preventDefault();
                          return;
                        }
                        moveOptionFocus(event, position);
                      }}
                      onClick={() => pickOption(question, option.label)}
                    >
                      <span className="chat-ask-option-index" aria-hidden="true">
                        {position + 1}.
                      </span>
                      <span className="chat-ask-option-body">
                        <span className="chat-ask-option-label">{option.label}</span>
                        {option.description && (
                          <small className="chat-ask-option-desc">{option.description}</small>
                        )}
                      </span>
                    </button>
                  );
                })}
                {question.allowFreeText && (
                  <label className="chat-ask-free">
                    <span className="chat-ask-option-index" aria-hidden="true">
                      {(question.options?.length ?? 0) + 1}.
                    </span>
                    <textarea
                      rows={2}
                      aria-label={`${question.prompt}（自由输入）`}
                      placeholder={question.placeholder ?? '补充说明（可选）'}
                      disabled={!editable}
                      maxLength={2000}
                      value={draftOf(question).freeText}
                      onCompositionStart={() => {
                        composingRef.current = true;
                      }}
                      onCompositionEnd={() => {
                        composingRef.current = false;
                      }}
                      onChange={(e) => updateFreeText(question, e.target.value)}
                      onKeyDown={(event) => {
                        if (event.key !== 'Enter' || event.shiftKey) return;
                        if (isComposing(event)) return;
                        event.preventDefault();
                        onContinue(interaction.interactionId);
                      }}
                    />
                  </label>
                )}
              </div>
              {interaction.status === 'failed' && interaction.error && (
                <div className="chat-ask-error" role="alert">
                  <span>
                    {interaction.error.message}（{interaction.error.code}）
                  </span>
                  {active && (
                    <button type="button" disabled={!canRetry && !editable} onClick={() => onContinue(interaction.interactionId)}>
                      重试提交
                    </button>
                  )}
                </div>
              )}
            </section>
            {notice && (
              <p className="chat-ask-notice" role="status">
                {notice}
              </p>
            )}
            <footer className="chat-ask-foot">
              <p className="chat-ask-hint">
                {pendingRetry ? '结果未确认：仅可重试原提交' : '↑↓ 选项 · Enter 选中 · Enter 继续 · Shift+Enter 换行'}
              </p>
              <button
                type="button"
                className="chat-ask-nav"
                disabled={!editable}
                onClick={() => onSkip(interaction.interactionId)}
              >
                忽略
              </button>
              <button
                type="button"
                className="chat-ask-nav primary"
                disabled={!(editable || canRetry)}
                onClick={() => onContinue(interaction.interactionId)}
              >
                {locked ? <LoaderCircle size={13} className="chat-tool-spin" aria-hidden="true" /> : null}
                {canRetry ? '重试提交' : '继续'}
              </button>
            </footer>
          </>
        )}

      {answered && (
        <dl className="chat-ask-summary">
          {interaction.questions.map((q) => (
            <div key={q.questionId}>
              <dt>{q.prompt}</dt>
              <dd>{summaryLine(q)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
