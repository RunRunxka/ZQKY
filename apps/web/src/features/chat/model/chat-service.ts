/**
 * 统一聊天事件服务：生产仅由真实 SSE 驱动状态与消息组件。
 *
 * 事件为以 type 为判别字段的联合类型：增量事件必须携带数据，工具事件必须携带
 * callId/名称/状态，必要字段不可缺失。事件分类对齐参考仓库 v1.6.5 的 turn 协议
 * （thinking→reasoning、content→text、done→end 等），并按 replica 约束携带
 * sessionId + turnId：消费方据此丢弃迟到、串会话与重复事件。
 * 真实路径不发送扩展快照等模拟字段；等待用户与产物事件为预留类型。
 */
import type {
  AskUserAnswer,
  AskUserInteraction,
  ChatArtifact,
  ChatRole,
  ChatServiceKind,
  TurnExtensionSnapshot,
} from '@/contracts/chat';
import { streamChat } from '@/services/chat-stream';

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
}

export type ChatServiceEvent =
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
   * 本轮扩展快照（发送时冻结的独立数据）。仅模拟服务消费；
   * 真实服务不读取、不向真实后端发送该字段。
   */
  extensions?: TurnExtensionSnapshot;
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
   * 真实服务显式不支持（返回 accepted:false），不静默转模拟；
   * 模拟实现接受后继续当前轮。缺省视为不支持。
   */
  submitReply?(request: ChatServiceReplyRequest): Promise<ChatReplyAck>;
}

/** 真实服务：包装现有 SSE 客户端，真实路径行为保持不变（不发送扩展快照） */
export function createRealChatService(deps?: { stream?: typeof streamChat }): ChatService {
  const runStream = deps?.stream ?? streamChat;
  return {
    kind: 'real',
    // 真实 SSE 协议暂无追问回答通道：显式拒绝，不静默转模拟
    async submitReply() {
      return {
        accepted: false,
        code: 'REPLY_NOT_SUPPORTED',
        message: '真实问答暂不支持追问回答。',
      };
    },
    async run(request, emit) {
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
