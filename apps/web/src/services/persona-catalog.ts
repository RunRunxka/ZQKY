'use client';
/**
 * 角色人设目录（S2 输入区 + S5-A /space/personas 业务页共用）。
 *
 * 目标项目尚无真实 persona 服务，这里提供与 extension-catalog 同构的本地目录：
 * 显式"载入演示数据"入口、localStorage 持久化、跨组件订阅。数据仅作演示，
 * 条目说明带"演示数据"标识，不冒充真实角色库。
 *
 * S5-A 扩展：content（markdown 正文，可选）、source（demo/user）、createdAt，
 * 以及业务页需要的增删改操作。旧数据缺省字段向后兼容。
 */
export interface PersonaEntry {
  id: string;
  name: string;
  description: string;
  /** markdown 正文（查看/编辑弹层使用；旧数据缺省为空） */
  content?: string;
  /** 来源：demo=显式载入的演示数据；user=用户创建 */
  source?: 'demo' | 'user';
  createdAt?: string;
}
const KEY = 'zqky.replica.personas.v1';
const EVENT = 'zqky:personas';

export const DEMO_PERSONAS: PersonaEntry[] = [
  {
    id: 'demo-persona-patient',
    name: '耐心的小学老师',
    description: '用生活例子拆解概念，多鼓励、少术语（演示数据）。',
    content: '# 耐心的小学老师\n\n- 语气亲切，多用生活化的例子。\n- 每个概念先给一个具体场景，再给定义。\n- 学生出错时先肯定思路，再指出偏差。',
    source: 'demo',
  },
  {
    id: 'demo-persona-rigorous',
    name: '严谨的高中老师',
    description: '强调推理步骤与规范表达，逐步板书式讲解（演示数据）。',
    content: '# 严谨的高中老师\n\n- 推理逐步展开，每一步写出依据。\n- 强调规范表达与完整过程。\n- 结尾给出一道同型变式题。',
    source: 'demo',
  },
  {
    id: 'demo-persona-socratic',
    name: '启发式助教',
    description: '先反问再引导，不直接给答案（演示数据）。',
    content: '# 启发式助教\n\n- 先用反问确认学生卡点。\n- 给提示不给答案，直到学生自己迈出一步。\n- 最后让学生复述思路。',
    source: 'demo',
  },
];

function validate(parsed: unknown): PersonaEntry[] {
  if (
    !Array.isArray(parsed) ||
    !parsed.every(
      (item) =>
        item &&
        typeof item.id === 'string' &&
        typeof item.name === 'string' &&
        typeof item.description === 'string',
    )
  )
    throw new Error('角色目录格式不兼容，原数据已保留。');
  return parsed as PersonaEntry[];
}

export function readPersonas(): PersonaEntry[] {
  const raw = window.localStorage.getItem(KEY);
  if (!raw) return [];
  return validate(JSON.parse(raw));
}

function writePersonas(list: PersonaEntry[]): void {
  window.localStorage.setItem(KEY, JSON.stringify(list));
  window.dispatchEvent(new Event(EVENT));
}

export function loadDemoPersonas() {
  const existing = readPersonas();
  const merged = [...existing];
  for (const demo of DEMO_PERSONAS) {
    if (!merged.some((item) => item.id === demo.id)) merged.push(demo);
  }
  writePersonas(merged);
}

export function subscribePersonas(listener: () => void) {
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

// ===== S5-A 业务页操作 =====

export class PersonaValidationError extends Error {}

function assertValidName(name: string, excludeId?: string): string {
  const trimmed = name.trim();
  if (!trimmed) throw new PersonaValidationError('名称不能为空。');
  if (trimmed.length > 50) throw new PersonaValidationError('名称过长（不超过 50 字）。');
  const clash = readPersonas().some((p) => p.id !== excludeId && p.name === trimmed);
  if (clash) throw new PersonaValidationError('已存在同名角色，请换一个名称。');
  return trimmed;
}

/** 新建角色（本地目录，无文件系统，因此不做参考的 slug 文件名校验，仅查重） */
export function createPersona(input: {
  name: string;
  description: string;
  content?: string;
}): PersonaEntry {
  const name = assertValidName(input.name);
  const entry: PersonaEntry = {
    id: `persona-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    name,
    description: input.description.trim(),
    content: input.content?.trim() || undefined,
    source: 'user',
    createdAt: new Date().toISOString(),
  };
  writePersonas([...readPersonas(), entry]);
  return entry;
}

/** 更新角色（rename 通过 patch.name；演示条目同样可编辑——本地目录无管理员锁） */
export function updatePersona(
  id: string,
  patch: { name?: string; description?: string; content?: string },
): PersonaEntry {
  const list = readPersonas();
  const idx = list.findIndex((p) => p.id === id);
  if (idx === -1) throw new PersonaValidationError('角色不存在或已被删除。');
  if (patch.name !== undefined) {
    const name = assertValidName(patch.name, id);
    list[idx] = { ...list[idx]!, name };
  }
  if (patch.description !== undefined) list[idx] = { ...list[idx]!, description: patch.description.trim() };
  if (patch.content !== undefined)
    list[idx] = { ...list[idx]!, content: patch.content.trim() || undefined };
  writePersonas(list);
  return list[idx]!;
}

export function deletePersona(id: string): boolean {
  const list = readPersonas();
  const kept = list.filter((p) => p.id !== id);
  if (kept.length === list.length) return false;
  writePersonas(kept);
  return true;
}
