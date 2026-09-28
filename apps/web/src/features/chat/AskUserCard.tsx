'use client';
import { useState } from 'react';
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  LoaderCircle,
  MessageCircleQuestion,
} from 'lucide-react';
import type {
  AskUserAnswer,
  AskUserDraft,
  AskUserInteraction,
  AskUserQuestion,
} from '@/contracts/chat';

const EMPTY_DRAFT: AskUserDraft = { labels: [], freeText: '' };

/**
 * 消息内追问卡（对照原版 AskUserOptions）：
 * - 预览只读；waiting 才开放作答，不允许回答半生成的问题；
 * - 单选选中后跳到下一道未答题；多选只切换不前进；自由文本与单选互斥；
 * - 未回答题目按原版语义在提交时标记为跳过，不做"必须答完"拦截；
 * - 提交中锁定（重复提交无效）；失败保留草稿与选项可重试；
 * - 已回答/已中断为只读摘要。草稿即时入 store，正文增量不重置用户选择；
 * - 本组件无 Enter 提交路径，中文 IME 组合不受影响。
 */
export function AskUserCard({
  interaction,
  active,
  submitting,
  onDraft,
  onSubmit,
  source = 'mock',
}: {
  interaction: AskUserInteraction;
  /** 是否为当前等待回答的卡（仅此卡可提交） */
  active: boolean;
  submitting: boolean;
  onDraft(interactionId: string, questionId: string, draft: AskUserDraft): void;
  onSubmit(interactionId: string, answers: AskUserAnswer[]): void;
  source?: 'rag' | 'mock';
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const total = interaction.questions.length;
  const question = interaction.questions[Math.min(activeIndex, Math.max(total - 1, 0))];
  const locked = interaction.status === 'submitting' || (submitting && active);
  // waiting 与 failed（保留草稿可重试）均可编辑导航；提交中锁定
  const answerable =
    (interaction.status === 'waiting' || interaction.status === 'failed') &&
    active &&
    !locked;
  const editable = answerable && !interaction.pendingSubmission;

  function draftOf(q: AskUserQuestion): AskUserDraft {
    return interaction.drafts[q.questionId] ?? EMPTY_DRAFT;
  }
  function hopToNextUnanswered(from: number, pickedId: string) {
    if (total <= 1) return;
    for (let step = 1; step < total; step += 1) {
      const j = (from + step) % total;
      if (interaction.questions[j]!.questionId === pickedId) continue;
      const draft = interaction.drafts[interaction.questions[j]!.questionId];
      if (!draft || (!draft.labels.length && !draft.freeText.trim())) {
        setActiveIndex(j);
        return;
      }
    }
  }
  function pickOption(q: AskUserQuestion, label: string) {
    if (!editable) return;
    if (q.multiSelect) {
      // 多选：只切换，不自动前进；选项与补充文本可共存
      const cur = draftOf(q).labels;
      const next = cur.includes(label) ? cur.filter((l) => l !== label) : [...cur, label];
      onDraft(interaction.interactionId, q.questionId, { ...draftOf(q), labels: next });
      return;
    }
    // 单选（R15）：选中即清空自由文本（双向互斥），并跳到下一道未答题（对照原版）
    onDraft(interaction.interactionId, q.questionId, { labels: [label], freeText: '' });
    hopToNextUnanswered(activeIndex, q.questionId);
  }
  function updateFreeText(q: AskUserQuestion, text: string) {
    if (!editable) return;
    const next: AskUserDraft = { ...draftOf(q), freeText: text };
    // 单选下自由文本与选项互斥（对照原版 selectCustom）
    if (!q.multiSelect && text.trim()) next.labels = [];
    onDraft(interaction.interactionId, q.questionId, next);
  }
  function skipCurrent(q: AskUserQuestion) {
    if (!editable) return;
    onDraft(interaction.interactionId, q.questionId, EMPTY_DRAFT);
    setActiveIndex((idx) => Math.min(total - 1, idx + 1));
  }
  function submit() {
    if (!answerable) return;
    // R15：序列化只提交当前有效分支——单选要么是选项要么是自由文本；多选允许共存
    const answers: AskUserAnswer[] = interaction.questions.map((q) => {
      const draft = draftOf(q);
      const hasLabels = draft.labels.length > 0;
      const hasText = draft.freeText.trim() !== '';
      if (!hasLabels && !hasText)
        return { questionId: q.questionId, labels: [], freeText: '', skipped: true };
      if (q.multiSelect)
        return { questionId: q.questionId, labels: draft.labels, freeText: draft.freeText };
      return hasLabels
        ? { questionId: q.questionId, labels: draft.labels, freeText: '' }
        : { questionId: q.questionId, labels: [], freeText: draft.freeText };
    });
    onSubmit(interaction.interactionId, answers);
  }
  function summaryLine(q: AskUserQuestion): string {
    const answer = interaction.answers?.find((a) => a.questionId === q.questionId);
    if (!answer || answer.skipped || (!answer.labels.length && !answer.freeText?.trim()))
      return '（已跳过）';
    const parts: string[] = [];
    if (answer.labels.length) parts.push(answer.labels.join('、'));
    if (answer.freeText?.trim()) parts.push(answer.freeText.trim());
    return parts.join('；') || '（已跳过）';
  }

  const answered = interaction.status === 'answered';
  const interrupted = interaction.status === 'interrupted' || (interaction.status === 'waiting' && !active);

  return (
    <div
      className={`chat-ask-card ${interaction.status}${active ? ' active' : ''}`}
      data-status={interaction.status}
    >
      <p className="chat-ask-head">
        <MessageCircleQuestion size={14} aria-hidden="true" />
        <span>
          {source === 'rag' ? '教材追问' : '追问（本地模拟）'}
          {total > 1 && ` · ${Math.min(activeIndex + 1, total)}/${total}`}
          {interaction.status === 'submitting' && ' · 提交中'}
          {answered && ' · 已回答'}
          {interrupted && ' · 已中断'}
        </span>
      </p>
      {interaction.intro && <p className="chat-ask-intro">{interaction.intro}</p>}
      {interaction.pendingSubmission && !locked && <p className="chat-ask-note">上次提交尚未确认。再次提交会核对原回答，不会重复处理。</p>}

      {interaction.status === 'preview' && (
        // R13：预览按原版呈现已有题目（只读），无题目时才显示骨架
        interaction.questions.length ? (
          <div className="chat-ask-readonly" aria-label="追问预览（暂不可作答）">
            {interaction.questions.map((q) => (
              <div key={q.questionId} className="chat-ask-question">
                {q.header && <h4>{q.header}</h4>}
                <p className="chat-ask-prompt">{q.prompt}</p>
                <div className="chat-ask-options">
                  {(q.options ?? []).map((option) => (
                    <button key={option.label} type="button" disabled aria-pressed={false}>
                      <span className="chat-ask-option-label">{option.label}</span>
                      {option.description && (
                        <small className="chat-ask-option-desc">{option.description}</small>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            <p className="chat-ask-note" role="status">
              正在准备追问，以下内容暂不可作答…
              <span className="chat-stream-dot">…</span>
            </p>
          </div>
        ) : (
          <p className="chat-status-text" role="status">
            正在准备追问…
            <span className="chat-stream-dot">…</span>
          </p>
        )
      )}

      {interrupted && (
        <p className="chat-ask-note" role="status">
          本轮等待已失效（取消或刷新后上下文不再可用），此卡不可提交；可重试原问题开启新的尝试。
        </p>
      )}

      {(interaction.status === 'waiting' || interaction.status === 'submitting' || interaction.status === 'failed') && question && (
        <>
          <section
            className="chat-ask-question"
            aria-label={`追问 ${Math.min(activeIndex + 1, total)}/${total}${question.header ? `：${question.header}` : ''}`}
          >
            {question.header && <h4>{question.header}</h4>}
            <p className="chat-ask-prompt">{question.prompt}</p>
            <div className="chat-ask-options" role="group" aria-label={question.prompt}>
              {(question.options ?? []).map((option) => {
                const picked = draftOf(question).labels.includes(option.label);
                return (
                  <button
                    key={option.label}
                    type="button"
                    aria-pressed={picked}
                    disabled={!answerable}
                    onClick={() => pickOption(question, option.label)}
                  >
                    <span className="chat-ask-option-label">{option.label}</span>
                    {option.description && (
                      <small className="chat-ask-option-desc">{option.description}</small>
                    )}
                  </button>
                );
              })}
            </div>
            {question.allowFreeText && (
              <textarea
                rows={2}
                aria-label={`${question.prompt}（自由输入）`}
                placeholder={question.placeholder ?? '补充说明（可选）'}
                disabled={!editable}
                maxLength={source === 'rag' ? 2000 : undefined}
                value={draftOf(question).freeText}
                onChange={(e) => updateFreeText(question, e.target.value)}
              />
            )}
            {interaction.status === 'failed' && interaction.error && (
              <div className="chat-ask-error" role="alert">
                <CircleAlert size={13} />
                <span>
                  {interaction.error.message}（{interaction.error.code}）
                </span>
                {active && (
                  <button type="button" onClick={submit}>
                    重试提交
                  </button>
                )}
              </div>
            )}
          </section>
          <footer className="chat-ask-foot">
            {total > 1 && activeIndex > 0 ? (
              <button
                type="button"
                className="chat-ask-nav"
                disabled={!answerable}
                onClick={() => setActiveIndex((idx) => Math.max(0, idx - 1))}
              >
                <ChevronLeft size={13} />
                上一题
              </button>
            ) : (
              <span className="chat-ask-hint">
                {total > 1 ? '未回答的题目将按跳过提交。' : '可跳过或直接提交。'}
              </span>
            )}
            {total > 1 && activeIndex < total - 1 ? (
              <button
                type="button"
                className="chat-ask-nav primary"
                disabled={!answerable}
                onClick={() => setActiveIndex((idx) => Math.min(total - 1, idx + 1))}
              >
                下一题
                <ChevronRight size={13} />
              </button>
            ) : (
              <button
                type="button"
                className="chat-ask-nav primary"
                disabled={!answerable}
                onClick={submit}
              >
                {locked ? (
                  <LoaderCircle size={13} className="chat-tool-spin" aria-hidden="true" />
                ) : null}
                {total > 1 ? '提交回答' : '提交'}
              </button>
            )}
          </footer>
          {total > 1 && (
            <p className="chat-ask-foot-actions">
              <button type="button" disabled={!editable} onClick={() => skipCurrent(question)}>
                跳过此题
              </button>
            </p>
          )}
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
      {interaction.status === 'submitting' && !active && (
        <p className="chat-ask-note">
          <AlertCircle size={12} /> 正在提交回答…
        </p>
      )}
    </div>
  );
}
