'use client';
import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  ArrowLeft,
  Bookmark,
  Highlighter,
  ListTree,
  NotebookPen,
  Pencil,
  Plus,
  Send,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import { listNotebooks } from '@/services/notebook-store';
import {
  ReadingValidationError,
  activateMaterial,
  addAnnotation,
  addBookmark,
  addMaterialToWorkspace,
  appendMessage,
  createSession,
  deleteAnnotation,
  deleteBookmark,
  getSession,
  organizeNotes,
  readAnnotations,
  readBookmarks,
  readMaterials,
  readSessions,
  readWorkspaces,
  removeMaterialFromWorkspace,
  renameWorkspace,
  saveReadingPosition,
  sendToNotebook,
  simulateCompanionReply,
  subscribeReading,
  type ReadingAnnotation,
  type ReadingBookmark,
  type ReadingMaterial,
  type ReadingSession,
  type ReadingWorkspace,
} from '@/services/reading-store';
import '@/features/space/styles/space.css';
import '@/features/reading/reading.css';

/** 会话 id 提取（对照参考 readingSessionIdFromPath） */
export function readingSessionIdFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/reading\/[^/]+\/sessions\/([^/?#]+)/);
  return match ? match[1]! : null;
}

const MARK_COLORS: Record<string, string> = {
  yellow: 'rgba(250, 204, 21, 0.55)',
  green: 'rgba(74, 222, 128, 0.45)',
  blue: 'rgba(96, 165, 250, 0.45)',
  pink: 'rgba(244, 114, 182, 0.45)',
  purple: 'rgba(192, 132, 252, 0.45)',
};

export function ReadingWorkspaceView() {
  const params = useParams<{ workspaceId?: string; sessionId?: string }>();
  const workspaceId = params?.workspaceId;
  const routeSessionId = params?.sessionId ?? null;
  if (!workspaceId) return null;
  return <WorkspaceView workspaceId={workspaceId} routeSessionId={routeSessionId} />;
}

function WorkspaceView({ workspaceId, routeSessionId }: { workspaceId: string; routeSessionId: string | null }) {
  const [workspaces, setWorkspaces] = useState<ReadingWorkspace[] | null>(null);
  const [materials, setMaterials] = useState<ReadingMaterial[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [addingMaterial, setAddingMaterial] = useState(false);
  const [organized, setOrganized] = useState<{ title: string; markdown: string } | null>(null);
  const [sendingNotebook, setSendingNotebook] = useState(false);
  const [courseScope, setCourseScope] = useState<string | null>(null);
  const [navOpen, setNavOpen] = useState(true);

  const refresh = useCallback(() => {
    try {
      setWorkspaces(readWorkspaces());
      setMaterials(readMaterials());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '阅读数据无法读取，原数据未修改。');
    }
  }, []);

  useEffect(() => {
    refresh();
    return subscribeReading(refresh);
  }, [refresh]);

  // ?course= 作用域标记（参考经 useCourseScope 贯通；目标仅展示作用域，会话课程标记未接入）
  useEffect(() => {
    const course = new URLSearchParams(window.location.search).get('course');
    setCourseScope(course);
  }, []);

  const workspace = useMemo(
    () => workspaces?.find((item) => item.id === workspaceId) ?? null,
    [workspaces, workspaceId],
  );

  if (workspaces !== null && !workspace) {
    return (
      <div className="space-page">
        <div className="space-empty" style={{ marginTop: 80 }}>
          <strong>阅读集合不存在或已被删除</strong>
          <span>它可能已被删除，或链接有误。</span>
          <Link className="space-button" href="/reading">
            <ArrowLeft size={14} />
            返回沉浸阅读
          </Link>
        </div>
      </div>
    );
  }
  if (!workspace) {
    return (
      <div className="space-page">
        <div className="space-banner" style={{ marginTop: 80 }}>
          正在读取阅读集合…
        </div>
      </div>
    );
  }

  const tabs = workspace.tabs
    .map((tab) => materials.find((item) => item.id === tab.materialId))
    .filter((item): item is ReadingMaterial => Boolean(item));
  const activeMaterial = tabs.find((item) => item.id === workspace.activeMaterialId) ?? tabs[0] ?? null;

  function switchMaterial(materialId: string) {
    activateMaterial(workspaceId, materialId);
  }

  return (
    <div className="space-page">
      <header className="space-header">
        <div className="space-header-row">
          <Link className="space-back" href="/reading">
            <ArrowLeft size={16} />
            返回沉浸阅读
          </Link>
          <div className="space-card-actions">
            <button className="space-button" onClick={() => setNavOpen((current) => !current)}>
              <ListTree size={14} />
              {navOpen ? '收起导航' : '展开导航'}
            </button>
            <button
              className="space-button"
              onClick={() => {
                if (!activeMaterial) return;
                setOrganized(organizeNotes(workspaceId));
              }}
            >
              <Sparkles size={14} />
              整理笔记
            </button>
            <button className="space-button" onClick={() => setSendingNotebook(true)}>
              <NotebookPen size={14} />
              发到笔记本
            </button>
          </div>
        </div>
        <h1>
          {workspace.title}
          <button
            className="icon-button"
            aria-label="重命名集合"
            style={{ marginLeft: 8, verticalAlign: 'middle' }}
            onClick={() => setRenaming(true)}
          >
            <Pencil size={13} />
          </button>
        </h1>
        <p className="space-description">
          {workspace.description || '三栏阅读工作区：导航（大纲/书签/批注）· 正文 · 伴生助手（模拟）。'}
          {courseScope && (
            <span className="space-chip" style={{ marginLeft: 8 }}>
              课程作用域 {courseScope}（会话课程标记未接入）
            </span>
          )}
        </p>
      </header>
      {notice && (
        <div className="space-content">
          <div className="space-banner info" role="status">
            {notice}
          </div>
        </div>
      )}
      {error && (
        <div className="space-content">
          <div className="space-banner error" role="alert">
            {error}
          </div>
        </div>
      )}
      <main className="space-content">
        {/* 材料 Tab 条 */}
        <div className="space-tabs" role="tablist" aria-label="材料切换" style={{ marginBottom: 14 }}>
          {tabs.map((material) => (
            <button
              key={material.id}
              role="tab"
              aria-selected={activeMaterial?.id === material.id}
              className={activeMaterial?.id === material.id ? 'current' : ''}
              onClick={() => switchMaterial(material.id)}
            >
              {material.title}
              <X
                size={11}
                aria-label={`移除材料 ${material.title}`}
                style={{ marginLeft: 6 }}
                onClick={(event) => {
                  event.stopPropagation();
                  removeMaterial(workspaceId, material.id);
                }}
              />
            </button>
          ))}
          <button onClick={() => setAddingMaterial(true)} aria-label="添加材料">
            <Plus size={13} />
            添加材料
          </button>
          <button onClick={() => routerPush('/reading/materials')}>材料库…</button>
        </div>

        <div className="reading-layout" style={{ ['--companion-width' as string]: '340px' }}>
          {navOpen && <SourceNavigator activeMaterial={activeMaterial} onNotice={setNotice} />}
          <ReaderPane
            material={activeMaterial}
            onNotice={setNotice}
            onAskAi={(quote) => window.dispatchEvent(new CustomEvent('zqky:reading-ask', { detail: quote }))}
          />
          <CompanionPane
            workspaceId={workspaceId}
            routeSessionId={routeSessionId}
            activeMaterial={activeMaterial}
            sessionError={sessionError}
            onSessionError={setSessionError}
          />
        </div>
      </main>

      {renaming && (
        <RenameForm
          workspace={workspace}
          onClose={() => setRenaming(false)}
          onSaved={(title) => {
            setRenaming(false);
            setNotice(`已重命名为「${title}」。`);
          }}
        />
      )}
      {addingMaterial && (
        <AddMaterialForm
          workspace={workspace}
          materials={materials}
          onClose={() => setAddingMaterial(false)}
          onAdded={(title) => {
            setAddingMaterial(false);
            setNotice(`已添加材料「${title}」。`);
          }}
        />
      )}
      {organized && (
        <Modal title="整理笔记（模拟整理）" onClose={() => setOrganized(null)}>
          <p className="space-footnote" style={{ marginTop: 0 }}>
            本地聚合批注生成（未接入模型整理）；可用「发到笔记本」保存。
          </p>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, margin: '0 0 10px' }}>{organized.markdown}</pre>
          <div className="space-form-footer">
            <button className="space-button" onClick={() => setOrganized(null)}>
              关闭
            </button>
          </div>
        </Modal>
      )}
      {sendingNotebook && (
        <SendNotebookForm
          workspaceId={workspaceId}
          onClose={() => setSendingNotebook(false)}
          onSent={(message) => {
            setSendingNotebook(false);
            setNotice(message);
          }}
        />
      )}
    </div>
  );
}

function routerPush(path: string) {
  window.history.pushState(null, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

function removeMaterial(workspaceId: string, materialId: string) {
  if (window.confirm('从集合移除该材料？材料保留在材料库中。')) {
    removeMaterialFromWorkspace(workspaceId, materialId);
  }
}

// ===== 左栏：大纲 / 书签 / 批注导航 =====

function SourceNavigator({
  activeMaterial,
  onNotice,
}: {
  activeMaterial: ReadingMaterial | null;
  onNotice: (message: string) => void;
}) {
  const [tab, setTab] = useState<'outline' | 'bookmarks' | 'annotations'>('outline');
  const [annotations, setAnnotations] = useState<ReadingAnnotation[]>([]);
  const [bookmarks, setBookmarks] = useState<ReadingBookmark[]>([]);

  useEffect(() => {
    const refresh = () => {
      setAnnotations(activeMaterial ? readAnnotations(activeMaterial.id) : []);
      setBookmarks(activeMaterial ? readBookmarks(activeMaterial.id) : []);
    };
    refresh();
    return subscribeReading(refresh);
  }, [activeMaterial]);

  const outline = useMemo(() => {
    if (!activeMaterial) return [];
    return activeMaterial.text
      .split('\n')
      .map((line, idx) => ({ line, idx }))
      .filter(({ line }) => /^#{1,4}\s+\S/.test(line))
      .map(({ line, idx }) => ({
        level: line.match(/^#+/)![0].length,
        text: line.replace(/^#+\s*/, ''),
        locator: `h-${idx}`,
      }));
  }, [activeMaterial]);

  function jumpTo(locator: string) {
    document.querySelector(`[data-loc="${locator}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  return (
    <aside className="reading-pane" style={{ padding: '12px 14px', maxHeight: 640, overflowY: 'auto' }} aria-label="阅读导航">
      <div className="space-tabs" role="tablist" aria-label="导航页签" style={{ marginBottom: 10 }}>
        <button role="tab" aria-selected={tab === 'outline'} className={tab === 'outline' ? 'current' : ''} onClick={() => setTab('outline')}>
          大纲
        </button>
        <button role="tab" aria-selected={tab === 'bookmarks'} className={tab === 'bookmarks' ? 'current' : ''} onClick={() => setTab('bookmarks')}>
          书签（{bookmarks.length}）
        </button>
        <button role="tab" aria-selected={tab === 'annotations'} className={tab === 'annotations' ? 'current' : ''} onClick={() => setTab('annotations')}>
          批注（{annotations.length}）
        </button>
      </div>
      {tab === 'outline' &&
        (outline.length === 0 ? (
          <p className="space-footnote">本材料没有“# 标题”行，无法生成大纲。</p>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, fontSize: 13 }}>
            {outline.map((item) => (
              <li key={item.locator} style={{ paddingLeft: (item.level - 1) * 12, marginBottom: 4 }}>
                <button className="space-button" style={{ width: '100%', justifyContent: 'flex-start' }} onClick={() => jumpTo(item.locator)}>
                  {item.text}
                </button>
              </li>
            ))}
          </ul>
        ))}
      {tab === 'bookmarks' &&
        (bookmarks.length === 0 ? (
          <p className="space-footnote">暂无书签。在正文中选中文字后可添加书签。</p>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, fontSize: 13 }}>
            {bookmarks.map((bookmark) => (
              <li key={bookmark.bookmarkId} className="space-session-card" style={{ marginBottom: 6, padding: '6px 8px' }}>
                <div className="space-session-top">
                  <Bookmark size={13} aria-hidden />
                  <button className="space-button" style={{ flex: 1, justifyContent: 'flex-start' }} onClick={() => jumpTo(bookmark.locator)}>
                    {bookmark.label}
                  </button>
                  <button
                    className="icon-button"
                    aria-label={`删除书签 ${bookmark.label}`}
                    onClick={() => {
                      deleteBookmark(bookmark.bookmarkId);
                      onNotice('书签已删除。');
                    }}
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ))}
      {tab === 'annotations' &&
        (annotations.length === 0 ? (
          <p className="space-footnote">暂无批注。选中正文文字后可高亮或写笔记。</p>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, fontSize: 13 }}>
            {annotations.map((annotation) => (
              <li key={annotation.annotationId} className="space-session-card" style={{ marginBottom: 6, padding: '6px 8px' }}>
                <div className="space-session-top">
                  <Highlighter size={13} aria-hidden style={{ color: annotation.kind === 'note' ? '#2563eb' : undefined }} />
                  <button
                    className="space-button"
                    style={{ flex: 1, justifyContent: 'flex-start' }}
                    onClick={() => {
                      const el = document.querySelector(`[data-annotation-id="${annotation.annotationId}"]`);
                      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                      else onNotice('该批注引用的原文段落已被修改，无法定位。');
                    }}
                  >
                    {annotation.quote.slice(0, 24)}
                    {annotation.quote.length > 24 ? '…' : ''}
                  </button>
                  <button
                    className="icon-button"
                    aria-label="删除批注"
                    onClick={() => {
                      deleteAnnotation(annotation.annotationId);
                      onNotice('批注已删除。');
                    }}
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
                {annotation.note && <p style={{ margin: '4px 0 0', color: 'rgba(0,0,0,0.65)' }}>{annotation.note}</p>}
              </li>
            ))}
          </ul>
        ))}
    </aside>
  );
}

// ===== 中栏：文本阅读器（标题层级渲染 + 批注高亮 + 选区浮条） =====

interface ReaderBlock {
  kind: 'heading' | 'para';
  level: number;
  text: string;
  locator: string;
}

function parseBlocks(material: ReadingMaterial): ReaderBlock[] {
  return material.text
    .split('\n')
    .map((line, idx) => {
      const heading = line.match(/^(#{1,4})\s+(.*)$/);
      if (heading) return { kind: 'heading' as const, level: heading[1]!.length, text: heading[2]!, locator: `h-${idx}` };
      return { kind: 'para' as const, level: 0, text: line, locator: `p-${idx}` };
    })
    .filter((block) => block.text.trim().length > 0);
}

/** 按批注 quote 把段落文本切分为普通文本与高亮 mark */
function renderMarked(text: string, annotations: ReadingAnnotation[]) {
  let parts: Array<string | ReadingAnnotation> = [text];
  for (const annotation of annotations) {
    parts = parts.flatMap((part) => {
      if (typeof part !== 'string' || !part.includes(annotation.quote)) return [part];
      const idx = part.indexOf(annotation.quote);
      return [part.slice(0, idx), annotation, part.slice(idx + annotation.quote.length)].filter(
        (piece) => (typeof piece === 'string' ? piece.length > 0 : true),
      );
    });
  }
  return parts.map((part, idx) =>
    typeof part === 'string' ? (
      part
    ) : (
      <mark
        key={`${part.annotationId}-${idx}`}
        data-annotation-id={part.annotationId}
        className="reading-mark"
        style={{ background: MARK_COLORS[part.color] ?? MARK_COLORS.yellow }}
        title={part.note || undefined}
      >
        {part.quote}
      </mark>
    ),
  );
}

function ReaderPane({
  material,
  onNotice,
  onAskAi,
}: {
  material: ReadingMaterial | null;
  onNotice: (message: string) => void;
  onAskAi: (quote: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const restoredRef = useRef(false);
  const saveTimerRef = useRef<number | null>(null);
  const [annotations, setAnnotations] = useState<ReadingAnnotation[]>([]);
  const [selection, setSelection] = useState<{ quote: string; locator: string; top: number; left: number } | null>(null);
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteText, setNoteText] = useState('');

  useEffect(() => {
    const refresh = () => setAnnotations(material ? readAnnotations(material.id) : []);
    refresh();
    return subscribeReading(refresh);
  }, [material]);

  // 恢复上次阅读位置（材料切换时重置）
  useEffect(() => {
    restoredRef.current = false;
  }, [material?.id]);
  useEffect(() => {
    if (!material || restoredRef.current) return;
    restoredRef.current = true;
    if (material.positionPct > 0) {
      requestAnimationFrame(() => {
        const el = containerRef.current;
        if (el) el.scrollTop = ((el.scrollHeight - el.clientHeight) * material.positionPct) / 100;
      });
    }
  }, [material]);

  const blocks = useMemo(() => (material ? parseBlocks(material) : []), [material]);

  function handleScroll() {
    if (saveTimerRef.current !== null) return;
    saveTimerRef.current = window.setTimeout(() => {
      saveTimerRef.current = null;
      const el = containerRef.current;
      if (!el || !material) return;
      const pct = (el.scrollTop / Math.max(1, el.scrollHeight - el.clientHeight)) * 100;
      saveReadingPosition(material.id, pct);
    }, 300);
  }

  function clearSelection() {
    window.getSelection()?.removeAllRanges();
    setSelection(null);
    setNoteOpen(false);
    setNoteText('');
  }

  function handleMouseUp(event: ReactMouseEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest('.reading-selection-bar')) return;
    const sel = window.getSelection();
    const quote = sel?.toString().trim() ?? '';
    if (!sel || sel.isCollapsed || !quote || !containerRef.current) {
      if (selection) clearSelection();
      return;
    }
    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    const containerRect = containerRef.current.getBoundingClientRect();
    let locator = '';
    let node: Node | null = sel.anchorNode;
    while (node && node !== containerRef.current) {
      if (node instanceof HTMLElement && node.dataset.loc) {
        locator = node.dataset.loc;
        break;
      }
      node = node.parentNode;
    }
    setSelection({
      quote,
      locator,
      top: rect.bottom - containerRect.top + 8,
      left: Math.max(8, Math.min(rect.left - containerRect.left, containerRect.width - 290)),
    });
    setNoteOpen(false);
    setNoteText('');
  }

  if (!material) {
    return (
      <div className="reading-pane" style={{ display: 'grid', placeItems: 'center' }}>
        <div className="space-empty">
          <strong>还没有打开的材料</strong>
          <span>用上方「添加材料」或「材料库…」把文本材料加入本集合。</span>
        </div>
      </div>
    );
  }

  function addHighlight(color: ReadingAnnotation['color']) {
    if (!material || !selection) return;
    try {
      addAnnotation({ materialId: material.id, kind: 'highlight', color, quote: selection.quote });
      onNotice('已添加高亮。');
    } catch (cause) {
      onNotice(cause instanceof ReadingValidationError ? cause.message : '添加高亮失败，请重试。');
    }
    clearSelection();
  }

  function saveNote(event: ReactMouseEvent | React.FormEvent) {
    event.preventDefault();
    if (!material || !selection) return;
    try {
      addAnnotation({ materialId: material.id, kind: 'note', quote: selection.quote, note: noteText });
      onNotice('已保存批注笔记。');
    } catch (cause) {
      onNotice(cause instanceof ReadingValidationError ? cause.message : '保存笔记失败，请重试。');
    }
    clearSelection();
  }

  return (
    <div
      ref={containerRef}
      className="reading-pane"
      style={{ position: 'relative', maxHeight: 640, overflowY: 'auto' }}
      onScroll={handleScroll}
      onMouseUp={handleMouseUp}
    >
      <header style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 10 }}>
        <strong style={{ fontSize: 15 }}>{material.title}</strong>
        <span className="space-chip">{material.charCount} 字</span>
        <span className="space-chip">读到 {material.positionPct}%</span>
      </header>
      {blocks.map((block) =>
        block.kind === 'heading' ? (
          block.level === 1 ? (
            <h1 key={block.locator} data-loc={block.locator}>
              {block.text}
            </h1>
          ) : block.level === 2 ? (
            <h2 key={block.locator} data-loc={block.locator}>
              {block.text}
            </h2>
          ) : (
            <h3 key={block.locator} data-loc={block.locator}>
              {block.text}
            </h3>
          )
        ) : (
          <p key={block.locator} data-loc={block.locator}>
            {renderMarked(block.text, annotations)}
          </p>
        ),
      )}

      {selection && (
        <div className="reading-selection-bar" style={{ top: selection.top, left: selection.left }} role="menu" aria-label="选区操作" onMouseDown={(event) => event.preventDefault()}>
          <div className="reading-quote-block">{selection.quote.slice(0, 80)}{selection.quote.length > 80 ? '…' : ''}</div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <span className="space-footnote" style={{ margin: 0 }}>高亮：</span>
            {(Object.keys(MARK_COLORS) as Array<keyof typeof MARK_COLORS>).map((color) => (
              <button
                key={color}
                type="button"
                aria-label={`高亮（${color}）`}
                className="reading-mark"
                style={{ width: 18, height: 18, background: MARK_COLORS[color], border: '1px solid rgba(0,0,0,0.18)', borderRadius: '50%', padding: 0 }}
                onClick={() => addHighlight(color as ReadingAnnotation['color'])}
              />
            ))}
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="space-button" onClick={() => setNoteOpen((current) => !current)}>
              <Pencil size={12} />
              笔记
            </button>
            <button
              className="space-button"
              onClick={() => {
                onAskAi(selection.quote);
                clearSelection();
              }}
            >
              <Sparkles size={12} />
              问 AI
            </button>
            <button
              className="space-button"
              onClick={() => {
                if (!material) return;
                try {
                  addBookmark(material.id, selection.locator || 'p-0', selection.quote.slice(0, 24));
                  onNotice('已添加书签。');
                } catch (cause) {
                  onNotice(cause instanceof ReadingValidationError ? cause.message : '添加书签失败，请重试。');
                }
                clearSelection();
              }}
            >
              <Bookmark size={12} />
              书签
            </button>
          </div>
          {noteOpen && (
            <form onSubmit={saveNote} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <textarea
                value={noteText}
                aria-label="批注笔记内容"
                placeholder="写下你的笔记…"
                style={{ minHeight: 54, fontSize: 13 }}
                onChange={(event) => setNoteText(event.target.value)}
              />
              <button type="submit" className="space-button primary">
                保存笔记
              </button>
            </form>
          )}
        </div>
      )}
    </div>
  );
}

// ===== 右栏：伴生助手（本地模拟回复） =====

function CompanionPane({
  workspaceId,
  routeSessionId,
  activeMaterial,
  sessionError,
  onSessionError,
}: {
  workspaceId: string;
  routeSessionId: string | null;
  activeMaterial: ReadingMaterial | null;
  sessionError: string | null;
  onSessionError: (message: string | null) => void;
}) {
  const [sessions, setSessions] = useState<ReadingSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [pendingQuote, setPendingQuote] = useState<string | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const routeSessionRef = useRef<string | null>(null);

  useEffect(() => {
    const refresh = () => {
      const list = readSessions(workspaceId);
      setSessions(list);
      setActiveId((current) => {
        if (current && list.some((item) => item.id === current)) return current;
        const routeValid = routeSessionRef.current && list.some((item) => item.id === routeSessionRef.current) ? routeSessionRef.current : null;
        return routeValid ?? list[0]?.id ?? null;
      });
    };
    refresh();
    return subscribeReading(refresh);
  }, [workspaceId]);

  // 路由会话 id 首次同步（深链进入时定位会话）
  useEffect(() => {
    routeSessionRef.current = routeSessionId;
    if (!routeSessionId) return;
    const list = readSessions(workspaceId);
    if (list.some((item) => item.id === routeSessionId)) {
      setActiveId(routeSessionId);
    } else if (list.length > 0) {
      onSessionError('链接指向的会话不存在，已切换到最近会话。');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeSessionId, workspaceId]);

  // 「问 AI」事件：选中文本预填输入框
  useEffect(() => {
    const handler = (event: Event) => {
      const quote = (event as CustomEvent<string>).detail;
      if (typeof quote === 'string' && quote.trim()) {
        setDraft(quote.trim());
        setPendingQuote(quote.trim());
      }
    };
    window.addEventListener('zqky:reading-ask', handler);
    return () => window.removeEventListener('zqky:reading-ask', handler);
  }, []);

  const active = sessions.find((item) => item.id === activeId) ?? null;
  const messageCount = active?.messages.length ?? 0;

  // 新消息自动滚到底部
  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [activeId, messageCount]);

  function focusSession(sessionId: string) {
    setActiveId(sessionId);
    onSessionError(null);
    window.history.replaceState(null, '', `/reading/${encodeURIComponent(workspaceId)}/sessions/${sessionId}`);
  }

  function newSession() {
    const session = createSession(workspaceId, activeMaterial?.id ?? null);
    focusSession(session.id);
  }

  function send() {
    const content = draft.trim();
    if (!content) return;
    let sessionId = activeId;
    if (!sessionId || !getSession(sessionId)) {
      const session = createSession(workspaceId, activeMaterial?.id ?? null);
      sessionId = session.id;
      window.history.replaceState(null, '', `/reading/${encodeURIComponent(workspaceId)}/sessions/${sessionId}`);
    } else {
      setActiveId(sessionId);
    }
    onSessionError(null);
    const quote = pendingQuote ?? undefined;
    appendMessage(sessionId!, { role: 'user', content, ...(quote ? { quote } : {}) });
    setDraft('');
    setPendingQuote(null);
    const reply = simulateCompanionReply({ materialTitle: activeMaterial?.title ?? null, userText: content, quote });
    appendMessage(sessionId!, { role: 'assistant', content: reply });
  }

  return (
    <aside className="reading-companion" aria-label="伴生助手（模拟）">
      <header style={{ padding: '10px 12px', borderBottom: '1px solid rgba(0,0,0,0.08)', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <strong style={{ fontSize: 14 }}>伴生助手</strong>
          <span className="space-chip">模拟回复</span>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <select
            aria-label="阅读会话选择"
            value={activeId ?? ''}
            style={{ flex: 1, fontSize: 13 }}
            onChange={(event) => {
              if (event.target.value) focusSession(event.target.value);
            }}
          >
            {sessions.length === 0 && <option value="">（暂无会话）</option>}
            {sessions.map((session) => (
              <option key={session.id} value={session.id}>
                {session.title}
              </option>
            ))}
          </select>
          <button className="space-button" onClick={newSession} aria-label="新建阅读会话">
            <Plus size={13} />
            新会话
          </button>
        </div>
      </header>
      {sessionError && (
        <div className="space-banner error" role="alert" style={{ margin: '8px 12px 0' }}>
          {sessionError}
        </div>
      )}
      <div className="reading-companion-body" ref={bodyRef}>
        {!active || active.messages.length === 0 ? (
          <p className="space-footnote" style={{ margin: 0 }}>
            伴生助手为本地模拟（未接入模型）：提问、或选中正文「问 AI」。回复均为模板生成并标注【模拟回复】。
          </p>
        ) : (
          active.messages.map((message) => (
            <div key={message.id} className={`reading-msg ${message.role}`}>
              {message.quote && <div className="reading-quote-block" style={{ marginBottom: 6 }}>{message.quote.slice(0, 60)}{message.quote.length > 60 ? '…' : ''}</div>}
              {message.content}
            </div>
          ))
        )}
      </div>
      <div className="reading-composer">
        <textarea
          value={draft}
          aria-label="向伴生助手提问"
          placeholder={pendingQuote ? '已携带选中文本，输入你的问题…' : '向伴生助手提问…'}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              send();
            }
          }}
        />
        <button className="space-button primary" onClick={send} aria-label="发送提问" disabled={!draft.trim()}>
          <Send size={14} />
          发送
        </button>
      </div>
    </aside>
  );
}

// ===== 弹窗：重命名 / 添加材料 / 发到笔记本 =====

function RenameForm({
  workspace,
  onClose,
  onSaved,
}: {
  workspace: ReadingWorkspace;
  onClose: () => void;
  onSaved: (title: string) => void;
}) {
  const [title, setTitle] = useState(workspace.title);
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal title="重命名阅读集合" onClose={onClose}>
      <form
        className="space-form"
        onSubmit={(event) => {
          event.preventDefault();
          try {
            const updated = renameWorkspace(workspace.id, title);
            if (updated) onSaved(updated.title);
            else setError('集合不存在或已被删除。');
          } catch (cause) {
            setError(cause instanceof ReadingValidationError ? cause.message : '保存失败，请重试。');
          }
        }}
      >
        <label>
          名称
          <input value={title} required maxLength={60} onChange={(event) => setTitle(event.target.value)} />
        </label>
        {error && (
          <p className="space-form-error" role="alert">
            {error}
          </p>
        )}
        <div className="space-form-footer">
          <button type="button" className="space-button" onClick={onClose}>
            取消
          </button>
          <button type="submit" className="space-button primary">
            保存
          </button>
        </div>
      </form>
    </Modal>
  );
}

function AddMaterialForm({
  workspace,
  materials,
  onClose,
  onAdded,
}: {
  workspace: ReadingWorkspace;
  materials: ReadingMaterial[];
  onClose: () => void;
  onAdded: (title: string) => void;
}) {
  const candidates = materials.filter((item) => !workspace.tabs.some((tab) => tab.materialId === item.id));
  return (
    <Modal title="添加材料到集合" onClose={onClose}>
      {candidates.length === 0 ? (
        <div className="space-empty">
          <strong>没有可添加的材料</strong>
          <span>先到材料库新建文本材料或载入演示数据。</span>
          <div className="space-form-footer">
            <button className="space-button" onClick={onClose}>
              关闭
            </button>
            <button
              className="space-button primary"
              onClick={() => {
                onClose();
                routerPush('/reading/materials');
              }}
            >
              打开材料库
            </button>
          </div>
        </div>
      ) : (
        <ul className="space-session-list">
          {candidates.map((material) => (
            <li className="space-session-card" key={material.id}>
              <div className="space-session-top">
                <span className="space-session-title">{material.title}</span>
                <span className="space-chip">{material.charCount} 字</span>
                <button
                  className="space-button"
                  onClick={() => {
                    try {
                      addMaterialToWorkspace(workspace.id, material.id, true);
                      onAdded(material.title);
                    } catch (cause) {
                      onClose();
                      onAdded(cause instanceof ReadingValidationError ? cause.message : '添加失败，请重试。');
                    }
                  }}
                >
                  添加
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}

function SendNotebookForm({
  workspaceId,
  onClose,
  onSent,
}: {
  workspaceId: string;
  onClose: () => void;
  onSent: (message: string) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const notebooks = listNotebooks();
  return (
    <Modal title="整理笔记发到笔记本" onClose={onClose}>
      <p className="space-footnote" style={{ marginTop: 0 }}>
        把本集合批注的整理结果（本地模拟整理）作为一条记录写入所选笔记本；之后可在「笔记本」中查看。
      </p>
      {error && (
        <div className="space-banner error" role="alert">
          {error}
        </div>
      )}
      <ul className="space-session-list">
        {notebooks.map((notebook) => (
          <li className="space-session-card" key={notebook.id}>
            <div className="space-session-top">
              <span className="space-session-title">{notebook.name}</span>
              <button
                className="space-button"
                onClick={() => {
                  const result = sendToNotebook({ workspaceId, notebookId: notebook.id });
                  if (result) onSent(`已把整理笔记写入笔记本「${notebook.name}」（记录：${result.title}）。`);
                  else setError('写入失败：集合或笔记本不存在，请刷新后重试。');
                }}
              >
                写入
              </button>
            </div>
          </li>
        ))}
      </ul>
    </Modal>
  );
}
