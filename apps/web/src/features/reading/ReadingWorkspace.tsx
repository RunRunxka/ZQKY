'use client';
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent, type ReactElement } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
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
  Square,
  Trash2,
  X,
} from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import { AnswerMarkdown } from '@/features/chat/AnswerMarkdown';
import { createReadingCompanionService, type CompanionService } from '@/features/reading/companion-service';
import { listNotebooks } from '@/services/notebook-store';
import { simulateMaterialIngest } from '@/services/reading-ingest';
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
  saveSessionDraft,
  sendToNotebook,
  subscribeReading,
  updateMaterialStatus,
  type ReadingAnnotation,
  type ReadingAnnotationSegment,
  type ReadingBookmark,
  type ReadingMaterial,
  type ReadingSession,
  type ReadingWorkspace,
} from '@/services/reading-store';
import '@/features/space/styles/space.css';
import '@/features/chat/styles/chat.css';
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

const SOURCE_KIND_LABELS: Record<string, string> = {
  text: '文本',
  pdf: 'PDF',
  epub: 'EPUB',
  webpage: '网页',
  video: '视频',
  audio: '音频',
};

export function ReadingWorkspaceView() {
  const params = useParams<{ workspaceId?: string; sessionId?: string }>();
  const workspaceId = params?.workspaceId;
  const routeSessionId = params?.sessionId ?? null;
  if (!workspaceId) return null;
  return <WorkspaceView workspaceId={workspaceId} routeSessionId={routeSessionId} />;
}

function WorkspaceView({ workspaceId, routeSessionId }: { workspaceId: string; routeSessionId: string | null }) {
  const router = useRouter();
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
  // 移动端（<1280px）抽屉面板：导航/伴生收入抽屉，正文保持可见（对照参考移动布局）
  const [mobilePanel, setMobilePanel] = useState<'nav' | 'companion' | null>(null);
  // 伴生栏宽度（对照参考 companionWidth：默认 380、范围 300–640、本地持久化、1280px 分界可拖拽）
  const [companionWidth, setCompanionWidth] = useState(380);
  const [isDesktopWide, setIsDesktopWide] = useState(false);
  const dragStateRef = useRef<{ startX: number; startWidth: number } | null>(null);

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

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem('zhiqikeyuan:reader:companionWidth');
      const parsed = raw ? Number.parseInt(raw, 10) : NaN;
      if (Number.isFinite(parsed)) setCompanionWidth(Math.min(640, Math.max(300, parsed)));
    } catch {
      // 忽略本地读取失败，保持默认宽度
    }
    const mql = window.matchMedia('(min-width: 1280px)');
    const update = () => setIsDesktopWide(mql.matches);
    update();
    mql.addEventListener('change', update);
    return () => mql.removeEventListener('change', update);
  }, []);

  const persistCompanionWidth = useCallback((width: number) => {
    try {
      window.localStorage.setItem('zhiqikeyuan:reader:companionWidth', String(width));
    } catch {
      // 持久化失败不影响当前会话使用
    }
  }, []);

  function onHandlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (!isDesktopWide) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragStateRef.current = { startX: event.clientX, startWidth: companionWidth };
  }

  function onHandlePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragStateRef.current;
    if (!drag) return;
    const next = Math.min(640, Math.max(300, drag.startWidth + (drag.startX - event.clientX)));
    setCompanionWidth(next);
  }

  function onHandlePointerUp(event: ReactPointerEvent<HTMLDivElement>) {
    if (!dragStateRef.current) return;
    dragStateRef.current = null;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // 指针捕获不存在时忽略
    }
    persistCompanionWidth(companionWidth);
  }

  function onHandleKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (!isDesktopWide) return;
    const step = event.shiftKey ? 32 : 16;
    let next: number | null = null;
    if (event.key === 'ArrowLeft') next = Math.min(640, companionWidth + step);
    else if (event.key === 'ArrowRight') next = Math.max(300, companionWidth - step);
    if (next !== null) {
      event.preventDefault();
      setCompanionWidth(next);
      persistCompanionWidth(next);
    }
  }

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
            {isDesktopWide ? (
              <button className="space-button" onClick={() => setNavOpen((current) => !current)}>
                <ListTree size={14} />
                {navOpen ? '收起导航' : '展开导航'}
              </button>
            ) : (
              <>
                <button className="space-button" onClick={() => setMobilePanel('nav')} aria-label="打开导航面板">
                  <ListTree size={14} />
                  导航
                </button>
                <button className="space-button" onClick={() => setMobilePanel('companion')} aria-label="打开伴生助手面板">
                  <NotebookPen size={14} />
                  伴生
                </button>
              </>
            )}
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
          <button onClick={() => router.push('/reading/materials')}>材料库…</button>
        </div>

        <div
          className="reading-layout"
          style={{
            ['--companion-width' as string]: `${companionWidth}px`,
            ...(isDesktopWide
              ? {
                  gridTemplateColumns: navOpen
                    ? 'minmax(184px,230px) minmax(0,1fr) 5px var(--companion-width)'
                    : 'minmax(0,1fr) 5px var(--companion-width)',
                }
              : {}),
          }}
        >
          {navOpen && isDesktopWide && <SourceNavigator activeMaterial={activeMaterial} onNotice={setNotice} />}
          <ReaderPane
            material={activeMaterial}
            onNotice={setNotice}
            onAskAi={(quote) => window.dispatchEvent(new CustomEvent('zqky:reading-ask', { detail: quote }))}
          />
          {isDesktopWide && (
            <div
              className="reading-companion-drag"
              role="separator"
              aria-orientation="vertical"
              aria-label="调整伴生栏宽度"
              title="拖拽或用左右方向键调整伴生栏宽度"
              tabIndex={0}
              onPointerDown={onHandlePointerDown}
              onPointerMove={onHandlePointerMove}
              onPointerUp={onHandlePointerUp}
              onKeyDown={onHandleKeyDown}
            />
          )}
          {isDesktopWide && (
            <CompanionPane
              workspaceId={workspaceId}
              routeSessionId={routeSessionId}
              activeMaterial={activeMaterial}
              sessionError={sessionError}
              onSessionError={setSessionError}
            />
          )}
        </div>

        {!isDesktopWide && mobilePanel && (
          <div className="reading-drawer-backdrop" onClick={() => setMobilePanel(null)}>
            <aside
              className="reading-drawer"
              role="dialog"
              aria-label={mobilePanel === 'nav' ? '阅读导航' : '伴生助手（模拟）'}
              onClick={(event) => event.stopPropagation()}
            >
              {mobilePanel === 'nav' ? (
                <SourceNavigator activeMaterial={activeMaterial} onNotice={setNotice} />
              ) : (
                <CompanionPane
                  workspaceId={workspaceId}
                  routeSessionId={routeSessionId}
                  activeMaterial={activeMaterial}
                  sessionError={sessionError}
                  onSessionError={setSessionError}
                />
              )}
            </aside>
          </div>
        )}
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
          onOpenLibrary={() => router.push('/reading/materials')}
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
      try {
        setAnnotations(activeMaterial ? readAnnotations(activeMaterial.id) : []);
        setBookmarks(activeMaterial ? readBookmarks(activeMaterial.id) : []);
      } catch {
        // 存储损坏时由页面级错误横幅提示；导航保持已有数据
      }
    };
    refresh();
    return subscribeReading(refresh);
  }, [activeMaterial]);

  const placements = useMemo(
    () => (activeMaterial ? resolveAnnotationPlacements(activeMaterial, annotations) : new Map<string, AnnotationPlacement>()),
    [activeMaterial, annotations],
  );

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
                      const placement = placements.get(annotation.annotationId);
                      const el = document.querySelector(`[data-annotation-id="${annotation.annotationId}"]`);
                      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                      else if (placement?.status === 'ambiguous')
                        onNotice('该批注为旧格式且引用的原文出现多处，无法唯一定位；可删除后重新添加。');
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

/** 边界在块内的字符偏移：用 Range 文本长度计算，避免 mark 片段化 DOM 的节点偏移误差 */
function textOffsetWithin(block: HTMLElement, node: Node, offset: number): number {
  const range = document.createRange();
  range.selectNodeContents(block);
  try {
    range.setEnd(node, offset);
    return range.toString().length;
  } catch {
    return 0;
  }
}

/** 选区覆盖的块级定位段（含跨块；文档顺序，与 parseBlocks 的 locator 对应） */
function collectSelectionSegments(range: Range, container: HTMLElement): ReadingAnnotationSegment[] {
  const blocks = Array.from(container.querySelectorAll<HTMLElement>('[data-loc]'));
  const segments: ReadingAnnotationSegment[] = [];
  for (const block of blocks) {
    if (!range.intersectsNode(block)) continue;
    const textLength = block.textContent?.length ?? 0;
    let start = 0;
    let end = textLength;
    if (block.contains(range.startContainer)) start = textOffsetWithin(block, range.startContainer, range.startOffset);
    if (block.contains(range.endContainer)) end = textOffsetWithin(block, range.endContainer, range.endOffset);
    if (end > start) segments.push({ locator: block.dataset.loc!, start, end });
  }
  return segments;
}

/** 批注解析结果：ok=可精确定位；ambiguous=旧 quote-only 数据多处命中；missing=原文已不存在 */
interface AnnotationPlacement {
  annotationId: string;
  color: ReadingAnnotation['color'];
  note: string;
  status: 'ok' | 'ambiguous' | 'missing';
  spans: Array<{ locator: string; start: number; end: number }>;
}

function normalizeText(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

/**
 * 解析批注在材料中的渲染位置（对照参考 resolveTextSelectors）：
 * 有 segments（TextPositionSelector 的块级形态）时按区间渲染，且单段需仍覆盖 quote，
 * 不再覆盖时回退 quote 匹配；旧 quote-only 数据按全文唯一匹配回退，多处命中为歧义、
 * 显式提示，不猜位置。
 */
function resolveAnnotationPlacements(
  material: ReadingMaterial,
  annotations: ReadingAnnotation[],
): Map<string, AnnotationPlacement> {
  const blocks = parseBlocks(material);
  const placements = new Map<string, AnnotationPlacement>();
  for (const annotation of annotations) {
    const base = { annotationId: annotation.annotationId, color: annotation.color, note: annotation.note };
    const matchByQuote = (): AnnotationPlacement => {
      const occurrences: Array<{ locator: string; start: number; end: number }> = [];
      for (const block of blocks) {
        let idx = block.text.indexOf(annotation.quote);
        while (idx !== -1) {
          occurrences.push({ locator: block.locator, start: idx, end: idx + annotation.quote.length });
          idx = block.text.indexOf(annotation.quote, idx + Math.max(1, annotation.quote.length));
        }
      }
      if (occurrences.length === 1) return { ...base, status: 'ok', spans: occurrences };
      return {
        ...base,
        status: occurrences.length === 0 ? 'missing' : 'ambiguous',
        spans: [],
      };
    };
    if (annotation.segments && annotation.segments.length > 0) {
      const spans: Array<{ locator: string; start: number; end: number }> = [];
      for (const segment of annotation.segments) {
        const block = blocks.find((item) => item.locator === segment.locator);
        if (!block) continue;
        const start = Math.max(0, Math.min(Math.floor(segment.start), block.text.length));
        const end = Math.max(start, Math.min(Math.floor(segment.end), block.text.length));
        if (end > start) spans.push({ locator: block.locator, start, end });
      }
      // 单段定位必须仍覆盖 quote，否则回退 quote 匹配（材料可能已被重新登记）
      if (
        spans.length === 1 &&
        annotation.segments.length === 1 &&
        normalizeText(blocks.find((item) => item.locator === spans[0]!.locator)?.text.slice(spans[0]!.start, spans[0]!.end) ?? '') !==
          normalizeText(annotation.quote)
      ) {
        placements.set(annotation.annotationId, matchByQuote());
        continue;
      }
      placements.set(annotation.annotationId, { ...base, status: spans.length > 0 ? 'ok' : 'missing', spans });
      continue;
    }
    placements.set(annotation.annotationId, matchByQuote());
  }
  return placements;
}

/** 按已解析区间把块文本切分为普通文本与高亮 mark（重叠区间跳过，先到先得） */
function renderMarked(
  text: string,
  marks: Array<{ start: number; end: number; placement: AnnotationPlacement }> | undefined,
) {
  if (!marks || marks.length === 0) return text;
  const sorted = [...marks].sort((a, b) => a.start - b.start);
  const accepted: Array<{ start: number; end: number; placement: AnnotationPlacement }> = [];
  let lastEnd = 0;
  for (const mark of sorted) {
    if (mark.start >= lastEnd && mark.end > mark.start) {
      accepted.push(mark);
      lastEnd = mark.end;
    }
  }
  if (accepted.length === 0) return text;
  const parts: Array<string | ReactElement> = [];
  let cursor = 0;
  for (const mark of accepted) {
    if (mark.start > cursor) parts.push(text.slice(cursor, mark.start));
    parts.push(
      <mark
        key={`${mark.placement.annotationId}-${mark.start}`}
        data-annotation-id={mark.placement.annotationId}
        className="reading-mark"
        style={{ background: MARK_COLORS[mark.placement.color] ?? MARK_COLORS.yellow }}
        title={mark.placement.note || undefined}
      >
        {text.slice(mark.start, mark.end)}
      </mark>,
    );
    cursor = mark.end;
  }
  if (cursor < text.length) parts.push(text.slice(cursor));
  return parts;
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
  const materialIdRef = useRef<string | null>(null);
  const pendingPositionRef = useRef<{ materialId: string; pct: number } | null>(null);
  const saveTimerRef = useRef<number | null>(null);
  const [annotations, setAnnotations] = useState<ReadingAnnotation[]>([]);
  const [selection, setSelection] = useState<{
    quote: string;
    segments: ReadingAnnotationSegment[];
    top: number;
    left: number;
  } | null>(null);
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteText, setNoteText] = useState('');

  useEffect(() => {
    const refresh = () => {
      try {
        setAnnotations(material ? readAnnotations(material.id) : []);
      } catch (cause) {
        setAnnotations([]);
        onNotice(cause instanceof Error ? cause.message : '批注数据无法读取，原数据未修改。');
      }
    };
    refresh();
    return subscribeReading(refresh);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [material?.id]);

  // 阅读位置生命周期（R30）：按材料 id 切换时结算旧材料待写位置、
  // 取消 rAF/定时器、失效选区浮条，并统一恢复新位置（含零位置回顶）。
  useEffect(() => {
    materialIdRef.current = material?.id ?? null;
    if (!material) return;
    const mat = material;
    setSelection(null);
    setNoteOpen(false);
    setNoteText('');
    const raf = requestAnimationFrame(() => {
      const el = containerRef.current;
      if (!el) return;
      el.scrollTop = ((el.scrollHeight - el.clientHeight) * mat.positionPct) / 100;
    });
    return () => {
      cancelAnimationFrame(raf);
      if (saveTimerRef.current !== null) {
        window.clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
        const pending = pendingPositionRef.current;
        pendingPositionRef.current = null;
        // pct 在滚动时已按旧材料内容捕获，此处只落盘，不会旧任务读新视图
        if (pending && pending.materialId === mat.id) saveReadingPosition(pending.materialId, pending.pct);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [material?.id]);

  const blocks = useMemo(() => (material ? parseBlocks(material) : []), [material]);
  const placements = useMemo(
    () => (material ? resolveAnnotationPlacements(material, annotations) : new Map<string, AnnotationPlacement>()),
    [material, annotations],
  );
  const marksByLocator = useMemo(() => {
    const map = new Map<string, Array<{ start: number; end: number; placement: AnnotationPlacement }>>();
    for (const placement of placements.values()) {
      if (placement.status !== 'ok') continue;
      for (const span of placement.spans) {
        const list = map.get(span.locator) ?? [];
        list.push({ start: span.start, end: span.end, placement });
        map.set(span.locator, list);
      }
    }
    return map;
  }, [placements]);

  function handleScroll() {
    const el = containerRef.current;
    const materialId = materialIdRef.current;
    if (!el || !materialId) return;
    const pct = Math.max(0, Math.min(100, (el.scrollTop / Math.max(1, el.scrollHeight - el.clientHeight)) * 100));
    pendingPositionRef.current = { materialId, pct };
    if (saveTimerRef.current !== null) return;
    saveTimerRef.current = window.setTimeout(() => {
      saveTimerRef.current = null;
      const pending = pendingPositionRef.current;
      pendingPositionRef.current = null;
      if (pending) saveReadingPosition(pending.materialId, pending.pct);
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
    // 记录块级精确定位段（含跨块）：offset 相对块原文，避免 mark 片段化 DOM 的影响
    const segments = collectSelectionSegments(range, containerRef.current);
    setSelection({
      quote,
      segments,
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
      addAnnotation({
        materialId: material.id,
        kind: 'highlight',
        color,
        quote: selection.quote,
        segments: selection.segments,
      });
      onNotice('已添加高亮。');
    } catch (cause) {
      onNotice(cause instanceof ReadingValidationError ? cause.message : '添加高亮失败，请重试。');
    }
    clearSelection();
  }

  /** 解析失败后的重试：重新排队并启动显式模拟解析 */
  function retryIngest() {
    if (!material) return;
    updateMaterialStatus(material.id, 'queued', null);
    simulateMaterialIngest(material.id);
  }

  function saveNote(event: ReactMouseEvent | React.FormEvent) {
    event.preventDefault();
    if (!material || !selection) return;
    try {
      addAnnotation({
        materialId: material.id,
        kind: 'note',
        quote: selection.quote,
        segments: selection.segments,
        note: noteText,
      });
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
        {material.sourceKind !== 'text' && (
          <span className="space-chip" title={material.statusNote ?? undefined}>
            {SOURCE_KIND_LABELS[material.sourceKind] ?? material.sourceKind} · 模拟解析
          </span>
        )}
      </header>
      {(material.status ?? 'ready') !== 'ready' ? (
        <div className="space-empty" role="status">
          <strong>
            {material.status === 'queued' && '排队解析中…（模拟）'}
            {material.status === 'processing' && '解析进行中…（模拟）'}
            {material.status === 'failed' && '解析失败（模拟）'}
          </strong>
          <span>{material.statusNote ?? '真实解析未接入；非文本材料按显式模拟流程演示。'}</span>
          {material.status === 'failed' && (
            <button className="space-button" onClick={retryIngest} aria-label="重试解析">
              重试解析
            </button>
          )}
        </div>
      ) : (
        <>
          {blocks.map((block) => {
            const content = renderMarked(block.text, marksByLocator.get(block.locator));
            if (block.kind === 'heading') {
              if (block.level === 1) return <h1 key={block.locator} data-loc={block.locator}>{content}</h1>;
              if (block.level === 2) return <h2 key={block.locator} data-loc={block.locator}>{content}</h2>;
              return <h3 key={block.locator} data-loc={block.locator}>{content}</h3>;
            }
            return <p key={block.locator} data-loc={block.locator}>{content}</p>;
          })}
        </>
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
                  addBookmark(material.id, selection.segments[0]?.locator ?? 'p-0', selection.quote.slice(0, 24));
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

// ===== 右栏：伴生助手（统一 ChatService 事件模型 + 本地确定性模拟） =====

interface CompanionTurnState {
  /** R-09：该轮次所属会话——终态与增量只在归属会话内生效，避免串会话 */
  sessionId: string;
  turnId: string;
  text: string;
  process: string[];
  stage: string | null;
  error: string | null;
  retryable: boolean;
}

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
  // R-09：轮次按会话归属存放。切走后旧会话的生成继续进行并只写回自身，新会话立即可用；
  // 迟到事件与收尾回调按 sessionId + turnId 校验，不污染当前会话。
  const [turns, setTurns] = useState<Record<string, CompanionTurnState>>({});
  // R-09：是否跟随最新。用户手动上滚即关闭；点"回到最新"恢复。
  const [followBottom, setFollowBottom] = useState(true);
  const bodyRef = useRef<HTMLDivElement>(null);
  const routeSessionRef = useRef<string | null>(null);
  const activeIdRef = useRef<string | null>(null);
  const serviceRef = useRef<CompanionService | null>(null);
  const abortsRef = useRef<Map<string, AbortController>>(new Map());
  const lastSendRef = useRef<Map<string, { text: string; quote?: string }>>(new Map());
  // READ-END：已收尾的轮次 id（重复/迟到终态只收尾一次，落库幂等）
  const finalizedTurnsRef = useRef<Set<string>>(new Set());
  /** 草稿归属：记录草稿状态对应的会话，切会话/卸载时按会话保存，不串写 */
  const draftOwnerRef = useRef<{ sessionId: string | null; draft: string; quote: string | null }>({
    sessionId: null,
    draft: '',
    quote: null,
  });
  const loadedSessionRef = useRef<string | null>(null);
  if (!serviceRef.current) serviceRef.current = createReadingCompanionService();

  useEffect(() => {
    const refresh = () => {
      try {
        const list = readSessions(workspaceId);
        setSessions(list);
        setActiveId((current) => {
          if (current && list.some((item) => item.id === current)) return current;
          const routeValid = routeSessionRef.current && list.some((item) => item.id === routeSessionRef.current) ? routeSessionRef.current : null;
          return routeValid ?? list[0]?.id ?? null;
        });
      } catch (cause) {
        setSessions([]);
        onSessionError(cause instanceof Error ? cause.message : '伴生会话数据无法读取，原数据未修改。');
      }
    };
    refresh();
    return subscribeReading(refresh);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  // 路由会话 id 首次同步（深链进入时定位会话）
  useEffect(() => {
    routeSessionRef.current = routeSessionId;
    if (!routeSessionId) return;
    try {
      const list = readSessions(workspaceId);
      if (list.some((item) => item.id === routeSessionId)) {
        setActiveId(routeSessionId);
      } else if (list.length > 0) {
        onSessionError('链接指向的会话不存在，已切换到最近会话。');
      }
    } catch {
      // 读取失败由订阅刷新的错误提示呈现
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeSessionId, workspaceId]);

  // 切换会话时加载该会话的持久化草稿（每会话一份，不互相覆盖）
  useEffect(() => {
    if (!activeId) {
      loadedSessionRef.current = null;
      setDraft('');
      setPendingQuote(null);
      return;
    }
    if (loadedSessionRef.current === activeId) return;
    loadedSessionRef.current = activeId;
    const session = sessions.find((item) => item.id === activeId);
    setDraft(session?.draft ?? '');
    setPendingQuote(session?.draftQuote ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId]);

  // 草稿变更防抖落盘 + 卸载兜底保存（归属当前会话）
  useEffect(() => {
    draftOwnerRef.current = { sessionId: activeId, draft, quote: pendingQuote };
  }, [activeId, draft, pendingQuote]);
  useEffect(() => {
    if (!activeId) return;
    const timer = window.setTimeout(() => {
      saveSessionDraft(activeId, draft, pendingQuote);
    }, 400);
    return () => window.clearTimeout(timer);
  }, [activeId, draft, pendingQuote]);
  useEffect(
    () => () => {
      const owner = draftOwnerRef.current;
      if (owner.sessionId) saveSessionDraft(owner.sessionId, owner.draft, owner.quote);
    },
    [],
  );

  // 「问 AI」事件：选中文本预填当前会话草稿（引用随会话归属保存）
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
  // 当前会话的轮次：其他会话的轮次只写回各自会话，不在此渲染
  const turn = activeId ? turns[activeId] ?? null : null;
  const turnActive = turn !== null && turn.error === null;
  useEffect(() => {
    activeIdRef.current = activeId;
  }, [activeId]);

  // R-09：切换会话时恢复"跟随最新"（每个会话从最新处开始看），
  // 避免在 A 会话上滚后切到 B 会话却不跟随的串用。
  useEffect(() => {
    setFollowBottom(true);
  }, [activeId]);

  // R-09：仅在"跟随最新"时自动滚到底部；用户上滚后不再强制拉回（只作用于伴生消息容器）
  useEffect(() => {
    if (!followBottom) return;
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [followBottom, activeId, messageCount, turn?.text, turn?.process.length]);

  // 卸载时中止进行中的轮次（保留已生成部分并落盘）
  useEffect(
    () => () => {
      abortsRef.current.forEach((controller) => controller.abort());
      abortsRef.current.clear();
    },
    [],
  );

  function flushDraft() {
    const owner = draftOwnerRef.current;
    if (owner.sessionId) saveSessionDraft(owner.sessionId, owner.draft, owner.quote);
  }

  /**
   * R-09 会话地址同步（对照主聊天 syncSessionUrl 契约）：
   * - 用户主动切换/新建会话走 pushState，形成可前进/后退的历史；
   * - 地址已一致时不写历史，避免初始化/重复切换制造重复条目；
   * - 只有"用户动作"与"浏览器导航（popstate）"两个来源会改地址。
   */
  function syncSessionUrl(sessionId: string, method: 'push' | 'replace') {
    const target = `/reading/${encodeURIComponent(workspaceId)}/sessions/${sessionId}`;
    if (window.location.pathname === target) return;
    (method === 'push' ? window.history.pushState : window.history.replaceState).call(
      window.history,
      null,
      '',
      target,
    );
  }

  // R-09：浏览器前进/后退时按 URL 重新定位空间与会话，草稿先按归属落盘再切换
  useEffect(() => {
    function onPopState() {
      const match = /^\/reading\/([^/]+)(?:\/sessions(?:\/([^/?#]+))?)?\/?$/.exec(window.location.pathname);
      if (!match) return; // 离开阅读板块：交由路由处理
      if (decodeURIComponent(match[1]!) !== workspaceId) return; // 其他空间：由路由参数变化重新挂载同步
      const sessionId = match[2] ? decodeURIComponent(match[2]) : null;
      let list: ReadingSession[];
      try {
        list = readSessions(workspaceId);
      } catch {
        return; // 读取失败由订阅刷新的错误提示呈现
      }
      if (sessionId) {
        if (!list.some((item) => item.id === sessionId)) {
          onSessionError('链接指向的会话不存在，已切换到最近会话。');
          return;
        }
        if (sessionId !== activeIdRef.current) flushDraft();
        setActiveId(sessionId);
        onSessionError(null);
        return;
      }
      // 后退到无会话地址（/reading/<ws> 或 /reading/<ws>/sessions）：回到该空间默认会话
      const fallback = list[0]?.id ?? null;
      if (fallback !== activeIdRef.current) flushDraft();
      setActiveId(fallback);
      onSessionError(null);
    }
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  function focusSession(sessionId: string) {
    if (sessionId !== activeId) flushDraft();
    setActiveId(sessionId);
    onSessionError(null);
    syncSessionUrl(sessionId, 'push');
  }

  function newSession() {
    const session = createSession(workspaceId, activeMaterial?.id ?? null);
    focusSession(session.id);
  }

  function finalizeTurn(sessionId: string, turnId: string, controller: AbortController, content: string, cancelled = false) {
    // READ-END 幂等：同一轮次的重复/迟到终态（取消收尾后再到 end、重复 end）只收尾一次，
    // 防止内容重复落库或复活已取消标注；新轮次有新 turnId，不受影响。
    if (finalizedTurnsRef.current.has(turnId)) return;
    finalizedTurnsRef.current.add(turnId);
    // 只释放本轮自己的控制器：旧轮次收尾不得夺走新轮次的取消能力
    if (abortsRef.current.get(sessionId) === controller) abortsRef.current.delete(sessionId);
    // R-09：内容始终落到**所属会话**（不丢已生成内容）
    if (content.trim()) {
      appendMessage(sessionId, { role: 'assistant', content });
    }
    // 只清理属于该会话、该轮的轮次块：切到别的会话或已开新轮后，旧轮收尾不得清掉新状态
    setTurns((current) => {
      if (current[sessionId]?.turnId !== turnId) return current;
      const next = { ...current };
      delete next[sessionId];
      return next;
    });
    if (!cancelled) lastSendRef.current.delete(sessionId);
  }

  function startTurn(sessionId: string, userText: string, quote?: string) {
    lastSendRef.current.set(sessionId, { text: userText, quote });
    // 同一会话不并发：新轮开始前中止该会话的上一轮（跨会话互不影响）
    abortsRef.current.get(sessionId)?.abort();
    const controller = new AbortController();
    abortsRef.current.set(sessionId, controller);
    const turnId = `rturn-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    // 本轮文本只存在本地闭包，避免切会话/新轮次后串用上一轮的内容
    let text = '';
    setTurns((current) => ({
      ...current,
      [sessionId]: { sessionId, turnId, text: '', process: [], stage: null, error: null, retryable: false },
    }));
    void serviceRef.current!.run(
      {
        sessionId,
        turnId,
        materialTitle: activeMaterial?.title ?? null,
        quote,
        userText,
        signal: controller.signal,
      },
      (event) => {
        // R-09 轮次守卫：**所有**事件（含 end/error 终态）都必须属于本轮与所属会话，
        // 否则丢弃——切会话/新轮次后迟到的终态不得改动新会话状态。
        if (event.turnId !== turnId || event.sessionId !== sessionId) return;
        const update = (mutate: (entry: CompanionTurnState) => CompanionTurnState) =>
          setTurns((current) => {
            const entry = current[sessionId];
            if (!entry || entry.turnId !== turnId) return current;
            return { ...current, [sessionId]: mutate(entry) };
          });
        switch (event.type) {
          case 'turn-start':
            break;
          case 'process':
            update((entry) => ({ ...entry, process: [...entry.process, event.delta] }));
            break;
          case 'stage':
            update((entry) => ({ ...entry, stage: event.phase === 'start' ? event.label : null }));
            break;
          case 'text':
            text += event.delta;
            update((entry) => ({ ...entry, text }));
            break;
          case 'error':
            update((entry) => ({ ...entry, error: event.error.message, retryable: event.error.retryable ?? false }));
            break;
          case 'end':
            finalizeTurn(sessionId, turnId, controller, text);
            break;
          default:
            break;
        }
      },
    ).catch((cause: unknown) => {
      if (cause instanceof DOMException && cause.name === 'AbortError') {
        // 取消：保留已生成部分并显式标注
        finalizeTurn(sessionId, turnId, controller, text ? `${text}\n\n（已取消）` : '', true);
        return;
      }
      setTurns((current) => {
        const entry = current[sessionId];
        if (!entry || entry.turnId !== turnId) return current;
        return {
          ...current,
          [sessionId]: {
            ...entry,
            error: cause instanceof Error ? cause.message : '伴生回复失败，请重试。',
            retryable: true,
          },
        };
      });
    });
  }

  function send() {
    const content = draft.trim();
    if (!content || turn) return;
    let sessionId = activeId;
    if (!sessionId || !getSession(sessionId)) {
      const session = createSession(workspaceId, activeMaterial?.id ?? null);
      sessionId = session.id;
      loadedSessionRef.current = sessionId;
      syncSessionUrl(sessionId, 'push');
    } else {
      setActiveId(sessionId);
    }
    onSessionError(null);
    const quote = pendingQuote ?? undefined;
    appendMessage(sessionId, { role: 'user', content, ...(quote ? { quote } : {}) });
    setDraft('');
    setPendingQuote(null);
    saveSessionDraft(sessionId, '', null);
    startTurn(sessionId, content, quote);
  }

  function cancelTurn() {
    if (activeId) abortsRef.current.get(activeId)?.abort();
  }

  function retryTurn() {
    const sessionId = activeId;
    const last = sessionId ? lastSendRef.current.get(sessionId) : null;
    // READ-RETRY：错误态（turn 保留但带 error）允许重试；流式进行中仍禁止重入。
    const errored = turn !== null && turn.error !== null;
    if (!sessionId || !last || (turn && !errored)) return;
    onSessionError(null);
    startTurn(sessionId, last.text, last.quote);
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
      <div
        className="reading-companion-body"
        ref={bodyRef}
        onScroll={() => {
          const el = bodyRef.current;
          if (!el) return;
          // R-09：距底 >90px 视为用户上滚阅读历史，关闭自动跟随
          setFollowBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 90);
        }}
      >
        {!active || (active.messages.length === 0 && !turn) ? (
          <p className="space-footnote" style={{ margin: 0 }}>
            伴生助手为本地模拟（未接入模型）：提问、或选中正文「问 AI」。回复为显式模拟事件流（流式/过程/取消/重试）并标注【模拟回复】。
          </p>
        ) : (
          <>
            {active.messages.map((message) => (
              <div key={message.id} className={`reading-msg ${message.role}`}>
                {message.quote && <div className="reading-quote-block" style={{ marginBottom: 6 }}>{message.quote.slice(0, 60)}{message.quote.length > 60 ? '…' : ''}</div>}
                {message.role === 'assistant' ? <AnswerMarkdown text={message.content} /> : message.content}
              </div>
            ))}
            {turn && (
              <div className="reading-msg assistant" aria-label="伴生回复生成中" data-testid="companion-turn">
                {turn.process.map((line, idx) => (
                  <p key={idx} className="chat-status-text" style={{ margin: '0 0 4px' }}>{line}</p>
                ))}
                {turn.stage && <p className="chat-status-text" style={{ margin: '0 0 4px' }}>〔{turn.stage}〕</p>}
                {turn.text && <AnswerMarkdown text={turn.text} />}
              </div>
            )}
            {turn?.error && (
              <div className="space-banner error" role="alert" style={{ margin: 0 }}>
                {turn.error}
                {turn.retryable && (
                  <button className="space-button" style={{ marginLeft: 8 }} onClick={retryTurn} aria-label="重试伴生回复">
                    重试
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
      {/* R-09：「回到最新」由用户显式触发，且只滚动伴生消息容器，不碰阅读正文与整页 */}
      {!followBottom && (
        <button
          type="button"
          className="space-button"
          style={{ alignSelf: 'center', margin: '6px 0 0' }}
          onClick={() => {
            setFollowBottom(true);
            const el = bodyRef.current;
            if (el) el.scrollTop = el.scrollHeight;
          }}
        >
          回到最新
        </button>
      )}
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
        {turnActive ? (
          <button className="space-button danger" onClick={cancelTurn} aria-label="停止生成">
            <Square size={14} />
            停止
          </button>
        ) : (
          <button className="space-button primary" onClick={send} aria-label="发送提问" disabled={!draft.trim()}>
            <Send size={14} />
            发送
          </button>
        )}
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
  onOpenLibrary,
  onAdded,
}: {
  workspace: ReadingWorkspace;
  materials: ReadingMaterial[];
  onClose: () => void;
  onOpenLibrary: () => void;
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
            <button className="space-button primary" onClick={onOpenLibrary}>
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
