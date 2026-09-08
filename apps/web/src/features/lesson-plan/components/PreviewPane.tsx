import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minus,
  Plus,
  Scan,
  Printer,
} from 'lucide-react';
import type { LessonPlanData } from '../model/types';
import { lessonTypeLabels } from '../model/types';
import { paginate } from '../services/pagination';
import schema from '../services/schema/lesson-plan.schema.json';
const grid = schema.tables[0].grid,
  total = grid.reduce((a, b) => a + b, 0);
const widths = [grid[0], grid.slice(1, 5).reduce((a, b) => a + b, 0), grid[5] + grid[6]].map(
  (w) => `${(w / total) * 100}%`,
);
export function PreviewPane({
  data,
  fontSize,
  focusMode,
  onFocus,
  onPrint,
}: {
  data: LessonPlanData;
  fontSize: number;
  focusMode: boolean;
  onFocus: () => void;
  onPrint: () => void;
}) {
  const pages = useMemo(() => paginate(data, fontSize), [data, fontSize]);
  const viewport = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(700);
  const [zoom, setZoom] = useState<number | null>(null);
  const [activePage, setActivePage] = useState(1);
  useEffect(() => {
    const el = viewport.current!;
    const observer = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  const scale = zoom ?? Math.min(1, (width - 56) / 794);
  const go = (page: number) => {
    const next = Math.max(1, Math.min(pages.length, page));
    setActivePage(next);
    document
      .getElementById(`paper-${next}`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  return (
    <section className={`preview-pane ${focusMode ? 'focused' : ''}`} aria-label="教案实时预览">
      <div className="preview-toolbar">
        <div className="preview-title">
          <span className="live-dot" />
          实时预览<span className="small-badge">A4</span>
        </div>
        <div className="preview-controls">
          <button
            className="icon-button"
            aria-label="缩小预览"
            onClick={() => setZoom(Math.max(0.25, scale - 0.1))}
          >
            <Minus size={15} />
          </button>
          <button className="zoom-label" onClick={() => setZoom(null)} title="点击恢复适合宽度">
            {Math.round(scale * 100)}%
          </button>
          <button
            className="icon-button"
            aria-label="放大预览"
            onClick={() => setZoom(Math.min(1.5, scale + 0.1))}
          >
            <Plus size={15} />
          </button>
          <span className="toolbar-divider" />
          <button className="icon-button" aria-label="适合宽度" onClick={() => setZoom(null)}>
            <Scan size={17} />
          </button>
          <button
            className="icon-button"
            aria-label={focusMode ? '退出专注预览' : '专注预览'}
            onClick={onFocus}
          >
            <Maximize2 size={16} />
          </button>
        </div>
      </div>
      <div className="preview-viewport" ref={viewport}>
        <div className="paper-stack">
          {pages.map((rows, index) => (
            <div
              className="paper-wrapper"
              id={`paper-${index + 1}`}
              key={index}
              style={{ width: 794 * scale, height: 1123 * scale }}
            >
              <article className="paper" style={{ transform: `scale(${scale})`, fontSize }}>
                <div className="paper-eyebrow">
                  智启课源 <span>教师备课 · 教案</span>
                </div>
                <h1>教师备课教案{index > 0 && <small>（续）</small>}</h1>
                {index === 0 ? (
                  <table className="lesson-table basic-table">
                    <colgroup>
                      <col style={{ width: '16.9%' }} />
                      <col style={{ width: '38.4%' }} />
                      <col style={{ width: '9.3%' }} />
                      <col style={{ width: '9.6%' }} />
                      <col style={{ width: '12.8%' }} />
                      <col style={{ width: '13%' }} />
                    </colgroup>
                    <tbody>
                      <tr>
                        <th>课题</th>
                        <td className="subject-cell">{data.title || ' '}</td>
                        <th>
                          本课题
                          <br />
                          总课时
                        </th>
                        <td className="center">{data.totalLessons}</td>
                        <th>本节课</th>
                        <td className="center">第 {data.currentLessonNo} 课时</td>
                      </tr>
                      <tr>
                        <th>课型</th>
                        <td colSpan={5}>
                          <div className="printed-types">
                            {Object.entries(lessonTypeLabels).map(([k, v]) => (
                              <span key={k}>
                                <span className="printed-checkbox">
                                  {data.lessonTypes.includes(
                                    k as keyof typeof lessonTypeLabels,
                                  ) && <Check size={11} />}
                                </span>
                                {v}
                                {k === 'other' &&
                                data.lessonTypes.includes('other') &&
                                data.otherTypeText
                                  ? `（${data.otherTypeText}）`
                                  : ''}
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                ) : (
                  <div className="continuation-title">{data.title || '未命名教案'} · 接上页</div>
                )}
                <table className="lesson-table content-table">
                  <colgroup>
                    {widths.map((width, i) => (
                      <col key={i} style={{ width }} />
                    ))}
                  </colgroup>
                  <tbody>
                    {rows.map((row, i) => (
                      <tr key={row.id} className={row.process ? 'process-print-row' : ''}>
                        {(!row.process || !rows[i - 1]?.process) && (
                          <th
                            rowSpan={
                              row.process
                                ? rows.slice(i).findIndex((r) => !r.process) < 0
                                  ? rows.length - i
                                  : rows.slice(i).findIndex((r) => !r.process)
                                : 1
                            }
                          >
                            {row.process ? (
                              <span className="vertical-label">教学过程</span>
                            ) : (
                              row.label
                            )}
                            {row.continued && <small>（续）</small>}
                          </th>
                        )}
                        <td colSpan={row.process ? 1 : 2} style={{ height: row.height }}>
                          {row.process && (
                            <div className="process-print-heading">
                              {i === 0 || !rows[i - 1].process ? (
                                <span className="table-column-label">教学设计</span>
                              ) : null}
                              <strong>
                                {row.label}
                                {row.continued ? '（续）' : ''}
                              </strong>
                            </div>
                          )}
                          <div className="print-text">{row.main || ' '}</div>
                        </td>
                        {row.process && (
                          <td className="secondary-cell">
                            {i === 0 || !rows[i - 1].process ? (
                              <span className="table-column-label">二次备课</span>
                            ) : null}
                            <div className="print-text">{row.secondary || ' '}</div>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {index === pages.length - 1 && (
                  <div className="approval-line">
                    <span>教研组核查等次：（优 / 良 / 中 / 差）</span>
                    <span>
                      教务处核查：（盖章）
                      <br />
                      <span className="approval-date">年　　月　　日</span>
                    </span>
                  </div>
                )}
                <footer className="paper-footer">
                  <span>{data.title || '未命名教案'}</span>
                  <span>
                    {index + 1} / {pages.length}
                  </span>
                </footer>
              </article>
            </div>
          ))}
        </div>
      </div>
      <div className="preview-bottom">
        <span>
          <Check size={13} /> 内容与 PDF 同步
        </span>
        <div className="page-switch">
          <button
            className="icon-button"
            aria-label="上一页"
            disabled={activePage <= 1}
            onClick={() => go(activePage - 1)}
          >
            <ChevronLeft size={15} />
          </button>
          <span>
            {Math.min(activePage, pages.length)} / {pages.length} 页
          </span>
          <button
            className="icon-button"
            aria-label="下一页"
            disabled={activePage >= pages.length}
            onClick={() => go(activePage + 1)}
          >
            <ChevronRight size={15} />
          </button>
        </div>
        <button className="icon-button" aria-label="打印教案" onClick={onPrint}>
          <Printer size={16} />
        </button>
      </div>
    </section>
  );
}
