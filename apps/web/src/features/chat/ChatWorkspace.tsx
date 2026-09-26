'use client';
import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowDown,
  ArrowUp,
  BookOpen,
  Download,
  Paperclip,
  Mic,
  PanelRight,
  Plus,
  Search,
  Square,
  X,
} from 'lucide-react';
import { WorkspaceShell } from '@/components/layout/WorkspaceShell';
import { Modal } from '@/components/ui/Modal';
import { ChatProvider, useChatSession, useChatStore } from './model/ChatContext';

import { CapabilityMenu } from './CapabilityMenu';

import { ContextRefTree } from './ComposerSpaceMenu';
import { useModelCatalog } from '@/features/model-settings/useModelCatalog';
import { ModelSelector } from '@/features/model-settings/ModelSelector';
import { readPersonas, subscribePersonas, type PersonaEntry } from '@/services/persona-catalog';
import { buildTurnExtensionSnapshot } from '@/services/extension-catalog';
import {
  readKnowledge,
  subscribeKnowledge,
  type KnowledgeEntry,
} from '@/services/knowledge-catalog';
import {
  CHAT_CAPABILITIES,
  capabilityAvailableInReal,
  capabilityValidationErrors,
  createDefaultCapabilityForms,
  getCapability,
  type CapabilityFormState,
} from '@/services/capability-catalog';
import {
  ATTACHMENT_ACCEPT,
  classifyFile,
  docIconFor,
  fileToPendingAttachment,
  formatBytes,
  isSvgFilename,
  selectAttachmentFiles,
  type PendingAttachment,
} from '@/services/doc-attachments';

import { conversationProjection } from './model/context-budget';
import { createIdbChatRepository } from '@/services/chat-repository';
import { resolveCourse, courseAvailabilityLabel } from '@/services/course-session';
import { subscribeCourses } from '@/services/courses-store';
import { Message } from './Message';
import { SessionPanel } from './SessionPanel';
import { InfoPanel } from './InfoPanel';
import { ArtifactPanelItem, WorkspacePanel } from './ArtifactPanel';
import { ComposerContextChips } from './ComposerContextChips';
import '@/features/model-settings/styles/model-settings.css';
import './styles/chat.css';
import './styles/chat-home.css';

/** R21：会话级待发送状态（人设/知识/会话引用/附件）——归属键为「模式+会话」 */
interface SessionPending {
  personaId: string | null;
  knowledgeIds: string[];
  historyIds: string[];
  attachments: PendingAttachment[];
}
const EMPTY_PENDING: SessionPending = {
  personaId: null,
  knowledgeIds: [],
  historyIds: [],
  attachments: [],
};

export function ChatWorkspace({
  initialSessionId,
  initialMessageId,
}: {
  initialSessionId?: string;
  /** R-10：来源深链的可选消息定位目标（仅在该会话内查找，不跨会话） */
  initialMessageId?: string;
}) {
  return (
    <ChatProvider>
      <ChatPage initialSessionId={initialSessionId} initialMessageId={initialMessageId} />
    </ChatProvider>
  );
}
function ChatPage({
  initialSessionId,
  initialMessageId,
}: {
  initialSessionId?: string;
  initialMessageId?: string;
}) {
  const store = useChatStore();
  const chatSession = useChatSession();
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 760px)');
    const update = () => setIsMobile(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  const { catalog, loading, error, refresh } = useModelCatalog();
  // R22/S3：右面板 = 结果工作区（标签页形态：活动主页 + 产物标签）。
  // null=关闭；'workspace'=打开（活动标签或某个产物标签由 artifactKey 决定）
  const [panelView, setPanelViewState] = useState<'workspace' | null>(null);
  const [panelExiting, setPanelExiting] = useState(false);
  function setPanelView(next: 'workspace' | null) {
    setPanelExiting(next === null);
    setPanelViewState(next);
  }
  useEffect(() => {
    if (!panelExiting) return;
    const timer = window.setTimeout(() => setPanelExiting(false), 220);
    return () => window.clearTimeout(timer);
  }, [panelExiting]);
  // R24：当前打开产物的复合身份 key（`${messageId}:${artifactId}`）；null=未选中
  const [artifactKey, setArtifactKey] = useState<string | null>(null);
  // S3：已关闭的产物标签（复合 key）。产物本体仍在消息上，关闭只是不再以标签呈现；
  // 重新点击产物 chip 可恢复标签；切换会话/模式时随标签一起重置（同参考 SessionViewerPanel）
  const [closedTabs, setClosedTabs] = useState<ReadonlySet<string>>(() => new Set());
  const [query, setQuery] = useState(''),
    [copyState, setCopyState] = useState<string | null>(null),
    [following, setFollowing] = useState(true);
  const [blockedNotice, setBlockedNotice] = useState<string | null>(null);
  // S2 输入区：业务能力（默认“对话”）+ 各能力配置表单 + 确认状态
  const [capabilityValue, setCapabilityValue] = useState('');
  const [capForms] = useState<CapabilityFormState>(createDefaultCapabilityForms);
  const [capConfirmed, setCapConfirmed] = useState(false);
  // R21：人设/知识/会话引用/附件按「模式+会话」归属存储；
  // ref 保存同步真值（供串行接纳队列等异步逻辑即时读取），bump 触发渲染。
  const [, bumpPending] = useState(0);
  const pendingRef = useRef<Record<string, SessionPending>>({});
  const pendingKey = store.activeId ?? '__pending__';
  const pending = pendingRef.current[pendingKey] ?? EMPTY_PENDING;
  const selectedPersonaId = pending.personaId;
  const selectedKnowledgeIds = pending.knowledgeIds;
  const selectedHistoryIds = pending.historyIds;
  const attachments = pending.attachments;
  // 人设/知识演示目录（页面级只读目录，选择的归属按会话计）
  const [personas, setPersonas] = useState<PersonaEntry[]>([]);
  const [knowledgeEntries, setKnowledgeEntries] = useState<KnowledgeEntry[]>([]);
  /** R21：写入指定会话的待发送状态（读改写必须走这里，保证跨批次的同步一致性） */
  function patchPending(key: string, patch: (p: SessionPending) => Partial<SessionPending>) {
    const current = pendingRef.current[key] ?? EMPTY_PENDING;
    pendingRef.current = { ...pendingRef.current, [key]: { ...current, ...patch(current) } };
    bumpPending((n) => n + 1);
  }
  // R21：会话尚未创建（欢迎页）时的选择暂存 __pending__；首个会话建立后随迁，
  // 避免发送触发 create() 时把已选人设/知识丢失
  useEffect(() => {
    if (!store.activeId) return;
    const fromKey = '__pending__';
    const carried = pendingRef.current[fromKey];
    if (!carried) return;
    const next = { ...pendingRef.current };
    delete next[fromKey];
    const toKey = store.activeId;
    if (!next[toKey]) next[toKey] = carried;
    pendingRef.current = next;
    bumpPending((n) => n + 1);
  }, [store.activeId]);
  // S3：产物标签归属会话——切换会话/模式后回到活动主页并恢复全部标签
  // （同参考"会话变化清空标签"；关闭态是会话内视图状态，随会话重置）
  useEffect(() => {
    setArtifactKey(null);
    setClosedTabs(new Set());
  }, [store.activeId]);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const attachmentErrorTimer = useRef<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const dragCounter = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [previewIndex, setPreviewIndex] = useState<number | null>(null);
  // S2 输入区：语音入口（无 STT 服务：明确未接入状态 + 显式演示转写，不采集音频）
  const [voiceOpen, setVoiceOpen] = useState(false);
  // 会话深链（/chat/[sessionId]）：R17——一次性定位，仅首次就绪时执行；
  // 用户随后的新建/切换/删除不被 URL 强行改写；刷新/前进后退（重新挂载）重新定位
  const [deepLinkHandled, setDeepLinkHandled] = useState(false);
  // R-10 消息定位：目标会话载入后在该会话内查找消息；找不到时明确提示"原消息已不存在"
  const [locatedMessageId, setLocatedMessageId] = useState<string | null>(null);
  const [messageMissing, setMessageMissing] = useState(false);
  // R-10：来源会话失效时不自动打开最近会话，改为此空态（保留学习记录与主动返回）
  const [sessionUnavailable, setSessionUnavailable] = useState(false);
  // 当前会话的课程归属（H1-COURSE-SESSIONS v1）：随 activeCourseId 与课程目录变化重算；
  // 只按稳定 courseId 解析，不按标题/最近访问猜测，课程不可用时如实标注且不回落其他课程。
  const [courseTick, bumpCourseTick] = useState(0);
  useEffect(() => subscribeCourses(() => bumpCourseTick((value) => value + 1)), []);
  const activeCourse = useMemo(() => {
    void courseTick; // 课程目录变化时重算（改名/删除/读取失败）
    return store.activeCourseId ? resolveCourse(store.activeCourseId) : null;
  }, [store.activeCourseId, courseTick]);
  // R-10：当前要在会话内定位的消息 id（初值来自 URL，前进/后退可更新；切换会话时清空）
  const [targetMessageId, setTargetMessageId] = useState<string | undefined>(initialMessageId);
  const [dialog, setDialog] = useState<{
      kind: 'rename' | 'remove';
      id: string;
      title: string;
    } | null>(null),
    [title, setTitle] = useState('');
  const textarea = useRef<HTMLTextAreaElement>(null),
    scroller = useRef<HTMLDivElement>(null);
  const stores = chatSession.stores;
  // 当前模式 store 的稳定实例：URL 同步与 popstate 处理经 getState() 取最新状态，
  // 不依赖渲染快照（R2：固定模式 store 各自独立）
  const activeStore = stores.real;
  // 会话存储的初始化与卸载清理统一由 ChatProvider 负责（R1/R2），此处只保留 UI 相关效果
  useEffect(() => {
    if (textarea.current) {
      textarea.current.style.height = 'auto';
      textarea.current.style.height = `${Math.min(textarea.current.scrollHeight, 180)}px`;
    }
  }, [store.draft]);
  useEffect(() => {
    // 订阅角色/知识来源演示目录（S2）：显式载入演示数据，不自动写入用户存储
    const updatePersonas = () => {
      try {
        setPersonas(readPersonas());
      } catch {
        /* 目录格式异常时保持现有列表 */
      }
    };
    const updateKnowledge = () => {
      try {
        setKnowledgeEntries(readKnowledge());
      } catch {
        /* 目录格式异常时保持现有列表 */
      }
    };
    updatePersonas();
    updateKnowledge();
    const unsubPersona = subscribePersonas(updatePersonas);
    const unsubKnowledge = subscribeKnowledge(updateKnowledge);
    return () => {
      unsubPersona();
      unsubKnowledge();
    };
  }, []);
  useEffect(() => {
    if (following && scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [store.messages, following]);
  useEffect(() => {
    // R17：一次性深链定位。守卫状态而非依赖 store——用户新建/切换/删除后不再强制回跳；
    // 刷新或前后导航重新挂载时按 URL 重新定位（保持草稿保存与运行取消语义不变）
    if (deepLinkHandled || !initialSessionId) return;

    if (!store.ready) return;
    setDeepLinkHandled(true);
    void (async () => {
      const target = activeStore.getState();
      // 用仓储直读判定会话存在（含已归档会话），与来源链接的校验口径一致
      const conversation = await createIdbChatRepository('zhiqikeyuan-chat').load(initialSessionId);
      if (conversation) {
        setSessionUnavailable(false);
        if (target.activeId !== initialSessionId) await activeStore.getState().selectConversation(initialSessionId);
      } else {
        // R-10：来源会话已不存在——给明确不可用态，不自动展示最近会话，也不新建/保存
        setSessionUnavailable(true);
        activeStore.getState().deactivate();
      }
    })();
    // deepLinkHandled 翻转后守卫恒为真，store 变化不会再次触发定位
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deepLinkHandled, initialSessionId, store.ready]);
  useEffect(() => {
    // R-10 消息定位：会话载入完成后，在**该会话内**按 data-message-id 查找目标消息。
    // 只查当前会话的 DOM，不跨会话搜索同名内容；找不到就明确提示"原消息已不存在"。
    if (!targetMessageId || !initialSessionId) return;
    if (!deepLinkHandled) return;
    if (sessionUnavailable) return;
    if (store.activeId !== initialSessionId) return; // 等待目标会话真正成为当前会话
    const scrollerEl = scroller.current;
    if (!scrollerEl) return;

    let cancelled = false;
    const highlightId = `msg-target-${Date.now()}`;
    const locate = () => {
      if (cancelled) return false;
      const node = scrollerEl.querySelector<HTMLElement>(
        `[data-message-id="${CSS.escape(targetMessageId)}"]`,
      );
      if (!node) return false;
      // 定位本身是一次主动跳转：先把"跟随最新"关掉，避免随后的消息变化把视口拉回底部
      setFollowing(false);
      const reduced =
        document.documentElement.dataset.motion === 'reduced' ||
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      node.scrollIntoView({ block: 'center', behavior: reduced ? 'auto' : 'smooth' });
      setLocatedMessageId(targetMessageId);
      setMessageMissing(false);
      // 可识别提示：短暂高亮该消息（减少动画时不加过渡类，仅静态描边）
      node.dataset.located = highlightId;
      // CSS 侧无 located 样式时用内联描边兜底，保证任何主题下都可见
      node.style.outline = '2px solid var(--blue)';
      node.style.outlineOffset = '2px';
      node.style.borderRadius = '12px';
      window.setTimeout(() => {
        node.style.outline = '';
        node.style.outlineOffset = '';
        node.style.borderRadius = '';
        delete node.dataset.located;
      }, 2600);
      return true;
    };
    // 会话刚切过来时消息可能还未提交渲染：下一帧起有限次重试，避免竞态
    let tries = 0;
    const tick = () => {
      if (cancelled) return;
      if (locate()) return;
      tries += 1;
      if (tries < 20) window.setTimeout(tick, 60);
      else setMessageMissing(true); // 会话内没有这条消息（已删除/旧数据）
    };
    tick();
    return () => {
      cancelled = true;
    };
    // 依赖 messageId 与目标会话，避免切到别的会话后旧请求把视口定位到错误消息
  }, [targetMessageId, initialSessionId, deepLinkHandled, sessionUnavailable, store.activeId]);

  /**
   * 深链契约（交付复核补充）：地址与当前会话同步。
   * - 用户主动选择/新建/删除/切换模式时经 history push/replace 更新地址（pushState
   *   不触发 Next 软导航重渲染，避免与一次性深链定位互相覆盖、形成双向循环）；
   * - 前进/后退（popstate）按 URL 重新定位会话。
   * 写入口只有这两个方向：用户动作与浏览器导航，来源明确。
   */
  function syncSessionUrl(id: string | null, method: 'push' | 'replace') {
    const target = id ? `/chat/${id}` : '/chat';
    if (window.location.pathname !== target) {
      (method === 'push' ? window.history.pushState : window.history.replaceState).call(
        window.history,
        null,
        '',
        target,
      );
    }
  }
  useEffect(() => {
    function onPopState() {
      const match = /^\/chat\/([^/]+)$/.exec(window.location.pathname);
      if (!match) return; // /chat 或导航离开聊天页：保持当前活动会话
      const id = decodeURIComponent(match[1]);
      // R-10：前进/后退到带 message 的来源链接时，重新在该会话内定位该消息
      const message = new URLSearchParams(window.location.search).get('message') ?? undefined;
      setTargetMessageId(message);
      setMessageMissing(false);
      const state = activeStore.getState();
      if (state.conversations.some((c) => c.id === id)) {
        setSessionUnavailable(false);
        if (state.activeId !== id) void state.selectConversation(id);
      } else if (state.ready) {
        // R-10：指向前进/后退到的已失效会话——同样给明确不可用态，不自动落到最近会话
        setSessionUnavailable(true);
        state.deactivate();
      }
    }
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [activeStore]);
  const profile = useMemo(() => {
    const selectedId = store.modelProfileId ?? catalog?.defaultChatProfileId;
    return catalog?.profiles.find((p) => p.id === selectedId) ?? null;
  }, [store.modelProfileId, catalog]);
  const selection = useMemo(() => {
    const valid =
      !!profile?.connection?.hasCredential &&
      !error &&
      (profile.purpose === 'chat' || profile.purpose === null);
    return profile && valid
      ? {
          id: profile.id,
          modelLabel: `${profile.displayName} · ${profile.modelId}`,
          contextTokens: profile.contextTokens,
          maxOutputTokens: profile.maxOutputTokens,
        }
      : null;
  }, [profile, error]);
  const activeTitle = store.conversations.find((c) => c.id === store.activeId)?.title ?? '新的对话';
  const hasMessages = store.messages.length > 0;
  // CHAT-CONTEXT-BUDGET v1：最近一轮**实际发送时**的字符账目（随助手消息持久化，刷新可核）。
  // 只如实转述裁剪事实，不声称精确 token，也不把估算说成模型上限保证。
  const lastTurnBudget = useMemo(
    () => [...store.messages].reverse().find((m) => m.role === 'assistant')?.requestBudget ?? null,
    [store.messages],
  );
  const budgetRecordNotice = useMemo(() => {
    if (!lastTurnBudget) return null;
    const parts: string[] = [];
    if (lastTurnBudget.courseDropped)
      parts.push('课程上下文整体超出本轮输入预算，本轮未携带课程上下文（如实丢弃，未发送残缺内容）');
    else if (lastTurnBudget.courseTrimmedFields.length)
      parts.push(`课程动态字段已按上限受限（${lastTurnBudget.courseTrimmedFields.join('、')}）`);
    if (lastTurnBudget.historyDroppedMessages > 0)
      parts.push(`已整条丢弃最旧的 ${lastTurnBudget.historyDroppedMessages} 条历史消息`);
    if (!parts.length) return null;
    return `本轮请求按字符估算裁剪：${parts.join('；')}。历史消息与课程数据未被改写。`;
  }, [lastTurnBudget]);
  // S3/R24：当前会话的全部产物，复合身份 key = `${messageId}:${artifactId}`——
  // 不同轮同 id 产物在列表、tab、复制、下载中互不串位；旧历史（无 turnId）同样兼容
  const conversationArtifacts: ArtifactPanelItem[] = useMemo(
    () =>
      store.messages.flatMap((m) =>
        (m.artifacts ?? []).map((artifact) => ({
          key: `${m.id}:${artifact.id}`,
          artifact,
          // R-10：把真实会话 id 一并带下去，保存到笔记/题库时落库，业务页才能正确回链
          sessionId: store.activeId,
        })),
      ),
    [store.messages, store.activeId],
  );
  // 标签列表 = 全量产物剔除已关闭标签（产物本体保留，恢复后可再开）
  const openArtifacts: ArtifactPanelItem[] = useMemo(
    () => conversationArtifacts.filter((item) => !closedTabs.has(item.key)),
    [conversationArtifacts, closedTabs],
  );
  useEffect(() => {
    if (selection) setBlockedNotice(null);
  }, [selection]);
  function blockedReason(): string | null {
    if (!selection) {
      if (error) return `无法读取模型配置：${error}`;
      if (loading) return '正在读取模型配置，请稍后重试。';
      if (!catalog?.profiles.length) return '还没有可用模型，请先在设置中添加模型连接。';
      if (profile) return '当前模型缺少凭证，请到设置补充后重试。';
      return '请先选择可用的问答模型。';
    }
    return null;
  }

  // ===== S2 输入区：能力选择 / 配置确认 / 附件 / 语音 =====
  const activeCap = getCapability(capabilityValue);
  const capErrors = useMemo(
    () => capabilityValidationErrors(capabilityValue, capForms),
    [capabilityValue, capForms],
  );
  // R19：门控不只看确认布尔——配置无效时同样阻断，非法配置无法绕过提交边界；
  // 确认对应当前能力与当前配置版本（字段变更即撤销确认，见 handleCapFormChange）
  const capBlocked = activeCap.needsConfig && (!capConfirmed || capErrors.length > 0);
  // 真实模式仅支持普通对话：其余能力为“真实服务未接入”的不可用状态（不静默转模拟）
  const unavailableCapabilities = useMemo(() => {
    return new Set(
      CHAT_CAPABILITIES.filter((cap) => !capabilityAvailableInReal(cap.value)).map(
        (cap) => cap.value,
      ),
    );
  }, []);

  function handleSelectCapability(value: string) {
    if (value === capabilityValue) return;
    setCapabilityValue(value);
    // 切换能力使旧确认失效：新能力有自己的配置表单（同参考行为）
    setCapConfirmed(false);
  }

  // R22：配置卡定位锚点（进入工作区活动主页后滚动/聚焦）
  const capConfigAnchorRef = useRef<HTMLDivElement>(null);
  /** R22：请求确认配置 → 激活工作区活动主页并定位/聚焦配置卡（不再被产物标签遮挡） */
  function showConfigPanel() {
    setArtifactKey(null);
    setPanelView('workspace');
    requestAnimationFrame(() => {
      capConfigAnchorRef.current?.scrollIntoView({ block: 'nearest' });
      capConfigAnchorRef.current?.focus({ preventScroll: true });
    });
  }
  /** S3：打开工作区活动主页（工具栏“会话详情”按钮） */
  function openWorkspaceHome() {
    setArtifactKey(null);
    setPanelView('workspace');
  }
  // S3：关闭当前产物标签——从标签栏移除（产物本体保留）并回退到相邻标签或活动主页
  // （同参考 SessionViewerPanel closeTab：关闭的是"标签"而非产物数据）
  function closeWorkspaceTab(key: string) {
    setClosedTabs((current) => new Set(current).add(key));
    setArtifactKey((currentKey) => {
      if (currentKey !== key) return currentKey;
      const idx = conversationArtifacts.findIndex((item) => item.key === key);
      const openRest = conversationArtifacts.filter(
        (item) => item.key !== key && !closedTabs.has(item.key),
      );
      return openRest.length === 0 ? null : (openRest[Math.max(0, idx - 1)] ?? openRest[0])!.key;
    });
  }

  function showAttachmentError(message: string) {
    setAttachmentError(message);
    if (attachmentErrorTimer.current) clearTimeout(attachmentErrorTimer.current);
    // 对照参考：附件错误提示 4s 后自动清除
    attachmentErrorTimer.current = window.setTimeout(() => {
      setAttachmentError(null);
      attachmentErrorTimer.current = null;
    }, 4000);
  }

  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  /**
   * R23：串行接纳队列——同一时刻只接纳一批文件；批次占位插入即预留配额，
   * 后续批次的配额核对包含读取中的占位（并发添加不再绕过总量上限）。
   * 读取完成时核对批次身份（占位仍在才落内容）：发送/移除/卸载后不插回；
   * 写入按发起时的会话键（sessionKey），切会话后迟到的结果不会进入其他会话；
   * 读取失败释放占位（额度同步释放）并给出可恢复错误。
   */
  const fileQueueRef = useRef<Promise<void>>(Promise.resolve());
  function enqueueFiles(files: File[]) {
    if (!files.length) return;
    const sessionKey = pendingKey;
    fileQueueRef.current = fileQueueRef.current.then(async () => {
      if (!mountedRef.current) return;
      const current = pendingRef.current[sessionKey] ?? EMPTY_PENDING;
      const existingBytes = current.attachments.reduce((total, item) => total + item.size, 0);
      const { accepted, rejected } = selectAttachmentFiles(files, existingBytes);
      if (rejected.length) {
        const first = rejected[0]!;
        const reasonText =
          first.reason === 'too_large'
            ? `文件过大（上限 20MB）：${first.name}`
            : first.reason === 'quota'
              ? '附件总量超出配额（25MB），已跳过部分文件。'
              : `不支持的文件类型：${first.name}`;
        showAttachmentError(reasonText);
      }
      if (!accepted.length) return;
      // 占位先入库（预留配额），内容读取完成后再原地补齐
      patchPending(sessionKey, (p) => ({
        attachments: [
          ...p.attachments,
          ...accepted.map((file) => ({
            filename: file.name,
            kind: classifyFile(file) ?? ('doc' as const),
            size: file.size,
            ...(file.type ? { mimeType: file.type } : {}),
            reading: true,
          })),
        ],
      }));
      for (const file of accepted) {
        try {
          const att = await fileToPendingAttachment(file);
          if (!mountedRef.current) return;
          patchPending(sessionKey, (p) =>
            // 批次身份核对：占位已被发送/移除清掉时不再插回
            p.attachments.some((a) => a.reading && a.filename === file.name)
              ? {
                  attachments: p.attachments.map((a) =>
                    a.reading && a.filename === file.name
                      ? { ...a, base64: att.base64, previewUrl: att.previewUrl, reading: false }
                      : a,
                  ),
                }
              : {},
          );
        } catch {
          if (!mountedRef.current) return;
          patchPending(sessionKey, (p) => ({
            attachments: p.attachments.filter((a) => !(a.reading && a.filename === file.name)),
          }));
          showAttachmentError(`读取文件失败：${file.name}，已释放占位，可重新添加。`);
        }
      }
    });
  }

  function handleFileInputChange(event: React.ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(event.target.files ?? []);
    enqueueFiles(picked);
    // 重置以便重复选择同一文件仍触发 change（同参考）
    event.target.value = '';
  }

  function handlePasteAttachment(event: React.ClipboardEvent) {
    const files = Array.from(event.clipboardData.files);
    if (!files.length) return; // 纯文本粘贴不受影响
    // R20/R23：粘贴的文件统一走接纳队列，拒绝原因显式提示，不静默降级为纯文字请求
    event.preventDefault();
    enqueueFiles(files);
  }

  function onDragEnter(event: React.DragEvent) {
    event.preventDefault();
    dragCounter.current += 1;
    setDragging(true);
  }
  function onDragLeave(event: React.DragEvent) {
    event.preventDefault();
    dragCounter.current = Math.max(0, dragCounter.current - 1);
    if (dragCounter.current === 0) setDragging(false);
  }
  function onDragOver(event: React.DragEvent) {
    event.preventDefault();
  }
  function onDrop(event: React.DragEvent) {
    event.preventDefault();
    dragCounter.current = 0;
    setDragging(false);
    const files = Array.from(event.dataTransfer.files);
    // R20/R23：拖入文件统一走接纳队列，拒绝原因显式提示
    enqueueFiles(files);
  }

  /** 语音输入演示转写：无 STT 服务，不采集音频；插入带标识的演示文本体验流程 */
  const DEMO_TRANSCRIPT =
    '[演示转写] 这是语音输入的演示文本，用于体验转写接入流程（未访问任何语音服务）。';
  function insertDemoTranscript() {
    const current = store.draft.trim();
    store.setDraft(current ? `${current} ${DEMO_TRANSCRIPT}` : DEMO_TRANSCRIPT);
    setVoiceOpen(false);
    textarea.current?.focus();
  }

  function submit() {
    // 追问等待/提交期间属于同一轮次：主输入框走追问提交接口，不另开一轮
    if (store.sending && !store.waitingInteractionId) return;
    // R19/R22：配置阻断优先于空请求检查——按钮标签为「先确认能力配置」时，
    // 点击语义是打开配置卡并给出阻断说明，而不是发送；不清理任何选择
    if (!store.waitingInteractionId && capBlocked) {
      setBlockedNotice(`「${activeCap.label}」需要先确认能力配置。`);
      showConfigPanel();
      return;
    }
    const text = store.draft.trim();
    const hasPendingSelections = attachments.length > 0 || selectedHistoryIds.length > 0;
    // R20：完全空请求（无文字且无附件/引用）拒绝
    if (!text && !hasPendingSelections) return;
    if (store.waitingInteractionId) {
      if (!text || store.submittingReply) return;
      setBlockedNotice(null);
      setFollowing(true);
      void store.submitComposerReply(text);
      return;
    }

    if (!capabilityAvailableInReal(capabilityValue)) {
      // 防御路径：真实模式不允许非对话能力发起（菜单已禁用，含 RAG 模式），
      // 仍到达时明确说明并保留输入——绝不把请求发到普通聊天冒充该模式成功。
      setBlockedNotice(
        capabilityValue === 'rag'
          ? '「RAG 模式」尚未接入（规划中）：本轮未发送任何检索请求，输入已保留；请切回“对话”能力。'
          : `「${activeCap.label}」暂无真实服务，已保留选择；请切回“对话”能力。`,
      );
      return;
    }
    if (attachments.length) {
      // R20：真实服务无文件解析/上传通道——不静默剥离附件转纯文字请求；
      // 保留输入与附件，用户明确移除附件后才能继续纯文字请求
      setBlockedNotice(
        '当前真实服务不支持附件发送（未接入文件解析服务）：已保留输入与附件，请移除附件后再发送。',
      );
      return;
    }
    if (!text) {
      // 真实服务无文件解析/上传通道：仅引用无法构成真实请求
      setBlockedNotice('当前真实服务不支持仅引用发送（无文件解析服务），请输入文字后发送。');
      return;
    }
    const reason = blockedReason();
    if (reason) {
      // 发送受阻必须给出即时反馈，不允许静默吞掉用户消息
      setBlockedNotice(reason);
      return;
    }
    setBlockedNotice(null);
    setFollowing(true);
    // 发送即冻结：从扩展目录取本轮已启用的技能说明；无有效技能时不带 extensions 字段
    void store.send(text, selection!, buildTurnExtensionSnapshot());
  }
  async function fresh() {
    setTargetMessageId(undefined);
    setMessageMissing(false);
    setLocatedMessageId(null);
    store.stop();
    if (await store.flush()) {
      store.newConversation();
      // 新建后地址指向新会话（replace：创建不是一次页面浏览，回退应回到之前的会话）
      syncSessionUrl(activeStore.getState().activeId, 'replace');
      setFollowing(true);
      textarea.current?.focus();
    }
  }
  function backup() {
    const blob = new Blob([store.exportActive()], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = '学习问答备份.json';
    link.click();
    URL.revokeObjectURL(url);
  }
  /** 学习记录（UX-PERF-CLOSEOUT v1）：并入全站左侧导航的可滚动区域，不再是聊天区
   *  与导航之间的独立中栏；手机上随同一个全站导航抽屉呈现，不另开弹窗。 */
  const learningRecords = (
    <section className="chat-sessions-panel" aria-label="学习记录">
      <div className="chat-session-head">
        <span>学习记录</span>
      </div>
      <div className="chat-session-search">
        <Search size={14} />
        <input
          aria-label="搜索会话"
          placeholder="搜索会话"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <SessionPanel
        conversations={store.conversations.filter((c) =>
          c.title.toLowerCase().includes(query.toLowerCase()),
        )}
        activeId={store.activeId}
        onNew={() => void fresh()}
        onSelect={(id) => {
          // 用户主动切换会话：先前深链的消息目标不再适用，避免在别的会话里误定位或残留提示
          setTargetMessageId(undefined);
          setMessageMissing(false);
          setLocatedMessageId(null);
          void store.selectConversation(id).then(() => {
            // 选择成功且未被更新的操作顶替时，地址跟随当前会话（刷新/前进后退可恢复）
            if (activeStore.getState().activeId === id) syncSessionUrl(id, 'push');
          });
          setFollowing(true);
        }}
        onRename={(id) => {
          const name = store.conversations.find((c) => c.id === id)?.title ?? '';
          setTitle(name);
          setDialog({ kind: 'rename', id, title: name });
        }}
        onRemove={(id) =>
          setDialog({
            kind: 'remove',
            id,
            title: store.conversations.find((c) => c.id === id)?.title ?? '',
          })
        }
      />
      <p className="chat-local-note">会话保存在当前浏览器</p>
    </section>
  );
  return (
    <WorkspaceShell
      pageTitle="学习问答"
      className="chat-home-shell"
      sidebarLayout
      sidebarContent={learningRecords}
      beforeNavigate={async () => {
        stores.real.getState().stop();
        const results = await Promise.all([stores.real.getState().flush()]);
        if (!results.every(Boolean)) throw new Error('unsaved');
      }}
    >
      <div className={`chat-page ${panelView !== null ? 'info-open' : ''}`}>
        <section className={`chat-main ${hasMessages ? '' : 'chat-welcome'}`}>
          <header className="chat-toolbar">
            <span className="chat-title">{activeTitle}</span>

            <span className="chat-flex-spacer" />
            <button className="icon-button" aria-label="新建对话" onClick={() => void fresh()}>
              <Plus size={17} />
            </button>
            <button
              className="icon-button"
              aria-label="备份当前会话"
              disabled={!store.activeId}
              onClick={backup}
            >
              <Download size={17} />
            </button>
            <button
              className="icon-button"
              aria-label="会话详情"
              aria-pressed={panelView === 'workspace' && artifactKey === null}
              onClick={() => {
                // 打开/关闭工作区；已打开且在活动主页时关闭（同参考 focusActivityHome）
                if (panelView === 'workspace' && artifactKey === null) setPanelView(null);
                else openWorkspaceHome();
              }}
            >
              <PanelRight size={17} />
            </button>
          </header>
          {store.activeCourseId && activeCourse && (
            <div className="chat-banner course" role="status" data-course-id={store.activeCourseId}>
              {activeCourse.state === 'ok' ? (
                <>
                  <span>
                    所属课程：<strong>{activeCourse.course.name}</strong>
                  </span>
                  <Link href={`/courses/${store.activeCourseId}`}>返回课程</Link>
                </>
              ) : (
                <>
                  <span>{courseAvailabilityLabel(activeCourse)}</span>
                  {activeCourse.state === 'unavailable' && (
                    <button onClick={() => bumpCourseTick((value) => value + 1)}>重试读取课程</button>
                  )}
                  <Link href="/courses">课程列表</Link>
                </>
              )}
            </div>
          )}
          {store.budgetNotice && (
            <div className="chat-banner warn chat-budget-notice" role="alert">
              {store.budgetNotice}
              <button onClick={() => store.dismissBudgetNotice()}>知道了</button>
            </div>
          )}
          {budgetRecordNotice && (
            <div className="chat-banner warn" role="status" data-budget-record>
              {budgetRecordNotice}
            </div>
          )}
          {store.courseContextWarning && (
            <div className="chat-banner warn" role="alert">
              {store.courseContextWarning}
              <button onClick={() => store.dismissCourseContextWarning()}>知道了</button>
            </div>
          )}
          {sessionUnavailable && (
            <div className="chat-banner warn" role="status">
              来源会话已不存在或已被删除，无法打开。
              <Link href="/chat">返回学习问答</Link>
            </div>
          )}
          {locatedMessageId && !messageMissing && (
            <div className="chat-banner" role="status">
              已定位到来源消息。
              <button onClick={() => setLocatedMessageId(null)}>知道了</button>
            </div>
          )}
          {messageMissing && (
            <div className="chat-banner warn" role="status">
              原消息已不存在，已打开所属会话。
              <button onClick={() => setMessageMissing(false)}>知道了</button>
            </div>
          )}

          {store.storageWarning && (
            <div className="chat-banner warn" role="alert">
              {store.storageWarning}
              <button onClick={backup}>备份当前内容</button>
              <button onClick={() => void store.flush()}>重试保存</button>
            </div>
          )}
          {error && (
            <div className="chat-banner error" role="alert">
              无法读取模型配置：{error}
              <button onClick={() => void refresh()}>重试</button>
            </div>
          )}
          {!loading && !error && !selection && (
            <div className="chat-banner warn">
              {profile
                ? '当前模型缺少凭证，请到设置补充。'
                : store.modelProfileId
                  ? '此前选择的模型已不可用，请重新选择。'
                  : catalog?.profiles.length
                    ? '请选择模型，或在设置中指定默认模型。'
                    : '还没有可用的模型，请先添加模型连接。'}
              <Link href="/settings">设置</Link>
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
              <div className="chat-empty">
                <span className="chat-empty-mark">
                  <BookOpen size={25} />
                </span>
                <p className="chat-eyebrow">智启课源 · 学习问答</p>
                <h1>从一个问题，开始理解。</h1>
                <p>梳理知识、解释概念，或一起推敲教学思路。</p>
              </div>
            )}
            <div className="chat-message-column">
              {store.messages.map((message, index) => (
                <Message
                  key={message.id}
                  message={message}
                  copied={copyState === message.id}
                  ask={{
                    waitingId: store.waitingInteractionId,
                    submitting: store.submittingReply,
                    onDraft: (interactionId, questionId, draft) =>
                      store.setAskDraft(interactionId, questionId, draft),
                    onSubmit: (interactionId, answers) => void store.submitReply(answers),
                  }}
                  onCopy={async () => {
                    try {
                      // R12：复制走统一对话投影，包含已确认追问交流与同轮续写
                      await navigator.clipboard.writeText(conversationProjection(message));
                      setCopyState(message.id);
                    } catch {
                      setCopyState('failed');
                    }
                  }}
                  onRetry={
                    index === store.messages.length - 1 && !store.sending && !!selection
                      ? () => void store.retry(message.id, selection)
                      : undefined
                  }
                  onReuse={() => {
                    const user = [...store.messages.slice(0, index + 1)]
                      .reverse()
                      .find((m) => m.role === 'user');
                    if (user) store.setDraft(user.content);
                    textarea.current?.focus();
                  }}
                  onOpenArtifact={(artifactId) => {
                    // R24：以复合身份（消息+产物）打开对应标签，不同轮同 id 产物各自正确；
                    // 若标签此前被关闭则恢复（点 chip = 再次打开该产物）
                    const key = `${message.id}:${artifactId}`;
                    setClosedTabs((current) => {
                      if (!current.has(key)) return current;
                      const next = new Set(current);
                      next.delete(key);
                      return next;
                    });
                    setArtifactKey(key);
                    setPanelView('workspace');
                    setFollowing(true);
                  }}
                />
              ))}
            </div>
          </div>
          {!following && hasMessages && (
            <button
              className="chat-jump"
              onClick={() => {
                setFollowing(true);
              }}
            >
              <ArrowDown size={14} />
              回到最新
            </button>
          )}
          <div className="chat-composer-wrap">
            <div
              className={`chat-composer ${dragging ? 'dragging' : ''}`}
              onDragEnter={onDragEnter}
              onDragLeave={onDragLeave}
              onDragOver={onDragOver}
              onDrop={onDrop}
            >
              {dragging && (
                <div className="chat-drop-overlay" aria-hidden="true">
                  <strong>松开以添加附件</strong>
                  <small>图片、Office 文档、代码与文本</small>
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept={ATTACHMENT_ACCEPT}
                onChange={handleFileInputChange}
                hidden
                aria-hidden="true"
                tabIndex={-1}
              />
              <ContextRefTree
                personaName={personas.find((item) => item.id === selectedPersonaId)?.name ?? null}
                knowledgeNames={knowledgeEntries
                  .filter((item) => selectedKnowledgeIds.includes(item.id))
                  .map((item) => ({ id: item.id, name: item.name }))}
                historyTitles={store.conversations
                  .filter((c) => selectedHistoryIds.includes(c.id))
                  .map((c) => ({ id: c.id, title: c.title }))}
                onRemovePersona={() => patchPending(pendingKey, () => ({ personaId: null }))}
                onRemoveKnowledge={(id) =>
                  patchPending(pendingKey, (p) => ({
                    knowledgeIds: p.knowledgeIds.filter((item) => item !== id),
                  }))
                }
                onRemoveHistory={(id) =>
                  patchPending(pendingKey, (p) => ({
                    historyIds: p.historyIds.filter((item) => item !== id),
                  }))
                }
              />
              <textarea
                ref={textarea}
                rows={1}
                aria-label="输入问题"
                disabled={!store.ready}
                value={store.draft}
                placeholder={
                  store.waitingInteractionId
                    ? '回答当前追问：输入内容后 Enter 提交（同一轮内续答，不新开一轮）'
                    : '输入问题，Enter 发送，Shift+Enter 换行'
                }
                onChange={(e) => store.setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    submit();
                  }
                }}
                onPaste={handlePasteAttachment}
                onBlur={() => void store.flush()}
              />

              {!!attachments.length && (
                <div className="chat-attach-row">
                  {attachments.map((a, i) => {
                    const spec = docIconFor(a.filename);
                    const SpecIcon = spec.Icon;
                    return (
                      <div
                        key={`${a.filename}-${i}`}
                        className="chat-attach-card"
                        title={a.filename}
                      >
                        {a.previewUrl ? (
                          <button
                            type="button"
                            className="chat-attach-thumb"
                            aria-label={`预览 ${a.filename}`}
                            onClick={() => setPreviewIndex(i)}
                          >
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={a.previewUrl}
                              alt={a.filename}
                              className={isSvgFilename(a.filename) ? 'svg' : ''}
                            />
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="chat-attach-doc"
                            aria-label={`预览 ${a.filename}`}
                            onClick={() => setPreviewIndex(i)}
                          >
                            <span className="chat-attach-doc-icon">
                              <SpecIcon size={20} strokeWidth={1.5} />
                            </span>
                            <span className="chat-attach-doc-text">
                              <strong>{a.filename}</strong>
                              <small>
                                {spec.label} · {formatBytes(a.size)}
                                {/* R23：读取中的占位卡——配额已预留，内容读取完成后原地补齐 */}
                                {a.reading ? ' · 读取中…' : ''}
                              </small>
                            </span>
                          </button>
                        )}
                        <button
                          type="button"
                          className="chat-attach-remove"
                          aria-label={`移除附件 ${a.filename}`}
                          onClick={() =>
                            patchPending(pendingKey, (p) => ({
                              // R23：移除占位/已完成卡片都从这里走，额度随之释放
                              attachments: p.attachments.filter((_, index) => index !== i),
                            }))
                          }
                        >
                          <X size={10} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
              {attachmentError && (
                <p className="chat-attach-error" role="alert">
                  {attachmentError}
                </p>
              )}
              <div className="chat-composer-tools">
                <CapabilityMenu
                  value={capabilityValue}
                  onSelect={handleSelectCapability}
                  disabled={store.sending}
                  unavailable={unavailableCapabilities}
                />
                {
                  <button
                    className="chat-add-trigger"
                    aria-label="添加附件"
                    title="添加附件（真实模式暂不支持发送附件）"
                    disabled={store.sending}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Paperclip size={18} strokeWidth={1.65} />
                  </button>
                }
                <span className="chat-flex-spacer" />
                <ComposerContextChips
                  contextTokens={profile?.contextTokens}
                  contentChars={
                    store.messages.reduce(
                      (total, message) => total + conversationProjection(message).length,
                      0,
                    ) + store.draft.length
                  }
                />
                {
                  <ModelSelector
                    catalog={catalog}
                    value={store.modelProfileId}
                    onChange={(id) => store.setModel(id)}
                    disabled={store.sending || loading}
                    presentation="popover"
                  />
                }
                {<span className="chat-ext-unavailable">扩展 · 真实模式尚未接入</span>}
                {/* 语音入口（S2）：无 STT 服务——明确未接入说明与演示转写，不采集音频 */}
                <div className="chat-voice-picker">
                  <button
                    type="button"
                    className="chat-voice-trigger"
                    aria-label="语音输入（未接入，查看说明）"
                    aria-expanded={voiceOpen}
                    disabled={store.sending}
                    onClick={() => setVoiceOpen((v) => !v)}
                  >
                    <Mic size={16} strokeWidth={1.9} />
                  </button>
                  {voiceOpen && (
                    <div className="chat-voice-panel" role="dialog" aria-label="语音输入说明">
                      <strong>语音输入 · 未接入</strong>
                      <p>
                        语音转写需要 STT 服务，当前未接入；此处不采集任何音频。
                        可插入一段带标识的演示转写文本，体验接入后的流程。
                      </p>
                      <button
                        type="button"
                        className="button subtle"
                        onClick={insertDemoTranscript}
                      >
                        插入演示转写
                      </button>
                    </div>
                  )}
                </div>
                {/* 单按钮覆盖整轮（对照参考 ChatComposer）：发送、进行中、停止是同一个元素，
                    箭头↔方块在原位交叉淡变——点击瞬间按钮不会从指针下被替换（R 连续发送回归）。
                    生成中或等待追问且主输入为空 → 停止；等待追问且有输入 → 提交回答。 */}
                {(() => {
                  const streamingBlocksSend =
                    store.sending && !(store.waitingInteractionId && store.draft.trim());
                  // R19：配置未确认/非法（capBlocked）时按钮保持可点击——点击走 submit 的
                  // capBlocked 分支打开配置卡，而不是禁用造成"必须先输入文字才能确认配置"的死锁
                  const canSend = capBlocked
                    ? store.ready
                    : store.waitingInteractionId
                      ? !!store.draft.trim() && !store.submittingReply
                      : (!!store.draft.trim() ||
                          attachments.length > 0 ||
                          selectedHistoryIds.length > 0) &&
                        store.ready &&
                        !!selection;
                  const label = streamingBlocksSend
                    ? '停止'
                    : store.waitingInteractionId
                      ? '提交回答'
                      : capBlocked
                        ? '先确认能力配置'
                        : '发送';
                  return (
                    <button
                      type="button"
                      onClick={streamingBlocksSend ? store.stop : submit}
                      disabled={!streamingBlocksSend && !canSend}
                      className={`chat-send-button ${streamingBlocksSend ? 'streaming' : ''} ${
                        !streamingBlocksSend && capBlocked ? 'blocked' : ''
                      }`}
                      aria-label={label}
                      title={
                        !streamingBlocksSend && capBlocked
                          ? '先在右侧确认能力配置，再发送。'
                          : undefined
                      }
                    >
                      <ArrowUp
                        size={20}
                        className={`chat-send-glyph ${streamingBlocksSend ? 'chat-send-glyph-off' : ''}`}
                      />
                      <Square
                        size={14}
                        fill="currentColor"
                        className={`chat-send-glyph chat-send-glyph-stop ${
                          streamingBlocksSend ? '' : 'chat-send-glyph-off'
                        }`}
                      />
                    </button>
                  );
                })()}
              </div>
            </div>
            {blockedNotice && true && (
              <p role="alert" className="chat-composer-note chat-blocked-notice">
                {blockedNotice}
                <Link href="/settings">打开设置</Link>
              </p>
            )}
            {!hasMessages && (
              <div className="chat-suggestions">
                {['用通俗语言解释一个概念', '帮我梳理知识点之间的联系', '一起设计课堂提问'].map(
                  (text) => (
                    <button
                      key={text}
                      onClick={() => {
                        store.setDraft(text);
                        textarea.current?.focus();
                      }}
                    >
                      {text}
                    </button>
                  ),
                )}
              </div>
            )}
            <p className="chat-composer-note">
              回答由模型生成，请核对重要信息。
              {store.waitingInteractionId
                ? '正在等待追问回答；输入内容后 Enter 提交，停止按钮在清空输入后显示。'
                : store.sending
                  ? '正在生成，可随时停止。'
                  : 'Shift + Enter 换行'}
            </p>
            {copyState === 'failed' && (
              <p role="alert" className="chat-composer-note">
                复制失败，请选择文字手动复制。
              </p>
            )}
          </div>
        </section>
        {(panelView !== null || panelExiting) && !isMobile && (
          <aside
            className={`chat-info ${panelView === null ? 'closing' : ''}`}
            inert={panelView === null}
            aria-hidden={panelView === null}
          >
            <WorkspacePanel
              items={openArtifacts}
              activeKey={artifactKey}
              onOpen={setArtifactKey}
              onCloseTab={closeWorkspaceTab}
              onClose={() => setPanelView(null)}
              home={
                <>
                  <InfoPanel
                    profile={profile}
                      conversations={store.conversations}
                    activeId={store.activeId}
                    messageCount={store.messages.length}
                  />
                </>
              }
            />
          </aside>
        )}
      </div>
      {panelView !== null && isMobile && (
        <Modal title="结果工作区" onClose={() => setPanelView(null)}>
          <WorkspacePanel
            items={openArtifacts}
            activeKey={artifactKey}
            onOpen={setArtifactKey}
            onCloseTab={closeWorkspaceTab}
            onClose={() => setPanelView(null)}
            home={
              <>
                <InfoPanel
                  profile={profile}
                  conversations={store.conversations}
                  activeId={store.activeId}
                  messageCount={store.messages.length}
                />
              </>
            }
          />
        </Modal>
      )}
      {previewIndex !== null && attachments[previewIndex] && (
        <Modal title={attachments[previewIndex]!.filename} onClose={() => setPreviewIndex(null)}>
          {attachments[previewIndex]!.previewUrl ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={attachments[previewIndex]!.previewUrl}
              alt={attachments[previewIndex]!.filename}
              style={{ maxWidth: '100%', maxHeight: '60vh', display: 'block', margin: '0 auto' }}
            />
          ) : (
            <p style={{ fontSize: 13, lineHeight: 1.7 }}>
              该文件类型暂无内置预览（当前无文件解析服务）。发送时仅随配置快照携带文件名、
              类型与大小，不会上传或解析文件内容。
            </p>
          )}
          <p style={{ fontSize: 12, color: '#8c929c', marginTop: 8 }}>
            {attachments[previewIndex]!.filename} · {formatBytes(attachments[previewIndex]!.size)}
          </p>
        </Modal>
      )}
      {dialog && (
        <Modal
          title={dialog.kind === 'rename' ? '重命名会话' : '删除会话'}
          onClose={() => setDialog(null)}
        >
          {dialog.kind === 'rename' ? (
            <input
              aria-label="会话名称"
              autoFocus
              value={title}
              maxLength={80}
              onChange={(e) => setTitle(e.target.value)}
            />
          ) : (
            <p>删除「{dialog.title}」？删除后无法恢复，请先备份重要内容。</p>
          )}
          <footer>
            <button className="button subtle" onClick={() => setDialog(null)}>
              取消
            </button>
            <button
              className="button primary"
              onClick={() => {
                if (dialog.kind === 'rename') void store.renameConversation(dialog.id, title);
                else
                  void store.removeConversation(dialog.id).then(() => {
                    // 删除活动会话后地址回到 /chat；删除非活动会话时地址已匹配则不变
                    syncSessionUrl(activeStore.getState().activeId, 'replace');
                  });
                setDialog(null);
              }}
            >
              {dialog.kind === 'rename' ? '保存名称' : '删除会话'}
            </button>
          </footer>
        </Modal>
      )}
    </WorkspaceShell>
  );
}
