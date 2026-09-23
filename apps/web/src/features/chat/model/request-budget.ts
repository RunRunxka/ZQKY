/**
 * 请求预算构建（CHAT-CONTEXT-BUDGET v1）。
 *
 * 本模块是「一次真实请求到底发送什么」的唯一构建入口：课程上下文（system 块）、
 * 历史与当前问题在**同一预算**内共同裁剪，并给出可核对的字符账目
 * （`RequestBudgetRecord`）与如实说明（`RequestNote`）。
 *
 * 语义边界（不得夸大）：
 * - 全部数字是**字符估算**（1 token ≈ 2 字符的保守估计），不是精确 token 计数，
 *   也不保证不超模型自身上下文上限；只保证不超本轮输入预算与后端硬限制；
 * - 裁剪顺序：① 课程块动态字段受限 → ② 整条丢弃最旧的旧历史 → ③ 整体丢弃课程块；
 *   当前问题逐字不裁剪：放不下时**发送前**明确失败（ok:false），不静默截断、不发送超限请求；
 * - 绝不拼接半条消息：历史与课程块都按整段取舍，不截断历史正文；
 * - 只读取快照入参并生成新字符串，**不回写**课程原始数据（StudyCourse）或历史消息正文。
 */
import {
  contextBudgetChars,
  type ChatMessage,
  type ChatRole,
  type RequestBudgetRecord,
  type TurnCourseSnapshot,
} from '@/contracts/chat';
import {
  COURSE_CONTEXT_MESSAGE_LIMIT,
  COURSE_CONTEXT_RESOURCE_ITEM_LIMIT,
  COURSE_CONVENTIONS_LIMIT,
  COURSE_RESOURCE_LABEL_LIMIT,
} from '@/services/course-session';
import {
  projectRequestHistory,
  takeNewestMessages,
  type RequestMessage,
} from './context-budget';

/**
 * 后端硬限制的唯一事实来源（apps/api/app/schemas/chat.py: MAX_MESSAGES/MAX_MESSAGE_CHARS/MAX_TOTAL_CHARS）。
 * 前端不引入第二套数字：超限请求必须在发送前被本模块挡下。
 */
export const BACKEND_REQUEST_LIMITS = {
  maxMessages: 200,
  maxMessageChars: 32_000,
  maxTotalChars: 120_000,
};

export interface BackendRequestLimits {
  maxMessages: number;
  maxMessageChars: number;
  maxTotalChars: number;
}

/** 本轮请求的裁剪说明（面向界面/账目的如实说明，不是错误） */
export type RequestNote =
  | { kind: 'history-dropped'; messages: number }
  | { kind: 'course-trimmed'; fields: string[] }
  | { kind: 'course-dropped' };

export type BuildRequestResult =
  | {
      ok: true;
      messages: { role: ChatRole; content: string }[];
      record: RequestBudgetRecord;
      notes: RequestNote[];
    }
  | {
      ok: false;
      reason: 'question-too-large';
      message: string;
      questionChars: number;
      allowedChars: number;
    };

/** §4 课程块动态字段上限（与 services/course-session.ts 的既有常量同源，避免两套数字） */
export const COURSE_BLOCK_FIELD_LIMITS = {
  /** 课程名（课程名原始校验上限 60；渲染期再兜底） */
  nameChars: 80,
  /** 下一个未完成单元标题（本轮 D1 缺陷的直接来源） */
  nextTitleChars: 120,
};

/**
 * 固定免责句（课程块未被整体丢弃时必须出现）。
 * 与 `services/course-session.ts` 的资源行前缀保持同一句话，不另造口径。
 */
export const COURSE_CONTEXT_DISCLAIMER = '内容未解析、未检索、未随本请求发送';
const COURSE_HEADER =
  '本节对话属于一门课程，以下是课程上下文（本地登记信息，供你组织回答；不是用户消息）：';
const COURSE_CONVENTIONS_HEADING = '课程约定（学员填写，请遵守）：';
const COURSE_RESOURCE_PREFIX = `课程资源（仅登记引用：${COURSE_CONTEXT_DISCLAIMER}）：`;

/** 按字符上限截断（含省略号后总长不超过 limit）；只读入参，返回新字符串 */
function ellipsize(text: string, limit: number): string {
  const trimmed = text.trim();
  if (limit <= 0) return '';
  if (trimmed.length <= limit) return trimmed;
  return `${trimmed.slice(0, limit - 1)}…`;
}

/** 课程块渲染参数（阶梯收缩用；每步只减少不改写） */
interface CourseBlockPlan {
  nameLimit: number;
  nextTitleLimit: number;
  conventionsLimit: number;
  labelLimit: number;
  itemLimit: number;
}

const FULL_COURSE_PLAN: CourseBlockPlan = {
  nameLimit: COURSE_BLOCK_FIELD_LIMITS.nameChars,
  nextTitleLimit: COURSE_BLOCK_FIELD_LIMITS.nextTitleChars,
  conventionsLimit: COURSE_CONVENTIONS_LIMIT,
  labelLimit: COURSE_RESOURCE_LABEL_LIMIT,
  itemLimit: COURSE_CONTEXT_RESOURCE_ITEM_LIMIT,
};

/**
 * 渲染课程块（纯函数）：对**快照入参**做防御性裁剪（历史里的旧快照可能带超长字段），
 * 生成全新字符串，绝不修改入参对象。
 * 免责句与固定行（课程名/大纲行/资源行）在任何收缩路径下都保留，只压缩动态内容。
 */
/**
 * 防御性取文本（§4）：历史或外部损坏的快照可能带非字符串字段（数字/布尔/对象）——
 * 一律按文本安全降级，绝不在发送/重试路径抛 `.trim is not a function`。
 * 空值 → 空串（渲染层据此省略该字段，不伪造内容）。
 */
function asText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return ''; // 对象/数组/符号等一律按缺失处理，不产出 [object Object] 之类的噪音
}

const RESOURCE_AVAILABILITY = new Set(['available', 'missing', 'unknown']);

/** 只接受字符串 kind，其余（数字/对象/缺失）一律 unknown，避免把脏值当标签展示 */
function asKind(value: unknown): string {
  return typeof value === 'string' && value.trim() ? value : 'unknown';
}

function asAvailability(value: unknown): string {
  return typeof value === 'string' && RESOURCE_AVAILABILITY.has(value) ? value : 'unknown';
}

/**
 * 防御性读取快照资源（§4）：历史或外部损坏的快照可能含 `null`/非对象条目或缺失字段——
 * 这些都**不是**类型系统与本应用写入器能产出的形态，但发送/重试路径不得因此抛错
 * （失败必须仍然可重试）。非对象条目一律丢弃；「…等共 N 项」只计**存活条目**（丢弃项不是资源，
 * 计入会让总数失真），不伪造内容。
 */
function safeResources(snapshot: TurnCourseSnapshot): TurnCourseSnapshot['resources'] {
  const raw = Array.isArray(snapshot.resources) ? snapshot.resources : [];
  return raw.filter((resource): resource is TurnCourseSnapshot['resources'][number] => {
    if (resource === null || typeof resource !== 'object' || Array.isArray(resource)) return false;
    const candidate = resource as { label?: unknown; kind?: unknown; availability?: unknown };
    // 既无可读标签、也没有可识别的 kind/可用性 —— 该条目不承载任何信息，丢弃而不是渲染噪音
    return (
      asText(candidate.label).trim().length > 0 ||
      typeof candidate.kind === 'string' ||
      (typeof candidate.availability === 'string' && RESOURCE_AVAILABILITY.has(candidate.availability))
    );
  });
}

function renderCourseBlock(snapshot: TurnCourseSnapshot, plan: CourseBlockPlan): string {
  const name = ellipsize(asText(snapshot.name), plan.nameLimit);
  const lines = [COURSE_HEADER, `课程名称：${name}`];
  const conventions = ellipsize(asText(snapshot.conventions), plan.conventionsLimit);
  if (conventions) lines.push(`${COURSE_CONVENTIONS_HEADING}\n<<<\n${conventions}\n>>>`);
  const total = snapshot.syllabus?.total ?? 0;
  const covered = snapshot.syllabus?.covered ?? 0;
  const nextTitle = ellipsize(asText(snapshot.syllabus?.nextTitle), plan.nextTitleLimit);
  if (total > 0)
    lines.push(
      `大纲进度：共 ${total} 个单元，已完成 ${covered} 个（学员手判）${
        nextTitle ? `；下一个未完成单元：${nextTitle}` : ''
      }`,
    );
  const resources = safeResources(snapshot);
  if (resources.length > 0) {
    const shown = resources
      .slice(0, Math.max(0, plan.itemLimit))
      .map(
        (resource) =>
          `${ellipsize(asText(resource.label), plan.labelLimit)}（${asKind(resource.kind)}·${asAvailability(
            resource.availability,
          )}）`,
      );
    const omitted = resources.length - shown.length;
    // 条目减少时以「…等共 N 项」如实说明总量，不假装列全
    lines.push(
      `${COURSE_RESOURCE_PREFIX}${shown.join('、')}${omitted > 0 ? `…等共 ${resources.length} 项` : ''}`,
    );
  } else {
    // 无登记资源时也必须带上固定免责句，避免"没有资源就没有免责说明"的假完整
    lines.push(`${COURSE_RESOURCE_PREFIX}无登记资源`);
  }
  return lines.join('\n');
}

/** 整体超限时的收缩阶梯（每步累积、只减不增；步到位就停止并如实记录被裁剪字段） */
const COURSE_SHRINK_LADDER: { field: string; plan: CourseBlockPlan }[] = [
  { field: 'resourceLabels', plan: { ...FULL_COURSE_PLAN, labelLimit: 24 } },
  { field: 'resourceItems', plan: { ...FULL_COURSE_PLAN, labelLimit: 24, itemLimit: 6 } },
  { field: 'resourceItems', plan: { ...FULL_COURSE_PLAN, labelLimit: 24, itemLimit: 0 } },
  { field: 'conventions', plan: { ...FULL_COURSE_PLAN, labelLimit: 24, itemLimit: 0, conventionsLimit: 400 } },
  { field: 'conventions', plan: { ...FULL_COURSE_PLAN, labelLimit: 24, itemLimit: 0, conventionsLimit: 0 } },
  {
    field: 'syllabus',
    plan: { ...FULL_COURSE_PLAN, labelLimit: 24, itemLimit: 0, conventionsLimit: 0, nextTitleLimit: 40 },
  },
  {
    field: 'name',
    plan: {
      ...FULL_COURSE_PLAN,
      labelLimit: 24,
      itemLimit: 0,
      conventionsLimit: 0,
      nextTitleLimit: 40,
      nameLimit: 40,
    },
  },
];

/**
 * 课程块渲染（§4）：上限为 `min(2400, maxMessageChars - 1)`。
 * 返回 `null` 表示给定单条上限内无法渲染出含固定行与免责句的课程块——
 * 调用方必须**整体丢弃**课程上下文（不得发送残缺/伪造的课程块）。
 */
export function renderCourseContextBlock(
  snapshot: TurnCourseSnapshot,
  limits: BackendRequestLimits = BACKEND_REQUEST_LIMITS,
): { text: string; trimmedFields: string[] } | null {
  const cap = Math.min(COURSE_CONTEXT_MESSAGE_LIMIT, Math.max(0, limits.maxMessageChars - 1));
  if (cap <= 0) return null;
  const trimmed = new Set<string>();
  if (asText(snapshot.name).trim().length > COURSE_BLOCK_FIELD_LIMITS.nameChars) trimmed.add('name');
  if (asText(snapshot.conventions).trim().length > COURSE_CONVENTIONS_LIMIT)
    trimmed.add('conventions');
  if (asText(snapshot.syllabus?.nextTitle).trim().length > COURSE_BLOCK_FIELD_LIMITS.nextTitleChars)
    trimmed.add('syllabus');
  const resources = safeResources(snapshot);
  if (resources.some((resource) => asText(resource.label).trim().length > COURSE_RESOURCE_LABEL_LIMIT))
    trimmed.add('resourceLabels');
  if (resources.length > COURSE_CONTEXT_RESOURCE_ITEM_LIMIT) trimmed.add('resourceItems');

  let text = renderCourseBlock(snapshot, FULL_COURSE_PLAN);
  if (text.length > cap) {
    for (const step of COURSE_SHRINK_LADDER) {
      const next = renderCourseBlock(snapshot, step.plan);
      if (next.length >= text.length) continue; // 该步没有实际收缩：不记录字段
      text = next;
      trimmed.add(step.field);
      if (text.length <= cap) break;
    }
  }
  if (text.length > cap) return null; // 固定行与免责句不可被砍：宁可整体丢弃
  return { text, trimmedFields: [...trimmed] };
}

/** 收集「已过滤 superseded / error」的历史（课程块以外唯一的历史来源） */
export function requestHistory(messages: ChatMessage[]): ChatMessage[] {
  return messages.filter((message) => !message.superseded && message.status !== 'error');
}

export interface BuildChatRequestInput {
  /** 已过滤 superseded / error 的历史（可含最新一条用户消息＝当前问题，构建时不重复发送） */
  history: ChatMessage[];
  /** 当前问题原文（逐字不裁剪）；普通发送时＝即将入库的用户消息正文 */
  question: string;
  courseSnapshot?: TurnCourseSnapshot;
  contextTokens?: number | null;
  maxOutputTokens?: number | null;
  limits?: BackendRequestLimits;
}

function questionTooLarge(message: string, questionChars: number, allowedChars: number): BuildRequestResult {
  return { ok: false, reason: 'question-too-large', message, questionChars, allowedChars };
}

/**
 * 构建一次真实请求（唯一入口）。`ok:false` 时**无副作用**：不创建占位、不置 sending、
 * 不清输入——由调用方（store）保证，用户可修改后重发。
 */
export function buildChatRequest(input: BuildChatRequestInput): BuildRequestResult {
  const limits = input.limits ?? BACKEND_REQUEST_LIMITS;
  const maxMessages = Math.max(0, Math.floor(limits.maxMessages));
  const maxMessageChars = Math.max(0, Math.floor(limits.maxMessageChars));
  const maxTotalChars = Math.max(0, Math.floor(limits.maxTotalChars));
  const inputBudget = Math.max(
    0,
    Math.min(contextBudgetChars(input.contextTokens, input.maxOutputTokens), maxTotalChars),
  );
  const question = input.question;
  const questionChars = question.length;
  // 当前问题要同时满足「总预算」与「后端单条上限」；两者取小才是实际允许值
  const allowedChars = Math.min(inputBudget, maxMessageChars);
  if (questionChars === 0)
    return questionTooLarge('当前请求没有可发送的问题内容，请先输入文字。', 0, allowedChars);
  if (maxMessages < 1)
    return questionTooLarge(
      `本轮可用消息条数为 0（上限 ${limits.maxMessages} 条），无法发送请求。`,
      questionChars,
      allowedChars,
    );
  if (questionChars > allowedChars)
    return questionTooLarge(
      `当前问题 ${questionChars} 个字符，超出本轮可用预算 ${allowedChars} 个字符（字符估算）。请缩短问题，或换用上下文预算更大的模型后重试。`,
      questionChars,
      allowedChars,
    );

  const history = projectRequestHistory(input.history);
  // 重试路径的历史尾部就是当前问题本身：以 question 为准，避免重复发送同一条用户消息
  const tail = history.at(-1);
  if (tail && tail.role === 'user' && tail.content === question) history.pop();

  let courseFields: string[] = [];
  let courseText: string | null = null;
  let courseDropped = false;
  if (input.courseSnapshot) {
    const block = renderCourseContextBlock(input.courseSnapshot, limits);
    if (block) {
      courseText = block.text;
      courseFields = block.trimmedFields;
    } else {
      // 单条上限内无法保留固定行与免责句：整体丢弃（不得发送残缺课程上下文）
      courseDropped = true;
    }
  }

  if (courseText) {
    const capacityChars = inputBudget - questionChars - courseText.length;
    const capacityCount = maxMessages - 2; // 课程块 + 当前问题各占一条
    if (capacityChars < 0 || capacityCount < 0) {
      // ③ 仍超限：整体丢弃课程块（不发送残缺上下文），剩余预算回给历史
      courseDropped = true;
      courseText = null;
      courseFields = [];
    }
  }
  const capacityChars = inputBudget - questionChars - (courseText?.length ?? 0);
  const capacityCount = maxMessages - 1 - (courseText ? 1 : 0);
  const picked = takeNewestMessages(history, {
    chars: capacityChars,
    count: capacityCount,
    maxChars: maxMessageChars,
  });
  const notes: RequestNote[] = [];
  if (picked.dropped > 0) notes.push({ kind: 'history-dropped', messages: picked.dropped });
  if (courseText && courseFields.length > 0)
    notes.push({ kind: 'course-trimmed', fields: courseFields });
  if (courseDropped) notes.push({ kind: 'course-dropped' });

  const messages: RequestMessage[] = [
    ...(courseText ? [{ role: 'system' as const, content: courseText }] : []),
    ...picked.messages,
    { role: 'user', content: question },
  ];
  const totalChars = messages.reduce((total, message) => total + message.content.length, 0);
  // 兜底自检：任何一项不满足都不发送（不返回假成功）
  const withinLimits =
    messages.length <= maxMessages &&
    totalChars <= Math.min(inputBudget, maxTotalChars) &&
    messages.every((message) => message.content.length <= maxMessageChars);
  if (!withinLimits)
    return questionTooLarge(
      `本轮请求在字符估算下仍超出可用预算（上限约 ${Math.min(inputBudget, maxTotalChars)} 字符）。请缩短问题或减少历史上下文后重试。`,
      questionChars,
      allowedChars,
    );

  return {
    ok: true,
    messages,
    record: {
      totalChars,
      inputBudgetChars: inputBudget,
      maxMessageChars,
      maxTotalChars,
      historyDroppedMessages: picked.dropped,
      courseTrimmedFields: courseFields,
      courseDropped,
    },
    notes,
  };
}
