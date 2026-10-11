'use client';
import { Eye, EyeOff, Type } from 'lucide-react';
import { LESSON_FONTS, LESSON_MODULES, moduleFilled, type LessonModuleId, type LessonStyleState } from '../model/modules';

/**
 * 三栏式左栏（C3-2 复刻 Magic Resume 结构，品牌蓝主题）：
 * 上半「教案模块」列表（基本信息固定；其余可显隐），下半「字体排版」卡。
 */
export function ModuleNav({
  data,
  selected,
  style,
  onSelect,
  onToggleHidden,
  onStyle,
}: {
  data: import('@/contracts/lesson-plans').LessonPlanData;
  selected: LessonModuleId;
  style: LessonStyleState;
  onSelect(id: LessonModuleId): void;
  onToggleHidden(id: LessonModuleId): void;
  onStyle(patch: Partial<LessonStyleState>): void;
}) {
  const visible = LESSON_MODULES.filter((m) => !style.hiddenModules.includes(m.id));
  return (
    <aside className="lesson-modnav" aria-label="教案模块与排版">
      <section className="lesson-modnav-card">
        <h3>教案模块</h3>
        <ul className="lesson-modlist">
          {visible.map((m) => (
            <li key={m.id}>
              <button
                type="button"
                className={`lesson-moditem ${selected === m.id ? 'selected' : ''}`}
                onClick={() => onSelect(m.id)}
              >
                <span className="lesson-modno">{m.no}</span>
                <span className="lesson-modname">{m.label}</span>
                {moduleFilled(m.id, data) && <span className="lesson-moddot" aria-label="已填写" />}
                {!m.fixed && (
                  <span
                    role="button"
                    tabIndex={0}
                    aria-label={`隐藏 ${m.label}`}
                    className="lesson-modhide"
                    onClick={(e) => { e.stopPropagation(); onToggleHidden(m.id); }}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); onToggleHidden(m.id); } }}
                  >
                    <Eye size={13} aria-hidden />
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
        {style.hiddenModules.length > 0 && (
          <div className="lesson-modhidden">
            <span>已隐藏：</span>
            {style.hiddenModules.map((id) => {
              const m = LESSON_MODULES.find((x) => x.id === id)!;
              return (
                <button key={id} type="button" className="lesson-modrestore" onClick={() => onToggleHidden(id)}>
                  <EyeOff size={11} aria-hidden /> {m.label}
                </button>
              );
            })}
          </div>
        )}
      </section>
      <section className="lesson-modnav-card">
        <h3><Type size={13} aria-hidden /> 字体排版</h3>
        <label className="lesson-style-field">
          字体
          <select value={style.fontId} onChange={(e) => onStyle({ fontId: e.target.value })}>
            {LESSON_FONTS.map((f) => (
              <option key={f.id} value={f.id}>{f.label}</option>
            ))}
          </select>
        </label>
        <label className="lesson-style-field">
          字号 <span className="lesson-style-value">{style.fontSize}px</span>
          <input
            type="range" min={12} max={18} step={1}
            value={style.fontSize}
            onChange={(e) => onStyle({ fontSize: Number(e.target.value) })}
          />
        </label>
        <label className="lesson-style-field">
          行高 <span className="lesson-style-value">{style.lineHeight.toFixed(1)}</span>
          <input
            type="range" min={1.3} max={2.2} step={0.1}
            value={style.lineHeight}
            onChange={(e) => onStyle({ lineHeight: Number(e.target.value) })}
          />
        </label>
      </section>
    </aside>
  );
}
