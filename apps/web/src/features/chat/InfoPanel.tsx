'use client';
import Link from 'next/link';
import { CAPABILITY_EVIDENCE_LABELS } from '@/contracts/model-settings';
import type { ModelProfileView } from '@/contracts/model-settings';
import type { ConversationMeta } from '@/contracts/chat';

/**
 * 会话详情面板（骨架版）：当前模型 + 本会话统计 + 数据说明。
 * 能力边界随业务重建逐项回归时再扩展。
 */
export function InfoPanel({
  profile,
  conversations,
  activeId,
  messageCount,
}: {
  profile: ModelProfileView | null;
  conversations: ConversationMeta[];
  activeId: string | null;
  messageCount: number;
}) {
  return (
    <div className="chat-info-inner">
      <section>
        <h3>当前模型</h3>
        {profile ? (
          <ul className="chat-info-list">
            <li>{profile.displayName}</li>
            <li className="chat-info-muted">模型 ID：{profile.modelId}</li>
            <li className="chat-info-muted">
              对话能力：{CAPABILITY_EVIDENCE_LABELS[profile.capabilities.chat ?? 'unknown']}
            </li>
            <li className="chat-info-muted">
              连接：{profile.connection?.displayName ?? '未找到'}（
              {profile.connection?.hasCredential ? '已配置凭证' : '未配置凭证'}）
            </li>
          </ul>
        ) : (
          <p className="chat-info-muted">未选择模型</p>
        )}
      </section>
      <section>
        <h3>本会话</h3>
        <ul className="chat-info-list">
          <li>{messageCount} 条消息</li>
          <li className="chat-info-muted">共 {conversations.length} 个会话（保存在当前浏览器）</li>
        </ul>
      </section>
      <p className="chat-info-muted">
        历史保存在当前浏览器；发送时会将对话历史传给所选模型服务。清理数据前请备份重要内容。
      </p>
      <p className="chat-info-muted">
        模型配置有问题？前往{' '}
        <Link href="/settings" className="chat-link">
          设置
        </Link>{' '}
        检查连接与凭证。
      </p>
      {activeId === null && <span className="chat-hidden" aria-hidden="true" />}
    </div>
  );
}
