'use client';

/**
 * 书册「编辑分类」：读取书册详情 → 元数据表单 → 以 `expectedRevision` 乐观锁保存。
 * 409（REVISION_CONFLICT）时保留用户填写、重新读取服务端版本供比较，不覆盖输入、不静默重试。
 */

import { useCallback, useEffect, useState } from 'react';
import type { DocumentDetail, DocumentMetadataInput } from '@/contracts/textbook';
import { ApiError } from '@/services/api-client';
import { getDocument, patchDocument } from '@/services/textbook-api';
import { asApiError, errorText } from './hooks';
import { MetadataForm, metadataErrors, normalizeMetadata } from './MetadataForm';
import type { TaxonomyIndex } from './taxonomy';

type LoadState =
  | { phase: 'loading' }
  | { phase: 'ready'; detail: DocumentDetail }
  | { phase: 'failed'; error: ApiError };

export function DocumentEditForm({
  documentId,
  taxonomy,
  onSaved,
  onConflictRefresh,
  onCancel,
}: {
  documentId: string;
  taxonomy: TaxonomyIndex;
  onSaved: () => void;
  /** 冲突时通知父级刷新列表（只刷新展示，不覆盖本表单输入）。 */
  onConflictRefresh: () => void;
  onCancel: () => void;
}) {
  const [state, setState] = useState<LoadState>({ phase: 'loading' });
  const [value, setValue] = useState<DocumentMetadataInput | null>(null);
  const [serverSnapshot, setServerSnapshot] = useState<DocumentMetadataInput | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setState({ phase: 'loading' });
      try {
        const detail = await getDocument(documentId, signal);
        setState({ phase: 'ready', detail });
        return detail;
      } catch (cause) {
        setState({ phase: 'failed', error: asApiError(cause) });
        return null;
      }
    },
    [documentId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal).then((detail) => {
      if (detail) setValue({ ...detail.metadata });
    });
    return () => controller.abort();
  }, [load]);

  async function save() {
    if (!value || state.phase !== 'ready') return;
    const errors = metadataErrors(value);
    if (errors.length > 0) {
      setFormError(errors.join(' '));
      return;
    }
    setFormError(null);
    setConflict(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await patchDocument(documentId, {
        expectedRevision: state.detail.revision,
        metadata: normalizeMetadata(value),
        libraryIds: state.detail.libraryIds,
      });
      if (updated) setState({ phase: 'ready', detail: updated });
      setNotice('分类已保存。');
      onSaved();
    } catch (cause) {
      const apiError = asApiError(cause);
      if (apiError.status === 409) {
        // 保留用户输入；重新读取服务端最新分类供比较
        setConflict(`保存冲突（${apiError.code}）：${apiError.message} 你的填写已保留。`);
        const latest = await load();
        if (latest) setServerSnapshot({ ...latest.metadata });
        onConflictRefresh();
      } else {
        setFormError(errorText(cause));
      }
    } finally {
      setBusy(false);
    }
  }

  if (state.phase === 'loading') {
    return <div className="space-skeleton" style={{ height: 120 }} aria-hidden />;
  }

  if (state.phase === 'failed') {
    return (
      <div className="space-banner error" role="alert">
        书册详情读取失败（{state.error.code}）：{state.error.message}
        <div className="textbook-panel-actions">
          <button className="space-button" onClick={() => void load()}>
            重试
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="textbook-edit">
      <p className="textbook-hint">
        保存使用乐观锁：当前书册修订 r{state.detail.revision}；若期间被其他操作修改会返回
        409，届时保留你的填写供比较。
      </p>
      {value && (
        <MetadataForm
          value={value}
          onChange={setValue}
          taxonomy={taxonomy}
          idPrefix={`edit-${documentId}`}
          disabled={busy}
        />
      )}
      {formError && (
        <p className="space-banner error" role="alert">
          {formError}
        </p>
      )}
      {conflict && (
        <div className="space-banner error" role="alert">
          {conflict}
          {serverSnapshot && (
            <div>
              <p className="textbook-hint">
                服务端最新分类：{serverSnapshot.title} · 学段{' '}
                {taxonomy.stageLabel(serverSnapshot.stageId)} · 年级{' '}
                {taxonomy.gradeLabels(serverSnapshot.gradeIds) || '—'} · 学科{' '}
                {taxonomy.subjectLabel(serverSnapshot.subjectId)} · 版本{' '}
                {taxonomy.editionLabel(serverSnapshot.editionId)}
              </p>
              <button className="space-button" onClick={() => setValue({ ...serverSnapshot })}>
                用服务端版本覆盖我的填写
              </button>
            </div>
          )}
        </div>
      )}
      {notice && (
        <p className="space-banner info" role="status">
          {notice}
        </p>
      )}
      <div className="textbook-panel-actions">
        <button className="space-button primary" onClick={() => void save()} disabled={busy}>
          {busy ? '保存中…' : '保存分类'}
        </button>
        <button className="space-button" onClick={onCancel} disabled={busy}>
          取消
        </button>
      </div>
    </div>
  );
}
