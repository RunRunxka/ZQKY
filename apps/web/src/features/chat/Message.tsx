'use client';
import { Fragment, useEffect, useState } from 'react';
import { Check, Copy, FileText, Pencil, Plus, RotateCcw } from 'lucide-react';
import { ThinkingOrb } from './vendor/thinking-orbs';
import type { AskUserAnswer, AskUserDraft, ChatMessage } from '@/contracts/chat';
import { CHAT_CAPABILITIES, capabilityAvailableInReal } from '@/services/capability-catalog';
import { conversationProjection } from './model/context-budget';
import { formatTurnDuration, turnDurationSeconds } from './model/trace-timing';
import { ReasoningDisclosure } from './ReasoningDisclosure';
import { AnswerMarkdown } from './AnswerMarkdown';
import { StreamingMarkdown } from './StreamingMarkdown';
import { TraceStages } from './TraceStages';
import { AskUserCard } from './AskUserCard';
import { ToolProcessPanel } from './ToolProcessPanel';

/** 来源与上下文条目（S3 引用/来源定位）：来自本轮冻结的扩展快照，只如实展示 */
interface MessageSourceItem {
  key: string;
  label: string;
  detail: string;
}

function collectSources(message: ChatMessage): MessageSourceItem[] {
  const ext = message.extensions;
  if (!ext) return [];
  const items: MessageSourceItem[] = [];
  // 本轮模式（历史能力值降级展示，UX-PERF-CLOSEOUT v1）：轮次快照里的 capability 一律
  // 如实展示；入口已被移除（如「更多能力」三项）或当前未接入时**明确标注降级原因**，
  // 绝不静默丢弃、不改写数据、不冒充为当前可用模式。
  const capability = ext.capability;
  if (capability?.value) {
    const known = CHAT_CAPABILITIES.find((cap) => cap.value === capability.value);
    items.push({
      key: `capability:${capability.value}`,
      label: `模式 · ${(known?.label ?? capability.label) || capability.value}`,
      detail: !known
        ? '该模式入口已停用（随「更多能力」一并移除），此处仅按历史轮次快照如实展示，历史记录保持可读。'
        : capabilityAvailableInReal(known.value)
          ? '本轮按该模式发起（轮次快照）。'
          : '该模式当前未接入，仅按轮次快照如实展示，不代表现在可以发起。',
    });
  }
  if (ext.persona)
    items.push({
      key: `persona:${ext.persona.id}`,
      label: `角色 · ${ext.persona.name}`,
      detail: '本轮启用的会话级角色人设（演示目录），随轮次快照冻结。',
    });
  (ext.knowledge ?? []).forEach((entry) =>
    items.push({
      key: `knowledge:${entry.id}`,
      label: `知识 · ${entry.name}`,
      detail: '声明的检索范围（演示目录）；本轮未执行真实检索，不假装返回文档内容。',
    }),
  );
  (ext.historyRefs ?? []).forEach((entry) =>
    items.push({
      key: `history:${entry.id}`,
      label: `会话引用 · ${entry.title}`,
      detail: '纳入本轮上下文说明的历史会话。',
    }),
  );
  (ext.attachments ?? []).forEach((entry, index) =>
    items.push({
      key: `attachment:${entry.filename}:${index}`,
      label: `附件 · ${entry.filename}`,
      detail: '仅携带文件名/类型/大小元数据；未读取文件内容（当前无解析服务）。',
    }),
  );
  (ext.mcps ?? []).forEach((entry) =>
    items.push({
      key: `mcp:${entry.id}`,
      label: `MCP · ${entry.name}`,
      detail: entry.description || '本轮载入的扩展（模拟执行，明确标识）。',
    }),
  );
  (ext.skills ?? []).forEach((entry) =>
    items.push({
      key: `skill:${entry.id}`,
      label: `Skill · ${entry.name}`,
      detail: entry.description || '技能上下文已加载（非远程工具调用）。',
    }),
  );
  return items;
}

/**
 * 轮级耗时（S3）：流式逐秒滴答、完成后冻结（对照参考 trace-timing 的单一状态行设计）。
 * R25：只渲染一处（标题区），正文/推理/工具/追问/产物期间持续可见；
 * 全部结束路径（end/error/停止/断流/恢复）都写入 finishedAt，终态后冻结。
 */
function TurnDuration({ startedAt, finishedAt }: { startedAt?: string; finishedAt?: string }) {
  const [, setTick] = useState(0);
  const streaming = !finishedAt;
  useEffect(() => {
    if (!streaming || !startedAt) return;
    const timer = window.setInterval(() => setTick((n) => n + 1), 1000);
    return () => window.clearInterval(timer);
  }, [streaming, startedAt]);
  if (!startedAt) return null;
  return (
    <span className="chat-turn-duration">
      {formatTurnDuration(turnDurationSeconds(startedAt, finishedAt))}
    </span>
  );
}

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
  /** 追问交互句柄：等待回答的卡可交互，草稿与提交路由到 store */
  ask?: {
    waitingId: string | null;
    submitting: boolean;
    onDraft(interactionId: string, questionId: string, draft: AskUserDraft): void;
    onSubmit(interactionId: string, answers: AskUserAnswer[]): void;
  };
  /** S3：点击产物入口打开右侧结果工作区 */
  onOpenArtifact?: (artifactId: string) => void;
}) {
  // R12 补充：复制等操作的可用性按统一投影判断——纯追问续答有正文即可复制，
  // 真正的空白占位不显示无意义操作
  const copyableText = conversationProjection(message);
  // S3 引用/来源定位：本轮冻结快照中的来源条目（知识/会话引用/附件/扩展）
  const sources = collectSources(message);
  if (message.role === 'user')
    return (
      // data-message-id：来源深链按 id 在本会话内定位该条消息（R-10）
      <div className="chat-row user" data-message-id={message.id}>
        <div className="chat-bubble user">{message.content}</div>
        {/* S3 消息操作（对照参考 ChatMessageList 悬停操作）：复制 / 复用到输入框 */}
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
    // data-message-id：来源深链按 id 在本会话内定位该条消息（R-10）
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
          {/* R25：耗时唯一渲染点——只要有开始时间就显示（流式滴答/终态冻结），
              修复“正文出现后耗时而从状态行消失、部分终态继续计时”的问题 */}
          {message.startedAt && (
            <TurnDuration startedAt={message.startedAt} finishedAt={message.finishedAt} />
          )}
        </ReasoningDisclosure>
        {/* 工具/技能执行过程：对照原版位于正文之前，按 callId 原地更新，手动展开态不被正文增量重置 */}
        <ToolProcessPanel toolCalls={message.toolCalls} />
        {/* S4 轮内阶段序列（planning→…→writing 等）：进行中可见，终态收起为紧凑消息 */}
        <TraceStages stages={message.stages} />
        {/* S3：产物入口（关联结果定位到右侧结果工作区） */}
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
          /* R25：等待占位不再重复渲染耗时（标题区已有唯一耗时节点） */
          <p className="chat-status-text" role="status">
            {message.stageLabel ?? '正在等待模型回复'}
            <span className="chat-stream-dot">…</span>
          </p>
        ) : null}
        {/* 追问卡与各自续写按序渲染：正文→提问→回答记录→续写（同轮顺序） */}
        {message.asks?.map((interaction) => (
          <Fragment key={interaction.interactionId}>
            {ask ? (
              <AskUserCard
                interaction={interaction}
                active={ask.waitingId === interaction.interactionId}
                submitting={ask.submitting}
                onDraft={ask.onDraft}
                onSubmit={ask.onSubmit}
              />
            ) : (
              <AskUserCard
                interaction={interaction}
                active={false}
                submitting={false}
                onDraft={() => undefined}
                onSubmit={() => undefined}
              />
            )}
            {interaction.followUp && <AnswerMarkdown text={interaction.followUp} />}
          </Fragment>
        ))}
        {message.status === 'streaming' && message.processNote && (
          <p className="chat-process-note">{message.processNote}</p>
        )}
        {/* S3 引用/来源定位：本轮冻结快照的来源条目，展开定位详情（只如实展示，不伪造检索） */}
        {sources.length > 0 && (
          <details className="chat-sources">
            <summary>
              <FileText size={12} />
              来源与上下文（{sources.length}）
            </summary>
            <ul>
              {sources.map((source) => (
                <li key={source.key}>
                  <strong>{source.label}</strong>
                  <small>{source.detail}</small>
                </li>
              ))}
            </ul>
          </details>
        )}

        {message.status === 'stopped' && (
          <span className="small-badge">
            {message.finishReason === 'client-stop' ? '已停止' : '已中断'}
          </span>
        )}
        {message.finishReason === 'length' && (
          <p className="chat-status-text">已达到输出上限，回答可能不完整。</p>
        )}
        {message.status === 'error' && (
          <div className="chat-error" role="alert">
            <p>
              {message.error?.message}（{message.error?.code}）
            </p>
            {onRetry && <button onClick={onRetry}>重试</button>}
          </div>
        )}
        {message.superseded && <span className="small-badge">之前的尝试 · 已保留</span>}
        <footer className="chat-bubble-foot">
          <span title={message.modelLabel}>{message.modelLabel}</span>
          {message.usage && (
            <span>
              输入 {message.usage.inputTokens ?? '未知'} · 输出{' '}
              {message.usage.outputTokens ?? '未知'} tokens
            </span>
          )}
          <span className="chat-flex-spacer" />
          {copyableText.trim() && (
            <button aria-label={copied ? '已复制' : '复制回答'} onClick={onCopy}>
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </button>
          )}
          {message.status === 'stopped' && onRetry && (
            <button aria-label="重新生成" onClick={onRetry}>
              <RotateCcw size={14} />
            </button>
          )}
          {message.status !== 'streaming' && (
            <button aria-label="复制问题到输入框" onClick={onReuse}>
              <Plus size={14} />
            </button>
          )}
        </footer>
      </div>
    </article>
  );
}
