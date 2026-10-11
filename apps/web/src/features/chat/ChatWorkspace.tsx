'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDown, Paperclip, PanelRight, Plus, Square, X, Brain } from 'lucide-react';
import { WorkspaceShell } from '@/components/layout/WorkspaceShell';
import { useEntrance } from '@/components/motion/useEntrance';
import { ChatProvider, useChatStore } from './model/ChatContext';
import { useModelCatalog } from '@/features/model-settings/useModelCatalog';
import { ModelSelector } from '@/features/model-settings/ModelSelector';
import { REASONING_EFFORT_LABELS, REASONING_EFFORT_VALUES } from '@/contracts/model-settings';
import { uploadAgent } from '@/services/agent-stream';
import { Message } from './Message';
import { SessionPanel } from './SessionPanel';
import { InfoPanel } from './InfoPanel';
import { ArtifactPanelItem, WorkspacePanel } from './ArtifactPanel';
import { ComposerContextChips } from './ComposerContextChips';
import type { PendingAttachment } from '@/services/doc-attachments';
import { fileToPendingAttachment, selectAttachmentFiles, ATTACHMENT_ACCEPT } from '@/services/doc-attachments';
import './styles/chat.css';
import './styles/chat-home.css';

/**
 * 对话工作台（推倒重做骨架版）：会话 + 消息 + 输入区（附件/上下文小圈/思考强度/模型）+ 右侧产物区。
 * 发送默认走 Agent 通道（agent-chat-service）；仅保留对话与 Agent，无业务模块入口。
 */
export function ChatWorkspace() {
  return (
    <ChatProvider>
      <ChatPage />
    </ChatProvider>
  );
}

function ChatPage() {
  const store = useChatStore();
  const entranceRef = useRef<HTMLDivElement>(null);
  useEntrance(entranceRef, { preset: 'page', enabled: store.ready });
  const { catalog, error: catalogError } = useModelCatalog();
  const [modelPreference, setModelPreference] = useState<string | null>(null);
  const [draftAttachments, setDraftAttachments] = useState<PendingAttachment[]>([]);
  const [uploadedRefs, setUploadedRefs] = useState<
    Array<{ filename: string; kind: 'image' | 'doc'; size: number; mimeType?: string; assetId: string }>
  >([]);
  const [uploading, setUploading] = useState(false);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const [reasoningEffort, setReasoningEffort] = useState<string | null>(null);
  const [panelView, setPanelView] = useState<'workspace' | null>(null);
  const [artifactKey, setArtifactKey] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const [following, setFollowing] = useState(true);

  useEffect(() => {
    void store.init();
  }, [store]);

  const profile = useMemo(() => {
    const selectedId = modelPreference ?? store.modelProfileId ?? catalog?.defaultChatProfileId;
    return catalog?.profiles.find((p) => p.id === selectedId) ?? null;
  }, [modelPreference, store.modelProfileId, catalog]);
  const selection = useMemo(() => {
    const valid = !!profile?.connection?.hasCredential && (profile.purpose === 'chat' || profile.purpose === null);
    return profile && valid
      ? {
          id: profile.id,
          modelLabel: `${profile.displayName} · ${profile.modelId}`,
          contextTokens: profile.contextTokens,
          maxOutputTokens: profile.maxOutputTokens,
        }
      : null;
  }, [profile]);

  useEffect(() => {
    if (!store.ready || !following) return;
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight });
  }, [store.messages, store.ready, following]);

  const hasMessages = store.messages.length > 0;
  const activeTitle =
    store.conversations.find((c) => c.id === store.activeId)?.title?.trim() || '新的对话';

  function handleFiles(files: FileList | File[] | null) {
    if (!files) return;
    const list = Array.from(files);
    const existingBytes = draftAttachments.reduce((total, item) => total + item.size, 0);
    const { accepted, rejected } = selectAttachmentFiles(list, existingBytes);
    if (rejected.length > 0) {
      const first = rejected[0]!;
      setAttachmentError(
        first.reason === 'too_large'
          ? `文件过大（上限 20MB）：${first.name}`
          : first.reason === 'quota'
            ? '附件总量超出配额（25MB）。'
            : `不支持的文件类型：${first.name}`,
      );
    }
    if (accepted.length === 0) return;
    void (async () => {
      setUploading(true);
      try {
        for (const file of accepted) {
          const attachment = await fileToPendingAttachment(file);
          setDraftAttachments((prev) => [...prev, attachment]);
          const uploaded = await uploadAgent(file);
          setUploadedRefs((prev) => [
            ...prev,
            {
              filename: attachment.filename,
              kind: attachment.kind,
              size: attachment.size,
              ...(attachment.mimeType ? { mimeType: attachment.mimeType } : {}),
              assetId: uploaded.assetId,
            },
          ]);
        }
      } catch (error) {
        setAttachmentError(`附件上传失败：${(error as Error).message ?? '未知错误'}`);
      } finally {
        setUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
    })();
  }

  function removeAttachment(index: number) {
    setDraftAttachments((prev) => prev.filter((_, i) => i !== index));
    setUploadedRefs((prev) => prev.filter((_, i) => i !== index));
  }

  function submit() {
    if (store.sending || store.waitingInteractionId) {
      // 追问等待中：主输入框走追问提交
      const text = store.draft.trim();
      if (store.waitingInteractionId && text) void store.submitComposerReply(text);
      return;
    }
    const text = store.draft.trim();
    if (!text && uploadedRefs.length === 0) return;
    const messageText =
      text || `请处理随附的 ${uploadedRefs.length} 个文件（${uploadedRefs.map((u) => u.filename).join('、')}）。`;
    setFollowing(true);
    void store.send(messageText, selection, {
      mcps: [],
      skills: [],
      capability: {
        value: '',
        label: '对话',
        ...(reasoningEffort ? { config: { reasoningEffort } } : {}),
      },
      ...(uploadedRefs.length ? { attachments: uploadedRefs } : {}),
    });
    setDraftAttachments([]);
    setUploadedRefs([]);
    setAttachmentError(null);
  }

  async function copyMessage(id: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      window.setTimeout(() => setCopiedId((current) => (current === id ? null : current)), 1500);
    } catch {
      /* 复制失败静默：用户可手动选择文本 */
    }
  }

  const panelItems: ArtifactPanelItem[] = useMemo(
    () =>
      store.messages.flatMap((message) =>
        (message.artifacts ?? []).map((artifact) => ({
          key: `${message.id}:${artifact.id}`,
          artifact,
          sessionId: store.activeId,
        })),
      ),
    [store.messages, store.activeId],
  );

  if (!store.ready) {
    return (
      <WorkspaceShell pageTitle="对话" className="chat-home-shell">
        <main className="status-page" role="status">
          正在恢复本地会话…
        </main>
      </WorkspaceShell>
    );
  }

  return (
    <WorkspaceShell
      pageTitle="对话"
      className="chat-home-shell"
      sidebarLayout
      sidebarContent={
        <SessionPanel
          conversations={store.conversations}
          activeId={store.activeId}
          onNew={() => store.newConversation()}
          onSelect={(id) => void store.selectConversation(id)}
          onRename={(id) => {
            const current = store.conversations.find((c) => c.id === id)?.title ?? '';
            const next = window.prompt('重命名会话', current);
            if (next && next.trim()) void store.renameConversation(id, next.trim());
          }}
          onRemove={(id) => void store.removeConversation(id)}
        />
      }
      beforeNavigate={async () => {
        store.stop();
        if (!(await store.flush())) throw new Error('unsaved');
      }}
    >
      <div ref={entranceRef} className={`chat-page ${panelView !== null ? 'info-open' : ''}`}>
        <section className={`chat-main ${hasMessages ? '' : 'chat-welcome'}`}>
          <header className="chat-toolbar" data-motion-reveal>
            <span className="chat-title">{activeTitle}</span>
            <span className="chat-flex-spacer" />
            <button className="icon-button" aria-label="新建对话" onClick={() => store.newConversation()}>
              <Plus size={17} />
            </button>
            <button
              className="icon-button"
              aria-label="会话详情"
              aria-pressed={panelView === 'workspace'}
              onClick={() => {
                if (panelView === 'workspace' && artifactKey === null) setPanelView(null);
                else {
                  setArtifactKey(null);
                  setPanelView('workspace');
                }
              }}
            >
              <PanelRight size={17} />
            </button>
          </header>

          {(store.storageWarning || store.loadError || store.serviceNotice || catalogError) && (
            <div className="chat-banner" role="status">
              <span>{store.storageWarning ?? store.loadError ?? store.serviceNotice ?? catalogError}</span>
            </div>
          )}
          {store.budgetNotice && (
            <div className="chat-banner" role="status">
              <span>{store.budgetNotice}</span>
              <button onClick={() => store.dismissBudgetNotice()}>知道了</button>
            </div>
          )}

          <div
            ref={scroller}
            className="chat-messages"
            onScroll={() => {
              const el = scroller.current;
              if (el) setFollowing(el.scrollHeight - el.scrollTop - el.clientHeight < 90);
            }}
          >
            {!hasMessages && (
              <div className="chat-empty" data-motion-reveal>
                <p className="chat-eyebrow">智启课源 · 对话</p>
                <h1>从一个问题，开始理解。</h1>
                <p>可直接提问，也可附上传文件（后续能力随 Agent 重建逐步接入）。</p>
              </div>
            )}
            <div className="chat-message-column">
              {store.messages.map((message) => (
                <Message
                  key={message.id}
                  message={message}
                  copied={copiedId === message.id}
                  onCopy={() => void copyMessage(message.id, message.content)}
                  onRetry={
                    message.role === 'assistant' && message.status !== 'streaming'
                      ? () => void store.retryLast(selection)
                      : undefined
                  }
                  onReuse={() => store.setDraft(message.content)}
                  ask={{
                    waitingId: store.waitingInteractionId,
                    submitting: store.submittingReply,
                    focus: store.askFocus,
                    notice: store.askNotice,
                    onDraft: (interactionId, questionId, draft) =>
                      store.setAskDraft(interactionId, questionId, draft),
                    onFocusChange: (interactionId, questionId) =>
                      store.setAskFocus(interactionId, questionId),
                    onContinue: (interactionId) => void store.continueAsk(interactionId),
                    onSkip: (interactionId) => void store.skipAskQuestion(interactionId),
                  }}
                  onOpenArtifact={(artifactId) => {
                    setArtifactKey(`${message.id}:${artifactId}`);
                    setPanelView('workspace');
                  }}
                />
              ))}
            </div>
          </div>

          {!following && (
            <button
              className="chat-jump"
              aria-label="回到最新"
              onClick={() => {
                setFollowing(true);
                scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' });
              }}
            >
              <ArrowDown size={15} />
            </button>
          )}

          <div className="chat-composer-wrap">
            <div className="chat-composer">
              {draftAttachments.length > 0 && (
                <ul className="chat-attach-row" aria-label="待发送附件">
                  {draftAttachments.map((attachment, index) => (
                    <li key={`${attachment.filename}-${index}`} className="chat-attach-chip">
                      <Paperclip size={12} aria-hidden />
                      <span>{attachment.filename}</span>
                      <button
                        type="button"
                        aria-label={`移除附件 ${attachment.filename}`}
                        onClick={() => removeAttachment(index)}
                      >
                        <X size={12} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {attachmentError && (
                <p className="chat-composer-note" role="alert">
                  {attachmentError}
                </p>
              )}
              <textarea
                ref={textarea}
                className="chat-input"
                aria-label="输入问题"
                placeholder={store.waitingInteractionId ? '补充回答当前问题…' : '输入消息…（Shift+Enter 换行）'}
                rows={3}
                value={store.draft}
                disabled={!selection && !store.waitingInteractionId}
                onChange={(event) => store.setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault();
                    submit();
                  }
                }}
                onPaste={(event) => {
                  const items = event.clipboardData?.files;
                  if (items && items.length > 0) handleFiles(items);
                }}
              />
              <div className="chat-composer-actions">
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  hidden
                  accept={ATTACHMENT_ACCEPT}
                  onChange={(event) => handleFiles(event.target.files)}
                />
                <button
                  type="button"
                  className="chat-add-trigger"
                  aria-label="添加附件"
                  disabled={store.sending || uploading}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Paperclip size={18} strokeWidth={1.65} />
                </button>
                <span className="chat-flex-spacer" />
                <ComposerContextChips
                  contextTokens={profile?.contextTokens}
                  contentChars={store.messages.reduce((total, m) => total + m.content.length, 0) + store.draft.length}
                />
                {profile?.reasoningEnabled && (
                  <label className="chat-effort-picker" title="思考强度（本轮覆盖，随模型支持）">
                    <Brain size={14} strokeWidth={1.8} aria-hidden="true" />
                    <select
                      aria-label="思考强度"
                      value={reasoningEffort ?? ''}
                      disabled={store.sending}
                      onChange={(event) => setReasoningEffort(event.target.value || null)}
                    >
                      <option value="">
                        默认{profile.reasoningEffort ? `（${REASONING_EFFORT_LABELS[profile.reasoningEffort]}）` : ''}
                      </option>
                      {REASONING_EFFORT_VALUES.filter((v) => v !== 'none').map((v) => (
                        <option key={v} value={v}>
                          {REASONING_EFFORT_LABELS[v]}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <ModelSelector
                  catalog={catalog}
                  value={modelPreference ?? store.modelProfileId}
                  onChange={(id) => {
                    setModelPreference(id);
                    store.setModel(id);
                  }}
                  disabled={store.sending}
                  presentation="popover"
                />
                {store.sending ? (
                  <button className="chat-send stop" aria-label="停止生成" onClick={() => store.stop()}>
                    <Square size={15} />
                  </button>
                ) : (
                  <button
                    className="chat-send"
                    aria-label="发送"
                    disabled={
                      (!selection && !store.waitingInteractionId) ||
                      (!store.draft.trim() && uploadedRefs.length === 0 && !store.waitingInteractionId)
                    }
                    onClick={submit}
                  >
                    <ArrowDown size={16} className="chat-send-arrow" />
                  </button>
                )}
              </div>
            </div>
            <p className="chat-composer-foot chat-info-muted">
              {!profile
                ? catalogError ?? '尚未选择可用的模型；请在设置中配置连接与模型。'
                : store.sending
                  ? '正在生成，可随时停止。'
                  : 'Enter 发送 · Shift+Enter 换行'}
            </p>
          </div>
        </section>

        {panelView !== null && (
          <aside className="chat-info" aria-label="会话工作区">
            <WorkspacePanel
              items={panelItems}
              activeKey={artifactKey}
              onOpen={(key) => setArtifactKey(key)}
              onCloseTab={(key) => setArtifactKey((current) => (current === key ? null : current))}
              onClose={() => setPanelView(null)}
              home={
                <InfoPanel
                  profile={profile}
                  conversations={store.conversations}
                  activeId={store.activeId}
                  messageCount={store.messages.length}
                />
              }
            />
          </aside>
        )}
      </div>
    </WorkspaceShell>
  );
}
