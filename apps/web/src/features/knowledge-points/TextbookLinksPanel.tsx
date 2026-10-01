'use client';

/**
 * 教材依据（可选）：列出 / 新增（`documentRevisionId` + `charStart/charEnd`）/ 删除。
 *
 * 关键纪律（任务卡 §7）：
 * - 教材目录不可用时后端返回 503 `TEXTBOOK_EVIDENCE_UNAVAILABLE` →
 *   必须显示「教材依据暂不可用（服务未就绪）」，**绝不能显示成「没有依据」**；
 * - 「没有依据」只在**成功读取且 0 条**时出现；
 * - 区间交服务端向教材目录核验并冻结标题，前端不自己拼标题；
 * - 删除带知识点 `expectedRevision`（乐观锁；冲突显示当前版本并刷新）。
 */

import { useState } from 'react';
import { Link2, RefreshCw, Trash2 } from 'lucide-react';
import type { KnowledgePointView, TextbookLinkView } from '@/contracts/knowledge';
import type { DocumentSummary } from '@/contracts/textbook';
import {
  createTextbookLink,
  deleteTextbookLink,
  listTextbookLinks,
} from '@/services/knowledge-points-api';
import { listDocuments } from '@/services/textbook-api';
import { asApiError, useAsyncResource } from './hooks';
import {
  TEXTBOOK_EVIDENCE_UNAVAILABLE_CODE,
  TEXTBOOK_EVIDENCE_UNAVAILABLE_TEXT,
  formatDateTime,
} from './labels';

export function TextbookLinksPanel({
  point,
  onPointChanged,
}: {
  point: KnowledgePointView;
  onPointChanged: (next: KnowledgePointView) => void;
}) {
  const links = useAsyncResource(
    (signal) => listTextbookLinks(point.id, signal),
    `kp-links|${point.id}`,
  );
  const documents = useAsyncResource((signal) => listDocuments({}, signal), 'kp-documents');

  const [documentId, setDocumentId] = useState('');
  const [documentRevisionId, setDocumentRevisionId] = useState('');
  const [charStart, setCharStart] = useState('0');
  const [charEnd, setCharEnd] = useState('1');
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyLinkId, setBusyLinkId] = useState<string | null>(null);

  const linksError = links.state.phase === 'failed' ? links.state.error : null;
  const unavailable = linksError?.code === TEXTBOOK_EVIDENCE_UNAVAILABLE_CODE;

  const documentOptions: DocumentSummary[] =
    documents.state.phase === 'ready' ? documents.state.data.documents : [];

  function pickDocument(nextId: string) {
    setDocumentId(nextId);
    const found = documentOptions.find((item) => item.documentId === nextId);
    setDocumentRevisionId(found?.currentRevision?.revisionId ?? '');
  }

  async function addLink() {
    const start = Number.parseInt(charStart, 10);
    const end = Number.parseInt(charEnd, 10);
    if (!documentRevisionId.trim()) {
      setFormError('请填写或选择教材修订 id（documentRevisionId）。');
      return;
    }
    if (!Number.isInteger(start) || start < 0 || !Number.isInteger(end) || end <= start) {
      setFormError('字符区间需满足 charStart ≥ 0 且 charEnd > charStart。');
      return;
    }
    setBusy(true);
    setFormError(null);
    setNotice(null);
    try {
      const created = await createTextbookLink(point.id, {
        expectedRevision: point.revision,
        documentRevisionId: documentRevisionId.trim(),
        charStart: start,
        charEnd: end,
        source: 'human',
      });
      setNotice(
        `已新增教材依据：${created.titleSnapshot}（字符 ${created.charStart}–${created.charEnd}）。`,
      );
      setDocumentRevisionId('');
      links.reload();
      onPointChanged(point);
    } catch (cause) {
      const error = asApiError(cause);
      if (error.code === TEXTBOOK_EVIDENCE_UNAVAILABLE_CODE) {
        setFormError(`${TEXTBOOK_EVIDENCE_UNAVAILABLE_TEXT}：${error.message}`);
      } else if (error.status === 409) {
        setFormError(
          `当前版本 ${error.details?.currentRevision ?? '未知'}，已刷新为最新，请重试：${error.message}`,
        );
        links.reload();
      } else {
        // 422 等字段级错误：把服务端给的定位字段一并显示，便于修正区间/修订 id
        const fields = error.details?.fields?.join('、');
        setFormError(
          `新增教材依据失败（${error.code}）${fields ? `（定位字段：${fields}）` : ''}：${error.message}`,
        );
      }
    } finally {
      setBusy(false);
    }
  }

  async function removeLink(link: TextbookLinkView) {
    setBusyLinkId(link.linkId);
    setFormError(null);
    setNotice(null);
    try {
      await deleteTextbookLink(point.id, link.linkId, point.revision);
      setNotice('已删除该条教材依据（历史修订与冻结标题不在此处改写）。');
      links.reload();
    } catch (cause) {
      const error = asApiError(cause);
      if (error.status === 409) {
        setFormError(
          `当前版本 ${error.details?.currentRevision ?? '未知'}，已刷新为最新，请重试：${error.message}`,
        );
      } else if (error.status === 404) {
        setFormError('该教材依据已不存在（可能已被删除）；已刷新列表。');
        links.reload();
      } else {
        setFormError(`删除教材依据失败（${error.code}）：${error.message}`);
      }
    } finally {
      setBusyLinkId(null);
    }
  }

  return (
    <section className="kp-subpanel" aria-label="教材依据">
      <header className="kp-subpanel-head">
        <h3>
          <Link2 size={14} aria-hidden />
          教材依据
        </h3>
        <button className="space-button" onClick={links.reload}>
          <RefreshCw size={13} aria-hidden />
          刷新依据
        </button>
      </header>
      <p className="kp-hint">
        可选：把知识点挂到教材的某个不可变修订区间上（服务端会核验区间并冻结标题快照）。
      </p>

      {unavailable && linksError && (
        <div className="space-banner error" role="alert">
          <div className="space-banner-row">
            <span data-testid="kp-evidence-unavailable">
              {TEXTBOOK_EVIDENCE_UNAVAILABLE_TEXT}：{linksError.message}
            </span>
            <button className="space-button" onClick={links.reload}>
              重试
            </button>
          </div>
          <span>这里是有依据但读不到，和「没有依据」不同；请检查教材目录服务后就绪后重试。</span>
        </div>
      )}

      {linksError && !unavailable && (
        <div className="space-banner error" role="alert">
          <div className="space-banner-row">
            <span>
              教材依据读取失败（{linksError.code}）：{linksError.message}
            </span>
            <button className="space-button" onClick={links.reload}>
              重试
            </button>
          </div>
        </div>
      )}

      {links.state.phase === 'loading' && (
        <div
          className="space-skeleton"
          style={{ height: 48 }}
          aria-busy="true"
          aria-label="正在读取教材依据"
        />
      )}

      {links.state.phase === 'ready' && links.state.data.items.length === 0 && (
        <p className="space-empty" data-testid="kp-evidence-empty">
          <strong>没有教材依据</strong>
          <span>服务端已成功读取，该知识点当前没有挂任何教材依据。</span>
        </p>
      )}

      {links.state.phase === 'ready' && links.state.data.items.length > 0 && (
        <ul className="kp-link-list">
          {links.state.data.items.map((link) => (
            <li key={link.linkId} className="kp-link-row">
              <span className="kp-link-title">{link.titleSnapshot}</span>
              <span className="space-meta-row">
                <span className="space-chip">
                  字符 {link.charStart}–{link.charEnd}
                </span>
                <span className="space-chip">
                  {link.source === 'ai_confirmed' ? 'AI 候选确认' : '人工挂接'}
                </span>
                <span className="space-chip">修订 {link.documentRevisionId}</span>
                <span className="space-chip">{formatDateTime(link.createdAt)}</span>
              </span>
              <button
                className="space-button danger"
                disabled={busyLinkId === link.linkId}
                onClick={() => void removeLink(link)}
              >
                <Trash2 size={13} aria-hidden />
                {busyLinkId === link.linkId ? '删除中…' : '删除依据'}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="kp-link-form">
        <label className="kp-field">
          <span className="kp-field-label">教材书册（可选，用于带出当前修订）</span>
          <select
            className="space-select"
            value={documentId}
            aria-label="选择教材书册"
            onChange={(event) => pickDocument(event.target.value)}
          >
            <option value="">不选择（直接填写修订 id）</option>
            {documentOptions.map((item) => (
              <option key={item.documentId} value={item.documentId}>
                {item.title}
                {item.currentRevision ? '' : '（尚未入库修订）'}
              </option>
            ))}
          </select>
        </label>
        <label className="kp-field">
          <span className="kp-field-label">教材修订 id</span>
          <input
            value={documentRevisionId}
            aria-label="教材修订 id"
            placeholder="documentRevisionId"
            disabled={busy}
            onChange={(event) => setDocumentRevisionId(event.target.value)}
          />
        </label>
        <label className="kp-field kp-field-narrow">
          <span className="kp-field-label">起始字符</span>
          <input
            type="number"
            min={0}
            value={charStart}
            disabled={busy}
            onChange={(event) => setCharStart(event.target.value)}
          />
        </label>
        <label className="kp-field kp-field-narrow">
          <span className="kp-field-label">结束字符</span>
          <input
            type="number"
            min={1}
            value={charEnd}
            disabled={busy}
            onChange={(event) => setCharEnd(event.target.value)}
          />
        </label>
        <button className="space-button primary" disabled={busy} onClick={() => void addLink()}>
          {busy ? '新增中…' : '新增教材依据'}
        </button>
      </div>

      {formError && (
        <p className="space-banner error" role="alert">
          {formError}
        </p>
      )}
      {notice && (
        <p className="space-banner info" role="status">
          {notice}
        </p>
      )}
    </section>
  );
}
