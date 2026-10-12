'use client';
/**
 * 左栏两块卡片：布局（模块列表 + 添加模块 + 已移除）与排版（字体/字号/行高/间距）。
 *
 * - 排序：拖拽手柄（pointer 事件，实时换位）与 ↑/↓ 按钮两种方式，键盘可达；
 * - 显隐、删除（内置固定模块只能隐藏）；删除的自定义模块进入「已移除」可还原；
 * - 所有排版控件都是受控 slider/select，改值实时进预览（同一份 style 状态）。
 */
import { useRef, useState } from 'react';
import { ChevronDown, ChevronUp, Eye, EyeOff, GripVertical, Plus, RotateCcw, Trash2, Undo2 } from 'lucide-react';
import type { LessonPlanData, LessonWorkbenchStyleWire } from '@/contracts/lesson-plans';
import {
  BUILTIN_MODULES,
  LESSON_FONTS,
  STYLE_LIMITS,
  chineseNumber,
  moduleFilled,
  type LessonModuleEntry,
} from '../model/modules';

/* ------------------------------------------------------------------ 布局 */

export function LayoutPanel({
  modules,
  removed,
  data,
  activeModuleId,
  onSelect,
  onMove,
  onReorder,
  onToggleHidden,
  onRemove,
  onRestore,
  onAddCustom,
}: {
  modules: LessonModuleEntry[];
  removed: LessonModuleEntry[];
  data: LessonPlanData;
  activeModuleId: string;
  onSelect: (id: string) => void;
  onMove: (id: string, delta: number) => void;
  onReorder: (from: number, to: number) => void;
  onToggleHidden: (id: string) => void;
  onRemove: (id: string) => void;
  onRestore: (id: string) => void;
  onAddCustom: (label: string) => void;
}) {
  const [customLabel, setCustomLabel] = useState('');
  const dragIndex = useRef<number | null>(null);

  const builtinNo = new Map<string, string>();
  let visibleBuiltin = 0;
  for (const entry of modules) {
    if (entry.kind !== 'builtin') continue;
    if (!entry.hidden) visibleBuiltin += 1;
    const def = BUILTIN_MODULES.find((item) => item.id === entry.builtinId);
    builtinNo.set(entry.id, def ? def.no : chineseNumber(visibleBuiltin));
  }

  return (
    <section className="lw-card" aria-label="布局" data-testid="lw-layout-card">
      <header className="lw-card-head">
        <h2>布局</h2>
        <span className="lw-card-hint">{modules.filter((m) => !m.hidden).length} 个模块进预览</span>
      </header>
      <ul className="lw-module-list" data-testid="lw-module-list">
        {modules.map((entry, index) => {
          const filled = moduleFilled(entry, data);
          return (
            <li
              key={entry.id}
              className={`lw-module-item ${entry.id === activeModuleId ? 'selected' : ''} ${
                entry.hidden ? 'hidden' : ''
              }`}
              data-module-index={index}
              data-testid={`lw-module-item-${entry.id}`}
            >
              <button
                type="button"
                className="lw-drag"
                aria-label={`拖动排序：${entry.label}`}
                data-testid={`lw-module-drag-${entry.id}`}
                onPointerDown={(event) => {
                  dragIndex.current = index;
                  event.currentTarget.setPointerCapture(event.pointerId);
                }}
                onPointerMove={(event) => {
                  if (dragIndex.current === null) return;
                  const node = document
                    .elementFromPoint(event.clientX, event.clientY)
                    ?.closest('[data-module-index]');
                  const target = node ? Number(node.getAttribute('data-module-index')) : NaN;
                  if (Number.isInteger(target) && target !== dragIndex.current) {
                    onReorder(dragIndex.current, target);
                    dragIndex.current = target;
                  }
                }}
                onPointerUp={(event) => {
                  dragIndex.current = null;
                  if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                    event.currentTarget.releasePointerCapture(event.pointerId);
                  }
                }}
              >
                <GripVertical size={14} aria-hidden />
              </button>
              <button
                type="button"
                className="lw-module-name"
                data-testid={`lw-module-select-${entry.id}`}
                onClick={() => onSelect(entry.id)}
                aria-current={entry.id === activeModuleId ? 'true' : undefined}
              >
                <span className={`lw-module-no ${entry.kind === 'custom' ? 'custom' : ''}`}>
                  {entry.kind === 'custom' ? '自' : (builtinNo.get(entry.id) ?? '')}
                </span>
                <span className="lw-module-label">{entry.label}</span>
                <span
                  className={`lw-module-dot ${filled ? 'filled' : ''}`}
                  title={filled ? '已有内容' : '尚未填写'}
                />
              </button>
              <span className="lw-module-actions">
                <button
                  type="button"
                  className="lw-icon-button"
                  aria-label={`上移：${entry.label}`}
                  data-testid={`lw-module-up-${entry.id}`}
                  disabled={index === 0}
                  onClick={() => onMove(entry.id, -1)}
                >
                  <ChevronUp size={14} />
                </button>
                <button
                  type="button"
                  className="lw-icon-button"
                  aria-label={`下移：${entry.label}`}
                  data-testid={`lw-module-down-${entry.id}`}
                  disabled={index === modules.length - 1}
                  onClick={() => onMove(entry.id, 1)}
                >
                  <ChevronDown size={14} />
                </button>
                <button
                  type="button"
                  className="lw-icon-button"
                  aria-label={entry.hidden ? `显示：${entry.label}` : `隐藏：${entry.label}`}
                  data-testid={`lw-module-hide-${entry.id}`}
                  disabled={entry.kind === 'builtin' && entry.builtinId === 'basic'}
                  onClick={() => onToggleHidden(entry.id)}
                >
                  {entry.hidden ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
                <button
                  type="button"
                  className="lw-icon-button danger"
                  aria-label={`删除：${entry.label}`}
                  data-testid={`lw-module-remove-${entry.id}`}
                  disabled={entry.kind === 'builtin'}
                  onClick={() => onRemove(entry.id)}
                >
                  <Trash2 size={14} />
                </button>
              </span>
            </li>
          );
        })}
      </ul>

      <form
        className="lw-add-module"
        onSubmit={(event) => {
          event.preventDefault();
          const label = customLabel.trim();
          if (!label) return;
          onAddCustom(label);
          setCustomLabel('');
        }}
      >
        <label className="lw-visually-hidden" htmlFor="lw-add-module-input">
          新模块标题
        </label>
        <input
          id="lw-add-module-input"
          data-testid="lw-module-add-input"
          value={customLabel}
          placeholder="添加模块（如：课前测试安排）"
          onChange={(event) => setCustomLabel(event.target.value)}
        />
        <button type="submit" className="lw-button" data-testid="lw-module-add-button">
          <Plus size={15} aria-hidden />
          添加模块
        </button>
      </form>

      {removed.length > 0 && (
        <div className="lw-removed" data-testid="lw-removed-modules">
          <span className="lw-removed-label">已移除：</span>
          {removed.map((entry) => (
            <button
              key={entry.id}
              type="button"
              className="lw-chip"
              data-testid={`lw-module-restore-${entry.id}`}
              onClick={() => onRestore(entry.id)}
            >
              <Undo2 size={13} aria-hidden />
              {entry.label}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ 排版与间距 */

function RangeField({
  label,
  testId,
  value,
  min,
  max,
  step,
  suffix,
  onChange,
}: {
  label: string;
  testId: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix?: string;
  onChange: (value: number) => void;
}) {
  return (
    <label className="lw-range">
      <span className="lw-range-label">
        {label}
        <span className="lw-range-value">
          {Number.isInteger(value) ? value : value.toFixed(2)}
          {suffix ?? ''}
        </span>
      </span>
      <input
        type="range"
        data-testid={testId}
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}

export function StylePanel({
  style,
  onChange,
  onReset,
}: {
  style: LessonWorkbenchStyleWire;
  onChange: (patch: Partial<LessonWorkbenchStyleWire>) => void;
  onReset: () => void;
}) {
  return (
    <section className="lw-card" aria-label="排版与间距" data-testid="lw-style-card">
      <header className="lw-card-head">
        <h2>排版</h2>
        <button type="button" className="lw-icon-button" aria-label="恢复默认排版" onClick={onReset}>
          <RotateCcw size={14} />
        </button>
      </header>
      <label className="lw-field">
        <span>字体</span>
        <select
          data-testid="lw-font-select"
          value={style.fontId}
          onChange={(event) => onChange({ fontId: event.target.value as LessonWorkbenchStyleWire['fontId'] })}
        >
          {LESSON_FONTS.map((font) => (
            <option key={font.id} value={font.id}>
              {font.label}
            </option>
          ))}
        </select>
      </label>
      <RangeField
        label="正文字号"
        testId="lw-size-base"
        value={style.baseSize}
        {...STYLE_LIMITS.baseSize}
        suffix="px"
        onChange={(value) => onChange({ baseSize: value })}
      />
      <RangeField
        label="模块标题字号"
        testId="lw-size-heading"
        value={style.headingSize}
        {...STYLE_LIMITS.headingSize}
        suffix="px"
        onChange={(value) => onChange({ headingSize: value })}
      />
      <RangeField
        label="字段标签字号"
        testId="lw-size-label"
        value={style.labelSize}
        {...STYLE_LIMITS.labelSize}
        suffix="px"
        onChange={(value) => onChange({ labelSize: value })}
      />
      <RangeField
        label="行高"
        testId="lw-line-height"
        value={style.lineHeight}
        {...STYLE_LIMITS.lineHeight}
        onChange={(value) => onChange({ lineHeight: value })}
      />

      <header className="lw-card-head sub">
        <h2>间距</h2>
      </header>
      <RangeField
        label="页边距"
        testId="lw-page-margin"
        value={style.pageMargin}
        {...STYLE_LIMITS.pageMargin}
        suffix="px"
        onChange={(value) => onChange({ pageMargin: value })}
      />
      <RangeField
        label="模块间距"
        testId="lw-module-gap"
        value={style.moduleGap}
        {...STYLE_LIMITS.moduleGap}
        suffix="px"
        onChange={(value) => onChange({ moduleGap: value })}
      />
      <RangeField
        label="段落间距"
        testId="lw-paragraph-gap"
        value={style.paragraphGap}
        {...STYLE_LIMITS.paragraphGap}
        suffix="px"
        onChange={(value) => onChange({ paragraphGap: value })}
      />
    </section>
  );
}
