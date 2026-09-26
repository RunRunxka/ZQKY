import { createStore } from 'zustand/vanilla';
import {
  type AskUserAnswer,
  type AskUserCardStatus,
  type AskUserDraft,
  type AskUserInteraction,
  type ChatMessage,
  type ChatServiceKind,
  type Conversation,
  type ConversationMeta,
  type ToolCallRecord,
  type TraceStageRecord,
  type TurnCourseSnapshot,
  type TurnExtensionSnapshot,
} from '@/contracts/chat';
import { createIdbChatRepository, type ChatRepository, toMeta } from '@/services/chat-repository';
import { streamChat, type ChatStreamInput } from '@/services/chat-stream';
import { ApiError } from '@/services/api-client';
import {
  createRealChatService,
  type ChatService,
  type ChatServiceEvent,
  type ChatToolCall,
} from './chat-service';
import {
  buildChatRequest,
  requestHistory,
  type BuildRequestResult,
} from './request-budget';
import { buildNewConversation, resolveCourseSnapshot } from '@/services/course-session';
import { isRagCapability, LOCAL_RAG_PROFILE } from './rag-service';

export interface ChatProfileSelection {
  id: string;
  modelLabel: string;
  contextTokens?: number | null;
  maxOutputTokens?: number | null;
}
export interface ChatDeps {
  /** 当前会话仓储，默认只打开真实问答库。 */
  repository?: ChatRepository;
  /** 兼容旧测试：注入真实服务的底层 SSE 客户端 */
  stream?: (input: ChatStreamInput, handlers: Parameters<typeof streamChat>[1]) => Promise<void>;
  service?: ChatService;
}
export interface ChatState {
  ready: boolean;
  loadError: string | null;
  storageWarning: string | null;
  /** 课程上下文不可用时的如实提示（H1-COURSE-SESSIONS v1）；null = 无提示 */
  courseContextWarning: string | null;
  /**
   * 请求构建失败时的可读提示（CHAT-CONTEXT-BUDGET v1）：当前问题超出本轮可用预算，
   * **未发送任何请求**，草稿与历史保持原样，可修改后重发；null = 无提示。
   */
  budgetNotice: string | null;
  serviceNotice: string | null;
  /** 只重连已持久化的教材轮次；不新建消息或重新推理。 */
  resumeRag(messageId: string): Promise<void>;
  /** 关闭预算提示（只清提示，不改动草稿、历史与会话归属） */
  dismissBudgetNotice(): void;
  /** 当前会话的课程归属（稳定 courseId；缺失 = 未归属）；供聊天页展示与"返回课程" */
  activeCourseId: string | null;
  /** 关闭"课程上下文不可用"提示（只清提示，不改变会话归属与历史） */
  dismissCourseContextWarning(): void;
  mode: ChatServiceKind;
  conversations: ConversationMeta[];
  activeId: string | null;
  messages: ChatMessage[];
  sending: boolean;
  draft: string;
  modelProfileId: string | null;
  init(): Promise<void>;
  /**
   * 新建会话。`options.courseId` 只在课程页创建时传入（稳定归属，不因页面停留自动绑定）；
   * 不带参数即普通未归属会话。
   */
  newConversation(options?: { courseId?: string; title?: string }): void;
  selectConversation(id: string): Promise<void>;
  renameConversation(id: string, title: string): Promise<void>;
  removeConversation(id: string): Promise<void>;
  /**
   * 深链指向已不存在的会话时的明确空态（R-10）：清空当前会话且**不创建、不保存、不自动
   * 落到最近会话**。学习记录列表与“返回学习问答”等主动操作保持不变。
   */
  deactivate(): void;
  send(
    text: string,
    profile: ChatProfileSelection | null,
    extensions?: TurnExtensionSnapshot,
    /** R20：轮次被接纳（用户消息与轮次已入库）时同步回调；拒绝路径不会触发，调用方据此清理一次性选择 */
    onAccepted?: () => void,
  ): Promise<void>;
  stop(): void;
  retryLast(profile: ChatProfileSelection | null): Promise<void>;
  retry(id: string, profile: ChatProfileSelection | null): Promise<void>;
  /** 当前等待回答的追问卡；null 表示没有进行中的等待 */
  waitingInteractionId: string | null;
  /** 追问回答提交中（幂等守卫） */
  submittingReply: boolean;
  /** 保存追问草稿（选择/自由文本），随会话持久化 */
  setAskDraft(interactionId: string, questionId: string, draft: AskUserDraft): void;
  /** 提交追问回答（幂等；失败保留草稿返回 false） */
  submitReply(answers: AskUserAnswer[]): Promise<boolean>;
  /** 主输入框回答当前追问：自由文本计入第一道未答题，其余按草稿/跳过提交 */
  submitComposerReply(text: string): Promise<boolean>;
  setDraft(text: string): void;
  setModel(id: string | null): void;
  flush(): Promise<boolean>;
  dispose(): void;
  exportActive(): string;
}
const uid = () => crypto.randomUUID();
const now = () => new Date().toISOString();

export function createChatStore(deps: ChatDeps = {}) {
  const repo = deps.repository ?? createIdbChatRepository();
  const service = deps.service ?? createRealChatService({ stream: deps.stream });
  const docs = new Map<string, Conversation>(),
    dirty = new Set<string>();
  let timer: ReturnType<typeof setTimeout> | null = null;
  let saving: Promise<boolean> | null = null,
    initPromise: Promise<void> | null = null;
  type GenerationToken = {
    controller: AbortController;
    conversationId: string;
    assistantId: string;
    turnId: string;
    channel?: 'rag';
    /** R3：本轮是否已终态（end/error/取消）。终态后拒绝一切阶段与过程更新 */
    terminal: boolean;
    /** R11 补充：轮次以何种方式结束——区分正常完成与错误/断流/停止（迟到 ACK 归属判定用） */
    endReason: 'end' | 'error' | 'stop' | 'disconnect' | null;
  };
  let generation: GenerationToken | null = null;
  let selectionEpoch = 0;
  let ragPreflightPending = false;
  /** 当前进行中的追问提交（R11：结果只归属发起时的身份，不持久化） */
  let activeSubmissionId: string | null = null;
  /** 当前等待回答的追问（运行上下文，不持久化） */
  /**
   * 流式文本的 UI 提交合并（UX-PERF-CLOSEOUT v1，长推理流卡顿）。
   *
   * 每个增量都单独提交会让浏览器对**整段增长中的推理文本**重做一次换行布局：
   * 实测 50k 字推理轮 2000 次提交 → 布局 11.7s、脚本 2.2s。这里按「前缘立即 +
   * 尾部合并」节流：首个增量立即可见（首个可见增量延迟不变差），其后最多每
   * `STREAM_COMMIT_INTERVAL_MS` 提交一次，**可见更新时延上限就是该值**。
   * 缓冲按顺序保存每一段（推理/正文），提交时按原顺序折叠，事件顺序与原文不丢；
   * 任何非文本事件、终止/停止/切换会话/落盘前都先 flush，保证不吞增量。
   */
  let pendingStream: {
    apply: (update: (m: ChatMessage) => ChatMessage) => void;
    segments: { text?: string; reasoning?: string }[];
  } | null = null;
  let streamCommitTimer: ReturnType<typeof setTimeout> | null = null;
  let lastStreamCommitAt = -Infinity;
  return createStore<ChatState>()((set, get) => {
    const TOOL_TERMINAL: ToolCallRecord['status'][] = ['done', 'error', 'cancelled'];
    /** 工具事件按 callId 去重更新；已终态（done/error/cancelled）的卡片不接受重开或改写 */
    function applyToolCall(m: ChatMessage, call: ChatToolCall): ChatMessage {
      const calls = m.toolCalls ?? [];
      const index = calls.findIndex((c) => c.callId === call.callId);
      if (index === -1)
        return {
          ...m,
          toolCalls: [
            ...calls,
            {
              callId: call.callId,
              kind: call.kind,
              name: call.name,
              status: call.status,
              note: call.note,
              detail: call.detail,
              startedAt: now(),
              ...(call.status !== 'running' ? { endedAt: now() } : {}),
            },
          ],
        };
      const existing = calls[index];
      if (TOOL_TERMINAL.includes(existing.status)) return m;
      const next = [...calls];
      next[index] = {
        ...existing,
        status: call.status,
        note: call.note ?? existing.note,
        detail: call.detail ?? existing.detail,
        ...(call.status !== 'running' && !existing.endedAt ? { endedAt: now() } : {}),
      };
      return { ...m, toolCalls: next };
    }
    /** 本轮收尾：所有仍在运行的工具统一结束为“已取消”，不永久停留在运行中 */
    function closeRunningTools(m: ChatMessage): ChatMessage {
      if (!m.toolCalls?.some((c) => c.status === 'running')) return m;
      return {
        ...m,
        toolCalls: m.toolCalls.map((c) =>
          c.status === 'running'
            ? { ...c, status: 'cancelled', endedAt: c.endedAt ?? now() }
            : c,
        ),
      };
    }
    /** S4：本轮收尾时未完成阶段统一收口——正常完成 done、异常/停止 cancelled */
    function closeRunningStages(m: ChatMessage, final: 'done' | 'cancelled'): ChatMessage {
      if (!m.stages?.some((s) => s.status === 'running')) return m;
      return {
        ...m,
        stages: m.stages.map((s) =>
          s.status === 'running'
            ? { ...s, status: final, endedAt: s.endedAt ?? now() }
            : s,
        ),
      };
    }
    const ASK_OPEN_STATUSES: AskUserCardStatus[] = ['preview', 'waiting', 'submitting', 'failed'];
    /** 追问等待收尾：轮次终态/取消/历史恢复后，未回答的卡标记中断，不可再提交 */
    function closeUnansweredAsks(m: ChatMessage): ChatMessage {
      if (!m.asks?.some((a) => ASK_OPEN_STATUSES.includes(a.status))) return m;
      return {
        ...m,
        asks: m.asks.map((a) =>
          ASK_OPEN_STATUSES.includes(a.status) ? { ...a, status: 'interrupted' } : a,
        ),
      };
    }
    /** 已终结的卡不受迟到 wait-user 事件影响（R14） */
    const ASK_PROTECTED_STATUSES: AskUserCardStatus[] = ['answered', 'submitting', 'interrupted'];
    /**
     * wait-user 事件按 interactionId 就地更新（R13/R14）：
     * - 不重复建卡；已回答/提交中/中断的卡不受迟到事件影响；
     * - 新事件为权威数据：按稳定 id 整体更新题目与引言（部分预览可被完整 waiting 补全）；
     * - 保留已填草稿；迟到 preview 不把 waiting 降级。
     */
    function upsertAsk(
      m: ChatMessage,
      interaction: Pick<AskUserInteraction, 'interactionId' | 'intro' | 'questions' | 'status'>,
    ): ChatMessage {
      const asks = m.asks ?? [];
      const index = asks.findIndex((a) => a.interactionId === interaction.interactionId);
      if (index === -1)
        return {
          ...m,
          asks: [
            ...asks,
            {
              interactionId: interaction.interactionId,
              intro: interaction.intro,
              questions: interaction.questions,
              status: interaction.status,
              drafts: {},
            },
          ],
        };
      const existing = asks[index]!;
      const next = [...asks];
      if (ASK_PROTECTED_STATUSES.includes(existing.status)) {
        return { ...m, asks: next };
      }
      // R13 补充：waiting/failed 之后的过期 preview 不得覆盖已确认完整的题目、选项或引言
      if (interaction.status === 'preview' && existing.status !== 'preview') {
        return { ...m, asks: next };
      }
      next[index] = {
        ...existing,
        intro: interaction.intro ?? existing.intro,
        questions: interaction.questions.length ? interaction.questions : existing.questions,
        status: interaction.status,
      };
      return { ...m, asks: next };
    }
    /** 正文增量路由：首卡之前进 content，之后进最近一张卡的续写（同轮顺序正确） */
    function appendTurnText(m: ChatMessage, delta: string): ChatMessage {
      const asks = m.asks;
      if (asks?.length) {
        const last = asks[asks.length - 1]!;
        const next = [...asks];
        next[asks.length - 1] = { ...last, followUp: (last.followUp ?? '') + delta };
        return { ...m, asks: next };
      }
      return { ...m, content: m.content + delta };
    }
    function updateAsk(
      id: string,
      interactionId: string,
      update: (a: AskUserInteraction) => AskUserInteraction,
    ) {
      change(id, (c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.asks?.some((a) => a.interactionId === interactionId)
            ? {
                ...m,
                asks: m.asks!.map((a) =>
                  a.interactionId === interactionId ? update(a) : a,
                ),
              }
            : m,
        ),
      }));
    }
    function markReplyFailed(
      sessionId: string | null,
      interactionId: string,
      code: string,
      message: string,
    ) {
      // R11：写入发起时会话，而不是完成时恰好活跃的会话
      if (!sessionId) return;
      updateAsk(sessionId, interactionId, (a) => ({
        ...a,
        status: a.status === 'answered' ? a.status : 'failed',
        error: { code, message },
      }));
    }
    /** 追问提交核心（R11）：结果只归属发起时的会话/轮次/交互/提交身份；幂等守卫、失败保留草稿 */
    async function submitReplyAnswers(answers: AskUserAnswer[]): Promise<boolean> {
      const interactionId = get().waitingInteractionId;
      // 幂等：无有效等待或已在提交中时直接拒绝，重复点击/确认只消费一次
      if (!interactionId || get().submittingReply) return false;
      const activeGeneration = generation;
      if (!activeGeneration || activeGeneration.terminal) {
        // 本地等待上下文已失效（取消/断流/切轮）：明确拒绝并收尾，不假装成功
        markReplyFailed(get().activeId, interactionId, 'WAIT_INVALID', '本轮等待已失效，无法提交。');
        set({ waitingInteractionId: null });
        return false;
      }
      // R11：发起时冻结全部身份；异步返回只允许修改仍由它拥有的状态
      const sessionId = get().activeId!;
      const turnId = activeGeneration.turnId;
      const ownerToken = activeGeneration;
      const ownerCard = docs.get(sessionId)?.messages.flatMap((m) => m.asks ?? []).find((a) => a.interactionId === interactionId);
      // 请求已发出而 ACK 丢失时，必须复用原载荷和幂等键，不能再次消费不同答案。
      const pending = ownerToken.channel === 'rag' ? ownerCard?.pendingSubmission : undefined;
      const submissionId = pending?.submissionId ?? uid();
      if (pending) answers = structuredClone(pending.answers);
      if (!service.submitReply) {
        markReplyFailed(sessionId, interactionId, 'REPLY_NOT_SUPPORTED', '当前服务不支持追问回答。');
        return false;
      }
      activeSubmissionId = submissionId;
      set({ submittingReply: true });
      updateAsk(sessionId, interactionId, (a) =>
        a.status === 'answered' ? a : { ...a, status: 'submitting', error: undefined,
          ...(ownerToken.channel === 'rag' ? { pendingSubmission: { submissionId, answers: structuredClone(answers) } } : {}),
        },
      );
      try {
        // 在真正提交前持久化意图，刷新后才能安全重发同一 submissionId。
        if (ownerToken.channel === 'rag' && !(await flush())) {
          markReplyFailed(sessionId, interactionId, 'SAVE_FAILED', '回答尚未提交：本地保存失败，请重试保存。');
          return false;
        }
        const result = await service.submitReply({
          sessionId,
          turnId,
          interactionId,
          submissionId,
          answers,
          signal: ownerToken.controller.signal,
          ...(ownerToken.channel ? { channel: ownerToken.channel } : {}),
        });
        // 归属校验（R11 补充 + 交付复核 P2）：中止（取消/停止）或被新轮顶替后，迟到确认不得改写状态。
        // 终态与 Promise 生命周期区分：generation 仍指向本轮只说明运行对象未释放；
        // endReason 非 null 表示业务轮次已终结（end/error/stop/disconnect）——
        // error/断流后即使 run Promise 尚未返回，未确认的迟到 ACK 也一律拒绝。
        // 合法同步续答的顺序=确认（accept 消费）→ 续答/收尾（endReason='end'）→ 提交返回值，
        // 因此 endReason==='end' 时迟到确认仍然接受。
        const aborted = ownerToken.controller.signal.aborted;
        const superseded = generation !== null && generation !== ownerToken;
        const turnAlive = generation === ownerToken && ownerToken.endReason === null;
        const endedAfterAccept = ownerToken.endReason === 'end';
        const stillOwned =
          !aborted &&
          !superseded &&
          (turnAlive || endedAfterAccept) &&
          activeSubmissionId === submissionId &&
          get().activeId === sessionId;
        if (!stillOwned) return false;
        if (!result.accepted) {
          if (ownerToken.channel === 'rag') updateAsk(sessionId, interactionId, (a) => ({ ...a, pendingSubmission: undefined }));
          markReplyFailed(
            sessionId,
            interactionId,
            result.code ?? 'REPLY_REJECTED',
            result.message ?? '回答未被接受，草稿已保留，可重试。',
          );
          return false;
        }
        updateAsk(sessionId, interactionId, (a) => ({
          ...a,
          status: 'answered',
          answers,
          error: undefined,
          pendingSubmission: undefined,
        }));
        if (get().waitingInteractionId === interactionId)
          set({ waitingInteractionId: null });
        return true;
      } catch (error) {
        const stillOwned =
          generation === ownerToken &&
          ownerToken.endReason === null && // 终态后的迟到异常不重写已收尾的卡
          activeSubmissionId === submissionId &&
          get().activeId === sessionId;
        if (stillOwned) {
          // 明确的输入校验拒绝未消费回答，允许用户修改；网络错误继续保留原提交意图。
          if (ownerToken.channel === 'rag' && error instanceof ApiError && [400, 422].includes(error.status)) {
            updateAsk(sessionId, interactionId, (a) => ({ ...a, pendingSubmission: undefined }));
          }
          if (ownerToken.controller.signal.aborted) {
            markReplyFailed(sessionId, interactionId, 'WAIT_CANCELLED', '本轮已取消，回答未提交。');
          } else {
            markReplyFailed(
              sessionId,
              interactionId,
              'REPLY_FAILED',
              error instanceof Error ? error.message : '回答提交失败，草稿已保留，可重试。',
            );
          }
        }
        return false;
      } finally {
        // 只释放自己名下的提交锁（R11：不清掉新提交的身份）
        if (activeSubmissionId === submissionId) {
          activeSubmissionId = null;
          set({ submittingReply: false });
        }
      }
    }
    /**
     * 把合并缓冲里的文本按原顺序折叠进消息（一次 change = 一次 UI 提交）。
     * 只在消息仍为 streaming 时写入；轮次已终态时丢弃（迟到增量本来就该丢）。
     */
    function flushStreamText() {
      if (streamCommitTimer) {
        clearTimeout(streamCommitTimer);
        streamCommitTimer = null;
      }
      const pending = pendingStream;
      pendingStream = null;
      if (!pending || pending.segments.length === 0) return;
      const { apply, segments } = pending;
      lastStreamCommitAt = Date.now();
      apply((m) => {
        if (m.status !== 'streaming') return m;
        let next = m;
        for (const segment of segments) {
          if (segment.reasoning)
            next = { ...next, reasoning: (next.reasoning ?? '') + segment.reasoning };
          else if (segment.text) next = appendTurnText(next, segment.text);
        }
        return next;
      });
    }
    /** 入队一个文本增量：前缘立即提交，其后按 STREAM_COMMIT_INTERVAL_MS 合并 */
    const STREAM_COMMIT_INTERVAL_MS = 80;
    function queueStreamSegment(
      apply: (update: (m: ChatMessage) => ChatMessage) => void,
      segment: { text?: string; reasoning?: string },
    ) {
      if (!pendingStream) pendingStream = { apply, segments: [] };
      pendingStream.segments.push(segment);
      const elapsed = Date.now() - lastStreamCommitAt;
      if (elapsed >= STREAM_COMMIT_INTERVAL_MS) {
        flushStreamText();
        return;
      }
      if (!streamCommitTimer)
        streamCommitTimer = setTimeout(() => {
          streamCommitTimer = null;
          flushStreamText();
        }, STREAM_COMMIT_INTERVAL_MS - elapsed);
    }
    function publish() {
      // 本 store 的 docs 只包含自己模式的数据（R2），无需再按模式过滤。
      // S5-A：已归档会话不出现在聊天侧边栏（/space/chat-history 管理），仍可经深链打开
      const active = docs.get(get().activeId ?? '');
      set({
        messages: active?.messages ?? [],
        draft: active?.draft ?? '',
        modelProfileId: active?.modelProfileId ?? null,
        activeCourseId: active?.courseId ?? null,
        conversations: [...docs.values()]
          .filter((c) => !c.archived)
          .map(toMeta)
          .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)),
      });
    }
    function change(id: string, update: (c: Conversation) => Conversation) {
      const c = docs.get(id);
      if (!c) return;
      docs.set(id, { ...update(c), updatedAt: now() });
      dirty.add(id);
      publish();
      if (!timer)
        timer = setTimeout(() => {
          timer = null;
          void flush();
        }, 400);
    }
    async function flush(): Promise<boolean> {
      flushStreamText(); // 落库前先提交未进 UI 的增量，保证刷新/离开时不丢内容
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      // 串行保存队列（交付复核 S3 修复）：并发调用不得丢弃新脏数据——
      // 旧实现"保存中直接返回在途 Promise"会取消挂起的防抖 timer，
      // 导致保存期间到达的变更无人重排（点击面板/下载触发的 blur→flush 即可复现，
      // 刷新后数据丢失）。改为链式排队：后到的 flush 在前一个完成后处理剩余脏数据。
      //
      // UX-PERF-CLOSEOUT v1（长推理流卡顿）：每轮只保存"进入时脏快照"。
      // 旧实现的 `while (dirty.size)` 会在持续增量下把新脏数据不断接进同一轮循环，
      // 实测一次 50k 字推理轮写了 184 次 / 4.10MB（约每 170ms 一次整表结构化克隆）。
      // 改为快照按轮保存后退出：保存期间新增的脏数据仍留在 dirty 中，且 change() 在
      // timer 已清空时会重新安排 400ms 落盘，终态（end/error/停止/断流）与
      // 切会话/离开页面路径上的 flush 都以 generation===null 进入循环到清空，
      // 因此"显式 flush 落全部"的契约在需要它的时机不变。
      const tail = saving ?? Promise.resolve(true);
      const next = tail.then(async () => {
        do {
          for (const id of [...dirty]) {
            const snapshot = docs.get(id);
            dirty.delete(id);
            if (!snapshot) continue;
            try {
              const revision = await repo.save(snapshot, snapshot.revision ?? 0);
              const latest = docs.get(id);
              if (latest) docs.set(id, { ...latest, revision });
            } catch (error) {
              dirty.add(id);
              set({
                storageWarning:
                  error instanceof Error ? error.message : '保存失败，当前内容仍保留在页面中。',
              });
              return false;
            }
          }
        } while (dirty.size && generation === null);
        set({ storageWarning: null });
        return true;
      });
      saving = next;
      try {
        return await next;
      } finally {
        if (saving === next) saving = null;
      }
    }
    function stop() {
      const active = generation;
      if (!active) return;
      flushStreamText(); // 停止前提交尚未进入 UI 的增量，避免丢最后一段
      generation = null;
      active.terminal = true; // R3：取消即终态，此后迟到事件不再修改消息
      active.endReason = 'stop';
      activeSubmissionId = null;
      set({ waitingInteractionId: null, submittingReply: false });
      if (active.channel === 'rag') void service.cancel?.({ sessionId: active.conversationId, turnId: active.turnId, channel: 'rag' }).catch(() => {
        set({ serviceNotice: '已在本页停止；教材服务未确认取消，后台任务将按超时限制结束。' });
      });
      active.controller.abort();
      change(active.conversationId, (c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.id === active.assistantId && m.status === 'streaming'
            ? closeUnansweredAsks(
                closeRunningTools({ ...m, status: 'stopped', finishReason: 'client-stop', finishedAt: now(), ...(m.rag ? { rag: { ...m.rag, status: 'terminal' } } : {}) }),
              )
            : m,
        ),
      }));
      set({ sending: false });
      void flush();
    }
    function create(options?: { courseId?: string; title?: string }) {
      stop();
      selectionEpoch++;
      const id = uid();
      // 会话形状由 services/course-session.buildNewConversation 统一给出（课程页新建也用它，不建第二套形状）
      docs.set(
        id,
        buildNewConversation({
          id,
          ...(options?.courseId ? { courseId: options.courseId } : {}),
          ...(options?.title ? { title: options.title } : {}),
          now: now(),
        }),
      );
      // 新建会话：课程上下文警告属于上一轮/上一会话，随切换清除（A1 r1 F2）
      set({ activeId: id, courseContextWarning: null, budgetNotice: null });
      change(id, (conversation) => conversation);
    }
    /**
     * 统一事件路由：真实 SSE 与模拟服务都经这里进入状态。
     * 事件必须匹配当前轮次与会话；取消、切换会话、新一轮开始或本轮已终态
     * （收到 end/error 之后）的迟到事件一律丢弃（R3）。
     */
    function makeEmitter(
      token: {
        conversationId: string;
        assistantId: string;
        turnId: string;
        channel?: 'rag';
        terminal: boolean;
        endReason: 'end' | 'error' | 'stop' | 'disconnect' | null;
      },
      id: string,
    ) {
      return function emit(event: ChatServiceEvent) {
        if (generation !== token) return; // 已取消或已被新一轮替换
        if (event.turnId !== token.turnId || event.sessionId !== id) return; // 串会话/串轮次防御
        if (token.terminal) return; // 本轮已终态：end/error 之后不再接受阶段与过程更新
        const current = docs.get(id)?.messages.find((m) => m.id === token.assistantId);
        if (event.eventId !== undefined && current?.rag && event.eventId <= current.rag.lastEventId) return;
        const patch = (update: (m: ChatMessage) => ChatMessage) =>
          change(id, (c) => ({
            ...c,
            messages: c.messages.map((m) => {
              if (m.id !== token.assistantId) return m;
              const next = update(m);
              return next.rag && event.eventId !== undefined
                ? { ...next, rag: { ...next.rag, lastEventId: event.eventId } } : next;
            }),
          }));
        // 文本增量按顺序进合并缓冲；其他事件（阶段/工具/追问/产物/终态）先提交缓冲区，
        // 保证"事件顺序严格不变"与"不吞增量"
        const isStreamText = event.type === 'text' || event.type === 'reasoning';
        if (!isStreamText) flushStreamText();
        switch (event.type) {
          case 'text':
            if (token.channel === 'rag') patch((m) => appendTurnText(m, event.delta));
            else if (event.delta) queueStreamSegment(patch, { text: event.delta });
            break;
          case 'reasoning':
            if (event.delta) queueStreamSegment(patch, { reasoning: event.delta });
            break;
          case 'process':
            // 过程增量：最新一条展示为状态行；完整过程工作区在后续阶段接入
            if (event.delta) patch((m) => ({ ...m, processNote: event.delta }));
            break;
          case 'stage': {
            // S4：阶段序列记录（按 stageId 原地更新，重复事件不新增条目）；
            // stageLabel 仍保留“最新运行中阶段”供状态行使用
            const stageId = event.stageId ?? event.label;
            patch((m) => {
              const stages = m.stages ?? [];
              const idx = stages.findIndex((s) => s.stageId === stageId);
              const next = [...stages];
              if (event.phase === 'start') {
                const record: TraceStageRecord = {
                  stageId,
                  label: event.label,
                  status: 'running',
                  startedAt: stages[idx]?.startedAt ?? now(),
                };
                if (idx === -1) next.push(record);
                else next[idx] = { ...stages[idx]!, ...record };
              } else {
                const record: TraceStageRecord = {
                  stageId,
                  label: event.label,
                  status: 'done',
                  startedAt: stages[idx]?.startedAt ?? now(),
                  endedAt: now(),
                };
                if (idx === -1) next.push(record);
                else next[idx] = { ...stages[idx]!, ...record };
              }
              return {
                ...m,
                stageLabel: event.phase === 'end' ? undefined : event.label,
                stages: next,
              };
            });
            break;
          }
          case 'tool':
            patch((m) => applyToolCall(m, event.call));
            break;
          case 'wait-user': {
            // R14：活动卡依据 upsert 后的合法状态决定——事件标记 waiting 不直接赋权，
            // 已回答/提交中/中断的卡不会因重复事件重新取得等待权
            let upsertedStatus: AskUserCardStatus | null = null;
            patch((m) => {
              const next = upsertAsk(m, event.interaction);
              upsertedStatus =
                next.asks?.find((a) => a.interactionId === event.interaction.interactionId)
                  ?.status ?? null;
              return next;
            });
            if (upsertedStatus === 'waiting') {
              set({ waitingInteractionId: event.interaction.interactionId });
            }
            break;
          }
          case 'artifact':
            // S3 结果工作区：产物按 id 幂等更新（同 id 覆盖=增量/完成；新 id 追加）。
            // 终态/取消后 emit 入口守卫已拒绝迟到的产物事件，不污染当前会话。
            patch((m) => {
              const artifacts = m.artifacts ?? [];
              const index = artifacts.findIndex((a) => a.id === event.artifact.id);
              const next = [...artifacts];
              if (index === -1) next.push({ ...event.artifact, createdAt: now() });
              else next[index] = { ...event.artifact, createdAt: artifacts[index]!.createdAt };
              return { ...m, artifacts: next };
            });
            break;
          case 'reply-accepted':
            patch((m) => ({ ...m, asks: m.asks?.map((a) => a.interactionId === event.interactionId
              ? { ...a, status: 'answered', answers: event.answers, pendingSubmission: undefined, error: undefined } : a) }));
            if (get().waitingInteractionId === event.interactionId) set({ waitingInteractionId: null });
            break;
          case 'checkpoint':
          case 'turn-start':
            if (token.channel === 'rag') patch((m) => m);
            break;
          case 'usage':
            patch((m) => ({ ...m, usage: event.usage }));
            break;
          case 'end':
            patch((m) =>
              closeUnansweredAsks(
                closeRunningStages(
                  closeRunningTools(
                    m.status === 'streaming'
                      ? { ...m, status: 'done', finishReason: event.finishReason, finishedAt: now(), ...(m.rag ? { rag: { ...m.rag, status: 'terminal' } } : {}) }
                      : m,
                  ),
                  'done',
                ),
              ),
            );
            set({ waitingInteractionId: null });
            token.endReason = 'end';
            token.terminal = true;
            break;
          case 'error':
            patch((m) =>
              closeUnansweredAsks(
                closeRunningStages(
                  closeRunningTools(
                    m.status === 'streaming' ? { ...m, status: 'error', error: event.error, finishedAt: now(), ...(m.rag ? { rag: { ...m.rag, status: 'terminal' } } : {}) } : m,
                  ),
                  'cancelled',
                ),
              ),
            );
            set({ waitingInteractionId: null });
            token.endReason = 'error';
            token.terminal = true;
            break;
        }
        // 教材事件较稀疏；每条按完整内容+游标一起保存，防止刷新后游标超前。
        if (token.channel === 'rag') void flush();
      };
    }
    /** 本轮已构建好的请求（由 buildChatRequest 产出；request.messages 与实际发送逐条一致） */
    interface PreparedTurn {
      request: Extract<BuildRequestResult, { ok: true }>;
      extensions?: TurnExtensionSnapshot;
      courseSnapshot?: TurnCourseSnapshot;
    }
    async function run(profile: ChatProfileSelection, replyToId: string, prepared: PreparedTurn) {
      const { extensions, courseSnapshot } = prepared;
      const id = get().activeId!;
      const assistantId = uid();
      const turnId = uid();
      const isRag = isRagCapability(extensions);
      const rag = isRag ? { sessionId: id, turnId, question: prepared.request.messages.at(-1)!.content, lastEventId: 0, status: 'active' as const } : undefined;
      const token = {
        controller: new AbortController(),
        conversationId: id,
        assistantId,
        turnId,
        ...(isRag ? { channel: 'rag' as const } : {}),
        terminal: false,
        endReason: null,
      };
      generation = token;
      set({ sending: true });
      // CHAT-CONTEXT-BUDGET v1：请求体在**发送前**已由 buildChatRequest 统一构建
      // （课程块 + 历史 + 当前问题同一预算），这里只做透传，绝不二次裁剪，
      // 保证 requestBudget 账目与实际发送内容逐字段可核。
      const requestMessages = prepared.request.messages;
      change(id, (c) => ({
        ...c,
        messages: [
          ...c.messages,
          {
            id: assistantId,
            replyToId,
            role: 'assistant',
            content: '',
            status: 'streaming',
            startedAt: now(),
            modelLabel: profile.modelLabel,
            modelProfileId: profile.id,
            ...(rag ? { rag } : {}),
            // 快照随消息冻结并持久化：重试沿用，目录后续变化不影响本轮与历史展示
            ...(extensions ? { extensions: structuredClone(extensions) } : {}),
            // 课程快照同样随本轮冻结：课程改名/改约定只影响**新轮**，重试沿用原快照
            ...(courseSnapshot ? { courseContext: structuredClone(courseSnapshot) } : {}),
            // 本次请求的字符账目（字符估算）：随消息持久化，刷新可核
            requestBudget: structuredClone(prepared.request.record),
          },
        ],
      }));
      const emit = makeEmitter(token, id);
      try {
        if (isRag && !(await flush())) throw new ApiError('SAVE_FAILED', '本地保存失败，本轮尚未请求教材服务。', 0, true);
        await service.run(
          {
            sessionId: id,
            turnId,
            messages: requestMessages,
            modelProfileId: profile.id,
            maxOutputTokens: profile.maxOutputTokens ?? undefined,
            ...(extensions ? { extensions: structuredClone(extensions) } : {}),
            ...(rag ? { rag } : {}),
            signal: token.controller.signal,
          },
          emit,
        );
        patchStoppedIfStreaming(token, id);
      } catch (error) {
        if (
          token.controller.signal.aborted ||
          (error instanceof DOMException && error.name === 'AbortError') ||
          (error instanceof Error && error.name === 'AbortError')
        )
          patchStoppedIfStreaming(token, id, 'client-stop');
        else if (isRag && isRecoverableRagError(error)) patchRagInterrupted(token, error);
        else patchError(token, id, error);
      } finally {
        if (generation === token) {
          generation = null;
          set({ sending: false });
          // 等待/提交上下文只在运行期存在；R11：仅当本轮仍是活跃轮时才释放，
          // 旧轮迟到的收尾不得清掉新轮的等待身份或提交锁
          set({ waitingInteractionId: null, submittingReply: false });
        }
        await flush();
      }
    }
    function isRecoverableRagError(error: unknown): boolean {
      return !(error instanceof ApiError) || ['RAG_DISCONNECTED', 'STREAM_INTERRUPTED', 'SERVICE_UNAVAILABLE'].includes(error.code);
    }
    function patchRagInterrupted(token: GenerationToken, error?: unknown) {
      if (generation !== token || token.terminal) return;
      flushStreamText();
      token.terminal = true;
      token.endReason = 'disconnect';
      activeSubmissionId = null;
      change(token.conversationId, (c) => ({ ...c, messages: c.messages.map((m) => m.id === token.assistantId && m.rag
        ? closeUnansweredAsks({ ...m, status: 'stopped', finishReason: 'disconnected', finishedAt: now(),
          rag: { ...m.rag, status: 'interrupted' },
          error: { code: 'RAG_DISCONNECTED', message: error instanceof Error ? error.message : '连接已中断，可继续本轮恢复教材服务结果。', retryable: true },
        }) : m) }));
      set({ waitingInteractionId: null, submittingReply: false });
    }
    async function resumeRag(messageId: string) {
      if (generation || get().sending || !get().activeId) return;
      const id = get().activeId!;
      const message = docs.get(id)?.messages.find((m) => m.id === messageId);
      if (!message?.rag || message.rag.status !== 'interrupted' || message.rag.sessionId !== id) return;
      // 旧轮后已有新轮时不复活，避免旧答案写入用户正在使用的新轮。
      if (docs.get(id)?.messages.at(-1)?.id !== messageId) return;
      const rag = { ...message.rag, status: 'active' as const };
      const token: GenerationToken = { controller: new AbortController(), conversationId: id, assistantId: messageId, turnId: rag.turnId, channel: 'rag', terminal: false, endReason: null };
      generation = token;
      const lastAsk = message.asks?.at(-1);
      const waitingId = lastAsk && ['waiting', 'failed', 'submitting', 'interrupted'].includes(lastAsk.status) ? lastAsk.interactionId : null;
      change(id, (c) => ({ ...c, messages: c.messages.map((m) => m.id === messageId ? {
        ...m, status: 'streaming', finishedAt: undefined, finishReason: undefined, error: undefined, rag,
        asks: m.asks?.map((a) => a.interactionId === waitingId ? { ...a, status: 'waiting', error: undefined } : a),
      } : m) }));
      set({ sending: true, waitingInteractionId: waitingId, serviceNotice: null });
      try {
        await service.run({ sessionId: id, turnId: rag.turnId, rag, messages: [{ role: 'user', content: rag.question }],
          modelProfileId: LOCAL_RAG_PROFILE.id, extensions: message.extensions, signal: token.controller.signal,
        }, makeEmitter(token, id));
        patchStoppedIfStreaming(token, id);
      } catch (error) {
        if (!token.controller.signal.aborted) {
          if (isRecoverableRagError(error)) patchRagInterrupted(token, error);
          else patchError(token, id, error);
        }
      } finally {
        if (generation === token) {
          generation = null;
          set({ sending: false, waitingInteractionId: null, submittingReply: false });
        }
        await flush();
      }
    }
    function patchStoppedIfStreaming(
      token: {
        controller: AbortController;
        conversationId: string;
        assistantId: string;
        turnId: string;
        channel?: 'rag';
        terminal: boolean;
        endReason: 'end' | 'error' | 'stop' | 'disconnect' | null;
      },
      id: string,
      reason: 'disconnected' | 'client-stop' = 'disconnected',
    ) {
      if (generation !== token) return;
      // 终态只进入一次（交付复核 P2）：end/error 已给出明确终态时，
      // 通用断流兜底不得覆盖 endReason（否则合法同步续答的迟到确认会被误拒为断流）
      if (token.terminal || token.endReason) return;
      if (token.channel === 'rag' && reason === 'disconnected') {
        patchRagInterrupted(token);
        return;
      }
      flushStreamText(); // 断流也要把已收到的增量提交进 UI
      token.terminal = true; // 流已结束（含未收到 end 的断流）：本轮终态
      token.endReason = reason === 'client-stop' ? 'stop' : 'disconnect';
      change(id, (c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.id === token.assistantId && m.status === 'streaming'
            ? closeUnansweredAsks(
                closeRunningStages(
                  closeRunningTools({ ...m, status: 'stopped', finishReason: reason, finishedAt: now() }),
                  'cancelled',
                ),
              )
            : m,
        ),
      }));
    }
    function patchError(
      token: {
        conversationId: string;
        assistantId: string;
        turnId: string;
        terminal: boolean;
        endReason: 'end' | 'error' | 'stop' | 'disconnect' | null;
      },
      id: string,
      error: unknown,
    ) {
      if (generation !== token) return;
      // 终态只进入一次：end/stop 已给出明确终态时，异常收尾不得改判（幂等进入条件）
      if (token.terminal || token.endReason) return;
      flushStreamText(); // 异常收尾也要把已收到的增量提交进 UI
      token.terminal = true; // 异常收尾：本轮终态
      token.endReason = 'error';
      change(id, (c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.id === token.assistantId && m.status === 'streaming'
            ? closeUnansweredAsks(
                closeRunningStages(
                  closeRunningTools({
                    ...m,
                    status: 'error',
                    ...(m.rag ? { rag: { ...m.rag, status: 'terminal' as const } } : {}),
                    // R25：异常收尾也是终态——必须冻结耗时，不能让标题区继续计时
                    finishedAt: now(),
                    error:
                      error instanceof ApiError
                        ? { code: error.code, message: error.message, retryable: error.retryable }
                        : {
                            code: 'STREAM_INTERRUPTED',
                            message: '连接中断，已保留收到的内容。',
                            retryable: true,
                          },
                  }),
                  'cancelled',
                ),
              )
            : m,
        ),
      }));
    }
    function latestConversation(): Conversation | null {
      // S5-A：默认活动会话不落在已归档会话上
      return (
        [...docs.values()]
          .filter((c) => !c.archived)
          .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))[0] ?? null
      );
    }
    /**
     * 历史载入的统一恢复语义（R5）：标注本 store 模式，中断的 streaming 消息收尾为
     * 已停止，运行中的工具收尾为已取消，未完成的追问等待标记中断——初始化与再次
     * 选择会话共用，恢复不重放。保留 revision、消息内容、扩展快照、工具与追问历史，
     * 不清库、不覆盖其他标签页更新。
     * R25：恢复的耗时必须终态冻结——中断收尾与缺少 finishedAt 的历史消息统一以
     * 会话最后保存时间（c.updatedAt，持久化、跨次载入稳定）作为可解释的冻结结束值，
     * 不把离线经过时间当推理耗时，也不在每次载入时重算一个更大的结束值。
     */
    function normalizeLoaded(c: Conversation): Conversation {
      return {
        ...c,
        mode: 'real',
        messages: c.messages.map((m) => {
          if (m.rag && m.rag.status !== 'terminal') return closeUnansweredAsks({
            ...m, status: 'stopped', finishReason: 'disconnected', finishedAt: m.finishedAt ?? c.updatedAt,
            rag: { ...m.rag, status: 'interrupted' },
          });
          const closed = closeUnansweredAsks(
            closeRunningTools(
              m.status === 'streaming'
                ? {
                    ...m,
                    status: 'stopped',
                    finishReason: 'disconnected',
                    finishedAt: m.finishedAt ?? c.updatedAt,
                  }
                : m,
            ),
          );
          // 旧历史兼容：终态消息缺失 finishedAt 时补冻结值，避免载入后持续计时
          if (closed.startedAt && !closed.finishedAt && closed.status !== 'streaming')
            return { ...closed, finishedAt: c.updatedAt };
          return closed;
        }),
      };
    }
    function runInit(): Promise<void> {
      if (!initPromise)
        initPromise = (async () => {
          // R2：只加载自己的仓储；失败不覆盖已有数据，也不阻塞其他模式的 store
          try {
            const all = await repo.list();
            for (const meta of all) {
              const c = await repo.load(meta.id);
              if (c && !docs.has(c.id)) docs.set(c.id, normalizeLoaded(c));
            }
          } catch (error) {
            set({
              loadError: error instanceof Error ? error.message : '无法读取本地会话。',
              storageWarning: '历史无法读取，原数据未被覆盖。',
            });
          }
          if (!get().activeId) {
            const latest = latestConversation();
            if (latest) set({ activeId: latest.id });
          }
          publish();
          set({ ready: true });
        })();
      return initPromise;
    }
    function resolveProfile(profile: ChatProfileSelection | null): ChatProfileSelection | null {
      if (profile) return profile;
      return null;
    }
    return {
      ready: false,
      loadError: null,
      storageWarning: null,
      courseContextWarning: null,
      budgetNotice: null,
      serviceNotice: null,
      resumeRag,
      activeCourseId: null,
      mode: 'real',
      conversations: [],
      activeId: null,
      messages: [],
      sending: false,
      draft: '',
      modelProfileId: null,
      waitingInteractionId: null,
      submittingReply: false,
      init: runInit,
      newConversation: (options?: { courseId?: string; title?: string }) => create(options),
      dismissCourseContextWarning: () => set({ courseContextWarning: null }),
      dismissBudgetNotice: () => set({ budgetNotice: null }),
      async selectConversation(id) {
        stop(); // 内部先提交缓冲
        const epoch = ++selectionEpoch;
        if (!(await flush())) return;
        try {
          const c = await repo.load(id);
          if (c && epoch === selectionEpoch) {
            // R5：再次载入历史走同一套恢复语义，不复活无人执行的 streaming/running
            docs.set(id, normalizeLoaded(c));
            // 切换会话：清掉上一会话遗留的课程上下文警告（警告与该轮绑定，不跨会话保留）
            set({ activeId: id, courseContextWarning: null, budgetNotice: null });
            publish();
          }
        } catch {
          set({ storageWarning: '无法读取该会话，当前内容已保留。' });
        }
      },
      /** 见 ChatState.deactivate：只清当前会话，不动任何持久化数据。 */
      deactivate() {
        stop();
        set({ activeId: null, courseContextWarning: null, budgetNotice: null });
        publish();
      },
      async renameConversation(id, title) {
        change(id, (c) => ({ ...c, title: title.trim() || c.title }));
        await flush();
      },
      async removeConversation(id) {
        if (generation?.conversationId === id) stop();
        if (!(await flush())) return;
        const doc = docs.get(id);
        try {
          await repo.remove(id, doc?.revision ?? 0);
          docs.delete(id);
          if (get().activeId === id) set({ activeId: null, courseContextWarning: null });
          publish();
        } catch (error) {
          set({ storageWarning: error instanceof Error ? error.message : '删除失败。' });
        }
      },
      async send(text, profile, extensions, onAccepted) {
        // R20：可提交条件统一在 store 边界——文字、附件或会话引用至少其一；
        // 追问等待/提交期间属于同一轮次：不允许普通 send 另开一轮
        const hasContent =
          !!text.trim() || !!extensions?.attachments?.length || !!extensions?.historyRefs?.length;
        if (!hasContent || get().sending || get().waitingInteractionId) return;
        if (!get().ready) {
          // 页面刚加载时 init 可能尚未完成：等待（memoized）而不是静默丢弃用户消息
          await runInit();
          const stillValid =
            !!text.trim() || !!extensions?.attachments?.length || !!extensions?.historyRefs?.length;
          if (!stillValid || get().sending || get().waitingInteractionId || !get().ready) return;
        }
        const isRag = isRagCapability(extensions);
        const effectiveProfile = isRag ? LOCAL_RAG_PROFILE : resolveProfile(profile);
        if (!effectiveProfile) return; // 真实模式下缺少模型档案：由界面提示原因，不静默发送
        if (isRag) {
          if (ragPreflightPending) return;
          if (!text.trim() || text.trim().length > 4000 || extensions?.attachments?.length || extensions?.historyRefs?.length) {
            set({ serviceNotice: '教材服务需要 1–4000 字的题目文本；附件与会话引用暂不支持。输入已保留。' });
            return;
          }
          ragPreflightPending = true;
          const epoch = selectionEpoch;
          const activeId = get().activeId;
          try {
            const status = await service.checkRagAvailable?.();
            if (status && !status.available) {
              set({ serviceNotice: `教材服务不可用：${status.detail} 输入已保留。` });
              return;
            }
          } catch (error) {
            set({ serviceNotice: `教材服务不可用：${error instanceof Error ? error.message : '无法连接服务。'} 输入已保留。` });
            return;
          } finally { ragPreflightPending = false; }
          if (epoch !== selectionEpoch || activeId !== get().activeId || get().sending) return;
        }
        set({ serviceNotice: null });
        if (!get().activeId) create();
        // 课程上下文：**发送时**按当前会话归属现读课程并冻结快照（新轮用新快照）
        const activeCourseId = docs.get(get().activeId!)?.courseId;
        const courseResolution = resolveCourseSnapshot(isRag ? undefined : activeCourseId);
        if (courseResolution.state === 'ok') {
          set({ courseContextWarning: null });
        } else if (courseResolution.state === 'missing') {
          set({
            courseContextWarning:
              '所属课程已删除或不可用：本轮未附带课程上下文，已按普通问答发送（历史会话与消息保留）。',
          });
        } else if (courseResolution.state === 'unavailable') {
          set({
            courseContextWarning: `课程目录读取失败（${courseResolution.error}）：本轮未附带课程上下文，已按普通问答发送。`,
          });
        } else {
          set({ courseContextWarning: null });
        }
        const userId = uid();
        // 发送即冻结：深拷贝为独立数据，与扩展目录后续变化解耦
        const snapshot = extensions ? structuredClone(extensions) : undefined;
        // R20：仅附件/仅引用的请求形成明确标识的用户消息，不以空白气泡冒充
        const fallbackLabel = extensions?.attachments?.length
          ? `[附件] ${extensions.attachments.map((item) => item.filename).join('、')}`
          : `[引用会话] ${(extensions?.historyRefs ?? []).map((item) => item.title).join('、')}`;
        const userLabel = text.trim() || fallbackLabel;
        const courseSnapshot = courseResolution.state === 'ok' ? courseResolution.snapshot : undefined;
        // CHAT-CONTEXT-BUDGET v1：**先预检构建**再动任何状态——用候选问题 + 现有历史 +
        // 本轮课程快照走同一构建器。失败（当前问题放不下）时只给可读提示：
        // 不清草稿、不入库用户消息、不建助手占位、不置 sending，用户改短后可重发。
        const built = buildChatRequest({
          history: isRag ? [] : requestHistory(docs.get(get().activeId!)?.messages ?? []),
          question: userLabel,
          courseSnapshot,
          contextTokens: effectiveProfile.contextTokens,
          maxOutputTokens: effectiveProfile.maxOutputTokens,
        });
        if (!built.ok) {
          set({ budgetNotice: built.message });
          return;
        }
        set({ budgetNotice: null });
        change(get().activeId!, (c) => ({
          ...c,
          draft: isRag && (c.draft ?? '').trim() !== text.trim() ? c.draft : '',
          title: c.title === '新的对话' ? userLabel.slice(0, 28) : c.title,
          messages: [
            ...c.messages,
            { id: userId, role: 'user', content: userLabel, status: 'done' },
          ],
        }));
        // R20：此刻轮次已被接纳（用户消息已入库）——同步通知调用方清理本次消耗的一次性选择；
        // 上方任何拒绝路径都会提前返回，不会误触发清理
        onAccepted?.();
        await run(effectiveProfile, userId, {
          request: built,
          ...(snapshot ? { extensions: snapshot } : {}),
          ...(courseSnapshot ? { courseSnapshot } : {}),
        });
      },
      stop,
      setAskDraft(interactionId, questionId, draft) {
        const id = get().activeId;
        if (!id) return;
        updateAsk(id, interactionId, (a) => ({
          ...a,
          drafts: { ...a.drafts, [questionId]: draft },
        }));
      },
      async submitReply(answers) {
        return submitReplyAnswers(answers);
      },
      async submitComposerReply(text) {
        const trimmed = text.trim();
        const interactionId = get().waitingInteractionId;
        if (!trimmed || !interactionId || get().submittingReply) return false;
        const id = get().activeId!;
        const card = docs
          .get(id)
          ?.messages.flatMap((m) => m.asks ?? [])
          .find((a) => a.interactionId === interactionId);
        if (!card) return false;
        // 自由文本计入第一道未答题；已作答题保留草稿，其余按跳过提交
        const answers: AskUserAnswer[] = card.questions.map((q) => {
          const draft = card.drafts[q.questionId];
          const hasDraft = !!draft && (draft.labels.length > 0 || draft.freeText.trim() !== '');
          return hasDraft
            ? { questionId: q.questionId, labels: draft!.labels, freeText: draft!.freeText }
            : { questionId: q.questionId, labels: [], freeText: '', skipped: true };
        });
        const target = answers.find((a) => a.skipped) ?? answers.at(-1);
        if (target) {
          target.freeText = target.freeText ? `${target.freeText}\n${trimmed}` : trimmed;
          target.skipped = false;
        }
        const ok = await submitReplyAnswers(answers);
        if (ok) change(id, (c) => ({ ...c, draft: c.draft?.trim() === trimmed ? '' : c.draft }));
        return ok;
      },
      async retry(id, profile) {
        if (get().sending || !get().activeId) return;
        const targetMessage = get().messages.find((m) => m.id === id);
        if (targetMessage?.rag?.status === 'interrupted') return resumeRag(id);
        const effectiveProfile = targetMessage?.rag ? LOCAL_RAG_PROFILE : resolveProfile(profile);
        if (!effectiveProfile) return;
        const messages = get().messages,
          last = messages.at(-1);
        if (
          !last ||
          last.id !== id ||
          last.role !== 'assistant' ||
          !['error', 'stopped'].includes(last.status)
        )
          return;
        const user = [...messages].reverse().find((m) => m.role === 'user');
        if (!user) return;
        // 失败占位默认移除；带过程记录或追问交流的失败尝试必须保留（R12：可能没有正文）
        const settled = messages
          .filter(
            (m) =>
              m.id !== id ||
              m.content !== '' ||
              (m.toolCalls?.length ?? 0) > 0 ||
              (m.asks?.length ?? 0) > 0,
          )
          .map((m) => (m.id === id ? { ...m, superseded: true } : m));
        // CHAT-CONTEXT-BUDGET v1：重试同样**先预检**，并用旧轮冻结的课程快照
        // （旧轮的超长快照也经同一构建器安全渲染；不要求清库）。
        // 构建失败：保留失败态与重试入口，只给可读提示，不改动任何消息。
        const built = buildChatRequest({
          history: requestHistory(settled),
          question: user.content,
          courseSnapshot: last.courseContext,
          contextTokens: effectiveProfile.contextTokens,
          maxOutputTokens: effectiveProfile.maxOutputTokens,
        });
        if (!built.ok) {
          set({ budgetNotice: built.message });
          return;
        }
        set({ budgetNotice: null });
        // 落库的正是构建请求时所用的那一份消息（同一变换只算一次，账目与历史可逐条核对）
        change(get().activeId!, (c) => ({ ...c, messages: settled }));
        // 重试沿用原请求快照（含课程快照），不读取最新目录替换旧配置；想采用新配置需重新发送
        await run(effectiveProfile, user.id, {
          request: built,
          ...(last.extensions ? { extensions: last.extensions } : {}),
          ...(last.courseContext ? { courseSnapshot: last.courseContext } : {}),
        });
      },
      async retryLast(profile) {
        const last = get().messages.at(-1);
        if (last) await get().retry(last.id, profile);
      },
      setDraft(draft) {
        if (!get().activeId) create();
        change(get().activeId!, (c) => ({ ...c, draft }));
      },
      setModel(modelProfileId) {
        if (!get().activeId) create();
        change(get().activeId!, (c) => ({ ...c, modelProfileId }));
      },
      flush,
      /**
       * 卸载清理（R1）：取消进行中的生成并冲正保存。幂等——重复调用安全，
       * 且不销毁 store 本身，兼容 React StrictMode 的 setup-cleanup-setup 后再次挂载使用。
       */
      dispose() {
        if (generation?.channel === 'rag') {
          // 刷新/卸载只断开连接，保留服务端轮次；显式“停止”才发 cancel。
          const active = generation;
          patchRagInterrupted(active);
          generation = null;
          active.controller.abort();
          set({ sending: false });
        } else stop();
        void flush();
      },
      exportActive() {
        return JSON.stringify(docs.get(get().activeId ?? '') ?? null, null, 2);
      },
    };
  });
}
