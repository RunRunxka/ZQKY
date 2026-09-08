'use client';
import {
  Check,
  PanelLeftClose,
  SlidersHorizontal,
  ListTree,
  ShieldCheck,
  Upload,
  Info,
  RotateCcw,
} from 'lucide-react';
import { useLessonEditor } from '../model/EditorContext';
import { sections } from '../model/sections';
import { Field } from '@/components/ui/Field';
export function OutlinePanel() {
  const {
    active,
    layoutTab,
    setLayoutTab,
    setCollapsed,
    fontSize,
    setFontSize,
    fileInput,
    selectSection,
    completed,
    completeCount,
  } = useLessonEditor();
  return (
    <>
      <aside className="outline-panel">
        <div className="outline-heading">
          <span>教案配置</span>
          <button
            className="icon-button"
            aria-label="收起教案配置"
            onClick={() => setCollapsed(true)}
          >
            <PanelLeftClose size={17} />
          </button>
        </div>
        <div className="segmented">
          <button
            className={layoutTab === 'outline' ? 'selected' : ''}
            onClick={() => setLayoutTab('outline')}
          >
            <ListTree size={15} />
            内容结构
          </button>
          <button
            className={layoutTab === 'style' ? 'selected' : ''}
            onClick={() => setLayoutTab('style')}
          >
            <SlidersHorizontal size={15} />
            版式
          </button>
        </div>
        {layoutTab === 'outline' ? (
          <>
            <div className="sidebar-section-label">
              教案内容 <span>{completeCount} / 7</span>
            </div>
            <div className="section-nav">
              {sections.map((section, i) => {
                const Icon = section.icon;
                return (
                  <button
                    key={section.id}
                    className={`section-nav-item ${active === section.id ? 'active' : ''}`}
                    onClick={() => selectSection(section.id)}
                  >
                    <Icon size={17} />
                    <span>{section.label}</span>
                    {completed(section.id) ? (
                      <Check size={13} className="completion-check" />
                    ) : (
                      <span className="section-index">{String(i + 1).padStart(2, '0')}</span>
                    )}
                  </button>
                );
              })}
            </div>
            <div className="outline-note">
              <span className="small-dot" />
              教学反思可以在授课后补充
            </div>
            <div className="sidebar-divider" />
            <div className="sidebar-section-label">
              当前模板 <span className="small-badge">1 款</span>
            </div>
            <div className="template-card" role="img" aria-label="教师备课标准表格模板缩略图">
              <div className="template-mini">
                <div className="mini-title">教师备课教案</div>
                <div className="mini-table">
                  {Array.from({ length: 7 }, (_, i) => (
                    <div key={i}>
                      <i />
                      <span />
                    </div>
                  ))}
                </div>
              </div>
              <div className="template-card-caption">
                <span>
                  教师备课标准模板<small>原始 Word 模板适配</small>
                </span>
                <span className="template-selected">
                  <Check size={12} />
                </span>
              </div>
            </div>
            <button className="import-link" onClick={() => fileInput.current?.click()}>
              <Upload size={14} />
              导入教案草稿
            </button>
          </>
        ) : (
          <div className="style-settings">
            <h3>纸张与文字</h3>
            <Field label="PDF 纸张">
              <select value="a4" onChange={() => {}}>
                <option value="a4">A4 · 210 × 297 mm</option>
              </select>
            </Field>
            <Field label="预览与 PDF 字号" hint={`${fontSize}px`}>
              <input
                aria-label="预览字号"
                type="range"
                min="12"
                max="16"
                value={fontSize}
                onChange={(e) => setFontSize(+e.target.value)}
              />
            </Field>
            <div className="setting-note">
              <Info size={16} />
              <p>Word 保留原模板的纸张、字体和行高。此处字号仅用于网页预览与 PDF。</p>
            </div>
            <button className="button subtle" onClick={() => setFontSize(14)}>
              <RotateCcw size={14} />
              恢复默认版式
            </button>
          </div>
        )}
        <div className="local-mode">
          <ShieldCheck size={17} />
          <div>
            本地工作模式<small>草稿保存在当前浏览器</small>
          </div>
        </div>
      </aside>
    </>
  );
}
