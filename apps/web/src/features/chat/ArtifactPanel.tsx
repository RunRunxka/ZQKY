'use client';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Activity, Check, Copy, Download, FileText, X } from 'lucide-react';
import type { ChatArtifact } from '@/contracts/chat';
import { AnswerMarkdown } from './AnswerMarkdown';
import { QuizArtifactView } from './artifacts/QuizArtifactView';
import { ReportArtifactView } from './artifacts/ReportArtifactView';
import { MermaidPreview } from './artifacts/MermaidPreview';
import { ChartPreview } from './artifacts/ChartPreview';

const EXT: Record<ChatArtifact['kind'], string> = {
  markdown: 'md',
  svg: 'svg',
  html: 'html',
  text: 'txt',
  quiz: 'md',
  report: 'md',
  chart: 'json',
  mermaid: 'mmd',
};

/** 复合身份 key（`${messageId}:${artifactId}`）取消息 id（R24；id 不含冒号，按最后一个冒号切分） */
function messageIdOf(key: string): string {
  const idx = key.lastIndexOf(':');
  return idx === -1 ? key : key.slice(0, idx);
}

function downloadName(artifact: ChatArtifact): string {
  const clean = artifact.title.replace(/[\\/:*?"<>|]/g, '_') || '产物';
  return `${clean}.${EXT[artifact.kind]}`;
}

/** R24：工作区条目使用复合身份 key（消息 id + 产物 id），不同轮同 id 产物互不串位 */
export interface ArtifactPanelItem {
  key: string;
  artifact: ChatArtifact;
}

/* 工作区宽度（对照参考 SessionViewerPanel：400–960px、默认 620、拖动 rAF 合帧、
   持久化；键使用目标自己的 zhiqikeyuan:viewer-width，不沿用 dt: 前缀） */
const VIEWER_WIDTH_VAR = '--viewer-width';
const VIEWER_WIDTH_KEY = 'zhiqikeyuan:viewer-width';
const VIEWER_WIDTH_DEFAULT = 620;
const VIEWER_WIDTH_MIN = 400;
const VIEWER_WIDTH_MAX = 960;

function clampViewerWidth(px: number): number {
  // 硬上下限之外加软上限：始终为对话列保留约 30% 视口，面板不能吞掉会话（同参考）
  const ceiling =
    typeof window !== 'undefined'
      ? Math.max(VIEWER_WIDTH_MIN, Math.min(VIEWER_WIDTH_MAX, window.innerWidth * 0.7))
      : VIEWER_WIDTH_MAX;
  return Math.round(Math.max(VIEWER_WIDTH_MIN, Math.min(px, ceiling)));
}

function readStoredViewerWidth(): number {
  if (typeof window === 'undefined') return VIEWER_WIDTH_DEFAULT;
  const raw = window.localStorage.getItem(VIEWER_WIDTH_KEY);
  const parsed = raw ? Number(raw) : NaN;
  return Number.isFinite(parsed) ? clampViewerWidth(parsed) : VIEWER_WIDTH_DEFAULT;
}

/**
 * S3/R22 结果工作区（对照参考 SessionViewerPanel 的标签页形态）：
 * - 标签栏：「活动」主页常驻第一个（不可关闭），产物标签可关闭；
 *   关闭当前标签回退到相邻标签或活动主页；会话切换由父级重置活动标签。
 * - 活动主页 = 会话信息 + 能力配置卡（R22：配置请求激活主页并定位配置卡）。
 * - 产物预览：markdown 安全渲染 / svg data-URL img（img 上下文不执行脚本）/
 *   html 空 sandbox iframe（禁脚本）/ text 原样；复制与下载使用真实内容。
 * - 宽度：左缘拖动（pointer + rAF 合帧写 CSS var），400–960px 软上限钳制，
 *   持久化到 localStorage；<768px 隐藏拖动（手机用整幅抽屉，不套桌面最小宽度）。
 * - 展开 220ms（参考 ANIM_MS=220）；ESC 关闭整个工作区。
 */
export function WorkspacePanel({
  items,
  activeKey,
  onOpen,
  onCloseTab,
  onClose,
  home,
}: {
  items: ArtifactPanelItem[];
  activeKey: string | null;
  /** null = 打开活动主页；复合 key = 打开对应产物标签 */
  onOpen(key: string | null): void;
  onCloseTab(key: string): void;
  onClose(): void;
  /** 活动主页内容（会话信息 + 能力配置卡） */
  home: ReactNode;
}) {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const active = items.find((item) => item.key === activeKey) ?? null;
  const rootRef = useRef<HTMLDivElement>(null);

  // 宽度：挂载后恢复持久化值（首渲染用默认值，避免 SSR/水合不一致——同参考）
  useEffect(() => {
    const width = readStoredViewerWidth();
    document.documentElement.style.setProperty(VIEWER_WIDTH_VAR, `${width}px`);
  }, []);

  const startResize = useCallback((event: React.PointerEvent) => {
    event.preventDefault();
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
    let rafId = 0;
    let pendingX = event.clientX;
    let current = readStoredViewerWidth();
    const apply = () => {
      rafId = 0;
      current = clampViewerWidth(window.innerWidth - pendingX);
      document.documentElement.style.setProperty(VIEWER_WIDTH_VAR, `${current}px`);
    };
    const onMove = (ev: PointerEvent) => {
      // 每帧最多写一次 CSS var（pointermove 可能快于刷新率——同参考）
      pendingX = ev.clientX;
      if (!rafId) rafId = requestAnimationFrame(apply);
    };
    const onUp = () => {
      if (rafId) cancelAnimationFrame(rafId);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      window.localStorage.setItem(VIEWER_WIDTH_KEY, String(current));
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, []);

  // ESC 关闭工作区（同参考）
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  async function copyActive() {
    if (!active) return;
    try {
      await navigator.clipboard.writeText(active.artifact.content);
      setCopiedKey(active.key);
      window.setTimeout(
        () => setCopiedKey((current) => (current === active.key ? null : current)),
        2000,
      );
    } catch {
      /* 复制失败保持按钮态，由用户手动选择文本 */
    }
  }

  function downloadActive() {
    if (!active) return;
    const blob = new Blob([active.artifact.content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = downloadName(active.artifact);
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="chat-workspace" ref={rootRef}>
      {/* 左缘拖动把手（<768px 隐藏：手机为整幅抽屉） */}
      <div
        className="chat-workspace-resize"
        onPointerDown={startResize}
        role="separator"
        aria-orientation="vertical"
        aria-label="调整工作区宽度"
      />
      {/* 标签栏：活动主页常驻第一，产物标签可关闭 */}
      <div className="chat-workspace-tabs" role="tablist" aria-label="结果工作区标签">
        <button
          type="button"
          role="tab"
          aria-selected={active === null}
          className={active === null ? 'active' : ''}
          onClick={() => onOpen(null)}
          title="活动"
        >
          <Activity size={12} strokeWidth={1.9} />
          <span>活动</span>
        </button>
        {items.map((item) => (
          <span key={item.key} className={`chat-workspace-tab ${active?.key === item.key ? 'active' : ''}`}>
            <button
              type="button"
              role="tab"
              aria-selected={active?.key === item.key}
              onClick={() => onOpen(item.key)}
              title={item.artifact.title}
            >
              <FileText size={12} strokeWidth={1.9} />
              <span className="chat-workspace-tab-title">{item.artifact.title}</span>
            </button>
            <button
              type="button"
              className="chat-workspace-tab-close"
              aria-label={`关闭标签 ${item.artifact.title}`}
              onClick={(e) => {
                e.stopPropagation();
                onCloseTab(item.key);
              }}
            >
              <X size={10} />
            </button>
          </span>
        ))}
        <span className="chat-flex-spacer" />
        <button className="icon-button" aria-label="关闭结果工作区" onClick={onClose}>
          <X size={15} />
        </button>
      </div>
      <div className="chat-workspace-body">
        {active === null ? (
          home
        ) : (
          <div className="chat-artifact-panel">
            <div className="chat-artifact-preview">
              <div className="chat-artifact-preview-head">
                <strong>{active.artifact.title}</strong>
                <span>
                  <button
                    type="button"
                    aria-label={copiedKey === active.key ? '已复制' : '复制产物内容'}
                    onClick={copyActive}
                  >
                    {copiedKey === active.key ? <Check size={13} /> : <Copy size={13} />}
                    {copiedKey === active.key ? '已复制' : '复制'}
                  </button>
                  <button
                    type="button"
                    aria-label={`下载 ${downloadName(active.artifact)}`}
                    onClick={downloadActive}
                  >
                    <Download size={13} /> 下载
                  </button>
                </span>
              </div>
              <div className="chat-artifact-preview-body">
                {active.artifact.kind === 'markdown' && (
                  <AnswerMarkdown text={active.artifact.content} />
                )}
                {active.artifact.kind === 'quiz' && (
                  <QuizArtifactView artifact={active.artifact} messageId={messageIdOf(active.key)} />
                )}
                {active.artifact.kind === 'report' && (
                  <ReportArtifactView
                    artifact={active.artifact}
                    messageId={messageIdOf(active.key)}
                  />
                )}
                {active.artifact.kind === 'chart' && <ChartPreview artifact={active.artifact} />}
                {active.artifact.kind === 'mermaid' && (
                  <MermaidPreview artifact={active.artifact} />
                )}
                {active.artifact.kind === 'svg' && (
                  // data-URL <img>：SVG 内脚本在 img 上下文不执行（同参考 SvgPreview 安全说明）
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={`data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(active.artifact.content)))}`}
                    alt={active.artifact.title}
                  />
                )}
                {active.artifact.kind === 'html' && (
                  // 空 sandbox：禁脚本禁表单，隔离不受信任产物
                  <iframe title={active.artifact.title} sandbox="" srcDoc={active.artifact.content} />
                )}
                {active.artifact.kind === 'text' && <pre>{active.artifact.content}</pre>}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
