/** 学习问答契约（D04）。与 apps/api 的 schemas/chat.py 及 SSE 事件协议保持一致。 */

export type ChatRole = 'system' | 'user' | 'assistant';

export type ChatMessageStatus = 'done' | 'streaming' | 'stopped' | 'error';

export interface ChatMessageError {
  code: string;
  message: string;
  retryable?: boolean;
}

/**
 * 会话/服务的运行模式。
 *
 * 主聊天生产路径只有 `real`（真实模型 SSE）；`mock` 仅用于**读取历史**（旧本地模拟
 * 会话记录里可能仍带该值，只读展示用）与**测试替身注入**，不存在运行时模拟分支。
 * 其他模块（阅读/写作/知识库/whisper）的显式模拟使用各自独立的字面量类型，不经此契约。
 */
export type ChatServiceKind = 'real' | 'mock';

/** 本轮扩展快照：发送时从模拟扩展目录冻结的独立数据（重试沿用，不引用可变目录对象） */export interface TurnExtensionSnapshot {
  mcps: { id: string; name: string; description: string }[];
  skills: { id: string; name: string; description: string }[];
  /**
   * S2 输入区：本轮业务能力与配置（chat 能力不携带）。
   * 全部字段可选——旧快照（仅 mcps/skills）按原样读取，不迁移不重置。
   */
  capability?: {
    value: string;
    label: string;
    /** 能力配置表单的冻结值（无配置能力不携带） */
    config?: Record<string, unknown>;
  };
  /** 角色人设（会话级选择，发送时冻结） */
  persona?: { id: string; name: string };
  /** 知识来源（会话级检索范围声明，发送时冻结） */
  knowledge?: { id: string; name: string }[];
  /** 引用的其他会话（一次性，发送后随附件一起清空） */
  historyRefs?: { id: string; title: string }[];
  /**
   * 附件元数据（文件名/类别/大小/MIME）。无解析服务时不携带文件内容，
   * 模拟侧按“未读取文件内容”如实陈述，不伪装上传或解析成功。
   */
  attachments?: {
    filename: string;
    kind: 'image' | 'doc';
    size: number;
    mimeType?: string;
  }[];
}

/** 追问选项（对照原版 AskUserOptions 的选项与说明） */
export interface AskUserOption {
  label: string;
  description?: string;
}

/** 追问问题：稳定 questionId；选项、多选、自由文本能力显式声明 */
export interface AskUserQuestion {
  questionId: string;
  prompt: string;
  header?: string;
  options?: AskUserOption[];
  multiSelect?: boolean;
  allowFreeText?: boolean;
  placeholder?: string;
}

/** 单题答案：选项 labels 与自由文本；跳过为空 */
export interface AskUserAnswer {
  questionId: string;
  labels: string[];
  freeText?: string;
  /** 未回答按原版语义提交为跳过 */
  skipped?: boolean;
}

export type AskUserCardStatus =
  | 'preview' // 预览：只读，未开放作答
  | 'waiting' // 等待回答：可交互
  | 'submitting' // 提交中
  | 'answered' // 已回答：只读摘要
  | 'failed' // 提交失败：保留草稿可重试
  | 'interrupted'; // 等待上下文失效（取消/断流/刷新恢复）

export interface AskUserDraft {
  labels: string[];
  freeText: string;
}

/** 一张追问卡：随消息持久化（不含任何运行对象） */
export interface AskUserInteraction {
  interactionId: string;
  intro?: string;
  questions: AskUserQuestion[];
  status: AskUserCardStatus;
  /** 各题草稿：输入与选择即时保存 */
  drafts: Record<string, AskUserDraft>;
  /** 提交成功后的确认答案 */
  answers?: AskUserAnswer[];
  error?: { code: string; message: string };
  /** 本卡确认后、下一张卡或轮结束前的续写正文 */
  followUp?: string;
}

/**
 * 单条工具/技能执行记录（随消息持久化）。
 * MCP 为明确标识的模拟工具调用；Skill 只是"技能上下文已加载"，不是远程工具调用。
 * 按 callId 去重更新；终态（done/error/cancelled）后不再接受变更。
 */
export interface ToolCallRecord {
  callId: string;
  kind: 'mcp' | 'skill';
  name: string;
  status: 'running' | 'done' | 'error' | 'cancelled';
  /** 模拟标识与说明（面向用户，安全 Markdown 渲染，不执行内容） */
  note?: string;
  /** 可展开的结果/错误摘要 */
  detail?: string;
  startedAt: string;
  endedAt?: string;
}

/**
 * 本轮产物（S3 结果工作区）。kind 决定渲染器：markdown/SVG 用安全渲染，
 * html 经 sandbox iframe 隔离（不执行脚本），text 原样展示；
 * quiz/report 为 S4 能力结构化产物（data 携带结构，content 保持人类可读文本，
 * 复制/下载直接使用 content——不以空文件冒充成功）。按 id 幂等增量更新。
 */
export interface ChatArtifact {
  id: string;
  kind: 'markdown' | 'svg' | 'html' | 'text' | 'quiz' | 'report' | 'chart' | 'mermaid';
  title: string;
  content: string;
  /** 结构化载荷（quiz=题目数组、report=章节与引用、chart=Chart.js 配置、mermaid=源码；与 content 同源生成） */
  data?: unknown;
  createdAt: string;
}

/**
 * 轮内阶段记录（S4，对照参考 TracePresentation 的 stage 流水）：
 * 按 stageId 原地更新（重复事件不新增条目）；随会话持久化，刷新只恢复不重放。
 */
export interface TraceStageRecord {
  /** 稳定 id（参考 call_id/step_id 语义）：同 id 就地更新 */
  stageId: string;
  label: string;
  status: 'running' | 'done' | 'error' | 'cancelled';
  startedAt: string;
  endedAt?: string;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  status: ChatMessageStatus;
  /** assistant 消息标注实际使用的模型 */
  modelLabel?: string;
  modelProfileId?: string;
  replyToId?: string;
  superseded?: boolean;
  /** 推理模型的思考过程（reasoning_content / thinking 等），不是正文 */
  reasoning?: string;
  /** 过程阶段标签（stage 事件），流式时显示在状态行 */
  stageLabel?: string;
  /** 轮内阶段序列（S4，按 stageId 原地更新；随会话持久化） */
  stages?: TraceStageRecord[];
  /** 过程增量（process 事件）最新一条，流式时显示 */
  processNote?: string;
  /** 本轮使用的扩展快照（发送时冻结；模拟模式专用，真实消息没有该字段） */
  extensions?: TurnExtensionSnapshot;
  /** 工具/技能执行过程（按 callId 去重；随会话持久化，刷新只恢复不重放） */
  toolCalls?: ToolCallRecord[];
  /** 同轮追问卡（正文→提问→续写按序渲染；随会话持久化） */
  asks?: AskUserInteraction[];
  /** 本轮产物（artifact 事件按 id 幂等更新；随会话持久化，刷新只恢复不重放） */
  artifacts?: ChatArtifact[];
  /** 轮级计时（S3）：开始=助手占位创建；结束=end/error/取消收尾（完成后冻结时长显示） */
  startedAt?: string;
  finishedAt?: string;
  finishReason?: string;
  usage?: { inputTokens?: number | null; outputTokens?: number | null };
  error?: ChatMessageError;
}

export interface Conversation {
  schemaVersion?: number;
  revision?: number;
  draft?: string;
  modelProfileId?: string | null;
  /** 会话归属模式：生产恒为 real；旧模拟会话记录读取时可能为 mock（仅只读展示） */
  mode?: ChatServiceKind;
  /** S5-A：学习空间归档位——聊天侧边栏隐藏已归档会话，/space/chat-history 可归档/恢复 */
  archived?: boolean;
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
}

export interface ConversationMeta {
  id: string;
  title: string;
  messageCount: number;
  createdAt: string;
  updatedAt: string;
}

/** 对话上下文预算：1 token ≈ 2 个字符的保守估算（中文） */
export function contextBudgetChars(
  contextTokens: number | null | undefined,
  maxOutputTokens: number | null | undefined,
): number {
  const context = contextTokens ?? 8000;
  const reserve = (maxOutputTokens ?? 2048) * 3;
  return Math.max(2000, context * 2 - reserve);
}
