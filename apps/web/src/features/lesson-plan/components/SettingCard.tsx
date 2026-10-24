'use client';
/**
 * 左栏/中栏通用的设置卡（magic-resume SettingCard 的移植）。
 *
 * 图标 + 标题 + 可选提示 + 右侧动作 + 内容；只消费全局 token，不引入第二套主题。
 */
import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

export function SettingCard({
  icon: Icon,
  title,
  hint,
  action,
  children,
  className,
  testId,
  ariaLabel,
}: {
  icon: LucideIcon;
  title: string;
  hint?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  testId?: string;
  ariaLabel?: string;
}) {
  return (
    <section
      className={`lw-card lw-setting-card ${className ?? ''}`.trim()}
      data-testid={testId}
      aria-label={ariaLabel ?? title}
    >
      <header className="lw-card-head">
        <span className="lw-card-icon" aria-hidden>
          <Icon size={15} />
        </span>
        <div className="lw-card-titles">
          <h2>{title}</h2>
          {hint && <span className="lw-card-hint">{hint}</span>}
        </div>
        {action && <div className="lw-card-action">{action}</div>}
      </header>
      <div className="lw-card-body">{children}</div>
    </section>
  );
}
