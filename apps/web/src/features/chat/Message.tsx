'use client';
import { Fragment, useEffect, useState } from 'react';
import { Check, Copy, FileText, Pencil, RotateCcw } from 'lucide-react';
import { ThinkingOrb } from './vendor/thinking-orbs';
import type { AskUserDraft, ChatMessage } from '@/contracts/chat';
import { ReasoningDisclosure } from './ReasoningDisclosure';
import { AnswerMarkdown } from './AnswerMarkdown';
import { StreamingMarkdown } from './StreamingMarkdown';
import { TraceStages } from './TraceStages';
import { AskUserCard } from './AskUserCard';
import { ToolProcessPanel } from './ToolProcessPanel';
import { formatTokenCount } from './context-usage';

/**
 * 单条消息（骨架版）：用户气泡 / 助手卡（推理、阶段、工具过程、产物入口、追问卡）。
 * 无课程归属与业务模块入口（骨架只保留对话与 Agent）。
 */
export function Message({
  message,
  copied,
  onCopy,
  onRetry,
  onReuse,
  ask,
  onOpenArtifact,
}: {
  message: ChatMessage;
  copied: boolean;
  onCopy: () => void;
  onRetry?: () => void;
  onReuse: () => void;
  ask?: {
    waitingId: string | null;
    submitting: boolean;
    focus: { interactionId: string; questionId: string } | null;
    notice: { interactionId: string; text: string } | null;
    onDraft(interactionId: string, questionId: string, draft: AskUserDraft): void;
    onFocusChange(interactionId: string, questionId: string): void;
    onContinue(interactionId: string): void;
    onSkip(interactionId: string): void;
  };
  onOpenArtifact?: (artifactId: string) => void;
}) {
  if (message.role === 'user')
    return (
      <div className="chat-row user" data-message-id={message.id}>
        <div className="chat-bubble user">{message.content}</div>
        <div className="chat-msg-actions">
          <button aria-label={copied ? '已复制' : '复制提问'} onClick={onCopy}>
            {copied ? <Check size={13} /> : <Copy size={13} />}
          </button>
          <button aria-label="复用此提问到输入框" onClick={onReuse}>
            <Pencil size={13} />
          </button>
        </div>
      </div>
    );
  return (
    <article className="chat-row assistant" data-message-id={message.id}>
      <div className="chat-bubble assistant">
        <ReasoningDisclosure
          text={message.reasoning}
          working={message.status === 'streaming' && !!message.reasoning?.trim()}
          autoExpand={message.status === 'streaming' && !message.content?.trim()}
        >
          <span className="chat-assistant-mark">
            <ThinkingOrb
              state={
                message.status === 'streaming'
                  ? message.content
                    ? 'solving'
                    : 'working'
                  : 'breathing'
              }
              size={20}
              superSample={3}
              speed={message.status === 'streaming' ? 1 : 0.5}
              theme="light"
              style={{ width: 18, height: 18 }}
              aria-label="智启课源"
            />
          </span>
          <strong className={message.status === 'streaming' ? 'chat-thinking-label' : undefined}>
            {message.status === 'streaming'
              ? message.content?.trim()
                ? '正在回答'
                : message.reasoning
                  ? '正在推理'
                  : '正在生成'
              : message.status === 'error'
                ? '生成失败'
                : message.status === 'stopped'
                  ? '生成中断'
                  : '已完成'}
          </strong>
          {message.startedAt && (
            <TurnDuration startedAt={message.startedAt} finishedAt={message.finishedAt} />
          )}
          {message.usage?.inputTokens != null && (
            <span
              className="chat-usage"
              title="输入 = 最近一次模型调用的上下文快照（含系统提示/历史/工具结果）；输出 = 本轮累计"
            >
              ↑{formatTokenCount(message.usage.inputTokens)} ↓
              {formatTokenCount(message.usage.outputTokens ?? 0)}
            </span>
          )}
        </ReasoningDisclosure>
        <ToolProcessPanel toolCalls={message.toolCalls} />
        <TraceStages stages={message.stages} />
        {!!message.artifacts?.length && (
          <div className="chat-artifact-chips" role="list" aria-label="本轮产物">
            {message.artifacts.map((artifact) => (
              <button
                key={artifact.id}
                type="button"
                onClick={() => onOpenArtifact?.(artifact.id)}
                title={artifact.title}
              >
                <FileText size={13} />
                <span className="chat-artifact-chip-title">{artifact.title}</span>
                <small>{artifact.kind.toUpperCase()}</small>
              </button>
            ))}
          </div>
        )}
        {message.content ? (
          <div className="chat-answer-content">
            {message.status === 'streaming' ? (
              <StreamingMarkdown text={message.content} rawClassName="chat-answer-raw" />
            ) : (
              <AnswerMarkdown text={message.content} />
            )}
          </div>
        ) : message.reasoning ? null : message.status === 'streaming' ? (
          <p className="chat-status-text" role="status">
            {message.stageLabel ?? '正在等待模型回复'}
            <span className="chat-stream-dot">…</span>
          </p>
        ) : null}
        {message.asks?.map((interaction) => (
          <Fragment key={interaction.interactionId}>
            {ask ? (
              <AskUserCard
                interaction={interaction}
                active={ask.waitingId === interaction.interactionId}
                submitting={ask.submitting}
                focusQuestionId={
                  ask.focus?.interactionId === interaction.interactionId
                    ? ask.focus.questionId
                    : null
                }
                notice={
                  ask.notice?.interactionId === interaction.interactionId
                    ? ask.notice.text
                    : null
                }
                onDraft={ask.onDraft}
                onFocusChange={ask.onFocusChange}
                onContinue={ask.onContinue}
                onSkip={ask.onSkip}
              />
            ) : (
              <AskUserCard
                interaction={interaction}
                active={false}
                submitting={false}
                onDraft={() => undefined}
                onFocusChange={() => undefined}
                onContinue={() => undefined}
                onSkip={() => undefined}
              />
            )}
          </Fragment>
        ))}
        {message.error && (
          <p className="chat-error" role="alert">
            {message.error.message}（{message.error.code}）
          </p>
        )}
        <div className="chat-msg-actions">
          {message.content && (
            <button aria-label={copied ? '已复制' : '复制回答'} onClick={onCopy}>
              {copied ? <Check size={13} /> : <Copy size={13} />}
            </button>
          )}
          {onRetry && message.status !== 'streaming' && (
            <button aria-label="重试此轮" onClick={onRetry}>
              <RotateCcw size={13} />
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

/** 轮次耗时（流式滴答 / 终态冻结）。 */
function TurnDuration({ startedAt, finishedAt }: { startedAt?: string; finishedAt?: string }) {
  const [currentTime, setCurrentTime] = useState(() => Date.now());
  const running = !finishedAt;
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setCurrentTime(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  const start = new Date(startedAt ?? 0).getTime();
  const end = finishedAt ? new Date(finishedAt).getTime() : currentTime;
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  if (!Number.isFinite(seconds)) return null;
  return <span className="chat-turn-duration">{seconds}s</span>;
}
