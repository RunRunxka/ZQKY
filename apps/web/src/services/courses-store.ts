/**
 * 课程本地仓储（S5-C）。
 * 参考 StudyCourse 走后端 API + CourseState 聚合；目标项目为本地目录：
 * 大纲（covered 学员手判，不自动推断）、资源（引用本地知识库/笔记本/书籍目录，
 * 引用消失时显示"不可用"）、颜色标记。课程学习会话依赖 session.preferences.course_id，
 * 聊天侧尚未携带课程标记——如实标注未接入（见 docs/replica/HANDOFF 有意差异）。
 */
import { readKnowledge } from './knowledge-catalog';
import { listNotebooks } from './notebook-store';
import { readBooks } from './books-store';

export type CourseResourceKind = 'knowledge_base' | 'notebook' | 'book';
export type CourseColor = 'blue' | 'green' | 'amber' | 'purple' | 'gray';

export interface SyllabusUnit {
  id: string;
  position: number;
  title: string;
  topics: string[];
  covered: boolean;
}

export interface CourseResource {
  id: string;
  kind: CourseResourceKind;
  /** 引用本地目录条目 id */
  refId: string;
  label: string;
  position: number;
  addedAt: string;
}

export interface StudyCourse {
  id: string;
  name: string;
  description: string;
  color: CourseColor;
  instructions: string;
  syllabus: SyllabusUnit[];
  resources: CourseResource[];
  status: 'active' | 'archived';
  createdAt: string;
  updatedAt: string;
}

const KEY = 'zhiqikeyuan:courses';
const EVENT = 'zqky:courses';

export const COURSE_COLORS: CourseColor[] = ['blue', 'green', 'amber', 'purple', 'gray'];

export const COURSE_COLOR_DOT: Record<CourseColor, string> = {
  blue: '#2563eb',
  green: '#33876b',
  amber: '#b7791f',
  purple: '#7c5cd6',
  gray: '#8a8a8a',
};

export const COURSE_KIND_LABEL: Record<CourseResourceKind, string> = {
  knowledge_base: '知识库',
  notebook: '笔记本',
  book: '书籍',
};

export class CourseValidationError extends Error {}

function uid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function readList(): StudyCourse[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item): item is StudyCourse =>
        item && typeof item.id === 'string' && typeof item.name === 'string',
    );
  } catch {
    return [];
  }
}

function writeList(list: StudyCourse[]): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(KEY, JSON.stringify(list));
  notify();
}

function notify(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(EVENT));
}

export function readCourses(): StudyCourse[] {
  return readList();
}

export function subscribeCourses(listener: () => void): () => void {
  const storage = (event: StorageEvent) => {
    if (event.key === KEY || event.key === null) listener();
  };
  window.addEventListener(EVENT, listener);
  window.addEventListener('storage', storage);
  return () => {
    window.removeEventListener(EVENT, listener);
    window.removeEventListener('storage', storage);
  };
}

// ===== CRUD =====

export function createCourse(name: string, description: string, color: CourseColor = 'blue'): StudyCourse {
  const trimmed = name.trim();
  if (!trimmed) throw new CourseValidationError('课程名称不能为空。');
  if (trimmed.length > 60) throw new CourseValidationError('课程名称过长（不超过 60 字）。');
  const list = readList();
  if (list.some((course) => course.name === trimmed))
    throw new CourseValidationError('已存在同名课程，请换一个名称。');
  const now = new Date().toISOString();
  const course: StudyCourse = {
    id: uid('cs'),
    name: trimmed,
    description: description.trim(),
    color,
    instructions: '',
    syllabus: [],
    resources: [],
    status: 'active',
    createdAt: now,
    updatedAt: now,
  };
  writeList([...list, course]);
  return course;
}

export function updateCourse(
  courseId: string,
  patch: { name?: string; description?: string; color?: CourseColor; instructions?: string },
): StudyCourse {
  const list = readList();
  const idx = list.findIndex((course) => course.id === courseId);
  if (idx === -1) throw new CourseValidationError('课程不存在或已被删除。');
  if (patch.name !== undefined) {
    const trimmed = patch.name.trim();
    if (!trimmed) throw new CourseValidationError('课程名称不能为空。');
    if (list.some((course) => course.id !== courseId && course.name === trimmed))
      throw new CourseValidationError('已存在同名课程，请换一个名称。');
  }
  list[idx] = {
    ...list[idx]!,
    ...(patch.name !== undefined ? { name: patch.name.trim() } : {}),
    ...(patch.description !== undefined ? { description: patch.description.trim() } : {}),
    ...(patch.color !== undefined ? { color: patch.color } : {}),
    ...(patch.instructions !== undefined ? { instructions: patch.instructions } : {}),
    updatedAt: new Date().toISOString(),
  };
  writeList(list);
  return list[idx]!;
}

export function deleteCourse(courseId: string): boolean {
  const list = readList();
  const kept = list.filter((course) => course.id !== courseId);
  if (kept.length === list.length) return false;
  writeList(kept);
  return true;
}

export function setCourseArchived(courseId: string, archived: boolean): StudyCourse | null {
  const list = readList();
  const idx = list.findIndex((course) => course.id === courseId);
  if (idx === -1) return null;
  list[idx] = { ...list[idx]!, status: archived ? 'archived' : 'active', updatedAt: new Date().toISOString() };
  writeList(list);
  return list[idx]!;
}

// ===== 大纲（学员手判 covered，不自动推断） =====

/** 解析大纲文本：每行 "标题 | topic1, topic2"（对照参考 CourseSyllabus textarea） */
export function parseSyllabusText(text: string): SyllabusUnit[] {
  const units: SyllabusUnit[] = [];
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const [rawTitle, rawTopics = ''] = trimmed.split('|');
    const title = rawTitle.trim();
    if (!title) continue;
    units.push({
      id: uid('unit'),
      position: units.length,
      title,
      topics: rawTopics
        .split(/[,，]/)
        .map((topic) => topic.trim())
        .filter(Boolean),
      covered: false,
    });
  }
  return units;
}

export function setCourseSyllabus(courseId: string, units: SyllabusUnit[]): StudyCourse | null {
  const list = readList();
  const idx = list.findIndex((course) => course.id === courseId);
  if (idx === -1) return null;
  list[idx] = {
    ...list[idx]!,
    syllabus: units.map((unit, position) => ({ ...unit, position })),
    updatedAt: new Date().toISOString(),
  };
  writeList(list);
  return list[idx]!;
}

export function toggleUnitCovered(courseId: string, unitId: string): StudyCourse | null {
  const list = readList();
  const idx = list.findIndex((course) => course.id === courseId);
  if (idx === -1) return null;
  const syllabus = list[idx]!.syllabus.map((unit) =>
    unit.id === unitId ? { ...unit, covered: !unit.covered } : unit,
  );
  list[idx] = { ...list[idx]!, syllabus, updatedAt: new Date().toISOString() };
  writeList(list);
  return list[idx]!;
}

export interface SyllabusSummary {
  total: number;
  covered: number;
  /** 第一个未 covered 单元（无则 null） */
  next: SyllabusUnit | null;
}

export function syllabusSummary(course: StudyCourse): SyllabusSummary {
  const covered = course.syllabus.filter((unit) => unit.covered).length;
  return {
    total: course.syllabus.length,
    covered,
    next: course.syllabus.find((unit) => !unit.covered) ?? null,
  };
}

// ===== 资源（本地目录引用；目标消失显示"不可用"） =====

export interface ResourceCandidate {
  kind: CourseResourceKind;
  refId: string;
  label: string;
}

/** 候选来自本地目录：知识库 + 笔记本 + 书籍（真实跨页联动） */
export function listResourceCandidates(): ResourceCandidate[] {
  const candidates: ResourceCandidate[] = [];
  for (const kb of readKnowledge()) {
    candidates.push({ kind: 'knowledge_base', refId: kb.id, label: kb.name });
  }
  for (const notebook of listNotebooks()) {
    candidates.push({ kind: 'notebook', refId: notebook.id, label: notebook.name });
  }
  for (const book of readBooks()) {
    if (book.status === 'archived') continue;
    candidates.push({ kind: 'book', refId: book.id, label: book.title });
  }
  return candidates;
}

export function attachCourseResource(
  courseId: string,
  kind: CourseResourceKind,
  refId: string,
  label: string,
): StudyCourse | null {
  const list = readList();
  const idx = list.findIndex((course) => course.id === courseId);
  if (idx === -1) return null;
  const course = list[idx]!;
  if (course.resources.some((resource) => resource.kind === kind && resource.refId === refId)) {
    throw new CourseValidationError('该资源已附加到本课程。');
  }
  list[idx] = {
    ...course,
    resources: [
      ...course.resources,
      { id: uid('res'), kind, refId, label, position: course.resources.length, addedAt: new Date().toISOString() },
    ],
    updatedAt: new Date().toISOString(),
  };
  writeList(list);
  return list[idx]!;
}

export function detachCourseResource(courseId: string, resourceId: string): StudyCourse | null {
  const list = readList();
  const idx = list.findIndex((course) => course.id === courseId);
  if (idx === -1) return null;
  list[idx] = {
    ...list[idx]!,
    resources: list[idx]!.resources.filter((resource) => resource.id !== resourceId),
    updatedAt: new Date().toISOString(),
  };
  writeList(list);
  return list[idx]!;
}

export interface CourseResourceState {
  resource: CourseResource;
  /** 引用目标是否仍存在于本地目录 */
  available: boolean;
  /** 可用时的跳转地址 */
  href: string | null;
}

function resourceHref(kind: CourseResourceKind, refId: string): string | null {
  if (kind === 'knowledge_base') {
    const kb = readKnowledge().find((entry) => entry.id === refId);
    return kb ? `/knowledge-bases/${encodeURIComponent(kb.name)}` : null;
  }
  if (kind === 'notebook') {
    return listNotebooks().some((notebook) => notebook.id === refId) ? `/notebooks/${refId}` : null;
  }
  return readBooks().some((book) => book.id === refId && book.status !== 'archived') ? `/books/${refId}` : null;
}

export function courseResourceStates(course: StudyCourse): CourseResourceState[] {
  return course.resources.map((resource) => {
    const href = resourceHref(resource.kind, resource.refId);
    return { resource, available: href !== null, href };
  });
}

// ===== 演示数据 =====

const DEMO_COURSES: StudyCourse[] = [
  {
    id: 'demo-course-math',
    name: '七年级数学（演示课程）',
    description: '围绕分数与方程的学期课程（演示数据）。',
    color: 'blue',
    instructions: '每次课前先复习上一单元错题（演示约定）。',
    syllabus: [
      { id: 'demo-unit-1', position: 0, title: '分数与比例', topics: ['分数大小比较', '比例应用'], covered: true },
      { id: 'demo-unit-2', position: 1, title: '一元一次方程', topics: ['解方程', '应用题'], covered: false },
    ],
    // 引用演示知识库目录的 id：未载入知识库演示数据时显示"不可用"（对照参考 Unavailable 行为）
    resources: [
      { id: 'demo-res-1', kind: 'knowledge_base', refId: 'demo-kb-curriculum', label: '课程标准库', position: 0, addedAt: '2026-09-08T01:00:00.000Z' },
    ],
    status: 'active',
    createdAt: '2026-09-08T01:00:00.000Z',
    updatedAt: '2026-09-08T01:00:00.000Z',
  },
  {
    id: 'demo-course-archived',
    name: '暑期阅读营（已归档演示）',
    description: '已结束的阅读课程（演示归档状态）。',
    color: 'gray',
    instructions: '',
    syllabus: [],
    resources: [],
    status: 'archived',
    createdAt: '2026-08-01T01:00:00.000Z',
    updatedAt: '2026-08-20T01:00:00.000Z',
  },
];

/** 显式载入演示课程（幂等） */
export function loadDemoCourses(): void {
  const existing = readList();
  const merged = [...existing];
  for (const demo of DEMO_COURSES) {
    if (!merged.some((item) => item.id === demo.id)) merged.push(demo);
  }
  writeList(merged);
}
