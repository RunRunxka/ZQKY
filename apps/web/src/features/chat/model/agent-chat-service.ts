/**
 * Agent 通道服务：把 /api/v1/agent/* 的 SSE 包装成统一 ChatService。
 *
 * Agent 化改造（C1 学习问答/Agent 融合）：对话页默认走 Agent——普通问答由 Agent 直答，
 * 业务意图由 Agent 调工具，写操作经确认闸门；无独立 RAG 通道。
 * 本服务即对话页默认通道（由 createRealChatService 装配）。
 *
 * 事件映射（agent-stream → ChatServiceEvent）：
 * - message.start → turn-start；text.delta → text；message.end → end；error → error；
 * - tool.call/tool.result → tool（kind='skill'，过程展示）；
 * - wait-confirm / wait-select → wait-user（弹窗选择/写确认卡，submitReply 经 /agent/confirm 续跑）。
 */
import type {
  AskUserAnswer,
  AskUserInteraction,
  AskUserQuestion,
} from '@/contracts/chat';
import {
  confirmAgent,
  streamAgent,
  type AgentConfirmPayload,
  type AgentStreamHandlers,
} from '@/services/agent-stream';
import type {
  ChatReplyAck,
  ChatService,
  ChatServiceEvent,
  ChatServiceReplyRequest,
} from './chat-service';

/** 写操作确认/弹窗选择卡在 agent 端的载荷（interrupt value）。 */
interface AgentWaitPayload extends AgentConfirmPayload {
  /** 卡片种类：confirm=写操作确认；select=参数选择 */
  kind?: 'confirm' | 'select';
  /** 选择卡题干（select 用） */
  prompt?: string;
  /** 选择项（select 用） */
  options?: { label: string; description?: string }[];
}

/** 把 agent 的 wait 载荷规整为统一追问卡（复用 AskUserCard 交互）。 */
function toInteraction(confirmId: string, payload: AgentWaitPayload): Pick<
  AskUserInteraction,
  'interactionId' | 'intro' | 'questions' | 'status'
> {
  const kind = payload.kind === 'select' ? 'select' : 'confirm';
  const promptText =
    (typeof payload.prompt === 'string' && payload.prompt) ||
    (typeof payload.summary === 'string' && payload.summary) ||
    '需要你的确认';
  const options =
    kind === 'select' && Array.isArray(payload.options)
      ? (payload.options as { label: string; description?: string }[]).map((o) => ({
          label: String(o.label),
          ...(o.description ? { description: String(o.description) } : {}),
        }))
      : [
          { label: '确认执行' },
          { label: '放弃' },
        ];
  const question: AskUserQuestion = {
    questionId: `${confirmId}-q`,
    prompt: promptText,
    options,
    allowFreeText: false,
    multiSelect: false,
  };
  return {
    interactionId: confirmId,
    intro: kind === 'confirm' ? '写操作确认' : '请选择',
    questions: [question],
    status: 'waiting',
  };
}

/** 两条通道（首轮 / 确认续跑）共用的事件映射：同一套 SSE 事件写回同一轮消息。 */
function buildHandlers(
  sessionId: string,
  turnId: string,
  emit: (event: ChatServiceEvent) => void,
  onStart: () => void,
): AgentStreamHandlers {
  return {
    onStart,
    onText: (delta) => emit({ sessionId, turnId, type: 'text', delta }),
    onToolCall: (call) =>
      emit({
        sessionId,
        turnId,
        type: 'tool',
        call: {
          callId: call.callId,
          kind: 'skill',
          name: call.name,
          status: 'running',
        },
      }),
    onToolResult: (result) =>
      emit({
        sessionId,
        turnId,
        type: 'tool',
        call: {
          callId: result.callId,
          kind: 'skill',
          name: result.name,
          status: 'done',
          detail: result.output,
        },
      }),
    onWaitConfirm: (confirm) =>
      emit({
        sessionId,
        turnId,
        type: 'wait-user',
        interaction: toInteraction(confirm.confirmId, confirm.payload as AgentWaitPayload),
      }),
    onEnd: (finishReason) => emit({ sessionId, turnId, type: 'end', finishReason }),
    onError: (error) => emit({ sessionId, turnId, type: 'error', error }),
  };
}

export function createAgentChatService(): ChatService {
  return {
    kind: 'real',
    async run(request, emit) {
      const turnId = request.turnId;
      const sessionId = request.sessionId;
      const message = request.messages.at(-1)?.content ?? '';
      // Agent 会话线程：与 chat 会话对齐（每会话一 thread，沿用会话持久化）。
      const threadId = sessionId;
      // 附件：extensions.attachments 里已上传的 assetRef（C1），转成后端 attachments。
      const attachments = (request.extensions?.attachments ?? [])
        .filter((a) => typeof a.assetId === 'string' && a.assetId.length > 0)
        .map((a) => ({
          assetId: a.assetId as string,
          fileName: a.filename,
          mediaType: a.mimeType ?? '',
          kind: (a.importKind ?? 'auto') as 'auto',
        }));
      // 思考强度（D6）：发送时随 capability.config.reasoningEffort 冻结传入。
      const effortRaw = request.extensions?.capability?.config?.reasoningEffort;
      const reasoningEffort = typeof effortRaw === 'string' && effortRaw ? effortRaw : undefined;
      await streamAgent(
        {
          requestId: turnId.replaceAll('-', ''),
          threadId,
          message,
          modelProfileId: request.modelProfileId ?? '',
          ...(attachments.length > 0 ? { attachments } : {}),
          ...(reasoningEffort ? { reasoningEffort } : {}),
          signal: request.signal,
        },
        buildHandlers(sessionId, turnId, emit, () =>
          emit({ sessionId, turnId, type: 'turn-start' }),
        ),
      );
    },
    async submitReply(
      request: ChatServiceReplyRequest,
      emit?: (event: ChatServiceEvent) => void,
    ): Promise<ChatReplyAck> {
      const modelProfileId = request.modelProfileId?.trim() ?? '';
      if (!modelProfileId) {
        return {
          accepted: false,
          code: 'MODEL_PROFILE_MISSING',
          message: '未找到本轮模型档位：请重新选择模型后再确认。',
        };
      }
      // 写确认/弹窗选择：confirm 映射 approve/reject；select 把选定值经 value 传给后端 resume。
      const answer: AskUserAnswer | undefined = request.answers[0];
      const picked = answer?.labels?.[0] ?? answer?.freeText ?? '';
      const isConfirm = picked === '确认执行' || picked === '放弃';
      const decision: 'approve' | 'reject' = isConfirm
        ? picked === '确认执行'
          ? 'approve'
          : 'reject'
        : 'approve';
      const handlers: AgentStreamHandlers = emit
        ? buildHandlers(request.sessionId, request.turnId, emit, () =>
            emit({
              sessionId: request.sessionId,
              turnId: request.turnId,
              type: 'reply-accepted',
              interactionId: request.interactionId,
              submissionId: request.submissionId,
              answers: request.answers,
            }),
          )
        : {};
      try {
        await confirmAgent(
          {
            submissionId: request.submissionId,
            requestId: request.turnId.replaceAll('-', ''),
            threadId: request.sessionId,
            modelProfileId,
            confirmId: request.interactionId,
            decision,
            ...(!isConfirm && picked ? { value: picked } : {}),
            signal: request.signal,
          },
          handlers,
        );
        return { accepted: true };
      } catch (error) {
        const e = error as { code?: string; message?: string };
        return {
          accepted: false,
          code: e.code ?? 'REQUEST_FAILED',
          message: e.message ?? '确认提交失败。',
        };
      }
    },
  };
}
