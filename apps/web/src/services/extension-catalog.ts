import type { TurnExtensionSnapshot } from '@/contracts/chat';

export type ExtensionKind = 'mcp' | 'skill';
export interface ExtensionEntry {
  id: string;
  kind: ExtensionKind;
  name: string;
  description: string;
  content: string;
  enabled: boolean;
}
const KEY = 'zqky.replica.extensions.v1';
const EVENT = 'zqky:extensions';
export function readExtensions(): ExtensionEntry[] {
  const raw = window.localStorage.getItem(KEY);
  if (!raw) return [];
  const parsed: unknown = JSON.parse(raw);
  if (
    !Array.isArray(parsed) ||
    !parsed.every(
      (item) =>
        item &&
        typeof item.id === 'string' &&
        (item.kind === 'mcp' || item.kind === 'skill') &&
        typeof item.name === 'string' &&
        typeof item.description === 'string' &&
        typeof item.content === 'string' &&
        typeof item.enabled === 'boolean',
    )
  )
    throw new Error('扩展目录格式不兼容，原数据已保留。');
  return parsed;
}
export function saveExtension(entry: ExtensionEntry) {
  const next = readExtensions().filter((item) => item.id !== entry.id);
  if (!entry.name.trim()) throw new Error('请输入名称。');
  if (next.some((item) => item.kind === entry.kind && item.name === entry.name))
    throw new Error('名称已存在。');
  window.localStorage.setItem(KEY, JSON.stringify([...next, entry]));
  window.dispatchEvent(new Event(EVENT));
}
export function removeExtension(id: string) {
  window.localStorage.setItem(
    KEY,
    JSON.stringify(readExtensions().filter((item) => item.id !== id)),
  );
  window.dispatchEvent(new Event(EVENT));
}
export function subscribeExtensions(listener: () => void) {
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

/**
 * 技能是否真的会生效：说明正文非空才会作为系统上下文发送。
 * 空正文的技能只是目录条目，界面必须如实说明，不显示"已启用"以外的成效暗示。
 */
export function skillTakesEffect(entry: ExtensionEntry): boolean {
  return entry.kind === 'skill' && entry.content.trim() !== '';
}

/**
 * 发送时冻结的技能快照：只取「已启用 + 说明正文非空」的技能。
 * 无有效技能时返回 undefined——调用方据此不携带 extensions 字段，保持旧请求形态。
 */
export function buildTurnExtensionSnapshot(): TurnExtensionSnapshot | undefined {
  const skills = readExtensions()
    .filter((item) => item.kind === 'skill' && item.enabled && skillTakesEffect(item))
    .map((item) => ({
      id: item.id,
      name: item.name,
      description: item.description,
      content: item.content,
    }));
  if (!skills.length) return undefined;
  // MCP 尚无执行通道（后端无工具循环），因此不进入快照，避免展示"本轮已载入"的假状态
  return { mcps: [], skills };
}

/** 内置教学技能预置：只由用户在设置中显式载入，不自动写入目录 */
export const BUILTIN_SKILLS = [
  {
    name: '教案规范',
    description: '按备课模板的栏目与顺序输出教案，可直接落到教案工作台',
    content: [
      '撰写教案时，严格按以下栏目组织，栏目名称与顺序不增删、不改写。',
      '',
      '1. 课题：只写课题本身。',
      '2. 总课时 / 本节课：用阿拉伯数字，如"总课时 2、本节课 1"。',
      '3. 课型：只能取 新课 / 复习课 / 试题讲评课 / 实验课 / 其它 中的一项或多项。',
      '4. 核心素养目标：分条列出，每条写成"素养维度：具体表现"，覆盖本学科核心素养的 2—3 个维度，不用"了解""掌握"等不可观测的笼统动词单独成句。',
      '5. 教学重、难点：分两行，分别以"教学重点："和"教学难点："开头；重点来自课标要求的核心内容，难点来自学生的真实认知障碍，不把考试重点直接当作难点。',
      '6. 教学设计：写清教学主线、主要方法与板书设计。',
      '7. 教学过程：按环节列表输出，每个环节写"环节名称 · 时长"，正文分别写教师活动、学生活动与设计意图。',
      '8. 练习与作业：区分"课堂练习"与"课后作业"，标明题量与大致用时。',
      '9. 教学反思：未实际授课时不编造反思，留空或写"待授课后补充"。',
      '',
      '通用要求：',
      '- 每条核心素养目标都要能在教学过程中找到对应环节，两者不对应就是空话，需重写。',
      '- 课时分配与各环节时长之和必须与"总课时"一致。',
      '- 内容必须贴合给定课题、教材版本与学情。缺少教材版本、课时安排或学生基础时先追问，不自行假设。',
      '- 不套用与学科无关的环节名称，不堆砌形容词。',
    ].join('\n'),
  },
  {
    name: '课标对齐',
    description: '规范教学目标、重难点与评价任务的表述方式',
    content: [
      '撰写教学目标、重难点与评价任务时，按以下规范表述。',
      '',
      '- 目标结构用"行为动词 + 学习内容 + 达成程度"。行为动词取可观察的课标用词，如说明、分析、归纳、比较、绘制、解释、论证、设计；不要单独使用"了解""掌握""体会"这类无法观测的动词。',
      '- 每条目标注明对应的核心素养维度；涉及水平层次时使用"学业质量水平"的表述。',
      '- 重难点与目标一一对应，写清"为什么是重点"和"学生卡在哪里"。',
      '- 评价任务与目标对应，写出可观察的达成表现，如"能独立完成…""能说明…的理由"。',
      '- 需要引用课标条目编号、教材页码或学业质量原文时，只能来自用户提供或检索到的材料；材料中没有就标注"待核对"，绝不凭印象编写条目编号、原文或页码。',
      '- 区分"课程标准要求"与"学校/教研组惯例"：前者可溯源自课标，后者要标明是惯例。',
    ].join('\n'),
  },
  {
    name: '命题规范',
    description: '统一题干、答案、解析与赋分的输出格式',
    content: [
      '命制题目时，按以下格式逐题输出。',
      '',
      '每道题包含五项，缺项即为不合格：',
      '1. 题干：情境完整、指向明确，不出现"以上都对"这类无效选项。',
      '2. 题型与赋分：标明题型（选择题/概念题/填空题/简答题/写作题）与分值。',
      '3. 难度标注：按"容易/中等/较难"标注，并说明判断依据（如需要几步推理、是否需要跨知识点综合）。',
      '4. 答案：明确唯一，主观题给出评分要点与分层给分说明。',
      '5. 解析：分"思路"和"易错点"两段，写清关键步骤的推理依据，不写"显然""易得"。',
      '',
      '通用要求：',
      '- 涉及数据、史实、教材原文、公式常数时，只能使用用户提供或检索到的材料；材料中没有就标注"待核对"，不编造实验数据、文献或年份。',
      '- 组卷时按题型、难度、分值给出分布说明，并核对总分与各题分值之和一致。',
      '- 不出现同一份卷子内部答案互相矛盾或选项重复的题目。',
      '- 仿照既有试卷出题时，只仿结构、题型与难度分布，不照抄原题题干。',
    ].join('\n'),
  },
] as const;

/**
 * 载入内置教学技能（幂等）：跳过同名条目，不覆盖、不改动用户已有配置。
 * 返回新增与跳过数量，供界面如实回报结果。
 */
export function seedBuiltinSkills(): { added: number; skipped: number } {
  const existing = readExtensions();
  const names = new Set(existing.filter((item) => item.kind === 'skill').map((item) => item.name));
  const added = BUILTIN_SKILLS.filter((preset) => !names.has(preset.name)).map((preset) => ({
    id: crypto.randomUUID(),
    kind: 'skill' as const,
    name: preset.name,
    description: preset.description,
    content: preset.content,
    enabled: true,
  }));
  if (added.length) {
    window.localStorage.setItem(KEY, JSON.stringify([...existing, ...added]));
    window.dispatchEvent(new Event(EVENT));
  }
  return { added: added.length, skipped: BUILTIN_SKILLS.length - added.length };
}
