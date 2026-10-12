/**
 * 教学目标（知识 / 能力 / 思政）与冻结契约 `coreCompetencies` 的编解码（R7-FE）。
 *
 * 冻结契约里教学目标只有一个字符串字段，而用户模板第 3 页起的目标表是
 * 「教学目标」合并单元格 + **知识/能力/思政 三行 vMerge**。工作台用可逆的行编码：
 *
 * ```
 * 知识：……
 * 能力：……
 * 思政：……
 * ```
 *
 * - 解码：识别 `知识/能力/思政` 标签行（容忍 `【知识目标】`、`**知识**：`、`1. 知识：` 等写法），
 *   后续无标签续行归入当前行；标签行之前的无标签文本进 `other`（**永不丢弃**）；
 * - 编码：按行输出标签行，再输出 `other`；
 * - 完全没有标签的旧文本 `structured=false`，编辑器退回「整体文本」模式，不猜测、不重排版。
 */
import { emptyLessonData } from './lesson-data';

export interface ObjectiveRowKey {
  key: 'knowledge' | 'ability' | 'ideological';
  label: string;
}

export const OBJECTIVE_ROWS: readonly ObjectiveRowKey[] = [
  { key: 'knowledge', label: '知识' },
  { key: 'ability', label: '能力' },
  { key: 'ideological', label: '思政' },
] as const;

export interface ObjectivesView {
  /** 三行内容（未识别到的行为空串）。 */
  rows: { knowledge: string; ability: string; ideological: string };
  /** 标签行之外保留的原文行。 */
  other: string[];
  /** 至少识别到一个标签行。 */
  structured: boolean;
}

const LABEL_NAMES: Record<string, 'knowledge' | 'ability' | 'ideological'> = {
  知识: 'knowledge',
  能力: 'ability',
  思政: 'ideological',
};

/** 行首噪声（Markdown 粗体、编号、方括号、项目符号）先剥掉再识别标签。 */
const LABEL_PATTERN = /^\s*(?:[#>*\-–—•·]+\s*)*(?:\d+\s*[.、)）]?\s*)?(?:【|\[|（|\()?\s*(知识|能力|思政)\s*(?:目标|素养)?\s*(?:】|\]|）|\))?\s*(?:[#>*\-–—•·]+\s*)?[：:、.．]?\s*(.*)$/;

/** 教学重点/难点行：不属于「知识/能力/思政」三行，识别出来单独保留（见 readKeyPoints）。 */
const KEYPOINTS_LINE = /^\s*(?:[#>*\-–—•·]+\s*)*(?:\d+\s*[.、)）]?\s*)?(?:【|\[|（|\()?\s*教学(?:重点|难点|重、难点|重难点)\s*(?:】|\]|）|\))?/;

/** 该行是否是教学重点/难点标签行（供生成流解析器把两类内容分开）。 */
export function isKeyPointsLine(line: string): boolean {
  return KEYPOINTS_LINE.test(line.trim());
}

export function readObjectives(coreCompetencies: string): ObjectivesView {
  const view: ObjectivesView = {
    rows: { knowledge: '', ability: '', ideological: '' },
    other: [],
    structured: false,
  };
  let current: 'knowledge' | 'ability' | 'ideological' | null = null;
  for (const rawLine of (coreCompetencies ?? '').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    if (KEYPOINTS_LINE.test(line)) {
      // 重点/难点混在同一字段时：结束当前行，原文进 other（不丢字，也不粘进思政行）。
      current = null;
      view.other.push(line);
      continue;
    }
    const match = LABEL_PATTERN.exec(line);
    const key = match ? LABEL_NAMES[match[1]] : undefined;
    if (key) {
      view.structured = true;
      current = key;
      const value = (match?.[2] ?? '').trim();
      if (value) {
        view.rows[key] = view.rows[key] ? `${view.rows[key]}\n${value}` : value;
      }
      continue;
    }
    if (current) {
      view.rows[current] = view.rows[current] ? `${view.rows[current]}\n${line}` : line;
    } else {
      view.other.push(line);
    }
  }
  // 空内容视为「可按三行编辑」：新教案默认给出知识/能力/思政三个输入框，
  // 只有确实存在无法归类的旧文本时才退回整体文本模式。
  if (!(coreCompetencies ?? '').trim()) view.structured = true;
  return view;
}

export function writeObjectives(view: ObjectivesView): string {
  const lines: string[] = [];
  for (const row of OBJECTIVE_ROWS) {
    const value = view.rows[row.key].trim();
    if (value) lines.push(`${row.label}：${value}`);
  }
  for (const line of view.other) {
    if (line.trim()) lines.push(line);
  }
  return lines.join('\n');
}

export function emptyObjectivesView(): ObjectivesView {
  return { rows: { knowledge: '', ability: '', ideological: '' }, other: [], structured: true };
}

/* ------------------------------------------------------------------ 教学重点 / 难点 */

export interface KeyPointsView {
  key: string;
  difficulty: string;
  other: string[];
}

const KEY_LABEL = /^\s*(?:[#>*\-–—•·]+\s*)?(?:\d+\s*[.、)）]?\s*)?\s*(?:【|\[|（|\()?\s*教学(重点|难点|重、难点|重难点)\s*(?:】|\]|）|\))?\s*[：:、.．]?\s*(.*)$/;

export function readKeyPoints(keyPoints: string): KeyPointsView {
  const view: KeyPointsView = { key: '', difficulty: '', other: [] };
  let current: 'key' | 'difficulty' | null = null;
  for (const rawLine of (keyPoints ?? '').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const match = KEY_LABEL.exec(line);
    if (match) {
      current = match[1] === '重点' ? 'key' : 'difficulty';
      const value = (match[2] ?? '').trim();
      if (value) view[current] = view[current] ? `${view[current]}\n${value}` : value;
      continue;
    }
    if (current) {
      view[current] = view[current] ? `${view[current]}\n${line}` : line;
    } else {
      view.other.push(line);
    }
  }
  return view;
}

export function writeKeyPoints(view: KeyPointsView): string {
  const lines: string[] = [];
  if (view.key.trim()) lines.push(`教学重点：${view.key.trim()}`);
  if (view.difficulty.trim()) lines.push(`教学难点：${view.difficulty.trim()}`);
  for (const line of view.other) if (line.trim()) lines.push(line);
  return lines.join('\n');
}

/** 空教案的目标行初始视图（新建时即三行结构化）。 */
export function initialObjectives() {
  const data = emptyLessonData();
  return readObjectives(data.coreCompetencies);
}
