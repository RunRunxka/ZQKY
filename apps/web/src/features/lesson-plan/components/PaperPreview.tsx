'use client';
/**
 * 右栏 A4 预览（R7-FE）。
 *
 * - 灰底滚动区 + A4 白纸（210mm 宽），**只预览第 3 页起的内容**：封面（第 1 页）与目录
 *   （第 2 页）由导出时自动补齐，预览顶部固定给出该提示；
 * - 内容按内容流分页，每张纸下缘是红色虚线分页标记「第 N 页结束」；
 * - 缩放随预览区宽度自适应（fit），可手动缩放；
 * - AI 候选内容以「AI 候选」标注显示，采用前不影响草稿。
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Minus, Plus, Printer, Scan, Sparkles } from 'lucide-react';
import type { LessonPlanData, LessonWorkbenchModuleWire } from '@/contracts/lesson-plans';
import {
  A4_HEIGHT_PX,
  A4_WIDTH_PX,
  FIRST_CONTENT_PAGE,
  layoutPreview,
  pageEndLabel,
  paperStyleVars,
  type PreviewBlock,
} from '../services/pagination';

function BlockView({ block, candidate }: { block: PreviewBlock; candidate: boolean }) {
  const candidateBadge = candidate ? (
    <span className="lw-candidate-badge" title="AI 候选内容：采用后才写入草稿">
      <Sparkles size={11} aria-hidden />
      AI 候选
    </span>
  ) : null;

  if (block.kind === 'band' || block.kind === 'custom-band') {
    return (
      <div className="lw-sheet-band" data-testid={`lw-block-${block.id}`}>
        {block.label}
      </div>
    );
  }
  if (block.kind === 'process-head') {
    return (
      <div className="lw-sheet-row process head" data-testid={`lw-block-${block.id}`}>
        {block.cells.map((cell) => (
          <span key={cell} className="lw-sheet-cell header">
            {cell}
          </span>
        ))}
      </div>
    );
  }
  if (block.kind === 'process-phase') {
    return (
      <div className="lw-sheet-phase" data-testid={`lw-block-${block.id}`}>
        {block.label}
      </div>
    );
  }
  if (block.cells.length > 1) {
    return (
      <div
        className={`lw-sheet-row process ${candidate ? 'candidate' : ''}`}
        data-testid={`lw-block-${block.id}`}
        data-candidate={candidate ? 'true' : undefined}
      >
        {block.cells.map((cell, index) => (
          <span key={index} className={`lw-sheet-cell ${index === 0 ? 'title' : ''}`}>
            {cell || <em className="lw-sheet-empty">待填写</em>}
          </span>
        ))}
        {candidateBadge}
      </div>
    );
  }
  return (
    <div
      className={`lw-sheet-row ${candidate ? 'candidate' : ''}`}
      data-testid={`lw-block-${block.id}`}
      data-candidate={candidate ? 'true' : undefined}
    >
      <span className="lw-sheet-label">{block.label}</span>
      <span className="lw-sheet-cell">
        {block.subLabel && <strong className="lw-sheet-sublabel">{block.subLabel}</strong>}
        {block.cells[0]
          ? block.cells[0].split(/\r?\n/).map((line, index) => (
              <span key={index} className="lw-sheet-line">
                {line}
              </span>
            ))
          : <em className="lw-sheet-empty">待填写</em>}
      </span>
      {candidateBadge}
    </div>
  );
}

/** 同组连续行合并左侧标签列（模板「三、教学目标」的知识/能力/思政三行 vMerge）。 */
function PageBlocks({ blocks, filledFields }: { blocks: PreviewBlock[]; filledFields: Set<string> }) {
  const rendered: React.ReactNode[] = [];
  let index = 0;
  while (index < blocks.length) {
    const block = blocks[index];
    if (!block.mergeGroup) {
      rendered.push(<BlockView key={block.id} block={block} candidate={filledFields.has(block.id)} />);
      index += 1;
      continue;
    }
    const group: PreviewBlock[] = [block];
    let next = index + 1;
    while (next < blocks.length && blocks[next].mergeGroup === block.mergeGroup) {
      group.push(blocks[next]);
      next += 1;
    }
    rendered.push(
      <div className="lw-sheet-group" key={`group-${block.mergeGroup}-${block.id}`} data-testid={`lw-block-group-${block.mergeGroup}`}>
        <div className="lw-sheet-group-label">{block.groupLabel ?? block.label}</div>
        <div className="lw-sheet-group-rows">
          {group.map((row) => (
            <BlockView key={row.id} block={{ ...row, mergeGroup: undefined, groupLabel: undefined }} candidate={filledFields.has(row.id)} />
          ))}
        </div>
      </div>,
    );
    index = next;
  }
  return <>{rendered}</>;
}

export function PaperPreview({
  data,
  modules,
  style,
  filledFields,
  title,
}: {
  data: LessonPlanData;
  modules: LessonWorkbenchModuleWire[];
  style: unknown;
  /** 候选已填充的字段（预览行 id）；采用后为空。 */
  filledFields: Set<string>;
  title: string;
}) {
  const layout = useMemo(() => layoutPreview(data, modules, style), [data, modules, style]);
  const viewport = useRef<HTMLDivElement>(null);
  const [fitScale, setFitScale] = useState(0.72);
  const [zoom, setZoom] = useState<number | null>(null);
  const scale = zoom ?? fitScale;

  useEffect(() => {
    const element = viewport.current;
    if (!element || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width ?? 0;
      if (width > 0) setFitScale(Math.min(1.2, Math.max(0.25, (width - 40) / A4_WIDTH_PX)));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const step = (direction: number) => setZoom(Math.min(1.5, Math.max(0.25, Number((scale + direction * 0.1).toFixed(2)))));

  return (
    <section className="lw-preview" aria-label="教案预览" data-testid="lw-preview">
      <header className="lw-preview-bar">
        <p className="lw-preview-hint" data-testid="lw-preview-hint">
          封面与目录将在导出时自动补齐，这里预览的是第 {FIRST_CONTENT_PAGE} 页起的正文。
        </p>
        <div className="lw-zoom">
          <button type="button" className="lw-icon-button" aria-label="缩小预览" data-testid="lw-zoom-out" onClick={() => step(-1)}>
            <Minus size={14} />
          </button>
          <button
            type="button"
            className="lw-zoom-value"
            data-testid="lw-zoom-value"
            title="恢复适合宽度"
            onClick={() => setZoom(null)}
          >
            {Math.round(scale * 100)}%
          </button>
          <button type="button" className="lw-icon-button" aria-label="放大预览" data-testid="lw-zoom-in" onClick={() => step(1)}>
            <Plus size={14} />
          </button>
          <button
            type="button"
            className="lw-icon-button"
            aria-label="适合宽度"
            data-testid="lw-zoom-fit"
            onClick={() => setZoom(null)}
          >
            <Scan size={15} />
          </button>
          <button
            type="button"
            className="lw-icon-button"
            aria-label="打印预览"
            data-testid="lw-print"
            onClick={() => {
              if (typeof window !== 'undefined') window.print();
            }}
          >
            <Printer size={15} />
          </button>
        </div>
      </header>
      <div className="lw-preview-viewport" ref={viewport} data-testid="lw-preview-viewport">
        <div className="lw-paper-stack">
          {layout.pages.map((page) => (
            <div
              key={page.number}
              className="lw-page"
              style={{ width: A4_WIDTH_PX * scale }}
              data-testid={`lw-paper-${page.number}`}
            >
              <div className="lw-paper-frame" style={{ height: A4_HEIGHT_PX * scale }}>
                <article
                  className="lw-paper"
                  style={{
                    ...(paperStyleVars(style) as React.CSSProperties),
                    transform: `scale(${scale})`,
                    width: A4_WIDTH_PX,
                    height: A4_HEIGHT_PX,
                  }}
                >
                  <div className="lw-paper-content">
                    <header className="lw-paper-head">
                      <span className="lw-paper-title">{title || '（课题名称）'}</span>
                      <span className="lw-paper-sub">教学设计</span>
                    </header>
                    {page.blocks.length > 0 ? (
                      <PageBlocks blocks={page.blocks} filledFields={filledFields} />
                    ) : (
                      <p className="lw-sheet-empty">（没有可预览的模块：请取消隐藏或添加模块）</p>
                    )}
                  </div>
                  <footer className="lw-paper-foot">
                    <span>智启课源 · 教案</span>
                    <span>{page.number}</span>
                  </footer>
                </article>
              </div>
              <div className="lw-page-end" data-testid={`lw-page-end-${page.number}`}>
                <span className="lw-page-end-label">{pageEndLabel(page.number)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
