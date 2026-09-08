'use client';
import Link from 'next/link';
import { CAPABILITY_EVIDENCE_LABELS } from '@/contracts/model-settings';
import type { ModelProfileView } from '@/contracts/model-settings';
import type { ConversationMeta } from '@/contracts/chat';

export function InfoPanel({
  profile,
  mock,
  conversations,
  activeId,
  messageCount,
}: {
  profile: ModelProfileView | null;
  mock?: boolean;
  conversations: ConversationMeta[];
  activeId: string | null;
  messageCount: number;
}) {
  return (
    <div className="chat-info-inner">
      <section>
        <h3>当前模型</h3>
        {mock ? (
          <ul className="chat-info-list">
            <li>模拟模型 · 本地脚本</li>
            <li className="chat-info-muted">不访问真实模型、MCP 或外部工具</li>
            <li className="chat-info-muted">回复带【模拟回复】标识，仅用于体验对话流程</li>
          </ul>
        ) : profile ? (
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
      <section>
        <h3>对话能力边界</h3>
        <ul className="chat-info-planned">
          {['教材检索（RAG）与来源引用', '附件与图片解析', 'MCP 工具调用', 'Skills 技能'].map(
            (name) => (
              <li key={name}>
                <span>{name}</span>
                <span className="small-badge">规划中</span>
              </li>
            ),
          )}
        </ul>
        <p className="chat-info-muted">
          {mock
            ? '模拟会话保存在当前浏览器的独立存储，与真实问答相互隔离。'
            : '历史保存在当前浏览器；发送时会将选定上下文传给所选模型服务。清理数据前请备份重要内容。'}
        </p>
      </section>
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
