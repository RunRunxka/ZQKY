'use client';
/**
 * 右侧悬浮快捷 dock（magic-resume PreviewDock 的教案版）。
 *
 * - 只放「全局动作」：AI 生成、导出、本地教案、面板显隐、打印、帮助；
 * - 图标按钮全部带 tooltip（Radix）与 aria-label；
 * - 面板显隐用 `aria-pressed` 表达当前状态（显示 = 按下）；
 * - ≤1023px 隐藏（手机端用页签切换）。
 */
import { motion, useReducedMotion } from 'framer-motion';
import {
  Download,
  FolderOpen,
  HelpCircle,
  LoaderCircle,
  PanelLeft,
  PanelRight,
  Printer,
  ScanEye,
  Sparkles,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { Tip } from './Tooltip';

function DockButton({
  label,
  onClick,
  disabled,
  active,
  children,
  testId,
}: {
  label: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
  children: ReactNode;
  testId?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <Tip label={label}>
      <motion.button
        type="button"
        className={`lw-dock-button ${active ? 'active' : ''}`}
        aria-label={typeof label === 'string' ? label : undefined}
        aria-pressed={active}
        disabled={disabled}
        data-testid={testId}
        onClick={onClick}
        whileHover={reduce || disabled ? undefined : { scale: 1.12 }}
        whileTap={reduce || disabled ? undefined : { scale: 0.94 }}
        transition={{ type: 'spring', stiffness: 420, damping: 26 }}
      >
        {children}
      </motion.button>
    </Tip>
  );
}

export interface PreviewDockProps {
  onGenerate: () => void;
  onExport: () => void;
  exportBusy?: boolean;
  onLibrary: () => void;
  onPrint: () => void;
  onHelp: () => void;
  onToggleLayout: () => void;
  onToggleEditor: () => void;
  onTogglePreview: () => void;
  layoutVisible: boolean;
  editorVisible: boolean;
  previewVisible: boolean;
}

export function PreviewDock({
  onGenerate,
  onExport,
  exportBusy,
  onLibrary,
  onPrint,
  onHelp,
  onToggleLayout,
  onToggleEditor,
  onTogglePreview,
  layoutVisible,
  editorVisible,
  previewVisible,
}: PreviewDockProps) {
  const reduce = useReducedMotion();

  return (
    <motion.div
      className="lw-dock"
      role="toolbar"
      aria-orientation="vertical"
      aria-label="教案快捷操作"
      data-testid="lw-dock"
      initial={reduce ? false : { opacity: 0, x: 24 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
    >
      <DockButton label="AI 生成教案" onClick={onGenerate} testId="lw-dock-generate">
        <Sparkles size={17} />
      </DockButton>
      <DockButton
        label={exportBusy ? '正在导出…' : '导出 Word'}
        onClick={onExport}
        disabled={exportBusy}
        testId="lw-dock-export"
      >
        {exportBusy ? <LoaderCircle size={17} className="lw-spin" /> : <Download size={17} />}
      </DockButton>
      <DockButton label="本地教案" onClick={onLibrary} testId="lw-dock-library">
        <FolderOpen size={17} />
      </DockButton>

      <span className="lw-dock-divider" aria-hidden />

      <DockButton
        label={layoutVisible ? '隐藏布局栏' : '显示布局栏'}
        onClick={onToggleLayout}
        active={layoutVisible}
        testId="lw-dock-layout"
      >
        <PanelLeft size={17} />
      </DockButton>
      <DockButton
        label={editorVisible ? '隐藏编辑栏' : '显示编辑栏'}
        onClick={onToggleEditor}
        active={editorVisible}
        testId="lw-dock-editor"
      >
        <PanelRight size={17} />
      </DockButton>
      <DockButton
        label={previewVisible ? '隐藏预览' : '显示预览'}
        onClick={onTogglePreview}
        active={previewVisible}
        testId="lw-dock-preview"
      >
        <ScanEye size={17} />
      </DockButton>

      <span className="lw-dock-divider" aria-hidden />

      <DockButton label="打印预览" onClick={onPrint} testId="lw-dock-print">
        <Printer size={17} />
      </DockButton>
      <DockButton label="工作台帮助" onClick={onHelp} testId="lw-dock-help">
        <HelpCircle size={17} />
      </DockButton>
    </motion.div>
  );
}
