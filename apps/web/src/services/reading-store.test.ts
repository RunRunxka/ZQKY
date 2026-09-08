import { beforeEach, describe, expect, it } from 'vitest';
import {
  addAnnotation,
  addBookmark,
  addMaterialToWorkspace,
  appendMessage,
  createMaterial,
  createSession,
  createWorkspace,
  deleteAnnotation,
  deleteBookmark,
  deleteMaterial,
  deleteSession,
  deleteWorkspace,
  getSession,
  loadDemoReading,
  organizeNotes,
  readAnnotations,
  readBookmarks,
  readMaterials,
  readSessions,
  readWorkspaces,
  removeMaterialFromWorkspace,
  renameSession,
  renameWorkspace,
  saveReadingPosition,
  sendToNotebook,
  simulateCompanionReply,
} from './reading-store';
import { listRecordsOf } from './notebook-store';

beforeEach(() => {
  window.localStorage.clear();
});

describe('reading-store 材料', () => {
  it('createMaterial 校验空标题/空正文；deleteMaterial 级联清理', () => {
    const material = createMaterial({ title: '测试材料', text: '# 标题\n\n正文一段。' });
    expect(material.charCount).toBeGreaterThan(0);
    expect(material.sourceKind).toBe('text');
    expect(() => createMaterial({ title: '  ', text: '内容' })).toThrow('材料标题不能为空。');
    expect(() => createMaterial({ title: '无正文', text: '   ' })).toThrow(/仅登记文本材料/);
    addAnnotation({ materialId: material.id, kind: 'highlight', quote: '正文一段。' });
    addBookmark(material.id, 'h-0', '书签');
    expect(deleteMaterial(material.id)).toBe(true);
    expect(readMaterials()).toHaveLength(0);
    expect(readAnnotations()).toHaveLength(0);
    expect(readBookmarks()).toHaveLength(0);
  });

  it('saveReadingPosition 钳制到 0-100 且幂等', () => {
    const material = createMaterial({ title: '位置材料', text: '正文' });
    saveReadingPosition(material.id, 150);
    expect(readMaterials()[0]!.positionPct).toBe(100);
    saveReadingPosition(material.id, 42);
    expect(readMaterials()[0]!.positionPct).toBe(42);
    saveReadingPosition(material.id, 42);
    expect(readMaterials()[0]!.positionPct).toBe(42);
  });
});

describe('reading-store 工作区', () => {
  it('createWorkspace 重名拒绝；材料挂载/移除双向同步', () => {
    const ws = createWorkspace('测试集合', '说明');
    expect(() => createWorkspace('测试集合')).toThrow(/同名阅读集合/);
    expect(() => renameWorkspace(ws.id, '  ')).toThrow('集合名称不能为空。');
    expect(renameWorkspace(ws.id, '测试集合（改）')?.title).toBe('测试集合（改）');

    const material = createMaterial({ title: '挂载材料', text: '正文' });
    addMaterialToWorkspace(ws.id, material.id);
    expect(readWorkspaces()[0]!.tabs).toHaveLength(1);
    expect(readWorkspaces()[0]!.activeMaterialId).toBe(material.id);
    expect(readMaterials()[0]!.workspaceIds).toContain(ws.id);
    // 重复挂载幂等
    addMaterialToWorkspace(ws.id, material.id);
    expect(readWorkspaces()[0]!.tabs).toHaveLength(1);

    removeMaterialFromWorkspace(ws.id, material.id);
    expect(readWorkspaces()[0]!.tabs).toHaveLength(0);
    expect(readWorkspaces()[0]!.activeMaterialId).toBeNull();
    expect(readMaterials()[0]!.workspaceIds).not.toContain(ws.id);
  });

  it('deleteWorkspace 保留材料但解除归属并删除会话', () => {
    const ws = createWorkspace('删除集合');
    const material = createMaterial({ title: '保留材料', text: '正文' });
    addMaterialToWorkspace(ws.id, material.id);
    const session = createSession(ws.id, material.id);
    expect(deleteWorkspace(ws.id)).toBe(true);
    expect(readWorkspaces()).toHaveLength(0);
    expect(readMaterials()).toHaveLength(1);
    expect(readMaterials()[0]!.workspaceIds).toHaveLength(0);
    expect(readSessions()).toHaveLength(0);
    void session;
  });
});

describe('reading-store 批注/书签', () => {
  it('addAnnotation 空 quote 拒绝；删除往返', () => {
    const material = createMaterial({ title: '批注材料', text: '正文' });
    expect(() => addAnnotation({ materialId: material.id, kind: 'highlight', quote: '   ' })).toThrow(
      /引用文本不能为空/,
    );
    const ann = addAnnotation({ materialId: material.id, kind: 'note', quote: '被引用句', note: '笔记内容' });
    expect(readAnnotations(material.id)).toHaveLength(1);
    expect(readAnnotations('other')[0]?.annotationId).toBeUndefined();
    expect(deleteAnnotation(ann.annotationId)).toBe(true);
    expect(deleteAnnotation(ann.annotationId)).toBe(false);

    const bm = addBookmark(material.id, 'h-2', '章二');
    expect(readBookmarks(material.id)[0]!.label).toBe('章二');
    expect(deleteBookmark(bm.bookmarkId)).toBe(true);
  });
});

describe('reading-store 会话与模拟', () => {
  it('appendMessage 空会话以首条用户消息命名；删除/恢复', () => {
    const ws = createWorkspace('会话集合');
    const session = createSession(ws.id, null);
    appendMessage(session.id, { role: 'user', content: '这段讲了什么？' });
    appendMessage(session.id, { role: 'assistant', content: '【模拟回复】……' });
    const loaded = getSession(session.id)!;
    expect(loaded.messages).toHaveLength(2);
    expect(loaded.title).toBe('这段讲了什么？');
    expect(renameSession(session.id, '自定义标题')?.title).toBe('自定义标题');
    expect(deleteSession(session.id)).toBe(true);
    expect(getSession(session.id)).toBeNull();
  });

  it('simulateCompanionReply 显式模拟标注并携带材料与选段', () => {
    const reply = simulateCompanionReply({ materialTitle: '分数是什么', userText: '问题', quote: '分数表示整体的一部分' });
    expect(reply).toContain('【模拟回复】');
    expect(reply).toContain('《分数是什么》');
    expect(reply).toContain('分数表示整体的一部分');
  });

  it('organizeNotes 聚合批注；sendToNotebook 真实写入笔记本', () => {
    const ws = createWorkspace('笔记集合');
    const material = createMaterial({ title: '笔记材料', text: '正文' });
    addMaterialToWorkspace(ws.id, material.id);
    addAnnotation({ materialId: material.id, kind: 'note', quote: '引用句', note: '我的笔记' });
    const organized = organizeNotes(ws.id)!;
    expect(organized.annotationCount).toBe(1);
    expect(organized.markdown).toContain('# 笔记集合');
    expect(organized.markdown).toContain('> 引用句');

    const before = listRecordsOf('notebook-main').length;
    const sent = sendToNotebook({ workspaceId: ws.id, notebookId: 'notebook-main' });
    expect(sent?.notebookId).toBe('notebook-main');
    expect(listRecordsOf('notebook-main')).toHaveLength(before + 1);
    expect(listRecordsOf('notebook-main')[0]!.title).toContain('阅读笔记');
    // 不存在的笔记本拒绝
    expect(sendToNotebook({ workspaceId: ws.id, notebookId: 'ghost' })).toBeNull();
  });
});

describe('reading-store 演示数据', () => {
  it('loadDemoReading 幂等且要素齐全', () => {
    loadDemoReading();
    loadDemoReading();
    expect(readWorkspaces().some((item) => item.id === 'demo-reading-ws')).toBe(true);
    expect(readMaterials().filter((item) => item.id.startsWith('demo-reading-mat-'))).toHaveLength(2);
    expect(readAnnotations('demo-reading-mat-a')).toHaveLength(1);
    expect(readBookmarks('demo-reading-mat-a')).toHaveLength(1);
    expect(readSessions('demo-reading-ws')).toHaveLength(1);
    // 未分配材料在库中存在
    expect(readMaterials().some((item) => item.workspaceIds.length === 0)).toBe(true);
  });
});
