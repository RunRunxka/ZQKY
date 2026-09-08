import type { ReactNode } from 'react';
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span className="field-label">
        {label}
        {hint && <small>{hint}</small>}
      </span>
      {children}
    </label>
  );
}
