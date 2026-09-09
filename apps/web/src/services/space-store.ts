'use client';
import { readStrictList, writeStrictList } from './local-collection';
/**
 * S4/S5 本地模拟仓储：题库（quiz-bank）与笔记（notebook）。
 *
 * 对照参考 v1.6.5 的业务页数据流（web/lib/notebook-api.ts 的 NotebookEntry /
 * 题库条目语义），在本地以 localStorage 持久化——聊天产物"保存到题库/保存到
 * 笔记"与 S5 业务页（/space/questions、/notebooks 等）读写同一份仓储与身份，
 * 不另造静态副本。条目 id 沿用产物复合身份（消息 id + 产物/题目 id），
 * 与聊天侧 R24 的复合身份一致。
 *
 * S5-A 扩展：书签/已解决/分类/来源为可选字段（旧数据缺省即 false/未分类，
 * 向后兼容）；分类独立列表；演示题库显式载入（幂等），不自动写入。
 */

const QUIZ_BANK_KEY = 'zhiqikeyuan:quiz-bank';
const NOTEBOOK_KEY = 'zhiqikeyuan:notebook-entries';
const QUIZ_CATEGORY_KEY = 'zhiqikeyuan:quiz-categories';

/** 题目来源（对照参考 AssessmentSource，本仓库当前仅聊天出题与演示数据） */
export type QuizSource = 'deep_question' | 'demo';

/** 题库条目（题干/选项/答案/解析 + 作答记录；结构对照参考 QuizQuestion） */
export interface QuizBankEntry {
  /** 复合身份：`${messageId}:${questionId}`——同轮同 id 不重复，跨轮互不串位 */
  id: string;
  messageId: string;
  questionId: string;
  topic: string;
  question: string;
  questionType: string;
  options?: Record<string, string>;
  correctAnswer: string;
  explanation: string;
  difficulty: string;
  savedAt: string;
  /** 本地作答记录（作答反馈由聊天侧判定后写入） */
  lastAnswer?: { answer: string; correct: boolean | null; at: string };
  /** S5-A：书签（可选，旧数据视为 false） */
  bookmarked?: boolean;
  /** S5-A：已掌握/已解决标记 */
  resolved?: boolean;
  /** S5-A：所属分类 id（null = 未分类） */
  categoryId?: string | null;
  /** S5-A：来源（聊天能力或显式演示数据） */
  source?: QuizSource;
}

/** 题库分类（对照参考 NotebookCategory 的本地形态） */
export interface QuizCategory {
  id: string;
  name: string;
  createdAt: string;
}

/** 笔记条目（研究报告等长文档的保存形态） */
export interface NotebookEntry {
  /** 复合身份：`${messageId}:${artifactId}` */
  id: string;
  messageId: string;
  artifactId: string;
  title: string;
  /** 条目类型：research_report 等（S5 业务页按类型筛选） */
  kind: string;
  content: string;
  savedAt: string;
}

function readList<T>(key: string): T[] {
  return readStrictList<T>(key);
}

function writeList<T>(key: string, list: T[]): void {
  writeStrictList(key, list);
}

// ===== 题库 =====

export function listQuizBank(): QuizBankEntry[] {
  return readList<QuizBankEntry>(QUIZ_BANK_KEY);
}

/** 保存一组题目（同 id 幂等：已存在的不覆盖，保留其作答记录与书签等标记） */
export function saveQuizEntries(
  entries: Omit<QuizBankEntry, 'savedAt'>[],
): { added: number; skipped: number } {
  const list = listQuizBank();
  const known = new Set(list.map((e) => e.id));
  let added = 0;
  let skipped = 0;
  for (const entry of entries) {
    if (known.has(entry.id)) {
      skipped += 1;
      continue;
    }
    known.add(entry.id);
    list.push({ ...entry, savedAt: new Date().toISOString() });
    added += 1;
  }
  writeList(QUIZ_BANK_KEY, list);
  return { added, skipped };
}

export function recordQuizAnswer(
  id: string,
  answer: { answer: string; correct: boolean | null },
): void {
  const list = listQuizBank();
  const idx = list.findIndex((e) => e.id === id);
  if (idx === -1) return;
  list[idx] = { ...list[idx]!, lastAnswer: { ...answer, at: new Date().toISOString() } };
  writeList(QUIZ_BANK_KEY, list);
}

/** 就地更新条目字段（S5-A：书签/已解决/分类等本地标记） */
export function updateQuizEntry(id: string, patch: Partial<QuizBankEntry>): QuizBankEntry | null {
  const list = listQuizBank();
  const idx = list.findIndex((e) => e.id === id);
  if (idx === -1) return null;
  list[idx] = { ...list[idx]!, ...patch };
  writeList(QUIZ_BANK_KEY, list);
  return list[idx]!;
}

export function removeQuizEntries(ids: string[]): number {
  const doomed = new Set(ids);
  const list = listQuizBank();
  const kept = list.filter((e) => !doomed.has(e.id));
  writeList(QUIZ_BANK_KEY, kept);
  return list.length - kept.length;
}

// ===== 题库分类 =====

export function listQuizCategories(): QuizCategory[] {
  return readList<QuizCategory>(QUIZ_CATEGORY_KEY);
}

export function addQuizCategory(name: string): QuizCategory | null {
  const trimmed = name.trim();
  if (!trimmed) return null;
  const list = listQuizCategories();
  if (list.some((c) => c.name === trimmed)) return null;
  const category: QuizCategory = {
    id: `cat-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    name: trimmed,
    createdAt: new Date().toISOString(),
  };
  list.push(category);
  writeList(QUIZ_CATEGORY_KEY, list);
  return category;
}

export function renameQuizCategory(id: string, name: string): boolean {
  const trimmed = name.trim();
  if (!trimmed) return false;
  const list = listQuizCategories();
  if (list.some((c) => c.id !== id && c.name === trimmed)) return false;
  const idx = list.findIndex((c) => c.id === id);
  if (idx === -1) return false;
  list[idx] = { ...list[idx]!, name: trimmed };
  writeList(QUIZ_CATEGORY_KEY, list);
  return true;
}

/** 删除分类：条目回到未分类（不删题目） */
export function removeQuizCategory(id: string): void {
  writeList(
    QUIZ_CATEGORY_KEY,
    listQuizCategories().filter((c) => c.id !== id),
  );
  const list = listQuizBank();
  let changed = false;
  for (const entry of list) {
    if (entry.categoryId === id) {
      entry.categoryId = null;
      changed = true;
    }
  }
  if (changed) writeList(QUIZ_BANK_KEY, list);
}

// ===== 演示题库（显式载入，幂等） =====

interface DemoQuizSpec {
  questionId: string;
  topic: string;
  question: string;
  questionType: string;
  options?: Record<string, string>;
  correctAnswer: string;
  explanation: string;
  difficulty: string;
  bookmarked?: boolean;
  resolved?: boolean;
  lastWrong?: boolean;
}

const DEMO_QUIZ_SPECS: DemoQuizSpec[] = [
  {
    questionId: 'demo-q-1',
    topic: '分数的加减法',
    question: '计算 1/4 + 2/4 的结果是多少？',
    questionType: '选择题',
    options: { A: '3/8', B: '3/4', C: '2/16', D: '1/2' },
    correctAnswer: 'B',
    explanation: '同分母分数相加，分母不变分子相加：1+2=3，得 3/4。',
    difficulty: '基础',
    bookmarked: true,
    lastWrong: true,
  },
  {
    questionId: 'demo-q-2',
    topic: '比喻与拟人',
    question: '"小草偷偷地从土里钻出来"用了什么修辞手法？',
    questionType: '选择题',
    options: { A: '比喻', B: '夸张', C: '拟人', D: '排比' },
    correctAnswer: 'C',
    explanation: '"偷偷地""钻"赋予小草人的动作与情态，是拟人。',
    difficulty: '基础',
  },
  {
    questionId: 'demo-q-3',
    topic: '光的传播',
    question: '光在真空中的传播速度约为多少？',
    questionType: '填空题',
    correctAnswer: '3×10^8 米/秒',
    explanation: '光速 c ≈ 3×10⁸ m/s，是自然界最快的速度。',
    difficulty: '进阶',
  },
  {
    questionId: 'demo-q-4',
    topic: '三角形的内角和',
    question: '任意三角形的三个内角之和等于多少度？',
    questionType: '填空题',
    correctAnswer: '180',
    explanation: '三角形内角和定理：内角和恒为 180°。',
    difficulty: '基础',
    resolved: true,
  },
  {
    questionId: 'demo-q-5',
    topic: '铸剑为犁——成语理解',
    question: '请解释成语"铸剑为犁"的含义，并说明它表达了怎样的愿望。',
    questionType: '简答题',
    correctAnswer: '把铸造剑的金属改铸为犁，意味着放下武器、发展生产，表达了对和平的向往。',
    explanation: '开放作答，围绕"停止战争、向往和平"即可。',
    difficulty: '进阶',
  },
];

/** 显式载入演示题库（幂等：重复点击不产生重复条目/不改已作答标记） */
export function loadDemoQuizEntries(): { added: number; skipped: number } {
  return saveQuizEntries(
    DEMO_QUIZ_SPECS.map((spec) => ({
      id: `demo-message:${spec.questionId}`,
      messageId: 'demo-message',
      questionId: spec.questionId,
      topic: spec.topic,
      question: spec.question,
      questionType: spec.questionType,
      options: spec.options,
      correctAnswer: spec.correctAnswer,
      explanation: spec.explanation,
      difficulty: spec.difficulty,
      source: 'demo' as const,
      bookmarked: spec.bookmarked ?? false,
      resolved: spec.resolved ?? false,
      categoryId: null,
      lastAnswer: spec.lastWrong
        ? { answer: '3/8', correct: false, at: new Date().toISOString() }
        : undefined,
    })),
  );
}

// ===== 笔记 =====

export function listNotebookEntries(): NotebookEntry[] {
  return readList<NotebookEntry>(NOTEBOOK_KEY);
}

export function saveNotebookEntry(entry: Omit<NotebookEntry, 'savedAt'>): 'added' | 'exists' {
  const list = listNotebookEntries();
  if (list.some((e) => e.id === entry.id)) return 'exists';
  list.push({ ...entry, savedAt: new Date().toISOString() });
  writeList(NOTEBOOK_KEY, list);
  return 'added';
}
