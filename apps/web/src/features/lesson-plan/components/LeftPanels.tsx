'use client';
/**
 * 左栏三张设置卡：模块轨（magic-resume LayoutSetting 的移植）与排版。
 *
 * - 模块轨：framer-motion `Reorder` 拖拽手柄排序（基本模块固定在第一项），保留 ↑/↓、
 *   显隐、删除与「已移除」还原；每行显示模板序号、名称与已填状态点；
 * - 排版：字体与字号 / 间距 / 纸张三张卡，全部是受控控件，改值实时进预览。
 */
import { useState } from 'react';
import { Reorder, useDragControls, useReducedMotion } from 'framer-motion';
import {
  ChevronDown,
  ChevronUp,
  Eye,
  EyeOff,
  GripVertical,
  ListTree,
  Plus,
  RotateCcw,
  Ruler,
  ScrollText,
  Trash2,
  Type,
  Undo2,
} from 'lucide-react';
import type { LessonPlanData, LessonWorkbenchStyleWire } from '@/contracts/lesson-plans';
import {
  BUILTIN_MODULES,
  LESSON_FONTS,
  STYLE_LIMITS,
  moduleFilled,
  type LessonModuleEntry,
} from '../model/modules';
import { SettingCard } from './SettingCard';

/* ------------------------------------------------------------------ 布局 */

function ModuleItem({
  entry,
  index,
  count,
  numeral,
  active,
  filled,
  onSelect,
  onMove,
  onToggleHidden,
  onRemove,
}: {
  entry: LessonModuleEntry;
  index: number;
  count: number;
  numeral: string;
  active: boolean;
  filled: boolean;
  onSelect: () => void;
  onMove: (delta: number) => void;
  onToggleHidden: () => void;
  onRemove: () => void;
}) {
  const controls = useDragControls();
  const reduce = useReducedMotion();
  const fixed = entry.kind === 'builtin' && entry.builtinId === 'basic';

  return (
    <Reorder.Item
      value={entry.id}
      dragListener={false}
      dragControls={controls}
      data-module-index={index}
      data-testid={`lw-module-item-${entry.id}`}
      className={[
        'lw-module-item',
        active ? 'selected' : '',
        entry.hidden ? 'hidden' : '',
        fixed ? 'fixed' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      whileDrag={reduce ? undefined : { scale: 1.015, boxShadow: '0 12px 28px -14px rgb(23 32 51 / 35%)' }}
    >
      <button
        type="button"
        className="lw-module-grip"
        aria-label={`拖动排序（聚焦后 ↑/↓ 移动）：${entry.label}`}
        title={fixed ? '基本信息固定在首位' : `拖动排序：${entry.label}（聚焦后 ↑/↓ 移动）`}
        data-testid={`lw-module-drag-${entry.id}`}
        disabled={fixed}
        onPointerDown={(event) => {
          if (fixed) return;
          controls.start(event);
        }}
        onKeyDown={(event) => {
          if (fixed) return;
          if (event.key === 'ArrowUp') {
            event.preventDefault();
            onMove(-1);
          } else if (event.key === 'ArrowDown') {
            event.preventDefault();
            onMove(1);
          }
        }}
      >
        <GripVertical size={14} aria-hidden />
      </button>
      <button
        type="button"
        className="lw-module-name"
        title={entry.label}
        data-testid={`lw-module-select-${entry.id}`}
        onClick={onSelect}
        aria-current={active ? 'true' : undefined}
      >
        <span className={`lw-module-no ${entry.kind === 'custom' ? 'custom' : ''}`}>{numeral}</span>
        <span className="lw-module-label">{entry.label}</span>
        <span
          className={`lw-module-dot ${filled ? 'filled' : ''}`}
          title={filled ? '已有内容' : '尚未填写'}
          aria-label={filled ? '已有内容' : '尚未填写'}
        />
      </button>
      <span className="lw-module-actions">
        <span className="lw-module-move">
          <button
            type="button"
            className="lw-icon-button"
            aria-label={`上移：${entry.label}`}
            data-testid={`lw-module-up-${entry.id}`}
            disabled={index === 0}
            onClick={() => onMove(-1)}
          >
            <ChevronUp size={14} />
          </button>
          <button
            type="button"
            className="lw-icon-button"
            aria-label={`下移：${entry.label}`}
            data-testid={`lw-module-down-${entry.id}`}
            disabled={index === count - 1}
            onClick={() => onMove(1)}
          >
            <ChevronDown size={14} />
          </button>
        </span>
        <button
          type="button"
          className="lw-icon-button"
          aria-label={entry.hidden ? `显示：${entry.label}` : `隐藏：${entry.label}`}
          data-testid={`lw-module-hide-${entry.id}`}
          disabled={fixed}
          onClick={onToggleHidden}
        >
          {entry.hidden ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
        <button
          type="button"
          className="lw-icon-button danger"
          aria-label={`删除：${entry.label}`}
          data-testid={`lw-module-remove-${entry.id}`}
          disabled={entry.kind === 'builtin'}
          onClick={onRemove}
        >
          <Trash2 size={14} />
        </button>
      </span>
    </Reorder.Item>
  );
}

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
  const visibleCount = modules.filter((entry) => !entry.hidden).length;

  const numeralOf = (entry: LessonModuleEntry): string => {
    if (entry.kind === 'builtin') {
      return BUILTIN_MODULES.find((item) => item.id === entry.builtinId)?.no ?? '';
    }
    return '自';
  };

  const handleReorder = (nextIds: string[]) => {
    for (let index = 0; index < modules.length; index += 1) {
      if (modules[index].id !== nextIds[index]) {
        const to = nextIds.indexOf(modules[index].id);
        if (to >= 0) onReorder(index, to);
        return;
      }
    }
  };

  return (
    <SettingCard
      icon={ListTree}
      title="模块"
      hint={`${visibleCount} 个进入预览`}
      testId="lw-layout-card"
      action={<span className="lw-count-pill">{modules.length}</span>}
    >
      <Reorder.Group
        axis="y"
        values={modules.map((entry) => entry.id)}
        onReorder={handleReorder}
        className="lw-module-list"
        data-testid="lw-module-list"
      >
        {modules.map((entry, index) => (
          <ModuleItem
            key={entry.id}
            entry={entry}
            index={index}
            count={modules.length}
            numeral={numeralOf(entry)}
            active={entry.id === activeModuleId}
            filled={moduleFilled(entry, data)}
            onSelect={() => onSelect(entry.id)}
            onMove={(delta) => onMove(entry.id, delta)}
            onToggleHidden={() => onToggleHidden(entry.id)}
            onRemove={() => onRemove(entry.id)}
          />
        ))}
      </Reorder.Group>

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
          <span className="lw-removed-label">已移除</span>
          <div className="lw-removed-chips">
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
        </div>
      )}
    </SettingCard>
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
    <div className="lw-style-stack" data-testid="lw-style-card">
      <SettingCard icon={Type} title="字体与字号" hint="实时作用于右侧纸张">
        <label className="lw-field lw-field-inline">
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
      </SettingCard>

      <SettingCard icon={Ruler} title="间距" hint="行距与页面留白">
        <RangeField
          label="行高"
          testId="lw-line-height"
          value={style.lineHeight}
          {...STYLE_LIMITS.lineHeight}
          onChange={(value) => onChange({ lineHeight: value })}
        />
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
      </SettingCard>

      <SettingCard
        icon={ScrollText}
        title="纸张"
        hint="A4 · 正文从第 3 页起"
        action={
          <button type="button" className="lw-icon-button" aria-label="恢复默认排版" title="恢复默认排版" onClick={onReset}>
            <RotateCcw size={14} />
          </button>
        }
      >
        <p className="lw-note">
          预览与导出共用同一份排版：字体、字号、行高与页边距会同时进入 docx。页脚按模板从 1 起编号。
        </p>
      </SettingCard>
    </div>
  );
}
