'use client';
/**
 * 右栏 A4 预览（R12）：逐表还原 Word 模板正文。
 *
 * - 灰底滚动区 + A4 白纸（210mm 宽），**只预览第 3 页起的内容**：封面（第 1 页）与目录
 *   （第 2 页）由导出时自动补齐，预览顶部固定给出该提示；页脚按模板的正文页码显示（1 起）。
 * - 正文四张表按模板合并单元格：基本信息 4 列、教学分析 2 列、目标+策略同表（vMerge）、
 *   过程+评价+反思同表（两行表头、阶段行、评价四项、反思三项）。
 * - 内容按行高分页，每张纸下缘是红色虚线分页标记「第 N 页结束」；缩放随预览区宽度自适应。
 * - AI 候选内容以「AI 候选」标注显示，采用前不影响草稿。
 * - 悬停/点击表格区块可选中对应模块（与左栏模块轨联动）。
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
  tableColumnPercentages,
  type PreviewBlock,
  type PreviewCell,
} from '../services/pagination';

function cellIsCandidate(cell: PreviewCell, filledFields: Set<string>): boolean {
  return (cell.candidateIds ?? []).some((id) => filledFields.has(id));
}

function blockIsCandidate(block: PreviewBlock, filledFields: Set<string>): boolean {
  return filledFields.has(block.id) || block.cells.some((cell) => cellIsCandidate(cell, filledFields));
}

function CandidateBadge() {
  return (
    <span className="lw-candidate-badge" title="AI 候选内容：采用后才写入草稿">
      <Sparkles size={11} aria-hidden />
      AI 候选
    </span>
  );
}

function CellText({ text, placeholder = true }: { text: string; placeholder?: boolean }) {
  if (!text) return placeholder ? <em className="lw-sheet-empty">待填写</em> : null;
  return (
    <>
      {text.split(/\r?\n/).map((line, index) => (
        <span key={index} className="lw-sheet-line">
          {line || '\u00a0'}
        </span>
      ))}
    </>
  );
}

function rowProps(block: PreviewBlock, filledFields: Set<string>, onSelectModule?: (id: string) => void) {
  const candidate = blockIsCandidate(block, filledFields);
  return {
    'data-testid': `lw-block-${block.id}`,
    'data-module-id': block.moduleId,
    'data-candidate': candidate ? 'true' : undefined,
    className: ['lw-sheet-row', candidate ? 'candidate' : '', onSelectModule ? 'selectable' : ''].filter(Boolean).join(' '),
    title: onSelectModule ? '点击编辑这一节' : undefined,
    onClick: onSelectModule ? () => onSelectModule(block.moduleId) : undefined,
  } as const;
}

function BlockRow({
  block,
  filledFields,
  onSelectModule,
}: {
  block: PreviewBlock;
  filledFields: Set<string>;
  onSelectModule?: (id: string) => void;
}) {
  const candidate = blockIsCandidate(block, filledFields);
  const base = rowProps(block, filledFields, onSelectModule);

  if (block.kind === 'band' || block.kind === 'custom-band') {
    return (
      <tr {...base} className={`${base.className} lw-sheet-band ${block.kind === 'custom-band' ? 'custom' : ''}`}>
        <td colSpan={block.columns}>{block.label}</td>
      </tr>
    );
  }

  if (block.kind === 'process-head') {
    return (
      <tr {...base} className={`${base.className} lw-sheet-head`}>
        {block.cells.map((cell, index) => (
          <td
            key={index}
            colSpan={cell.colspan}
            rowSpan={cell.rowspan}
            className="lw-sheet-cell header"
          >
            {cell.text}
          </td>
        ))}
      </tr>
    );
  }

  if (block.kind === 'process-phase') {
    return (
      <tr {...base} className={`${base.className} lw-sheet-phase`}>
        <td colSpan={block.columns}>{block.label}</td>
      </tr>
    );
  }

  if (block.subRow) {
    return (
      <tr
        {...base}
        className={[
          base.className,
          'lw-sheet-subrow',
          block.noTopBorder ? 'no-top' : '',
          block.continuation ? 'lw-sheet-continuation' : '',
        ]
          .filter(Boolean)
          .join(' ')}
      >
        {block.cells.map((cell, index) => {
          const cellCandidate = cellIsCandidate(cell, filledFields);
          return (
            <td
              key={index}
              colSpan={cell.colspan ?? block.columns}
              className={['lw-sheet-cell', 'subcell', cellCandidate ? 'candidate-cell' : '']
                .filter(Boolean)
                .join(' ')}
            >
              <CellText text={cell.text} placeholder={!block.continuation} />
              {candidate && !block.continuation && <CandidateBadge />}
            </td>
          );
        })}
      </tr>
    );
  }

  return (
    <tr
      {...base}
      className={[base.className, block.continuation ? 'lw-sheet-continuation' : ''].filter(Boolean).join(' ')}
    >
      {block.cells.map((cell, index) => {
        const cellCandidate = cellIsCandidate(cell, filledFields);
        const isLabel = cell.role === 'label';
        return (
          <td
            key={index}
            colSpan={cell.colspan}
            rowSpan={cell.rowspan}
            className={[
              isLabel ? 'lw-sheet-label' : 'lw-sheet-cell',
              cellCandidate ? 'candidate-cell' : '',
            ]
              .filter(Boolean)
              .join(' ')}
          >
            {cell.subLabel && <strong className="lw-sheet-sublabel">{cell.subLabel}</strong>}
            <CellText text={cell.text} placeholder={!isLabel && !block.continuation} />
            {candidate && !block.continuation && index === block.cells.length - 1 && <CandidateBadge />}
          </td>
        );
      })}
    </tr>
  );
}

function TableSegment({
  tableId,
  blocks,
  continued,
  filledFields,
  onSelectModule,
}: {
  tableId: string;
  blocks: PreviewBlock[];
  continued: boolean;
  filledFields: Set<string>;
  onSelectModule?: (id: string) => void;
}) {
  const percentages = tableColumnPercentages(tableId);
  return (
    <table className={`lw-sheet-table ${continued ? 'continued' : ''}`} data-table={tableId}>
      <colgroup>
        {percentages.map((percent, index) => (
          <col key={index} style={{ width: `${percent}%` }} />
        ))}
      </colgroup>
      <tbody>
        {blocks.map((block) => (
          <BlockRow
            key={block.id}
            block={block}
            filledFields={filledFields}
            onSelectModule={onSelectModule}
          />
        ))}
      </tbody>
    </table>
  );
}

export function PaperPreview({
  data,
  modules,
  style,
  filledFields,
  title,
  onSelectModule,
}: {
  data: LessonPlanData;
  modules: LessonWorkbenchModuleWire[];
  style: unknown;
  /** 候选已填充的字段（预览行 id）；采用后为空。 */
  filledFields: Set<string>;
  title: string;
  /** 点击预览区块选中左侧模块（手机端同时切到编辑页）。 */
  onSelectModule?: (id: string) => void;
}) {
  const layout = useMemo(() => layoutPreview(data, modules, style), [data, modules, style]);
  const viewport = useRef<HTMLDivElement>(null);
  const [fitScale, setFitScale] = useState(0.72);
  const [zoom, setZoom] = useState<number | null>(null);
  const scale = zoom ?? fitScale;
  const bodyTitle = data.basic?.courseName || title || '（课程名称）';

  useEffect(() => {
    const element = viewport.current;
    if (!element || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width ?? 0;
      if (width > 0) setFitScale(Math.min(1.2, Math.max(0.25, (width - 8) / A4_WIDTH_PX)));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const step = (direction: number) => setZoom(Math.min(1.5, Math.max(0.25, Number((scale + direction * 0.1).toFixed(2)))));

  return (
    <section className="lw-preview" aria-label="教案预览" data-testid="lw-preview">
      <header className="lw-preview-bar">
        <p className="lw-preview-hint" data-testid="lw-preview-hint">
          封面与目录将在导出时自动补齐，这里预览第 {FIRST_CONTENT_PAGE} 页起的正文。
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
          {layout.pages.map((page, pageIndex) => {
            const segments: Array<{ tableId: string; blocks: PreviewBlock[]; continued: boolean }> = [];
            for (const block of page.blocks) {
              const last = segments[segments.length - 1];
              if (last && last.tableId === block.tableId) {
                last.blocks.push(block);
              } else {
                const previousPage = pageIndex > 0 ? layout.pages[pageIndex - 1] : null;
                const continued =
                  pageIndex > 0 &&
                  (previousPage?.blocks.at(-1)?.tableId === block.tableId ||
                    segments.some((segment) => segment.tableId === block.tableId));
                segments.push({ tableId: block.tableId, blocks: [block], continued });
              }
            }
            return (
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
                      {pageIndex === 0 && <h2 className="lw-paper-title">{bodyTitle}　教学设计</h2>}
                      {segments.map((segment, segmentIndex) => (
                        <TableSegment
                          key={`${segment.tableId}-${segmentIndex}`}
                          tableId={segment.tableId}
                          blocks={segment.blocks}
                          continued={segment.continued}
                          filledFields={filledFields}
                          onSelectModule={onSelectModule}
                        />
                      ))}
                      {page.blocks.length === 0 && (
                        <p className="lw-sheet-empty">（没有可预览的模块：请取消隐藏或添加模块）</p>
                      )}
                    </div>
                    <footer className="lw-paper-foot">
                      <span>{page.number - (FIRST_CONTENT_PAGE - 1)}</span>
                    </footer>
                  </article>
                </div>
                <div className="lw-page-end" data-testid={`lw-page-end-${page.number}`}>
                  <span className="lw-page-end-label">{pageEndLabel(page.number)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
