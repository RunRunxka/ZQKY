/**
 * 课程学习会话：契约辅助（H1-COURSE-SESSIONS v1）。
 *
 * 本模块是"课程 ↔ 会话"归属与"轮次课程快照"的**唯一事实来源**（纯函数 + 一次目录读取）：
 * - 归属只认 `Conversation.courseId` 与 `StudyCourse.id` 的稳定相等，**不按标题/最近访问/URL 猜测**；
 * - 课程上下文在**发送时**冻结成 `TurnCourseSnapshot`（随助手消息持久化，重试沿用原快照）；
 * - 快照渲染成一条 `system` 消息进入既有真实请求链路（`/api/v1/chat/stream` 的 `messages`），
 *   不新增请求字段、不改后端协议；内容如实标注"资源仅登记、未解析未检索"。
 */
import type { Conversation, ConversationMeta, TurnCourseSnapshot } from '@/contracts/chat';
import {
  courseResourceStates,
  readCourses,
  type StudyCourse,
  type SyllabusUnit,
} from './courses-store';

/** 快照里课程约定与整体的字符上限（对照参考 `_COURSE_CONVENTIONS_LIMIT = 1200`） */
export const COURSE_CONVENTIONS_LIMIT = 1200;
export const COURSE_CONTEXT_MESSAGE_LIMIT = 2400;
/** 资源清单最多列出多少条（其余以「…等共 N 项」说明） */
export const COURSE_CONTEXT_RESOURCE_ITEM_LIMIT = 12;
/** 单条资源标签的字符上限（避免超长标签挤掉上下文） */
export const COURSE_RESOURCE_LABEL_LIMIT = 80;
/** 资源行的固定前缀：**保证不被截断**的免责说明 */
const RESOURCE_DISCLAIMER =
  '课程资源（仅登记引用：内容未解析、未检索、未随本请求发送）：';
/**
 * 渲染期字段上限（CHAT-CONTEXT-BUDGET v1 §4，对**旧快照**同样生效）：
 * 课程名 ≤80、下一个未完成单元标题 ≤120。与
 * `features/chat/model/request-budget.ts` 的同名上限保持同一数值（同一文案契约）。
 */
const COURSE_NAME_LIMIT = 80;
const COURSE_NEXT_TITLE_LIMIT = 120;

/** 课程解析结果：`unavailable` = 目录读取失败（不得当成"课程已被删除"，也不得沿用其他课程） */
export type CourseResolution =
  | { state: 'ok'; course: StudyCourse }
  | { state: 'missing' }
  | { state: 'unavailable'; error: string };

/** 按稳定 id 解析课程；读取失败与"不存在"分开（R-11 同口径） */
export function resolveCourse(courseId: string): CourseResolution {
  if (!courseId) return { state: 'missing' };
  try {
    const course = readCourses().find((item) => item.id === courseId);
    return course ? { state: 'ok', course } : { state: 'missing' };
  } catch (cause) {
    return {
      state: 'unavailable',
      error: cause instanceof Error ? cause.message : '课程目录无法读取，原数据未修改。',
    };
  }
}

/** 会话列表元数据 → 本课程会话（按更新时间倒序）；只认 courseId 相等 */
export function listCourseSessions(
  metas: ConversationMeta[],
  courseId: string,
): ConversationMeta[] {
  if (!courseId) return [];
  return metas
    .filter((meta) => meta.courseId === courseId)
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

/** 删除/归档课程后仍保留归属（本批契约）：这里只用于展示层判定 */
export function courseAvailabilityLabel(resolution: CourseResolution): string {
  if (resolution.state === 'ok') return resolution.course.name;
  if (resolution.state === 'missing') return '所属课程已删除或不可用';
  return '课程目录读取失败，暂无法确认课程上下文';
}

function truncate(text: string, limit: number): string {
  const trimmed = text.trim();
  return trimmed.length <= limit ? trimmed : `${trimmed.slice(0, limit)}…`;
}

/**
 * 冻结课程快照（发送时调用一次）：只包含"确需参与问答"的信息，资源仅登记形态。
 * 不做任何内容解析、不触发检索；`frozenAt` 记录冻结时刻。
 */
export function buildCourseSnapshot(
  course: StudyCourse,
  frozenAt: string = new Date().toISOString(),
): TurnCourseSnapshot {
  const resources = courseResourceStates(course).map((state) => ({
    kind: state.resource.kind,
    label: state.resource.label,
    availability: state.availability,
  }));
  const next: SyllabusUnit | null = course.syllabus.find((unit) => !unit.covered) ?? null;
  return {
    courseId: course.id,
    name: course.name,
    conventions: truncate(course.instructions, COURSE_CONVENTIONS_LIMIT),
    syllabus: {
      total: course.syllabus.length,
      covered: course.syllabus.filter((unit) => unit.covered).length,
      nextTitle: next ? next.title : null,
    },
    resources,
    frozenAt,
  };
}

/** 发送时解析本轮的课程快照；课程不存在/目录失败时明确区分（调用方据此提示且不注入上下文） */
export function resolveCourseSnapshot(
  courseId: string | undefined,
  frozenAt?: string,
): { state: 'none' } | { state: 'ok'; snapshot: TurnCourseSnapshot } | { state: 'missing' } | { state: 'unavailable'; error: string } {
  if (!courseId) return { state: 'none' };
  const resolved = resolveCourse(courseId);
  if (resolved.state === 'ok') {
    return { state: 'ok', snapshot: buildCourseSnapshot(resolved.course, frozenAt) };
  }
  return resolved.state === 'missing' ? { state: 'missing' } : { state: 'unavailable', error: resolved.error };
}

/**
 * 快照 → system 消息文本（进入既有真实请求链路）。
 * 如实表述边界：资源只是登记引用；不声称已解析、已检索或来自 RAG。
 */
export function courseContextMessage(snapshot: TurnCourseSnapshot): string {
  const header =
    '本节对话属于一门课程，以下是课程上下文（本地登记信息，供你组织回答；不是用户消息）：';
  // 字段上限（只影响本函数输出，不改快照字段、不回写课程原始数据）；
  // 超长值沿用既有 truncate 约定：截到上限并追加省略号。
  const name = truncate(snapshot.name, COURSE_NAME_LIMIT);
  const nextTitle = snapshot.syllabus.nextTitle
    ? truncate(snapshot.syllabus.nextTitle, COURSE_NEXT_TITLE_LIMIT)
    : null;
  const nameLine = `课程名称：${name}`;
  const syllabusLine =
    snapshot.syllabus.total > 0
      ? `大纲进度：共 ${snapshot.syllabus.total} 个单元，已完成 ${snapshot.syllabus.covered} 个（学员手判）${
          nextTitle ? `；下一个未完成单元：${nextTitle}` : ''
        }`
      : null;

  let conventions = truncate(snapshot.conventions, COURSE_CONVENTIONS_LIMIT);
  let itemCount = Math.min(snapshot.resources.length, COURSE_CONTEXT_RESOURCE_ITEM_LIMIT);
  let labelLimit = COURSE_RESOURCE_LABEL_LIMIT;

  const build = (): string => {
    const lines = [header, nameLine];
    if (conventions) {
      lines.push(`课程约定（学员填写，请遵守）：\n<<<\n${conventions}\n>>>`);
    }
    if (syllabusLine) lines.push(syllabusLine);
    if (snapshot.resources.length > 0) {
      const shown = snapshot.resources
        .slice(0, itemCount)
        .map((resource) => `${truncate(resource.label, labelLimit)}（${resource.kind}·${resource.availability}）`);
      const omitted = snapshot.resources.length - shown.length;
      // 免责句是固定前缀：收缩条目/约定而不是砍尾，避免把「仅登记引用」截掉
      lines.push(`${RESOURCE_DISCLAIMER}${shown.join('、')}${omitted > 0 ? `…等共 ${snapshot.resources.length} 项` : ''}`);
    }
    return lines.join('\n');
  };

  // 预算内收缩顺序：先压缩标签 → 再逐条减少条目（保留免责句）→ 最后压缩约定
  let text = build();
  for (let step = 0; step < 96 && text.length > COURSE_CONTEXT_MESSAGE_LIMIT; step += 1) {
    if (labelLimit > 24) labelLimit = 24;
    else if (itemCount > 0) itemCount -= 1;
    else if (conventions) conventions = truncate(conventions, Math.max(0, conventions.length - 160));
    else break;
    text = build();
  }
  return text;
}

/** 新建会话对象（课程页与聊天页共用同一形状；不建第二套会话库） */
export function buildNewConversation(input: {
  id: string;
  courseId?: string;
  title?: string;
  now?: string;
}): Conversation {
  const at = input.now ?? new Date().toISOString();
  return {
    id: input.id,
    title: input.title ?? '新的对话',
    messages: [],
    createdAt: at,
    updatedAt: at,
    schemaVersion: 1,
    revision: 0,
    draft: '',
    modelProfileId: null,
    mode: 'real',
    ...(input.courseId ? { courseId: input.courseId } : {}),
  };
}
