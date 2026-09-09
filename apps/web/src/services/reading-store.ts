/**
 * 沉浸阅读本地仓储（S5-D）。
 * 参考材料解析/切分/转录全部走服务端（PDF/EPUB/媒体/网页抓取）；目标项目无后端，
 * 此处仅登记文本类材料（粘贴/新建/演示），阅读器为文本形态（标题层级+段落定位）。
 * 批注按 quote 锚定（对照参考 TextUnitView 的 TextQuoteSelector 思路，无几何 rect）。
 * 伴生 AI 为本地确定性模拟回复（显式【模拟回复】），会话本地持久化；
 * "发到笔记本"写入 notebook-store（真实跨页联动）；整理笔记为本地模板聚合。
 */
import { createNotebookRecord } from './notebook-store';

export type ReadingSourceKind = 'text' | 'pdf' | 'epub' | 'webpage' | 'video' | 'audio';
export type ReadingAnnotationKind = 'highlight' | 'note';
/** 材料解析状态（对照参考 queued/processing/ready）：真实解析未接入，非文本为显式模拟流程 */
export type ReadingMaterialStatus = 'ready' | 'queued' | 'processing' | 'failed';

export interface ReadingMaterial {
  id: string;
  title: string;
  filename: string | null;
  sourceKind: ReadingSourceKind;
  sourceUrl: string | null;
  /** 正文文本（# 开头行按标题渲染）。非文本材料在模拟解析完成后填充（结构化样例，显式标注） */
  text: string;
  charCount: number;
  sizeBytes: number;
  /** 阅读位置（0-100，文本滚动百分比；对照参考 ReadingPosition 的本地形态） */
  positionPct: number;
  /** 解析状态；旧数据缺省视为 ready（读取时归一化） */
  status?: ReadingMaterialStatus;
  /** 解析器标识（对照参考 extractor：youtube-transcript / pdf-text 等，显式模拟） */
  extractor?: string | null;
  /** 解析说明（失败原因/取消/模拟标注） */
  statusNote?: string | null;
  /** 归属工作区 id 列表（未分配为空） */
  workspaceIds: string[];
  createdAt: string;
  updatedAt: string;
}

/** 批注精确定位段：块定位（p-<行>/h-<行>）+ 块内字符区间（对照参考 TextPositionSelector 的块级形态） */
export interface ReadingAnnotationSegment {
  locator: string;
  start: number;
  end: number;
}

export interface ReadingAnnotation {
  annotationId: string;
  materialId: string;
  kind: ReadingAnnotationKind;
  color: 'yellow' | 'green' | 'blue' | 'pink' | 'purple';
  quote: string;
  /**
   * 精确定位段（新批注必填；可跨块）。旧 quote-only 历史数据为空：
   * 渲染时按全文唯一匹配回退，多处命中视为歧义、显式提示，不猜位置。
   */
  segments?: ReadingAnnotationSegment[];
  note: string;
  createdAt: string;
}

export interface ReadingBookmark {
  bookmarkId: string;
  materialId: string;
  /** 段落定位 loc-<行索引> */
  locator: string;
  label: string;
  createdAt: string;
}

export interface ReadingMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  /** 问 AI 时携带的选中文本 */
  quote?: string;
  at: string;
}

export interface ReadingSession {
  id: string;
  workspaceId: string;
  title: string;
  activeMaterialId: string | null;
  messages: ReadingMessage[];
  /** 未发送草稿（按会话归属，切会话不串） */
  draft?: string;
  /** 草稿携带的选区引用（与草稿同会话归属） */
  draftQuote?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ReadingWorkspaceTab {
  materialId: string;
  addedAt: string;
}

export interface ReadingWorkspace {
  id: string;
  title: string;
  description: string;
  activeMaterialId: string | null;
  tabs: ReadingWorkspaceTab[];
  createdAt: string;
  updatedAt: string;
}

const MATERIALS_KEY = 'zhiqikeyuan:reading-materials';
const WORKSPACES_KEY = 'zhiqikeyuan:reading-workspaces';
const ANNOTATIONS_KEY = 'zhiqikeyuan:reading-annotations';
const BOOKMARKS_KEY = 'zhiqikeyuan:reading-bookmarks';
const SESSIONS_KEY = 'zhiqikeyuan:reading-sessions';
const EVENT = 'zqky:reading';

export class ReadingValidationError extends Error {}
/** 存储层错误：损坏/格式异常/写入被拒。抛出时原数据未被修改或已回滚。 */
export class ReadingStorageError extends Error {}

function uid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * 严格读取（R27）：键不存在才返回空数组；JSON 损坏、格式异常、存储拒绝一律抛出
 * ReadingStorageError，绝不把损坏库当空库，防止下一次写入覆盖可恢复数据。
 */
function readList<T>(key: string): T[] {
  if (typeof window === 'undefined') return [];
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(key);
  } catch (cause) {
    throw new ReadingStorageError(`本地阅读数据（${key}）读取被拒绝，原数据未修改。`, { cause });
  }
  if (raw === null) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new ReadingStorageError(`本地阅读数据（${key}）已损坏，无法安全解析；为保护原数据未做修改。`);
  }
  if (!Array.isArray(parsed)) {
    throw new ReadingStorageError(`本地阅读数据（${key}）格式异常（应为数组）；为保护原数据未做修改。`);
  }
  return parsed as T[];
}

function readRaw(key: string): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(key);
}

function writeRaw(key: string, raw: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(key, raw);
}

/**
 * 多键原子写入（R27）：先严格校验全部键（损坏即抛错、不进入写入），再逐键写入；
 * 任一写入失败回滚本批已写键并抛错，多键操作中途失败不再留下半套数据。
 */
function commitLists(entries: ReadonlyArray<readonly [string, unknown]>): void {
  if (typeof window === 'undefined') return;
  for (const [key] of entries) readList(key);
  const originals = entries.map(([key]) => [key, readRaw(key)] as const);
  const written: string[] = [];
  try {
    for (const [key, value] of entries) {
      writeRaw(key, JSON.stringify(value));
      written.push(key);
    }
  } catch (cause) {
    for (const key of written) {
      const original = originals.find(([k]) => k === key)?.[1] ?? null;
      try {
        if (original === null) window.localStorage.removeItem(key);
        else window.localStorage.setItem(key, original);
      } catch {
        // 回滚失败时保留现场，仍抛出原始错误
      }
    }
    throw new ReadingStorageError('写入本地阅读数据失败（存储可能已满）；本次修改已回滚，原数据保留。', { cause });
  }
  notify();
}

function writeList<T>(key: string, list: T[]): void {
  commitLists([[key, list]]);
}

function notify(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(EVENT));
}

export function subscribeReading(listener: () => void): () => void {
  const storage = (event: StorageEvent) => {
    if (event.key === EVENT || event.key === null || event.key?.startsWith('zhiqikeyuan:reading-')) {
      listener();
    }
  };
  window.addEventListener(EVENT, listener);
  window.addEventListener('storage', storage);
  return () => {
    window.removeEventListener(EVENT, listener);
    window.removeEventListener('storage', storage);
  };
}

// ===== 材料 =====

/** 读取归一化：旧数据无 status 视为 ready（缺字段不破坏既有库） */
export function readMaterials(): ReadingMaterial[] {
  return readList<ReadingMaterial>(MATERIALS_KEY)
    .filter((item) => item && item.id && typeof item.text === 'string')
    .map((item) => ({ ...item, status: item.status ?? 'ready' }));
}

export function createMaterial(input: {
  title: string;
  /** 文本材料必填；非文本材料允许为空（等模拟解析填充） */
  text?: string;
  filename?: string;
  /** 默认 text；非文本走显式模拟解析流程 */
  sourceKind?: ReadingSourceKind;
  sourceUrl?: string | null;
  /** 非文本导入的初始状态（默认 queued） */
  status?: ReadingMaterialStatus;
  extractor?: string | null;
}): ReadingMaterial {
  const title = input.title.trim();
  const text = (input.text ?? '').replace(/\r\n/g, '\n');
  const sourceKind = input.sourceKind ?? 'text';
  if (!title) throw new ReadingValidationError('材料标题不能为空。');
  if (sourceKind === 'text' && !text.trim())
    throw new ReadingValidationError('材料正文不能为空（参考的 PDF/网页解析未接入，仅登记文本材料）。');
  if (sourceKind !== 'text' && !input.filename?.trim())
    throw new ReadingValidationError('模拟导入需要提供文件名（解析为本地模拟，不读取真实文件）。');
  const now = new Date().toISOString();
  const material: ReadingMaterial = {
    id: uid('mat'),
    title,
    filename: input.filename?.trim() || null,
    sourceKind,
    sourceUrl: input.sourceUrl?.trim() || null,
    text,
    charCount: text.length,
    sizeBytes: text.length > 0 ? new Blob([text]).size : 0,
    positionPct: 0,
    status: input.status ?? (sourceKind === 'text' ? 'ready' : 'queued'),
    extractor: input.extractor ?? null,
    statusNote: null,
    workspaceIds: [],
    createdAt: now,
    updatedAt: now,
  };
  writeList(MATERIALS_KEY, [...readMaterials(), material]);
  return material;
}

/** 更新解析状态（供模拟解析流程推进；写前经严格校验） */
export function updateMaterialStatus(
  materialId: string,
  status: ReadingMaterialStatus,
  statusNote?: string | null,
): ReadingMaterial | null {
  const list = readMaterials();
  const idx = list.findIndex((item) => item.id === materialId);
  if (idx === -1) return null;
  list[idx] = {
    ...list[idx]!,
    status,
    statusNote: statusNote ?? null,
    updatedAt: new Date().toISOString(),
  };
  writeList(MATERIALS_KEY, list);
  return list[idx]!;
}

/** 模拟解析完成：写入结构化样例文本并置为 ready */
export function completeMaterialIngest(materialId: string, text: string, statusNote?: string | null): ReadingMaterial | null {
  const list = readMaterials();
  const idx = list.findIndex((item) => item.id === materialId);
  if (idx === -1) return null;
  const normalized = text.replace(/\r\n/g, '\n');
  list[idx] = {
    ...list[idx]!,
    text: normalized,
    charCount: normalized.length,
    sizeBytes: new Blob([normalized]).size,
    status: 'ready',
    statusNote: statusNote ?? null,
    updatedAt: new Date().toISOString(),
  };
  writeList(MATERIALS_KEY, list);
  return list[idx]!;
}

export function deleteMaterial(materialId: string): boolean {
  const materials = readMaterials();
  const kept = materials.filter((item) => item.id !== materialId);
  if (kept.length === materials.length) return false;
  // 级联清理批注/书签与工作区引用（单批原子提交，失败整体回滚）
  commitLists([
    [MATERIALS_KEY, kept],
    [ANNOTATIONS_KEY, readList<ReadingAnnotation>(ANNOTATIONS_KEY).filter((item) => item.materialId !== materialId)],
    [BOOKMARKS_KEY, readList<ReadingBookmark>(BOOKMARKS_KEY).filter((item) => item.materialId !== materialId)],
    [
      WORKSPACES_KEY,
      readList<ReadingWorkspace>(WORKSPACES_KEY).map((ws) => {
        const tabs = ws.tabs.filter((tab) => tab.materialId !== materialId);
        return {
          ...ws,
          tabs,
          activeMaterialId:
            ws.activeMaterialId === materialId ? tabs[0]?.materialId ?? null : ws.activeMaterialId,
        };
      }),
    ],
  ]);
  return true;
}

export function saveReadingPosition(materialId: string, positionPct: number): void {
  const list = readMaterials();
  const idx = list.findIndex((item) => item.id === materialId);
  if (idx === -1) return;
  const clamped = Math.max(0, Math.min(100, Math.round(positionPct)));
  if (list[idx]!.positionPct === clamped) return;
  list[idx] = { ...list[idx]!, positionPct: clamped, updatedAt: new Date().toISOString() };
  writeList(MATERIALS_KEY, list);
}

// ===== 工作区 =====

export function readWorkspaces(): ReadingWorkspace[] {
  return readList<ReadingWorkspace>(WORKSPACES_KEY).filter((item) => item && item.id);
}

export function createWorkspace(title: string, description = ''): ReadingWorkspace {
  const trimmed = title.trim();
  if (!trimmed) throw new ReadingValidationError('集合名称不能为空。');
  const list = readWorkspaces();
  if (list.some((item) => item.title === trimmed))
    throw new ReadingValidationError('已存在同名阅读集合，请换一个名称。');
  const now = new Date().toISOString();
  const workspace: ReadingWorkspace = {
    id: uid('rws'),
    title: trimmed,
    description: description.trim(),
    activeMaterialId: null,
    tabs: [],
    createdAt: now,
    updatedAt: now,
  };
  writeList(WORKSPACES_KEY, [...list, workspace]);
  return workspace;
}

export function renameWorkspace(workspaceId: string, title: string): ReadingWorkspace | null {
  const list = readWorkspaces();
  const idx = list.findIndex((item) => item.id === workspaceId);
  if (idx === -1) return null;
  const trimmed = title.trim();
  if (!trimmed) throw new ReadingValidationError('集合名称不能为空。');
  list[idx] = { ...list[idx]!, title: trimmed, updatedAt: new Date().toISOString() };
  writeList(WORKSPACES_KEY, list);
  return list[idx]!;
}

export function deleteWorkspace(workspaceId: string): boolean {
  const list = readWorkspaces();
  const kept = list.filter((item) => item.id !== workspaceId);
  if (kept.length === list.length) return false;
  // 材料保留在库中，仅解除归属；会话一并删除（单批原子提交）
  commitLists([
    [WORKSPACES_KEY, kept],
    [
      MATERIALS_KEY,
      readMaterials().map((item) =>
        item.workspaceIds.includes(workspaceId)
          ? { ...item, workspaceIds: item.workspaceIds.filter((id) => id !== workspaceId), updatedAt: new Date().toISOString() }
          : item,
      ),
    ],
    [SESSIONS_KEY, readList<ReadingSession>(SESSIONS_KEY).filter((item) => item.workspaceId !== workspaceId)],
  ]);
  return true;
}

export function addMaterialToWorkspace(workspaceId: string, materialId: string, activate = true): ReadingWorkspace | null {
  const list = readWorkspaces();
  const idx = list.findIndex((item) => item.id === workspaceId);
  if (idx === -1) return null;
  const ws = list[idx]!;
  if (ws.tabs.some((tab) => tab.materialId === materialId)) return ws;
  const material = readMaterials().find((item) => item.id === materialId);
  if (!material) throw new ReadingValidationError('材料不存在或已被删除。');
  list[idx] = {
    ...ws,
    tabs: [...ws.tabs, { materialId, addedAt: new Date().toISOString() }],
    activeMaterialId: activate ? materialId : ws.activeMaterialId,
    updatedAt: new Date().toISOString(),
  };
  writeList(WORKSPACES_KEY, list);
  const mlist = readMaterials();
  const mIdx = mlist.findIndex((item) => item.id === materialId);
  if (mIdx !== -1 && !mlist[mIdx]!.workspaceIds.includes(workspaceId)) {
    mlist[mIdx] = { ...mlist[mIdx]!, workspaceIds: [...mlist[mIdx]!.workspaceIds, workspaceId] };
    writeList(MATERIALS_KEY, mlist);
  }
  return list[idx]!;
}

export function activateMaterial(workspaceId: string, materialId: string): ReadingWorkspace | null {
  const list = readWorkspaces();
  const idx = list.findIndex((item) => item.id === workspaceId);
  if (idx === -1) return null;
  if (!list[idx]!.tabs.some((tab) => tab.materialId === materialId)) return list[idx]!;
  list[idx] = { ...list[idx]!, activeMaterialId: materialId, updatedAt: new Date().toISOString() };
  writeList(WORKSPACES_KEY, list);
  return list[idx]!;
}

export function removeMaterialFromWorkspace(workspaceId: string, materialId: string): ReadingWorkspace | null {
  const list = readWorkspaces();
  const idx = list.findIndex((item) => item.id === workspaceId);
  if (idx === -1) return null;
  const ws = list[idx]!;
  const tabs = ws.tabs.filter((tab) => tab.materialId !== materialId);
  list[idx] = {
    ...ws,
    tabs,
    activeMaterialId: ws.activeMaterialId === materialId ? tabs[0]?.materialId ?? null : ws.activeMaterialId,
    updatedAt: new Date().toISOString(),
  };
  writeList(WORKSPACES_KEY, list);
  const mlist = readMaterials();
  const mIdx = mlist.findIndex((item) => item.id === materialId);
  if (mIdx !== -1) {
    mlist[mIdx] = { ...mlist[mIdx]!, workspaceIds: mlist[mIdx]!.workspaceIds.filter((id) => id !== workspaceId) };
    writeList(MATERIALS_KEY, mlist);
  }
  return list[idx]!;
}

// ===== 批注与书签 =====

export function readAnnotations(materialId?: string): ReadingAnnotation[] {
  const list = readList<ReadingAnnotation>(ANNOTATIONS_KEY).filter((item) => item && item.annotationId);
  return materialId ? list.filter((item) => item.materialId === materialId) : list;
}

export function addAnnotation(input: {
  materialId: string;
  kind: ReadingAnnotationKind;
  color?: ReadingAnnotation['color'];
  quote: string;
  /** 精确定位段（选区时携带；缺失则按 quote 唯一匹配回退） */
  segments?: ReadingAnnotationSegment[];
  note?: string;
}): ReadingAnnotation {
  const quote = input.quote.trim();
  if (!quote) throw new ReadingValidationError('批注引用文本不能为空（请先在正文中选择文字）。');
  const segments = (input.segments ?? []).filter(
    (segment) => segment && typeof segment.locator === 'string' && segment.locator,
  );
  const annotation: ReadingAnnotation = {
    annotationId: uid('ann'),
    materialId: input.materialId,
    kind: input.kind,
    color: input.color ?? 'yellow',
    quote,
    ...(segments.length > 0 ? { segments } : {}),
    note: input.note?.trim() ?? '',
    createdAt: new Date().toISOString(),
  };
  writeList(ANNOTATIONS_KEY, [...readAnnotations(), annotation]);
  return annotation;
}

export function deleteAnnotation(annotationId: string): boolean {
  const list = readAnnotations();
  const kept = list.filter((item) => item.annotationId !== annotationId);
  if (kept.length === list.length) return false;
  writeList(ANNOTATIONS_KEY, kept);
  return true;
}

export function readBookmarks(materialId?: string): ReadingBookmark[] {
  const list = readList<ReadingBookmark>(BOOKMARKS_KEY).filter((item) => item && item.bookmarkId);
  return materialId ? list.filter((item) => item.materialId === materialId) : list;
}

export function addBookmark(materialId: string, locator: string, label: string): ReadingBookmark {
  const bookmark: ReadingBookmark = {
    bookmarkId: uid('bm'),
    materialId,
    locator,
    label: label.trim() || '未命名书签',
    createdAt: new Date().toISOString(),
  };
  writeList(BOOKMARKS_KEY, [...readBookmarks(), bookmark]);
  return bookmark;
}

export function deleteBookmark(bookmarkId: string): boolean {
  const list = readBookmarks();
  const kept = list.filter((item) => item.bookmarkId !== bookmarkId);
  if (kept.length === list.length) return false;
  writeList(BOOKMARKS_KEY, kept);
  return true;
}

// ===== 伴生会话（本地模拟 AI） =====

export function readSessions(workspaceId?: string): ReadingSession[] {
  const list = readList<ReadingSession>(SESSIONS_KEY).filter((item) => item && item.id);
  return workspaceId ? list.filter((item) => item.workspaceId === workspaceId) : list;
}

export function getSession(sessionId: string): ReadingSession | null {
  return readSessions().find((item) => item.id === sessionId) ?? null;
}

export function createSession(workspaceId: string, activeMaterialId: string | null): ReadingSession {
  const now = new Date().toISOString();
  const session: ReadingSession = {
    id: uid('rss'),
    workspaceId,
    title: '新的阅读会话',
    activeMaterialId,
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
  writeList(SESSIONS_KEY, [...readSessions(), session]);
  return session;
}

export function appendMessage(sessionId: string, message: Omit<ReadingMessage, 'id' | 'at'>): ReadingSession | null {
  const list = readSessions();
  const idx = list.findIndex((item) => item.id === sessionId);
  if (idx === -1) return null;
  const session = list[idx]!;
  const entry: ReadingMessage = { ...message, id: uid('msg'), at: new Date().toISOString() };
  list[idx] = {
    ...session,
    messages: [...session.messages, entry],
    title:
      session.messages.length === 0 && message.role === 'user'
        ? message.content.slice(0, 24) || session.title
        : session.title,
    updatedAt: new Date().toISOString(),
  };
  writeList(SESSIONS_KEY, list);
  return list[idx]!;
}

export function renameSession(sessionId: string, title: string): ReadingSession | null {
  const list = readSessions();
  const idx = list.findIndex((item) => item.id === sessionId);
  if (idx === -1) return null;
  list[idx] = { ...list[idx]!, title: title.trim() || list[idx]!.title, updatedAt: new Date().toISOString() };
  writeList(SESSIONS_KEY, list);
  return list[idx]!;
}

/** 保存会话草稿与引用（R32.3：切会话/刷新后按会话恢复，不跨会话串写） */
export function saveSessionDraft(sessionId: string, draft: string, draftQuote?: string | null): ReadingSession | null {
  const list = readSessions();
  const idx = list.findIndex((item) => item.id === sessionId);
  if (idx === -1) return null;
  const session = list[idx]!;
  const nextDraft = draft;
  const nextQuote = draftQuote ?? null;
  if ((session.draft ?? '') === nextDraft && (session.draftQuote ?? null) === nextQuote) return session;
  list[idx] = { ...session, draft: nextDraft, draftQuote: nextQuote, updatedAt: new Date().toISOString() };
  writeList(SESSIONS_KEY, list);
  return list[idx]!;
}

export function deleteSession(sessionId: string): boolean {
  const list = readSessions();
  const kept = list.filter((item) => item.id !== sessionId);
  if (kept.length === list.length) return false;
  writeList(SESSIONS_KEY, kept);
  return true;
}

/** 伴生 AI 的本地确定性模拟回复（显式【模拟回复】；不调用模型） */
export function simulateCompanionReply(input: {
  materialTitle: string | null;
  userText: string;
  quote?: string;
}): string {
  const materialPart = input.materialTitle ? `关于《${input.materialTitle}》` : '关于当前阅读内容';
  const quotePart = input.quote ? `，你选中的「${input.quote.slice(0, 40)}${input.quote.length > 40 ? '…' : ''}」已作为上下文` : '';
  return [
    `【模拟回复】${materialPart}${quotePart}：伴生助手尚未接入模型服务，本回复为本地模板生成，不执行真实检索或推理。`,
    '建议动作：',
    '- 用自己的话概括本段要点；',
    '- 对不懂的句子使用「选中 → 问 AI」或添加批注；',
    '- 完成后用「发到笔记本」沉淀记录。',
  ].join('\n');
}

/** 整理笔记（本地模板聚合批注；对照参考 organize-notes 的模拟形态） */
export function organizeNotes(workspaceId: string): { title: string; markdown: string; annotationCount: number } | null {
  const workspace = readWorkspaces().find((item) => item.id === workspaceId);
  if (!workspace) return null;
  const materialIds = workspace.tabs.map((tab) => tab.materialId);
  const materials = readMaterials().filter((item) => materialIds.includes(item.id));
  const annotations = readAnnotations().filter((item) => materialIds.includes(item.materialId));
  const lines: string[] = [`# ${workspace.title} · 整理笔记（模拟整理，本地聚合批注）`, ''];
  for (const material of materials) {
    lines.push(`## ${material.title}`, '');
    const items = annotations.filter((item) => item.materialId === material.id);
    if (items.length === 0) {
      lines.push('（本材料暂无批注）', '');
      continue;
    }
    for (const item of items) {
      lines.push(`> ${item.quote}`, '');
      lines.push(`- 类型：${item.kind === 'note' ? '笔记' : '高亮'}${item.note ? `；笔记：${item.note}` : ''}`, '');
    }
  }
  if (materials.length === 0) lines.push('（工作区暂无材料）', '');
  return { title: `${workspace.title} · 整理笔记`, markdown: lines.join('\n'), annotationCount: annotations.length };
}

/** 发到笔记本（真实跨页写入 notebook-store） */
export function sendToNotebook(input: {
  workspaceId: string;
  notebookId: string;
}): { notebookId: string; title: string } | null {
  const workspace = readWorkspaces().find((item) => item.id === input.workspaceId);
  if (!workspace) return null;
  const organized = organizeNotes(input.workspaceId);
  if (!organized) return null;
  const record = createNotebookRecord({
    notebookId: input.notebookId,
    title: `${workspace.title} · 阅读笔记`,
    content: organized.markdown,
    summary: `阅读工作区整理笔记（${organized.annotationCount} 条批注）`,
    type: 'research_report',
  });
  if (!record) return null;
  return { notebookId: input.notebookId, title: record.title };
}

// ===== 演示数据 =====

const DEMO_MATERIAL_TEXT = [
  '# 分数是什么',
  '',
  '分数表示把一个整体平均分成若干份，取其中的几份。写作 a/b，其中 b 是分母，a 是分子。',
  '',
  '## 分数的基本性质',
  '',
  '分子和分母同时乘或除以同一个不为零的数，分数的大小不变。这是约分与通分的依据。',
  '',
  '## 生活中的分数',
  '',
  '半块蛋糕是 1/2，四分之一张纸是 1/4。分数在时间（半小时）、测量（毫米）中处处出现。',
].join('\n');

/** 显式载入演示阅读数据（R26：按稳定 id 无损合并，用户数据优先，单批原子提交） */
export function loadDemoReading(): void {
  const demoLines = DEMO_MATERIAL_TEXT.split('\n');
  const demoQuote = '分子和分母同时乘或除以同一个不为零的数，分数的大小不变。';
  // 批注引用是所在行的子串：按 includes 定位行、indexOf 定位行内偏移
  const demoLineIndex = demoLines.findIndex((line) => line.includes(demoQuote));
  const demoStart = demoLineIndex >= 0 ? demoLines[demoLineIndex]!.indexOf(demoQuote) : 0;
  const demoSegment =
    demoLineIndex >= 0
      ? [{ locator: `p-${demoLineIndex}`, start: demoStart, end: demoStart + demoQuote.length }]
      : undefined;
  const now = new Date().toISOString();
  const materialA: ReadingMaterial = {
    id: 'demo-reading-mat-a',
    title: '分数是什么（演示材料）',
    filename: null,
    sourceKind: 'text',
    sourceUrl: null,
    text: DEMO_MATERIAL_TEXT,
    charCount: DEMO_MATERIAL_TEXT.length,
    sizeBytes: new Blob([DEMO_MATERIAL_TEXT]).size,
    positionPct: 0,
    workspaceIds: ['demo-reading-ws'],
    createdAt: now,
    updatedAt: now,
  };
  const materialB: ReadingMaterial = {
    id: 'demo-reading-mat-b',
    title: '修辞手法摘录（未分配演示材料）',
    filename: null,
    sourceKind: 'text',
    sourceUrl: null,
    text: '# 比喻\n\n比喻是用跟甲事物有相似点的乙事物来描写或说明甲事物的修辞手法。\n\n# 拟人\n\n拟人把事物人格化，赋予它们人的动作或情感。',
    charCount: 86,
    sizeBytes: 86,
    positionPct: 0,
    workspaceIds: [],
    createdAt: now,
    updatedAt: now,
  };
  const workspace: ReadingWorkspace = {
    id: 'demo-reading-ws',
    title: '分数阅读（演示集合）',
    description: '演示阅读工作区：材料解析/转录为本地模拟，伴生回复为模板生成。',
    activeMaterialId: materialA.id,
    tabs: [{ materialId: materialA.id, addedAt: now }],
    createdAt: now,
    updatedAt: now,
  };
  const demoAnnotation: ReadingAnnotation = {
    annotationId: 'demo-reading-ann-1',
    materialId: materialA.id,
    kind: 'note',
    color: 'yellow',
    quote: demoQuote,
    ...(demoSegment ? { segments: demoSegment } : {}),
    note: '约分通分的依据，考试常考。',
    createdAt: now,
  };
  const demoBookmark: ReadingBookmark = {
    bookmarkId: 'demo-reading-bm-1',
    materialId: materialA.id,
    locator: `h-${demoLines.indexOf('## 生活中的分数')}`,
    label: '生活中的分数',
    createdAt: now,
  };
  const demoSession: ReadingSession = {
    id: 'demo-reading-ss-1',
    workspaceId: 'demo-reading-ws',
    title: '什么是约分？',
    activeMaterialId: materialA.id,
    messages: [
      { id: 'demo-reading-msg-1', role: 'user' as const, content: '什么是约分？', at: now },
      {
        id: 'demo-reading-msg-2',
        role: 'assistant' as const,
        content: '【模拟回复】约分是把分子分母的公因数约去，使分数更简洁，例如 2/4 = 1/2。（本地模板生成，未接入模型）',
        at: now,
      },
    ],
    createdAt: now,
    updatedAt: now,
  };
  // 各集合按稳定 id 合并：已存在条目（用户或此前演示）原样保留，只补缺失的演示条目；
  // 用户先建的批注/书签/会话不会被演示数据删除，删除演示后再载入不产生重复 id。
  commitLists([
    [MATERIALS_KEY, mergeById(readMaterials(), [materialA, materialB])],
    [WORKSPACES_KEY, mergeById(readWorkspaces(), [workspace])],
    [ANNOTATIONS_KEY, mergeById(readAnnotations(), [demoAnnotation])],
    [BOOKMARKS_KEY, mergeById(readBookmarks(), [demoBookmark])],
    [SESSIONS_KEY, mergeById(readSessions(), [demoSession])],
  ]);
}

function mergeById<T extends { id?: string; annotationId?: string; bookmarkId?: string }>(
  existing: T[],
  demoItems: T[],
): T[] {
  const keyOf = (item: T) => item.annotationId ?? item.bookmarkId ?? item.id;
  const existingIds = new Set(existing.map((item) => keyOf(item)).filter(Boolean));
  const additions = demoItems.filter((item) => !existingIds.has(keyOf(item)!));
  return [...existing, ...additions];
}
