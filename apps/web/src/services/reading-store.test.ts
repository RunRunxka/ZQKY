import { beforeEach, describe, expect, it } from 'vitest';
import {
  addAnnotation,
  addBookmark,
  addMaterialToWorkspace,
  appendMessage,
  completeMaterialIngest,
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
  saveSessionDraft,
  sendToNotebook,
  simulateCompanionReply,
  updateMaterialStatus,
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

  it('R32: 非文本材料需文件名、初始排队；状态更新与解析完成写入', () => {
    expect(() =>
      createMaterial({ title: '无文件名', sourceKind: 'pdf', filename: '  ' }),
    ).toThrow(/模拟导入需要提供文件名/);
    const material = createMaterial({
      title: '模拟 PDF',
      sourceKind: 'pdf',
      filename: '样例.pdf',
      status: 'queued',
      extractor: 'pdf-simulated',
    });
    expect(material.status).toBe('queued');
    expect(material.text).toBe('');
    expect(updateMaterialStatus(material.id, 'processing', '解析中')?.status).toBe('processing');
    const done = completeMaterialIngest(material.id, '【模拟解析产物】样例');
    expect(done?.status).toBe('ready');
    expect(readMaterials()[0]!.charCount).toBe('【模拟解析产物】样例'.length);
    expect(readMaterials()[0]!.text).toContain('模拟解析产物');
  });

  it('R32: 旧数据无 status 字段读取时归一化为 ready', () => {
    const material = createMaterial({ title: '旧材料', text: '正文' });
    const raw = window.localStorage.getItem('zhiqikeyuan:reading-materials')!;
    const list = JSON.parse(raw) as Array<Record<string, unknown>>;
    delete list[0]!.status;
    window.localStorage.setItem('zhiqikeyuan:reading-materials', JSON.stringify(list));
    expect(readMaterials()[0]!.id).toBe(material.id);
    expect(readMaterials()[0]!.status).toBe('ready');
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

  it('R32: saveSessionDraft 按会话保存草稿与引用，切会话互不影响', () => {
    const ws = createWorkspace('草稿集合');
    const a = createSession(ws.id, null);
    const b = createSession(ws.id, null);
    saveSessionDraft(a.id, '会话 A 的草稿', '选中文本 A');
    saveSessionDraft(b.id, '会话 B 的草稿', null);
    expect(getSession(a.id)?.draft).toBe('会话 A 的草稿');
    expect(getSession(a.id)?.draftQuote).toBe('选中文本 A');
    expect(getSession(b.id)?.draft).toBe('会话 B 的草稿');
    expect(getSession(b.id)?.draftQuote).toBeNull();
    // 幂等：相同内容不产生额外写入（返回同一对象）
    expect(saveSessionDraft(b.id, '会话 B 的草稿', null)?.draft).toBe('会话 B 的草稿');
    // 发送消息不丢草稿字段（appendMessage 保留会话其余字段）
    appendMessage(a.id, { role: 'user', content: '问题' });
    expect(getSession(a.id)?.draft).toBe('会话 A 的草稿');
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

  it('R26: 载入演示保留既有用户批注/书签/会话（内容与关联不丢）', () => {
    const material = createMaterial({ title: '用户材料', text: '用户笔记原文' });
    const workspace = createWorkspace('用户集合');
    const annotation = addAnnotation({ materialId: material.id, kind: 'note', quote: material.text, note: '不能丢失' });
    const bookmark = addBookmark(material.id, 'p-0', '用户书签');
    const session = createSession(workspace.id, material.id);
    appendMessage(session.id, { role: 'user', content: '我的问题' });
    const savedSession = readSessions().find((item) => item.id === session.id);
    loadDemoReading();
    expect(readAnnotations()).toContainEqual(annotation);
    expect(readBookmarks()).toContainEqual(bookmark);
    expect(readSessions()).toContainEqual(savedSession);
    // 演示条目同时补齐
    expect(readMaterials().some((item) => item.id === 'demo-reading-mat-a')).toBe(true);
  });

  it('R26: 删除演示集合后再载入不产生重复材料身份', () => {
    loadDemoReading();
    deleteWorkspace('demo-reading-ws');
    loadDemoReading();
    const ids = readMaterials().map((item) => item.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('R26: 演示批注携带精确定位段，可唯一定位', () => {
    loadDemoReading();
    const [demo] = readAnnotations('demo-reading-mat-a');
    expect(demo?.segments).toEqual([{ locator: 'p-6', start: 0, end: demo!.quote.length }]);
  });
});

describe('reading-store 存储保护（R27）', () => {
  const MATERIALS_KEY = 'zhiqikeyuan:reading-materials';
  const ANNOTATIONS_KEY = 'zhiqikeyuan:reading-annotations';
  const WORKSPACES_KEY = 'zhiqikeyuan:reading-workspaces';
  const SESSIONS_KEY = 'zhiqikeyuan:reading-sessions';

  /**
   * 模拟写失败：把 window.localStorage 换成对指定键抛 QuotaExceededError 的替身。
   * （本环境 Storage 方法在原型上，vi.spyOn 实例拦截不生效；run 结束后恢复原对象。）
   */
  function withWriteFailure(blockedKey: string, run: () => void): void {
    const real = window.localStorage;
    const fake = {
      getItem: (key: string) => real.getItem(key),
      setItem: (key: string, value: string) => {
        if (key === blockedKey) throw new DOMException('QuotaExceededError', 'QuotaExceededError');
        real.setItem(key, value);
      },
      removeItem: (key: string) => real.removeItem(key),
      clear: () => real.clear(),
      key: (index: number) => real.key(index),
      get length() {
        return real.length;
      },
    };
    Object.defineProperty(window, 'localStorage', { configurable: true, get: () => fake });
    try {
      run();
    } finally {
      Object.defineProperty(window, 'localStorage', { configurable: true, value: real });
    }
  }

  it('R27: 损坏 JSON 阻止写入并保留原始字节', () => {
    const damaged = '[{"id":"precious","text":"recoverable"}';
    window.localStorage.setItem(MATERIALS_KEY, damaged);
    expect(() => createMaterial({ title: '新材料', text: '新正文' })).toThrow(/已损坏/);
    expect(window.localStorage.getItem(MATERIALS_KEY)).toBe(damaged);
  });

  it('R27: 非数组格式异常报错而非当作空库', () => {
    const broken = '{"id":"not-an-array"}';
    window.localStorage.setItem(MATERIALS_KEY, broken);
    expect(() => readMaterials()).toThrow(/格式异常/);
    expect(() => loadDemoReading()).toThrow(/格式异常/);
    expect(window.localStorage.getItem(MATERIALS_KEY)).toBe(broken);
  });

  it('R27: 键不存在才初始化为空（未写入前无键）', () => {
    expect(window.localStorage.getItem(MATERIALS_KEY)).toBeNull();
    expect(readMaterials()).toHaveLength(0);
  });

  it('R27: 多键级联删除在中途失败时整体回滚（deleteMaterial）', () => {
    loadDemoReading();
    const beforeMaterials = window.localStorage.getItem(MATERIALS_KEY);
    const beforeWorkspaces = window.localStorage.getItem(WORKSPACES_KEY);
    const beforeAnnotations = window.localStorage.getItem(ANNOTATIONS_KEY);
    withWriteFailure(WORKSPACES_KEY, () => {
      expect(() => deleteMaterial('demo-reading-mat-a')).toThrow(/已回滚/);
    });
    expect(window.localStorage.getItem(MATERIALS_KEY)).toBe(beforeMaterials);
    expect(window.localStorage.getItem(WORKSPACES_KEY)).toBe(beforeWorkspaces);
    expect(window.localStorage.getItem(ANNOTATIONS_KEY)).toBe(beforeAnnotations);
  });

  it('R27: 多键级联删除在中途失败时整体回滚（deleteWorkspace）', () => {
    loadDemoReading();
    const beforeMaterials = window.localStorage.getItem(MATERIALS_KEY);
    const beforeWorkspaces = window.localStorage.getItem(WORKSPACES_KEY);
    withWriteFailure(SESSIONS_KEY, () => {
      expect(() => deleteWorkspace('demo-reading-ws')).toThrow(/已回滚/);
    });
    expect(window.localStorage.getItem(MATERIALS_KEY)).toBe(beforeMaterials);
    expect(window.localStorage.getItem(WORKSPACES_KEY)).toBe(beforeWorkspaces);
    // 未回滚路径不受影响：正常删除仍成功
    expect(deleteWorkspace('demo-reading-ws')).toBe(true);
  });
});
