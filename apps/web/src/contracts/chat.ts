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

/**
 * 轮次课程快照（H1-COURSE-SESSIONS v1）：发送时从课程记录**冻结**的独立数据。
 *
 * - 随助手占位消息持久化：重试沿用原快照，不读取最新课程替换旧轮配置；课程修改只影响**新轮**。
 * - `resources` 只承载"登记引用"信息（kind/label/可用性），**不代表内容已解析、已检索或已传给模型**。
 * - 真实请求链路：快照渲染为一条 `system` 消息插在请求 messages 最前（见 chat-service/chat-stream）。
 */
export interface TurnCourseSnapshot {
  courseId: string;
  name: string;
  /** 课程约定（course.instructions），按上限截断 */
  conventions: string;
  /** 大纲摘要（covered 为学员手判，不推断掌握度） */
  syllabus: { total: number; covered: number; nextTitle: string | null };
  /** 仅登记引用：不代表资源内容已解析/已检索/已传给模型 */
  resources: { kind: string; label: string; availability: 'available' | 'missing' | 'unknown' }[];
  frozenAt: string;
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
  /** 本轮冻结的课程快照（发送时生成，重试沿用；未归属会话/课程不可用时缺省） */
  courseContext?: TurnCourseSnapshot;
  /**
   * 本轮请求的预算账目（CHAT-CONTEXT-BUDGET v1）：如实记录**实际发送时**的裁剪行为。
   * 全部为**字符估算**（1 token ≈ 2 字符的保守估计），不是精确 token 计数；历史原文不受影响。
   */
  requestBudget?: RequestBudgetRecord;
  /** 轮级计时（S3）：开始=助手占位创建；结束=end/error/取消收尾（完成后冻结时长显示） */
  startedAt?: string;
  finishedAt?: string;
  finishReason?: string;
  usage?: { inputTokens?: number | null; outputTokens?: number | null };
  error?: ChatMessageError;
}

/**
 * 本轮请求的预算账目（CHAT-CONTEXT-BUDGET v1；随助手消息持久化，刷新可核）。
 *
 * 语义边界：
 * - `inputBudgetChars` 由模型档案的 `contextTokens/maxOutputTokens` 估算而来，并受后端总长度上限约束；
 * - 裁剪顺序为「课程动态字段 → 旧历史 → 课程块整体丢弃」，当前问题与单条消息完整性不在裁剪范围内；
 * - 账目只记录**发送时**的事实，不反向改写课程数据、不改写历史消息正文。
 */
export interface RequestBudgetRecord {
  /** 实际发送的字符总数（课程块 + 历史 + 当前问题） */
  totalChars: number;
  /** 本轮采用的输入预算（字符） */
  inputBudgetChars: number;
  /** 后端单条消息字符上限（apps/api/app/schemas/chat.py: MAX_MESSAGE_CHARS） */
  maxMessageChars: number;
  /** 后端消息总长度字符上限（同文件：MAX_TOTAL_CHARS） */
  maxTotalChars: number;
  /** 因预算被丢弃的旧历史消息条数（不包含当前问题） */
  historyDroppedMessages: number;
  /** 课程块被裁剪的动态字段（如 name/conventions/syllabus/resourceLabels/resourceItems） */
  courseTrimmedFields: string[];
  /** 课程块整体无法容纳而被丢弃：本轮**未携带**课程上下文（如实标注，不伪造完整上下文） */
  courseDropped: boolean;
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
  /**
   * 课程归属（H1-COURSE-SESSIONS v1）：稳定 courseId；缺失/空串 = 未归属（旧会话保持未归属，
   * 不按标题、最近访问或 URL 猜测，也不因出现在某课程页而被改写）。
   */
  courseId?: string;
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
  /** 课程归属（缺失 = 未归属）：课程页按此过滤本课程会话 */
  courseId?: string;
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
