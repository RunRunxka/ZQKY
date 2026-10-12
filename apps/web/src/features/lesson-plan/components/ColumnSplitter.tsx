'use client';
/**
 * 三栏拖拽分栏（自研，不新增依赖）。
 *
 * pointer 事件 + `setPointerCapture` 拖动；键盘可达（←/→ 每次 1 个百分点），
 * 通过 `role="separator"` 暴露给辅助技术，最小/最大宽度由父级 `onResize` 统一夹取。
 */
import { useCallback, useRef } from 'react';

export function ColumnSplitter({
  label,
  testId,
  onResize,
}: {
  label: string;
  testId: string;
  /** delta 为占容器宽度的百分比（可为负）；返回实际应用的百分比变化。 */
  onResize: (deltaPercent: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const lastX = useRef(0);

  const containerWidth = useCallback(() => {
    const parent = ref.current?.parentElement;
    return parent ? parent.getBoundingClientRect().width : 0;
  }, []);

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    dragging.current = true;
    lastX.current = event.clientX;
    event.currentTarget.setPointerCapture(event.pointerId);
    event.preventDefault();
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging.current) return;
    const width = containerWidth();
    if (width <= 0) return;
    const delta = ((event.clientX - lastX.current) / width) * 100;
    if (Math.abs(delta) < 0.05) return;
    lastX.current = event.clientX;
    onResize(delta);
  };

  const stop = (event: React.PointerEvent<HTMLDivElement>) => {
    dragging.current = false;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  return (
    <div
      ref={ref}
      className="lw-splitter"
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      tabIndex={0}
      data-testid={testId}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={stop}
      onPointerCancel={stop}
      onKeyDown={(event) => {
        if (event.key === 'ArrowLeft') {
          event.preventDefault();
          onResize(-1);
        } else if (event.key === 'ArrowRight') {
          event.preventDefault();
          onResize(1);
        }
      }}
    >
      <span className="lw-splitter-line" aria-hidden />
    </div>
  );
}
