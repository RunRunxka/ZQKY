'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { LoaderCircle, Paperclip, SendHorizontal, Square, CircleCheck, CircleX, Wrench } from 'lucide-react';
import { AnswerMarkdown } from './AnswerMarkdown';
import { StreamingMarkdown } from './StreamingMarkdown';
import { ModelSelector } from '@/features/model-settings/ModelSelector';
import { useModelCatalog } from '@/features/model-settings/useModelCatalog';
import {
  confirmAgent,
  streamAgent,
  uploadAgent,
  type AgentAttachment,
  type AgentConfirmPayload,
} from '@/services/agent-stream';

/** Agent 单条消息 / 过程事件（本地态，不写 chat store，避免被现有 flush/repository 误处理）。 */
interface AgentToolStep {
  callId: string;
  name: string;
  status: 'running' | 'done' | 'error';
  output?: string;
}

interface AgentConfirmState {
  confirmId: string;
  payload: AgentConfirmPayload;
  decision: 'pending' | 'approve' | 'reject';
}

interface AgentMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  streaming?: boolean;
  steps?: AgentToolStep[];
  confirm?: AgentConfirmState;
  error?: { code: string; message: string };
}

function newId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/**
 * Agent 工作台面板（Agent 化改造 A5）：一句话（可附文件）驱动教学闭环。
 *
 * 独立于现有 ChatService 问答：自建消息状态与 threadId，走 /api/v1/agent/*；
 * 文本用 AnswerMarkdown/StreamingMarkdown 渲染，工具过程与写操作确认卡行内展示。
 * 写操作（confirm/apply）必须经教师点「确认」后才由后端落库（AI 只进候选红线）。
 */
export function AgentPanel() {
  const { catalog, loading: catalogLoading } = useModelCatalog();
  const [modelProfileId, setModelProfileId] = useState<string | null>(null);
  const effectiveProfileId = modelProfileId ?? catalog?.defaultChatProfileId ?? null;

  const [threadId, setThreadId] = useState<string>(() => newId());
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [attachments, setAttachments] = useState<AgentAttachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [running, setRunning] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const patchMessage = useCallback((id: string, patch: Partial<AgentMessage>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));
  }, []);

  const patchStep = useCallback((id: string, callId: string, patch: Partial<AgentToolStep>) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === id
          ? {
              ...m,
              steps: (m.steps ?? []).map((s) => (s.callId === callId ? { ...s, ...patch } : s)),
            }
          : m,
      ),
    );
  }, []);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        const uploaded = await uploadAgent(file);
        setAttachments((prev) => [
          ...prev,
          {
            assetId: uploaded.assetId,
            fileName: uploaded.fileName,
            mediaType: uploaded.mediaType,
            kind: 'auto',
          },
        ]);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '上传失败。';
      setMessages((prev) => [
        ...prev,
        { id: newId(), role: 'assistant', text: '', error: { code: 'UPLOAD_FAILED', message } },
      ]);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  function runStream(input: Parameters<typeof streamAgent>[0], assistantId: string) {
    const controller = new AbortController();
    abortRef.current = controller;
    setRunning(true);
    return streamAgent(
      { ...input, signal: controller.signal },
      {
        onText: (delta) =>
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, text: m.text + delta } : m)),
          ),
        onToolCall: (call) =>
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    steps: [
                      ...(m.steps ?? []),
                      { callId: call.callId, name: call.name, status: 'running' as const },
                    ],
                  }
                : m,
            ),
          ),
        onToolResult: (result) =>
          patchStep(assistantId, result.callId, { status: 'done', output: result.output }),
        onWaitConfirm: (confirm) =>
          patchMessage(assistantId, {
            confirm: { confirmId: confirm.confirmId, payload: confirm.payload, decision: 'pending' },
          }),
        onEnd: () => patchMessage(assistantId, { streaming: false }),
        onError: (error) =>
          patchMessage(assistantId, {
            streaming: false,
            error: { code: error.code, message: error.message },
          }),
      },
    )
      .catch((error) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          patchMessage(assistantId, { streaming: false });
          return;
        }
        const e = error as { code?: string; message?: string };
        patchMessage(assistantId, {
          streaming: false,
          error: { code: e.code ?? 'REQUEST_FAILED', message: e.message ?? '请求失败。' },
        });
      })
      .finally(() => {
        setRunning(false);
        abortRef.current = null;
      });
  }

  async function submit() {
    const text = draft.trim();
    if ((!text && attachments.length === 0) || running || !effectiveProfileId) return;
    const requestId = newId();
    const assistantId = newId();
    const userText =
      text || `请处理随附的 ${attachments.length} 个文件（${attachments.map((a) => a.fileName).join('、')}）。`;
    const sentAttachments = attachments;
    setMessages((prev) => [
      ...prev,
      { id: newId(), role: 'user', text: userText },
      { id: assistantId, role: 'assistant', text: '', streaming: true, steps: [] },
    ]);
    setDraft('');
    setAttachments([]);
    await runStream(
      {
        requestId,
        threadId,
        message: userText,
        modelProfileId: effectiveProfileId,
        attachments: sentAttachments,
      },
      assistantId,
    );
  }

  async function decideConfirm(message: AgentMessage, decision: 'approve' | 'reject') {
    if (!message.confirm || message.confirm.decision !== 'pending' || !effectiveProfileId) return;
    patchMessage(message.id, { confirm: { ...message.confirm, decision } });
    const assistantId = newId();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: 'assistant', text: '', streaming: true, steps: [] },
    ]);
    const controller = new AbortController();
    abortRef.current = controller;
    setRunning(true);
    try {
      await confirmAgent(
        {
          submissionId: `agent-${message.confirm.confirmId}`,
          requestId: newId(),
          threadId,
          modelProfileId: effectiveProfileId,
          confirmId: message.confirm.confirmId,
          decision,
          signal: controller.signal,
        },
        {
          onText: (delta) =>
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, text: m.text + delta } : m)),
            ),
          onToolCall: (call) =>
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      steps: [
                        ...(m.steps ?? []),
                        { callId: call.callId, name: call.name, status: 'running' as const },
                      ],
                    }
                  : m,
              ),
            ),
          onToolResult: (result) =>
            patchStep(assistantId, result.callId, { status: 'done', output: result.output }),
          onEnd: () => patchMessage(assistantId, { streaming: false }),
          onError: (error) =>
            patchMessage(assistantId, {
              streaming: false,
              error: { code: error.code, message: error.message },
            }),
        },
      );
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) {
        const e = error as { code?: string; message?: string };
        patchMessage(assistantId, {
          streaming: false,
          error: { code: e.code ?? 'REQUEST_FAILED', message: e.message ?? '请求失败。' },
        });
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }

  function stop() {
    abortRef.current?.abort();
  }

  function resetSession() {
    abortRef.current?.abort();
    setMessages([]);
    setAttachments([]);
    setThreadId(newId());
  }

  const confirmSummary = (payload: AgentConfirmPayload): string => {
    const summary = payload.summary ?? payload.prompt ?? payload.action;
    return typeof summary === 'string' && summary ? summary : '确认执行此写操作？';
  };

  const canSend = useMemo(
    () => !running && !catalogLoading && !!effectiveProfileId && (draft.trim().length > 0 || attachments.length > 0),
    [running, catalogLoading, effectiveProfileId, draft, attachments.length],
  );

  return (
    <div className="agent-panel">
      <header className="agent-panel-head">
        <div>
          <h2>教学 Agent</h2>
          <p>一句话（可附文件）驱动教学闭环：导入、学情分析、针对练习、教案调整。写操作需你确认后才落库。</p>
        </div>
        <button type="button" className="agent-reset" onClick={resetSession}>
          新会话
        </button>
      </header>

      <div className="agent-messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="agent-empty">
            <p>试试：</p>
            <ul>
              <li>「这是期中成绩单，帮我出学情分析」（附 Excel）</li>
              <li>「三年级二班有哪些需巩固的知识点」</li>
              <li>「基于最近的学情分析给班上出一份针对练习」</li>
            </ul>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`agent-msg ${m.role}`}>
            {m.role === 'user' ? (
              <div className="agent-msg-user">{m.text}</div>
            ) : (
              <div className="agent-msg-body">
                {m.steps && m.steps.length > 0 && (
                  <ul className="agent-steps">
                    {m.steps.map((s) => (
                      <li key={s.callId} data-status={s.status}>
                        <Wrench size={12} aria-hidden />
                        <span className="agent-step-name">{s.name}</span>
                        {s.status === 'running' && <LoaderCircle size={12} className="chat-tool-spin" aria-hidden />}
                        {s.output && <span className="agent-step-output">{s.output}</span>}
                      </li>
                    ))}
                  </ul>
                )}
                {m.text &&
                  (m.streaming ? <StreamingMarkdown text={m.text} /> : <AnswerMarkdown text={m.text} />)}
                {m.streaming && !m.text && (!m.steps || m.steps.length === 0) && (
                  <p className="agent-thinking">
                    <LoaderCircle size={13} className="chat-tool-spin" aria-hidden /> 正在思考…
                  </p>
                )}
                {m.confirm && (
                  <div className="agent-confirm-card" data-decision={m.confirm.decision}>
                    <p className="agent-confirm-title">需要你的确认</p>
                    <p className="agent-confirm-summary">{confirmSummary(m.confirm.payload)}</p>
                    {m.confirm.decision === 'pending' ? (
                      <div className="agent-confirm-actions">
                        <button
                          type="button"
                          className="agent-confirm-approve"
                          onClick={() => decideConfirm(m, 'approve')}
                        >
                          <CircleCheck size={14} aria-hidden /> 确认执行
                        </button>
                        <button
                          type="button"
                          className="agent-confirm-reject"
                          onClick={() => decideConfirm(m, 'reject')}
                        >
                          <CircleX size={14} aria-hidden /> 放弃
                        </button>
                      </div>
                    ) : (
                      <p className="agent-confirm-done">
                        {m.confirm.decision === 'approve' ? '已确认，正在执行…' : '已放弃，未执行写操作。'}
                      </p>
                    )}
                  </div>
                )}
                {m.error && (
                  <p className="agent-error" role="alert">
                    {m.error.message}（{m.error.code}）
                  </p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <footer className="agent-composer">
        {attachments.length > 0 && (
          <ul className="agent-attach-row">
            {attachments.map((a) => (
              <li key={a.assetId} className="agent-attach-chip">
                <Paperclip size={12} aria-hidden /> {a.fileName}
              </li>
            ))}
          </ul>
        )}
        <div className="agent-composer-row">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            hidden
            onChange={(e) => handleFiles(e.target.files)}
          />
          <button
            type="button"
            className="agent-attach-btn"
            aria-label="添加附件"
            disabled={uploading || running}
            onClick={() => fileInputRef.current?.click()}
          >
            {uploading ? <LoaderCircle size={16} className="chat-tool-spin" aria-hidden /> : <Paperclip size={16} aria-hidden />}
          </button>
          <textarea
            value={draft}
            placeholder="对教学 Agent 说一句话…（可附文件：成绩单 / 原卷 DOCX / 名单 / 题目）"
            rows={2}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                void submit();
              }
            }}
          />
          <div className="agent-composer-right">
            <ModelSelector
              catalog={catalog}
              value={modelProfileId}
              onChange={(id) => setModelProfileId(id)}
              presentation="popover"
            />
            {running ? (
              <button type="button" className="agent-stop" aria-label="停止" onClick={stop}>
                <Square size={15} aria-hidden />
              </button>
            ) : (
              <button
                type="button"
                className="agent-send"
                aria-label="发送"
                disabled={!canSend}
                onClick={() => void submit()}
              >
                <SendHorizontal size={15} aria-hidden />
              </button>
            )}
          </div>
        </div>
      </footer>
    </div>
  );
}
