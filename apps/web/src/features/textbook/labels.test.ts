import { describe, expect, it } from 'vitest';
import {
  MAX_UPLOAD_BYTES,
  type ImportDraftView,
  type ImportParsedView,
  type ImportState,
} from '@/contracts/textbook';
import { importFileError, IMPORT_ACCEPT, fileSuffix } from './import-file';
import {
  commitBlockReason,
  importStateLabel,
  isImportActive,
  isImportTerminal,
  jobKindLabel,
  jobStateLabel,
  progressPercent,
} from './labels';

describe('导入文件校验', () => {
  it('accept 只包含三种支持格式', () => {
    expect(IMPORT_ACCEPT.split(',')).toEqual(['.md', '.pdf', '.docx']);
  });

  it('拒绝不支持的后缀并给出明确原因', () => {
    const message = importFileError({ name: '教材.txt', size: 10 });
    expect(message).toContain('.txt');
    expect(message).toContain('.md');
    expect(importFileError({ name: '无扩展名', size: 10 })).toContain('不支持');
  });

  it('拒绝超过 100 MiB 的文件并给出体积原因', () => {
    expect(importFileError({ name: 'book.pdf', size: MAX_UPLOAD_BYTES })).toBeNull();
    expect(importFileError({ name: 'book.pdf', size: MAX_UPLOAD_BYTES + 1 })).toContain('过大');
  });

  it('大小写后缀按小写归一', () => {
    expect(fileSuffix('BOOK.MD')).toBe('.md');
    expect(importFileError({ name: 'BOOK.MD', size: 1 })).toBeNull();
  });
});

describe('阶段文案映射', () => {
  it('导入阶段使用契约文案，未列出的状态按原样显示', () => {
    expect(importStateLabel('uploaded')).toBe('已上传');
    expect(importStateLabel('chunking')).toBe('分块中');
    expect(importStateLabel('needs_review')).toBe('待确认');
    expect(importStateLabel('ready')).toBe('已入库');
    // 未冻结的状态不虚构名称（运行时兜底，类型上不可能出现）
    const unknown = 'unknown-state' as ImportState;
    expect(importStateLabel(unknown)).toBe('unknown-state');
  });

  it('终态与进行中区分明确', () => {
    const terminal: ImportState[] = ['ready', 'failed', 'cancelled'];
    const active: ImportState[] = [
      'uploaded',
      'extracting',
      'queued',
      'chunking',
      'embedding',
      'indexing',
    ];
    expect(terminal.every(isImportTerminal)).toBe(true);
    expect(active.every(isImportActive)).toBe(true);
    expect(isImportActive('needs_review')).toBe(false);
  });

  it('任务状态与类型文案', () => {
    expect(jobStateLabel('running')).toBe('执行中');
    expect(jobStateLabel('succeeded')).toBe('已完成');
    expect(jobKindLabel('ingest')).toBe('入库');
    expect(jobKindLabel('rebuild')).toBe('索引重建');
  });

  it('进度百分比不除以零且收敛到 0–100', () => {
    expect(progressPercent(0, 0)).toBe(0);
    expect(progressPercent(1, 2)).toBe(50);
    expect(progressPercent(5, 2)).toBe(100);
    expect(progressPercent(Number.NaN, 10)).toBe(0);
  });
});

const PARSED: ImportParsedView = {
  charCount: 100,
  chunkCount: 2,
  bodyChunkCount: 1,
  exerciseChunkCount: 1,
  needsOcr: false,
  sourceKind: 'markdown',
  pageCount: null,
  blockCount: 2,
  warnings: [],
  preview: [],
};

const METADATA = {
  title: '七年级数学上册',
  stageId: 'stage-j',
  gradeIds: ['g7'],
  subjectId: 'math',
  editionId: 'rj',
  publicationLabel: '',
  volumeLabel: '',
};

function draft(overrides: Partial<ImportDraftView> = {}): ImportDraftView {
  return {
    importId: 'imp-1',
    ownerId: 'local-user',
    state: 'needs_review',
    revision: 1,
    uploadedFileName: 'book.md',
    uploadedBytes: 1024,
    targetDocumentId: null,
    expectedCurrentRevisionId: null,
    metadata: null,
    metadataConfirmed: false,
    parsed: PARSED,
    warnings: [],
    errorCode: null,
    canCommit: false,
    createdAt: '2026-09-28T00:00:00Z',
    ...overrides,
  };
}

const GATE = { libraryCount: 1, hasWarnings: false, warningsAcknowledged: false, committed: false };

describe('提交入库前置原因', () => {
  it('服务端允许提交时只报告客户端缺口', () => {
    expect(commitBlockReason({ ...GATE, draft: draft({ canCommit: true }) })).toBeNull();
    expect(
      commitBlockReason({ ...GATE, draft: draft({ canCommit: true }), libraryCount: 0 }),
    ).toContain('目标逻辑库');
    expect(
      commitBlockReason({
        ...GATE,
        draft: draft({ canCommit: true }),
        hasWarnings: true,
      }),
    ).toContain('我已核对以上警告');
  });

  it('服务端不允许时按草稿状态给出具体原因，而不是笼统禁用', () => {
    expect(commitBlockReason({ ...GATE, draft: draft({ state: 'extracting' }) })).toContain(
      '当前阶段「解析中」不可提交',
    );
    expect(commitBlockReason({ ...GATE, draft: draft({}) })).toContain('尚未确认分类元数据');
    expect(
      commitBlockReason({
        ...GATE,
        draft: draft({ metadata: METADATA, metadataConfirmed: false }),
      }),
    ).toContain('尚未确认分类元数据');
    expect(
      commitBlockReason({
        ...GATE,
        draft: draft({ metadata: METADATA, metadataConfirmed: true }),
      }),
    ).toContain('服务端当前不允许提交');
    expect(
      commitBlockReason({
        ...GATE,
        draft: draft({ parsed: { ...PARSED, needsOcr: true } }),
      }),
    ).toContain('没有可用文本层');
    expect(commitBlockReason({ ...GATE, draft: draft({ state: 'failed' }) })).toContain('解析失败');
    expect(commitBlockReason({ ...GATE, draft: draft({ state: 'cancelled' }) })).toContain(
      '已取消',
    );
  });

  it('已提交或没有草稿时不显示阻断原因', () => {
    expect(commitBlockReason({ ...GATE, draft: null })).toBeNull();
    expect(
      commitBlockReason({ ...GATE, committed: true, draft: draft({ state: 'queued' }) }),
    ).toBeNull();
  });
});
