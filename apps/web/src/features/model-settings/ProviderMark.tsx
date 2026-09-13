'use client';

import { providerMark } from './provider-icons';

/** 供应商标记：有官方图标用图标，否则用首字母块（不猜测、不引入新素材）。 */
export function ProviderMark({
  providerId,
  label,
  size = 28,
}: {
  providerId: string | null | undefined;
  label?: string | null;
  size?: number;
}) {
  const mark = providerMark(providerId, label);
  if (mark.icon) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={`/provider-icons/${mark.icon}.svg`}
        alt=""
        width={size}
        height={size}
        className="provider-mark-image"
      />
    );
  }
  return (
    <span className="provider-mark-initials" aria-hidden="true" style={{ width: size, height: size }}>
      {mark.initials}
    </span>
  );
}
