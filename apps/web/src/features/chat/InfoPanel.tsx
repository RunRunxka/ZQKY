'use client';
import Link from 'next/link';
import { CAPABILITY_EVIDENCE_LABELS } from '@/contracts/model-settings';
import type { ModelProfileView } from '@/contracts/model-settings';
import type { ConversationMeta } from '@/contracts/chat';
import { buildCapabilityRows } from './model/capability-rows';
import { useCapabilityStatus } from './model/use-capability-status';

/**
 * 会话详情面板（学习问答）。
 *
 * 「对话能力边界」一节的每一行都由真实接口状态驱动（F1-CHAT v1.1 · 修复 A1 r1 D6）：
 * - 教材检索（RAG）与来源引用：`/capabilities` 的 rag 项 + `/rag/status` 分项；
 *   **不再硬编码「规划中」**，检索不可用时给出原因，并始终保留「人工教学质量尚未验收」；
 * - MCP / Skills：按 `/capabilities` 的 mcp/skills 状态显示；
 * - 附件与图片解析：无对应接口可判定，按前端实际门控如实标注「暂未接入」（不写「已实现」）；
 * - 任一接口读取失败：显示「状态未知 / 读取失败」并提供重试，**不回落成「规划中」或「可用」**。
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
  const capabilityStatus = useCapabilityStatus();
  const rows = buildCapabilityRows({
    features: capabilityStatus.features,
    rag: capabilityStatus.rag,
    capsError: capabilityStatus.capsError,
    ragError: capabilityStatus.ragError,
  });
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
      <section>
        <h3>对话能力边界</h3>
        <ul className="chat-info-capabilities">
          {rows.map((row) => (
            <li key={row.key} className={`chat-info-capability ${row.tone}`} data-capability={row.key}>
              <div className="chat-info-capability-head">
                <span className="chat-info-capability-name">{row.name}</span>
                <span className={`chat-info-state ${row.tone}`} data-state={row.badge}>
                  {row.badge}
                </span>
              </div>
              {row.details.length > 0 && (
                <ul className="chat-info-details">
                  {row.details.map((detail) => (
                    <li key={detail} className="chat-info-muted">
                      {detail}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
        {rows.some((row) => row.retry) && (
          <p className="chat-info-muted">
            能力状态读取失败，原因可能只是暂时不可达：
            <button type="button" className="chat-info-retry" onClick={capabilityStatus.reload}>
              重新读取状态
            </button>
          </p>
        )}
        <p className="chat-info-muted">
          历史保存在当前浏览器；发送时会将选定上下文传给所选模型服务。清理数据前请备份重要内容。
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
