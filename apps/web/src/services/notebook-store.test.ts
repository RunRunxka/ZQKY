import { beforeEach, describe, expect, it } from 'vitest';
import {
  createNotebook,
  DEFAULT_NOTEBOOK_ID,
  deleteNotebook,
  exportNotebookMarkdown,
  listNotebooks,
  listRecords,
  listRecordsOf,
  relocateRecord,
  removeNotebookRecord,
  updateNotebook,
  updateNotebookRecord,
} from './notebook-store';
import { saveNotebookEntry } from './space-store';

/**
 * S5-B 笔记本本地仓储：与聊天"保存到笔记"共用记录存储（缺省归默认笔记本）；
 * 笔记本 CRUD、记录编辑/删除/移动/复制、markdown 导出。
 */

describe('S5-B notebook-store', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('无笔记本时带出默认笔记本；聊天保存的记录自动归入默认笔记本', () => {
    expect(listNotebooks().map((n) => n.id)).toEqual([DEFAULT_NOTEBOOK_ID]);
    saveNotebookEntry({
      id: 'm1:report-1',
      messageId: 'm1',
      artifactId: 'report-1',
      title: '研究报告',
      kind: 'research_report',
      content: '# 内容',
    });
    const records = listRecords();
    expect(records).toHaveLength(1);
    expect(records[0]!.notebookId).toBe(DEFAULT_NOTEBOOK_ID);
    expect(records[0]!.type).toBe('research_report');
    expect(listRecordsOf(DEFAULT_NOTEBOOK_ID)).toHaveLength(1);
  });

  it('笔记本创建/重命名/删除：重名拒绝、默认笔记本不可删、记录回默认', () => {
    const nb = createNotebook('月度整理', '收集资料');
    expect(nb).not.toBeNull();
    expect(createNotebook('月度整理')).toBeNull();
    expect(createNotebook('  ')).toBeNull();

    saveNotebookEntry({
      id: 'm1:report-2',
      messageId: 'm1',
      artifactId: 'report-2',
      title: '报告二',
      kind: 'research_report',
      content: 'x',
    });
    updateNotebookRecord('m1:report-2', { notebookId: nb!.id });
    expect(listRecordsOf(nb!.id)).toHaveLength(1);

    expect(updateNotebook(nb!.id, { name: '月度整理（改）', color: 'amber' })?.name).toBe(
      '月度整理（改）',
    );
    expect(updateNotebook(nb!.id, { name: '学习笔记' })).toBeNull(); // 与默认笔记本重名

    expect(deleteNotebook(DEFAULT_NOTEBOOK_ID)).toBe(false);
    expect(deleteNotebook(nb!.id)).toBe(true);
    // 记录回默认笔记本，不丢失
    expect(listRecordsOf(DEFAULT_NOTEBOOK_ID).map((r) => r.id)).toContain('m1:report-2');
  });

  it('记录编辑与删除：空标题回退原题、删除生效', () => {
    saveNotebookEntry({
      id: 'm1:report-3',
      messageId: 'm1',
      artifactId: 'report-3',
      title: '原标题',
      kind: 'research_report',
      content: '旧内容',
    });
    const updated = updateNotebookRecord('m1:report-3', { title: '  ', content: '新内容' });
    expect(updated!.title).toBe('原标题'); // 空标题不生效
    expect(updated!.content).toBe('新内容');
    expect(removeNotebookRecord('m1:report-3')).toBe(true);
    expect(removeNotebookRecord('m1:report-3')).toBe(false);
  });

  it('移动与复制：移动改归属；复制生成副本标题', () => {
    const target = createNotebook('归档')!;
    saveNotebookEntry({
      id: 'm1:report-4',
      messageId: 'm1',
      artifactId: 'report-4',
      title: '报告四',
      kind: 'research_report',
      content: 'c',
    });
    const moved = relocateRecord('m1:report-4', target.id, 'move');
    expect(moved!.notebookId).toBe(target.id);
    expect(listRecordsOf(DEFAULT_NOTEBOOK_ID)).toHaveLength(0);

    const copy = relocateRecord('m1:report-4', DEFAULT_NOTEBOOK_ID, 'copy');
    expect(copy!.notebookId).toBe(DEFAULT_NOTEBOOK_ID);
    expect(copy!.title).toContain('副本');
    expect(listRecords()).toHaveLength(2);
    expect(relocateRecord('missing', target.id, 'move')).toBeNull();
  });

  it('导出 markdown：包含笔记本名与每条记录的实际内容', () => {
    saveNotebookEntry({
      id: 'm1:report-5',
      messageId: 'm1',
      artifactId: 'report-5',
      title: '导出报告',
      kind: 'research_report',
      content: '正文内容XYZ',
    });
    const result = exportNotebookMarkdown(DEFAULT_NOTEBOOK_ID)!;
    expect(result.name).toBe('学习笔记.md');
    expect(result.content).toContain('# 学习笔记');
    expect(result.content).toContain('## 导出报告');
    expect(result.content).toContain('正文内容XYZ');
    expect(exportNotebookMarkdown('nope')).toBeNull();
  });
});

describe('R-10 来源会话身份兼容', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('保存时带 sessionId 可读回；用于业务页回链', () => {
    saveNotebookEntry({
      id: 'm1:report-9',
      messageId: 'm1',
      sessionId: 'sess-9',
      artifactId: 'report-9',
      title: '带来源的报告',
      kind: 'research_report',
      content: '正文',
    });
    const record = listRecords().find((r) => r.id === 'm1:report-9');
    expect(record?.metadata?.sessionId).toBe('sess-9');
  });

  it('旧数据缺 sessionId：不猜测身份，解析为 undefined', () => {
    window.localStorage.setItem(
      'zhiqikeyuan:notebook-entries',
      JSON.stringify([
        { id: 'old:1', messageId: 'old', artifactId: '1', title: '旧记录', type: 'research_report', content: 'x' },
      ]),
    );
    const record = listRecords().find((r) => r.id === 'old:1');
    expect(record?.metadata?.sessionId).toBeUndefined();
    // 其余身份仍保留，供会话内定位
    expect(record?.metadata?.messageId).toBe('old');
  });

  it('脏身份（空串/非字符串）不作为可靠身份', () => {
    window.localStorage.setItem(
      'zhiqikeyuan:notebook-entries',
      JSON.stringify([
        { id: 'bad:1', metadata: { sessionId: '   ', messageId: 42 }, title: '脏', type: 'chat', content: 'x' },
      ]),
    );
    const record = listRecords().find((r) => r.id === 'bad:1');
    expect(record?.metadata?.sessionId).toBeUndefined();
    expect(record?.metadata?.messageId).toBeUndefined();
  });

  it('顶层扁平 sessionId（未来回填形态）也能被读取', () => {
    window.localStorage.setItem(
      'zhiqikeyuan:notebook-entries',
      JSON.stringify([{ id: 'flat:1', sessionId: 'sess-flat', messageId: 'm', title: '扁平', type: 'chat', content: 'x' }]),
    );
    expect(listRecords().find((r) => r.id === 'flat:1')?.metadata?.sessionId).toBe('sess-flat');
  });
});
