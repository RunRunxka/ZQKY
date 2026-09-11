/**
 * 知识库解析/索引显式模拟（B-H1-KB）。
 *
 * 真实 PDF 解析与向量索引依赖服务端，未接入。这里以定时推进 + 结构化样例
 * 复刻「登记 → 解析 → 索引 → 就绪/失败/取消」的前端闭环，保留服务接口与状态语义；
 * 全程标注【模拟】，不读取真实文件内容，不宣称真实解析/索引成功。
 *
 * 与 `features/reading/reading-ingest.ts` 同构（模块内注册表 + cancel + 定时推进），
 * 但持久化走 `knowledge-catalog` 的 write + `subscribeKnowledge` 事件，保持单一仓储。
 */
import {
  addKbIndexVersion,
  readKnowledge,
  updateKbDocument,
  type KbDocStatus,
  type KbDocument,
} from './knowledge-catalog';

/** 默认单阶段延迟（毫秒） */
export const KB_INGEST_STAGE_DELAY_MS = 600;

/** 内置本地索引标识（显式模拟，不对应真实向量库） */
export const KB_INDEX_PROVIDER = '内置本地索引（模拟）';

const FAIL_NOTE = '【模拟】解析失败：解析器不可用（演示失败路径，可重试）。';
const CANCEL_NOTE = '【模拟】已取消解析（演示取消路径，可重试）。';
const READY_NOTE = '已解析并写入模拟索引';

/** 模拟解析产出的字符数：确定性由文档名推导，保证单测可断言 */
export function kbSimulatedParsedChars(doc: Pick<KbDocument, 'name'>): number {
  return 1200 + doc.name.length * 7;
}

/** 模拟切片数：确定性由字符数推导，至少 1 */
export function kbSimulatedChunks(parsedChars: number): number {
  return Math.max(1, Math.floor(parsedChars / 400));
}

export interface KbIngestHandle {
  /** 取消未完成的模拟推进（清理定时器，不改变文档状态） */
  cancel(): void;
}

/** 进行中的模拟推进注册表（key = `${kbId}:${docId}`） */
const activeIngests = new Map<string, KbIngestHandle>();

type KbStage = 'parsing' | 'indexing' | 'ready';

/** 由当前状态推导待执行阶段；ready 表示无操作 */
function nextStage(status: KbDocStatus): KbStage | undefined {
  switch (status) {
    case 'registered':
    case 'error':
      return 'parsing';
    case 'parsing':
      return 'indexing';
    case 'indexing':
      return 'ready';
    case 'ready':
      return undefined;
  }
}

function findKbDoc(kbId: string, docId: string): KbDocument | undefined {
  return readKnowledge()
    .find((kb) => kb.id === kbId)
    ?.docs?.find((doc) => doc.id === docId);
}

/**
 * 全部文档就绪后追加模拟索引版本；最近版本 (docCount, chunkCount) 与当前一致时跳过，
 * 避免刷新恢复或多文档逐个就绪时重复追加。
 */
function maybeAppendIndexVersion(kbId: string): void {
  const kb = readKnowledge().find((item) => item.id === kbId);
  if (!kb) return;
  const docs = kb.docs ?? [];
  if (docs.length === 0) return;
  if (!docs.every((doc) => doc.status === 'ready')) return;
  const docCount = docs.length;
  const chunkCount = docs.reduce((sum, doc) => sum + (doc.chunks ?? 0), 0);
  const versions = kb.indexVersions ?? [];
  const last = versions[versions.length - 1];
  if (last && last.docCount === docCount && last.chunkCount === chunkCount) return;
  addKbIndexVersion(kbId, {
    docCount,
    chunkCount,
    provider: KB_INDEX_PROVIDER,
    note: '【模拟】由解析流水线自动追加。',
  });
}

/**
 * 推进单文档：registered/error → parsing → indexing → ready。
 * options.fail=true 时，在进入 ready 前以 error 收尾（演示失败，可重试）。
 * 重复调用先取消旧 handle；resume：按当前 status 从下一阶段继续。
 */
export function simulateKbDocIngest(
  kbId: string,
  docId: string,
  options?: { fail?: boolean; stageDelayMs?: number },
): KbIngestHandle {
  const key = `${kbId}:${docId}`;
  activeIngests.get(key)?.cancel();
  const delay = options?.stageDelayMs ?? KB_INGEST_STAGE_DELAY_MS;
  const timers: number[] = [];
  let cancelled = false;
  const schedule = (fn: () => void, ms: number) => {
    timers.push(window.setTimeout(fn, ms));
  };
  const handle: KbIngestHandle = {
    cancel() {
      cancelled = true;
      for (const timer of timers) window.clearTimeout(timer);
      if (activeIngests.get(key) === handle) activeIngests.delete(key);
    },
  };
  const finish = () => {
    if (activeIngests.get(key) === handle) activeIngests.delete(key);
  };

  const doc = findKbDoc(kbId, docId);
  const start = doc ? nextStage(doc.status ?? 'registered') : 'parsing';
  // 文档不存在或已就绪：无操作（不注册定时器）
  if (!doc || start === undefined) return handle;
  activeIngests.set(key, handle);

  const run = (stage: KbStage) => {
    if (cancelled) {
      finish();
      return;
    }
    const current = findKbDoc(kbId, docId);
    if (!current) {
      finish();
      return;
    }
    if (stage === 'parsing') {
      updateKbDocument(kbId, docId, {
        status: 'parsing',
        statusNote: null,
        progress: { stage: '解析中', percent: 35 },
      });
      schedule(() => run('indexing'), delay);
      return;
    }
    if (stage === 'indexing') {
      updateKbDocument(kbId, docId, {
        status: 'indexing',
        progress: { stage: '索引中', percent: 75 },
      });
      schedule(() => run('ready'), delay);
      return;
    }
    // ready
    finish();
    const target = findKbDoc(kbId, docId);
    if (!target) return;
    if (options?.fail) {
      updateKbDocument(kbId, docId, {
        status: 'error',
        progress: null,
        statusNote: FAIL_NOTE,
      });
      return;
    }
    const parsedChars = kbSimulatedParsedChars(target);
    const chunks = kbSimulatedChunks(parsedChars);
    updateKbDocument(kbId, docId, {
      status: 'ready',
      progress: null,
      parsedChars,
      chunks,
      statusNote: READY_NOTE,
    });
    maybeAppendIndexVersion(kbId);
  };

  schedule(() => run(start), delay);
  return handle;
}

/** 对该库所有 registered/error 文档启动模拟解析；ready 跳过 */
export function simulateKbIngestAll(
  kbId: string,
  options?: { fail?: boolean; stageDelayMs?: number },
): void {
  const kb = readKnowledge().find((item) => item.id === kbId);
  if (!kb) return;
  for (const doc of kb.docs ?? []) {
    if (doc.status === 'registered' || doc.status === 'error') {
      simulateKbDocIngest(kbId, doc.id, options);
    }
  }
}

/** 取消单个文档的模拟任务：停止定时器并显式标记取消（error + 说明，可重试） */
export function cancelKbDocIngest(kbId: string, docId: string): void {
  activeIngests.get(`${kbId}:${docId}`)?.cancel();
  const doc = findKbDoc(kbId, docId);
  if (doc && (doc.status === 'parsing' || doc.status === 'indexing')) {
    updateKbDocument(kbId, docId, {
      status: 'error',
      progress: null,
      statusNote: CANCEL_NOTE,
    });
  }
}

/** 取消库内所有进行中的模拟任务（标记 error + 取消说明，可重试） */
export function cancelKbIngestAll(kbId: string): void {
  const kb = readKnowledge().find((item) => item.id === kbId);
  if (!kb) return;
  for (const doc of kb.docs ?? []) {
    cancelKbDocIngest(kbId, doc.id);
  }
}

/** 刷新恢复：对处于 parsing/indexing 的文档重新挂载模拟推进（从下一阶段继续） */
export function resumeKbIngests(kbId: string): void {
  const kb = readKnowledge().find((item) => item.id === kbId);
  if (!kb) return;
  for (const doc of kb.docs ?? []) {
    if (doc.status === 'parsing' || doc.status === 'indexing') {
      simulateKbDocIngest(kbId, doc.id);
    }
  }
}

/** 测试用：清空注册表（不改变仓储数据） */
export function __resetKbIngestsForTest(): void {
  for (const handle of activeIngests.values()) handle.cancel();
  activeIngests.clear();
}
