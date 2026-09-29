'use client';
import { useRef } from 'react';
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  LoaderCircle,
  MessageCircleQuestion,
  Sparkles,
} from 'lucide-react';
import type {
  AskUserDraft,
  AskUserInteraction,
  AskUserQuestion,
} from '@/contracts/chat';

const EMPTY_DRAFT: AskUserDraft = { labels: [], freeText: '' };

/**
 * 教材追问卡 / 详解引导卡（RAG-REBUILD v1.0 §7.2–§7.3）。
 *
 * - 顶部：标签、问题、左右箭头、页码；箭头**只浏览**（不确认、不提交、不清空草稿）；
 * - 中部：编号选项（1. 2. …）+ 最后一项自由输入；单选选中**不自动跳题**；
 * - 底部：键盘说明、「忽略」与「继续」；「忽略」只把当前题标记 skipped 后前进；
 * - 最后一题的「继续」在存在未确认题时跳回该题并提示「还有问题尚未确认」，全部处理完才提交；
 * - `pendingSubmission` 存在（提交结果未确认）时改选/输入/忽略全部锁定，只允许同
 *   幂等键同载荷的精确重试；`reply.accepted` 到达后由 store 确认为已答；
 * - 旧历史多选卡（`multiSelect:true`）只读展示，不允许编辑后提交；
 * - 键盘：方向键只在选项列表内移动焦点；Enter/Space 选中；自由输入框 Enter 继续、
 *   Shift+Enter 换行；中文输入法组合期间不触发确认；Tab 顺序保持文档顺序。
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
  source = 'rag',
}: {
  interaction: AskUserInteraction;
  /** 是否为当前可作答的卡（澄清卡 = 服务端等待身份；引导卡 = 本地等待态） */
  active: boolean;
  submitting: boolean;
  /** 当前聚焦题（与主输入框补充回答共用同一聚焦语义） */
  focusQuestionId?: string | null;
  /** 即时提示（如「还有问题尚未确认」），随题绑定 */
  notice?: string | null;
  onDraft(interactionId: string, questionId: string, draft: AskUserDraft): void;
  onFocusChange(interactionId: string, questionId: string): void;
  onContinue(interactionId: string): void;
  onSkip(interactionId: string): void;
  source?: 'rag' | 'mock';
}) {
  const composingRef = useRef(false);
  const optionsRef = useRef<HTMLDivElement>(null);
  const total = interaction.questions.length;
  const requested = interaction.questions.findIndex((q) => q.questionId === focusQuestionId);
  const activeIndex = Math.min(Math.max(requested, 0), Math.max(total - 1, 0));
  const question: AskUserQuestion | undefined = interaction.questions[activeIndex];
  // 旧历史多选卡只读兼容：新卡统一单选，不允许编辑后提交
  const legacyMultiSelect = interaction.questions.some((q) => q.multiSelect === true);
  const pendingRetry = !!interaction.pendingSubmission;
  const locked = interaction.status === 'submitting' || (submitting && active);
  const answerable =
    (interaction.status === 'waiting' || interaction.status === 'failed') &&
    active &&
    !locked &&
    !legacyMultiSelect;
  const editable = answerable && !pendingRetry;
  /** 提交结果未确认时唯一可用的动作：同幂等键同载荷精确重试 */
  const canRetry = pendingRetry && answerable;
  const isGuidance = interaction.kind === 'guidance';
  const progress = (draft?: AskUserDraft) =>
    draft?.disposition === 'skipped' ? '已忽略' : undefined;

  const draftOf = (q: AskUserQuestion): AskUserDraft => interaction.drafts[q.questionId] ?? EMPTY_DRAFT;
  const isComposing = (event: React.KeyboardEvent) =>
    event.nativeEvent.isComposing || composingRef.current;

  function pickOption(q: AskUserQuestion, label: string) {
    if (!editable) return;
    // 单选（v2）：覆盖为唯一选择、清空自由文本；**不自动翻页**（§7.3）
    onDraft(interaction.interactionId, q.questionId, {
      labels: [label],
      freeText: '',
      disposition: 'unanswered',
    });
  }
  function updateFreeText(q: AskUserQuestion, text: string) {
    if (!editable) return;
    const current = draftOf(q);
    onDraft(interaction.interactionId, q.questionId, {
      labels: q.multiSelect ? current.labels : text.trim() ? [] : current.labels,
      freeText: text,
      disposition: 'unanswered',
    });
  }
  /** 方向键只在选项列表内移动焦点（不进入输入框、不改变选择） */
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
    if (!answer || answer.skipped || (!answer.labels.length && !answer.freeText?.trim()))
      return '（已跳过）';
    const parts: string[] = [];
    if (answer.labels.length) parts.push(answer.labels.join('、'));
    if (answer.freeText?.trim()) parts.push(answer.freeText.trim());
    return parts.join('；') || '（已跳过）';
  }

  const answered = interaction.status === 'answered';
  const interrupted = interaction.status === 'interrupted' || (interaction.status === 'waiting' && !active && !isGuidance);
  /**
   * 追问卡精简（RAG-QUALITY v1.1 · PLAN §4.4）：只压掉重复信息，不改状态机。
   * - 顶行合并为「标签 + 题干标签 + 分页」，不再单独渲染一张卡标题；
   * - 题干与标签含义相同时不重复显示；`intro` 与可见标签/题干逐字相同时不再重复一遍；
   * - 异常与待重试状态（提交中/已忽略/待重试/历史多选/预览）保留必要说明。
   */
  const kindLabel = isGuidance ? '教材详解' : source === 'rag' ? '教材追问' : '追问（本地模拟）';
  const headerText = question?.header?.trim() ?? '';
  const promptText = question?.prompt?.trim() ?? '';
  const showHeaderChip =
    !!headerText &&
    headerText !== kindLabel &&
    headerText !== '追问' &&
    headerText !== '详解方向' &&
    headerText !== promptText;
  const introText = interaction.intro?.trim() ?? '';
  // 题干提示与可见标签/题干逐字相同时不再重复一遍（普通状态）
  const showIntro = !!introText && ![kindLabel, headerText, promptText].includes(introText);
  const answerableState =
    interaction.status === 'waiting' || interaction.status === 'submitting' || interaction.status === 'failed';
  const headContent = (
    <>
      {isGuidance ? (
        <Sparkles size={14} aria-hidden="true" />
      ) : (
        <MessageCircleQuestion size={14} aria-hidden="true" />
      )}
      <span>
        {kindLabel}
        {interaction.status === 'submitting' && ' · 提交中'}
        {answered && (isGuidance ? ' · 已发起' : ' · 已回答')}
        {interrupted && ' · 已忽略'}
      </span>
    </>
  );

  return (
    <div
      className={`chat-ask-card ${interaction.status}${active ? ' active' : ''}${
        isGuidance ? ' guidance' : ''
      }`}
      data-status={interaction.status}
      data-kind={isGuidance ? 'guidance' : 'clarification'}
    >
      {(!answerableState || !question) && <p className="chat-ask-head">{headContent}</p>}
      {showIntro && <p className="chat-ask-intro">{introText}</p>}
      {pendingRetry && (
        <p className="chat-ask-note" role="status">
          <AlertCircle size={12} />
          上次提交结果尚未确认：改选、输入与忽略已锁定，只能按原答案精确重试（不会重复处理）。
        </p>
      )}
      {legacyMultiSelect && (
        <p className="chat-ask-note" role="status">
          历史多选卡：仅按原记录只读展示，不支持在此编辑或重新提交。
        </p>
      )}

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

      {interrupted && !answered && (
        <p className="chat-ask-note" role="status">
          {isGuidance
            ? '详解引导已忽略：未调用教材追问、取消或任何模型。'
            : '本轮等待已失效（取消或刷新后上下文不再可用），此卡不可提交；可重试原问题开启新的尝试。'}
        </p>
      )}

      {(interaction.status === 'waiting' ||
        interaction.status === 'submitting' ||
        interaction.status === 'failed') &&
        question && (
          <>
            <header className="chat-ask-pager">
              {/* 顶行合并：标签 + 题干标签 + 分页（不再单独渲染卡标题，避免同义重复） */}
              <span className="chat-ask-kind">{headContent}</span>
              {showHeaderChip && <span className="chat-ask-label">{headerText}</span>}
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
            <section
              className="chat-ask-question"
              aria-label={`${isGuidance ? '详解方向' : '追问'} ${activeIndex + 1}/${total}${
                question.header ? `：${question.header}` : ''
              }`}
            >
              <p className="chat-ask-prompt">{question.prompt}</p>
              <div
                ref={optionsRef}
                className="chat-ask-options"
                role="group"
                aria-label={question.prompt}
              >
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
                          // 中文输入法组合期间不触发确认
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
                      maxLength={source === 'rag' ? 2000 : undefined}
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
                        if (isComposing(event)) return; // 组合期间不触发确认
                        event.preventDefault();
                        onContinue(interaction.interactionId);
                      }}
                    />
                  </label>
                )}
              </div>
              {progress(draftOf(question)) && (
                <p className="chat-ask-question-state" role="status">
                  {progress(draftOf(question))}
                </p>
              )}
              {interaction.status === 'failed' && interaction.error && (
                <div className="chat-ask-error" role="alert">
                  <CircleAlert size={13} />
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
                {pendingRetry
                  ? '结果未确认：仅可重试原提交'
                  : legacyMultiSelect
                    ? '历史多选卡只读'
                    : '↑↓ 选项 · Enter 选中 · Enter 继续 · Shift+Enter 换行'}
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
                {canRetry ? '重试提交' : isGuidance ? '继续详解' : '继续'}
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
      {interaction.status === 'submitting' && !active && (
        <p className="chat-ask-note">
          <AlertCircle size={12} /> 正在提交回答…
        </p>
      )}
    </div>
  );
}
