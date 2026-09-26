/**
 * 统一聊天事件服务：生产仅由真实 SSE 驱动状态与消息组件。
 *
 * 事件为以 type 为判别字段的联合类型：增量事件必须携带数据，工具事件必须携带
 * callId/名称/状态，必要字段不可缺失。事件分类对齐参考仓库 v1.6.5 的 turn 协议
 * （thinking→reasoning、content→text、done→end 等），并按 replica 约束携带
 * sessionId + turnId：消费方据此丢弃迟到、串会话与重复事件。
 * 普通聊天保持原 SSE 协议；教材能力路由到专用本地服务，支持同轮追问与恢复。
 */
import type {
  AskUserAnswer,
  AskUserInteraction,
  ChatArtifact,
  ChatRole,
  ChatServiceKind,
  RagTurnState,
  TurnExtensionSnapshot,
} from '@/contracts/chat';
import { streamChat } from '@/services/chat-stream';
import { createRagChatService, isRagCapability, type RagServiceStatus } from './rag-service';

export type ChatToolStatus = 'running' | 'done' | 'error' | 'cancelled';

/** 工具事件负载：MCP 为明确标识的模拟工具调用；Skill 只是技能上下文加载 */
export interface ChatToolCall {
  callId: string;
  kind: 'mcp' | 'skill';
  name: string;
  status: ChatToolStatus;
  /** 模拟标识说明 */
  note?: string;
  /** 可展开的结果/错误摘要 */
  detail?: string;
}

/** artifact 事件负载：内容为真实已生成的本地文本（markdown/svg 源码/html/text）；createdAt 由 store 落盘时补齐 */
export type ChatArtifactPayload = Omit<ChatArtifact, 'createdAt'>;

interface ChatServiceEventBase {
  sessionId: string;
  turnId: string;
  eventId?: number;
}

export type ChatServiceEvent =
  | (ChatServiceEventBase & { type: 'checkpoint' })
  | (ChatServiceEventBase & { type: 'reply-accepted'; interactionId: string; submissionId: string; answers: AskUserAnswer[] })
  | (ChatServiceEventBase & { type: 'turn-start' })
  | (ChatServiceEventBase & { type: 'text'; delta: string })
  | (ChatServiceEventBase & { type: 'reasoning'; delta: string })
  | (ChatServiceEventBase & { type: 'process'; delta: string })
  | (ChatServiceEventBase & {
      type: 'stage';
      label: string;
      phase: 'start' | 'end';
      /** 稳定阶段 id（S4，对照参考 call_id 语义）：同 id 原地更新；缺省用 label */
      stageId?: string;
    })
  | (ChatServiceEventBase & { type: 'tool'; call: ChatToolCall })
  | (ChatServiceEventBase & {
      type: 'wait-user';
      /** 结构化追问卡载荷：preview 为只读预览，waiting 开放作答（同一 interactionId 就地更新） */
      interaction: Pick<
        AskUserInteraction,
        'interactionId' | 'intro' | 'questions' | 'status'
      >;
    })
  | (ChatServiceEventBase & {
      type: 'artifact';
      artifact: ChatArtifactPayload;
    })
  | (ChatServiceEventBase & {
      type: 'usage';
      usage: { inputTokens?: number | null; outputTokens?: number | null };
    })
  | (ChatServiceEventBase & { type: 'end'; finishReason: string })
  | (ChatServiceEventBase & {
      type: 'error';
      error: { code: string; message: string; retryable?: boolean };
    });

export interface ChatServiceRequest {
  sessionId: string;
  turnId: string;
  messages: { role: ChatRole; content: string }[];
  /** 真实服务必填；测试可注入服务实现 */
  modelProfileId?: string;
  maxOutputTokens?: number;
  /**
   * 本轮扩展快照；教材能力据此选择专用服务。普通聊天不向后端发送扩展。
   */
  extensions?: TurnExtensionSnapshot;
  rag?: RagTurnState;
  signal: AbortSignal;
}

/** 追问回答提交：与触发追问的轮次绑定（同 sessionId/turnId/interactionId） */
export interface ChatServiceReplyRequest {
  sessionId: string;
  turnId: string;
  interactionId: string;
  /** 幂等提交标识：重复提交只消费一次 */
  submissionId: string;
  answers: AskUserAnswer[];
  signal: AbortSignal;
  channel?: 'rag';
}

export interface ChatReplyAck {
  accepted: boolean;
  code?: string;
  message?: string;
}

export interface ChatService {
  readonly kind: ChatServiceKind;
  run(request: ChatServiceRequest, emit: (event: ChatServiceEvent) => void): Promise<void>;
  /**
   * 回答当前追问（同一轮暂停与续答）。
   * 教材服务支持同轮回答；普通聊天显式不支持，不静默转模拟。
   */
  submitReply?(request: ChatServiceReplyRequest): Promise<ChatReplyAck>;
  checkRagAvailable?(): Promise<RagServiceStatus>;
  cancel?(request: { sessionId: string; turnId: string; channel?: 'rag' }): Promise<unknown>;
}

/** 真实服务：包装现有 SSE 客户端，真实路径行为保持不变（不发送扩展快照） */
export function createRealChatService(deps?: { stream?: typeof streamChat }): ChatService {
  const runStream = deps?.stream ?? streamChat;
  const rag = createRagChatService();
  return {
    kind: 'real',
    checkRagAvailable: () => rag.checkRagAvailable!(),
    cancel: (request) => request.channel === 'rag' ? rag.cancel!(request) : Promise.resolve(),
    // 普通聊天协议不支持追问；教材轮次只走专用回答接口。
    async submitReply(request) {
      if (request.channel === 'rag') return rag.submitReply!(request);
      return {
        accepted: false,
        code: 'REPLY_NOT_SUPPORTED',
        message: '真实问答暂不支持追问回答。',
      };
    },
    async run(request, emit) {
      if (request.rag || isRagCapability(request.extensions)) return rag.run(request, emit);
      await runStream(
        {
          requestId: request.turnId.replaceAll('-', ''),
          modelProfileId: request.modelProfileId ?? '',
          messages: request.messages,
          maxOutputTokens: request.maxOutputTokens,
          signal: request.signal,
        },
        {
          onStart: () =>
            emit({ sessionId: request.sessionId, turnId: request.turnId, type: 'turn-start' }),
          onText: (delta) =>
            emit({ sessionId: request.sessionId, turnId: request.turnId, type: 'text', delta }),
          onReasoning: (delta) =>
            emit({
              sessionId: request.sessionId,
              turnId: request.turnId,
              type: 'reasoning',
              delta,
            }),
          onUsage: (usage) =>
            emit({ sessionId: request.sessionId, turnId: request.turnId, type: 'usage', usage }),
          onEnd: (finishReason) =>
            emit({
              sessionId: request.sessionId,
              turnId: request.turnId,
              type: 'end',
              finishReason,
            }),
          onError: (error) =>
            emit({ sessionId: request.sessionId, turnId: request.turnId, type: 'error', error }),
        },
      );
    },
  };
}
