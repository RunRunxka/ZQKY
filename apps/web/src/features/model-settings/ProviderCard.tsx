'use client';

import { ChevronRight, Star } from 'lucide-react';
import type { ModelConnectionView } from '@/contracts/model-settings';
import { ProviderMark } from './ProviderMark';

/**
 * 供应商卡片：一张卡代表一个连接（一个凭证 + 一个终端点）。
 *
 * "打开" 与 "使用" 是两个可见不同的动作——卡片点击只打开详情，切换问答默认
 * 模型只能由详情里明确的"使用此模型"触发。卡片右下角的箭头表示它可以打开。
 */
export function ProviderCard({
  connection,
  modelCount,
  inUseModelName,
  credentialKnown,
  onOpen,
}: {
  connection: ModelConnectionView;
  modelCount: number;
  inUseModelName: string | null;
  credentialKnown: boolean;
  onOpen: () => void;
}) {
  const label = connection.providerLabel ?? connection.displayName;
  return (
    <button
      type="button"
      className={`provider-card${inUseModelName ? ' in-use' : ''}`}
      onClick={onOpen}
      aria-label={`打开 ${connection.displayName} 的详情`}
    >
      <span className="provider-card-head">
        <ProviderMark providerId={connection.providerId} label={label} size={30} />
        <span className="provider-card-title">
          <strong>{connection.displayName}</strong>
          <small>{label ?? '自定义连接'}</small>
        </span>
      </span>
      <span className="provider-card-meta">
        <span className={`credential-chip${connection.hasCredential ? ' ready' : ''}`}>
          {connection.hasCredential ? '凭证已配置' : credentialKnown ? '需填写凭证' : '无需凭证'}
        </span>
        <span className="model-count-chip">
          {modelCount > 0 ? `${modelCount} 个模型` : '尚未添加模型'}
        </span>
      </span>
      <span className="provider-card-foot">
        {inUseModelName ? (
          <span className="in-use-note">
            <Star size={12} />
            当前使用 · {inUseModelName}
          </span>
        ) : (
          <span className="idle-note">{connection.apiFormat === 'auto' ? '自动格式' : connection.apiFormat}</span>
        )}
        <ChevronRight size={15} className="provider-card-chevron" />
      </span>
    </button>
  );
}
