/**
 * 课程本地仓储（S5-C）。
 * 参考 StudyCourse 走后端 API + CourseState 聚合；目标项目为本地目录：
 * 大纲（covered 学员手判，不自动推断）、资源（引用本地知识库/笔记本/书籍目录，
 * 引用消失时显示"不可用"）、颜色标记。参考的课程会话归属是 session.preferences.course_id（服务端会话形态）；
 * 本宿主的课程学习会话由 H1-COURSE-SESSIONS v1 落地：归属为 `Conversation.courseId`（本地会话库，见 services/course-session.ts）。
 */
import { readKnowledge, subscribeKnowledge, type KnowledgeEntry } from './knowledge-catalog';
import { listNotebooks, subscribeNotebooks, type Notebook } from './notebook-store';
import { readBooks, subscribeBooks, type ReplicaBook } from './books-store';
import { readStrictList, writeStrictList } from './local-collection';

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
  return readStrictList<StudyCourse>(KEY).filter(
    (item): item is StudyCourse =>
      item && typeof item.id === 'string' && typeof item.name === 'string',
  );
}

function writeList(list: StudyCourse[]): void {
  writeStrictList(KEY, list);
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

/**
 * 资源目录一致快照（R-11）。
 *
 * 三个外部目录**各自独立**读取：某一个失败（JSON 损坏 / 结构非法 / 存储读取失败）
 * 只把该目录标为 `null` 并记录错误，**不影响**其他目录与课程自身。
 * 读取集中在一次调用里完成并作为快照向下传递，渲染期间不再反复读取目录。
 */
export interface ResourceDirectorySnapshot {
  knowledge: KnowledgeEntry[] | null;
  knowledgeError: string | null;
  notebooks: Notebook[] | null;
  notebooksError: string | null;
  books: ReplicaBook[] | null;
  booksError: string | null;
}

function readDirectory<T>(read: () => T[]): { value: T[] | null; error: string | null } {
  try {
    return { value: read(), error: null };
  } catch (cause) {
    return {
      value: null,
      error: cause instanceof Error ? cause.message : '本地目录无法读取，原数据未修改。',
    };
  }
}

/** 集中读取三个资源目录，形成一次一致快照（失败目录为 null，不阻断其他目录）。 */
export function readResourceDirectories(): ResourceDirectorySnapshot {
  const knowledge = readDirectory(() => readKnowledge());
  const notebooks = readDirectory(() => listNotebooks());
  const books = readDirectory(() => readBooks());
  return {
    knowledge: knowledge.value,
    knowledgeError: knowledge.error,
    notebooks: notebooks.value,
    notebooksError: notebooks.error,
    books: books.value,
    booksError: books.error,
  };
}

/** 目录快照是否全成功（供界面决定是否显示"目录读取失败"与重试入口）。 */
export function snapshotError(snapshot: ResourceDirectorySnapshot): string | null {
  return snapshot.knowledgeError ?? snapshot.notebooksError ?? snapshot.booksError ?? null;
}

/** 资源目录变化（knowledge/notebooks/books）时通知课程页失效快照并重算。 */
export function subscribeResourceDirectories(listener: () => void): () => void {
  const offKnowledge = subscribeKnowledge(listener);
  const offNotebooks = subscribeNotebooks(listener);
  const offBooks = subscribeBooks(listener);
  return () => {
    offKnowledge();
    offNotebooks();
    offBooks();
  };
}

/**
 * 候选来自本地目录：知识库 + 笔记本 + 书籍（真实跨页联动）。
 * 传入快照时只看成功读取的目录；读取失败的目录不假装为空，也不阻断其他来源。
 */
export function listResourceCandidates(snapshot?: ResourceDirectorySnapshot): ResourceCandidate[] {
  const dirs = snapshot ?? readResourceDirectories();
  const candidates: ResourceCandidate[] = [];
  for (const kb of dirs.knowledge ?? []) {
    candidates.push({ kind: 'knowledge_base', refId: kb.id, label: kb.name });
  }
  for (const notebook of dirs.notebooks ?? []) {
    candidates.push({ kind: 'notebook', refId: notebook.id, label: notebook.name });
  }
  for (const book of dirs.books ?? []) {
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
  /** 引用目标是否仍存在于本地目录（仅当目录读取成功且命中时为 true） */
  available: boolean;
  /**
   * 三态可用性（R-11）：
   * - `available` 目标命中；
   * - `missing`   目录读取成功但目标不存在（原“目标已删除或未载入”）；
   * - `unknown`   目录读取失败，无法确认（显示错误与重试，**不**断言目标已删除）。
   */
  availability: 'available' | 'missing' | 'unknown';
  /** 可用时的跳转地址 */
  href: string | null;
  /** availability=unknown 时该目录的读取错误说明 */
  error: string | null;
}

/** 单条资源的解析：目录失败记为 unknown，绝不把“读取失败”当成“目标已删除”。 */
function resolveResource(
  resource: CourseResource,
  snapshot: ResourceDirectorySnapshot,
): CourseResourceState {
  if (resource.kind === 'knowledge_base') {
    if (snapshot.knowledge === null) {
      return { resource, available: false, availability: 'unknown', href: null, error: snapshot.knowledgeError };
    }
    const kb = snapshot.knowledge.find((entry) => entry.id === resource.refId);
    return {
      resource,
      available: kb !== undefined,
      availability: kb ? 'available' : 'missing',
      href: kb ? `/knowledge-bases/${encodeURIComponent(kb.name)}` : null,
      error: null,
    };
  }
  if (resource.kind === 'notebook') {
    if (snapshot.notebooks === null) {
      return { resource, available: false, availability: 'unknown', href: null, error: snapshot.notebooksError };
    }
    const found = snapshot.notebooks.some((notebook) => notebook.id === resource.refId);
    return {
      resource,
      available: found,
      availability: found ? 'available' : 'missing',
      href: found ? `/notebooks/${resource.refId}` : null,
      error: null,
    };
  }
  if (snapshot.books === null) {
    return { resource, available: false, availability: 'unknown', href: null, error: snapshot.booksError };
  }
  const found = snapshot.books.some((book) => book.id === resource.refId && book.status !== 'archived');
  return {
    resource,
    available: found,
    availability: found ? 'available' : 'missing',
    href: found ? `/books/${resource.refId}` : null,
    error: null,
  };
}

/** 计算资源状态；传入快照时不再重复读取目录（渲染路径不得触发目录读取）。 */
export function courseResourceStates(
  course: StudyCourse,
  snapshot?: ResourceDirectorySnapshot,
): CourseResourceState[] {
  const dirs = snapshot ?? readResourceDirectories();
  return course.resources.map((resource) => resolveResource(resource, dirs));
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
