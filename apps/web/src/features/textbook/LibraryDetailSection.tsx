'use client';

/**
 * 逻辑库详情：库信息 + 书册列表（当前可用修订、待入库修订、是否可检索）+ 每册
 * 「更新 / 编辑分类 / 删除 / 来源预览」。
 *
 * 所有数据来自服务端；删除与分类保存都带 `expectedRevision` 乐观锁，409 时提示冲突并
 * 刷新比较，绝不静默覆盖。
 */

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import '@/components/layout/space.css';
import '@/features/textbook/styles/textbook.css';
import type { DocumentMetadataInput, DocumentSummary, LibraryDetail } from '@/contracts/textbook';
import {
  deleteDocument,
  fetchTextbookTaxonomy,
  getDocument,
  getLibrary,
} from '@/services/textbook-api';
import { DocumentEditForm } from './DocumentEditForm';
import { DocumentSourcePreview } from './DocumentSourcePreview';
import { asApiError, useAsyncResource } from './hooks';
import { ImportPanel, type ImportTarget } from './ImportPanel';
import { LIBRARY_KIND_LABEL } from './labels';
import { buildTaxonomyIndex, type TaxonomyIndex } from './taxonomy';

function isRetrievable(document: DocumentSummary): boolean {
  return Boolean(document.currentRevision && !document.pendingRevisionId && !document.deletedAt);
}

type OpenPanel = { kind: 'edit' | 'source'; documentId: string } | null;

/** 更新目标只记 id/title；期望修订在渲染时从最新库数据派生，避免持有过期修订。 */
type UpdateTargetRef = { documentId: string; title: string };

export function LibraryDetailSection({ libraryId }: { libraryId: string }) {
  const [refreshToken, setRefreshToken] = useState(0);
  const [openPanel, setOpenPanel] = useState<OpenPanel>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [updateTarget, setUpdateTarget] = useState<UpdateTargetRef | null>(null);
  const [updateSeed, setUpdateSeed] = useState<DocumentMetadataInput | null>(null);
  const [updateSeedError, setUpdateSeedError] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  const refresh = () => setRefreshToken((value) => value + 1);
  const taxonomy = useAsyncResource((signal) => fetchTextbookTaxonomy(signal), 'detail-taxonomy');
  const index = useMemo(
    () => buildTaxonomyIndex(taxonomy.state.phase === 'ready' ? taxonomy.state.data : null),
    [taxonomy.state],
  );
  const { state, reload } = useAsyncResource(
    (signal) => getLibrary(libraryId, signal),
    `${libraryId}|${refreshToken}`,
  );

  // 期望修订始终取当前列表里的已发布修订（刷新后自动更新，不再持有过期值）
  const resolvedTarget: ImportTarget | null = updateTarget
    ? {
        documentId: updateTarget.documentId,
        title:
          (state.phase === 'ready'
            ? state.data.documents.find((item) => item.documentId === updateTarget.documentId)
                ?.title
            : undefined) ?? updateTarget.title,
        expectedCurrentRevisionId:
          state.phase === 'ready'
            ? (state.data.documents.find((item) => item.documentId === updateTarget.documentId)
                ?.currentRevision?.revisionId ?? null)
            : null,
      }
    : null;

  /** 打开「更新」：预取该书册完整分类用于预填（失败不阻断，提示手填）。 */
  async function openUpdate(document: DocumentSummary) {
    setUpdateTarget({ documentId: document.documentId, title: document.title });
    setUpdateSeed(null);
    setUpdateSeedError(null);
    setImportOpen(true);
    try {
      const detail = await getDocument(document.documentId);
      setUpdateSeed({ ...detail.metadata });
    } catch (cause) {
      setUpdateSeedError(asApiError(cause).message);
    }
  }

  async function removeDocument(document: DocumentSummary) {
    setBusyId(document.documentId);
    setActionError(null);
    try {
      await deleteDocument(document.documentId, { expectedRevision: document.revision });
      setConfirmDeleteId(null);
      setNotice(`已删除《${document.title}》：服务器停用该教材并排队清理向量，旧引用原文仍保留。`);
      refresh();
    } catch (cause) {
      const error = asApiError(cause);
      setActionError(
        error.status === 409
          ? `删除冲突（${error.code}）：${error.message} 已重新读取书册列表，请比较后重试。`
          : `删除失败：${error.message}`,
      );
      if (error.status === 409) refresh();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-page textbook-page textbook-detail">
      <header className="space-header">
        <Link className="space-back" href="/knowledge-bases">
          <ArrowLeft size={14} aria-hidden />
          返回教材资料库
        </Link>
        <div className="space-header-row">
          <h1>{state.phase === 'ready' ? state.data.displayName : '教材库详情'}</h1>
          <div className="space-card-actions">
            <button className="space-button" onClick={refresh}>
              <RefreshCw size={14} aria-hidden />
              刷新
            </button>
          </div>
        </div>
        {state.phase === 'ready' && <LibraryMeta library={state.data} taxonomy={index} />}
      </header>

      <main className="space-content">
        {state.phase === 'loading' && (
          <div aria-hidden>
            {[0, 1, 2].map((index) => (
              <div className="space-skeleton" key={index} style={{ height: 96 }} />
            ))}
          </div>
        )}

        {state.phase === 'failed' && (
          <div className="space-banner error" role="alert">
            教材库读取失败（{state.error.code}）：{state.error.message}
            <div className="textbook-panel-actions">
              <button className="space-button" onClick={reload}>
                重试
              </button>
            </div>
          </div>
        )}

        {notice && (
          <div className="space-banner info" role="status">
            {notice}
            <div className="textbook-panel-actions">
              <button className="space-button" onClick={() => setNotice(null)}>
                关闭
              </button>
            </div>
          </div>
        )}
        {actionError && (
          <div className="space-banner error" role="alert">
            {actionError}
            <div className="textbook-panel-actions">
              <button className="space-button" onClick={refresh}>
                刷新列表
              </button>
              <button className="space-button" onClick={() => setActionError(null)}>
                关闭
              </button>
            </div>
          </div>
        )}

        {state.phase === 'ready' && state.data.documents.length === 0 && (
          <div className="space-empty">
            <strong>该库还没有书册</strong>
            <span>用「更新」上传文件并提交入库后，书册会出现在这里。</span>
            <button
              className="space-button primary"
              onClick={() => {
                setUpdateTarget(null);
                setUpdateSeed(null);
                setUpdateSeedError(null);
                setImportOpen(true);
              }}
            >
              导入教材
            </button>
          </div>
        )}

        {state.phase === 'ready' && state.data.documents.length > 0 && (
          <ul className="textbook-document-list">
            {state.data.documents.map((document) => {
              const revision = document.currentRevision;
              const panelOpen = openPanel?.documentId === document.documentId;
              return (
                <li className="textbook-document-item" key={document.documentId}>
                  <div className="textbook-document-head">
                    <strong>{document.title}</strong>
                    <span className="space-meta-row">
                      <span className={`space-chip ${isRetrievable(document) ? 'green' : 'amber'}`}>
                        {isRetrievable(document) ? '可检索' : '尚不可检索'}
                      </span>
                      {document.pendingRevisionId && (
                        <span className="space-chip blue">有待入库修订</span>
                      )}
                      {document.deletedAt && <span className="space-chip amber">已删除</span>}
                    </span>
                  </div>
                  <div className="space-meta-row">
                    <span className="space-chip">
                      年级：{index.gradeLabels(document.gradeIds) || '—'}
                    </span>
                    <span className="space-chip">
                      学科：{index.subjectLabel(document.subjectId)}
                    </span>
                    <span className="space-chip">
                      版本：{index.editionLabel(document.editionId)}
                    </span>
                    <span className="space-chip">修订 r{document.revision}</span>
                    {document.libraryIds.length > 1 && (
                      <span className="space-chip">归属 {document.libraryIds.length} 个库</span>
                    )}
                  </div>
                  <div className="space-meta-row">
                    {revision ? (
                      <>
                        <span className="space-chip">字符 {revision.charCount}</span>
                        <span className="space-chip">块 {revision.chunkCount}</span>
                        <span className="space-chip">解析器 {revision.parserVersion}</span>
                        <span className="space-chip">发布 {revision.createdAt}</span>
                      </>
                    ) : (
                      <span className="space-chip amber">尚无已发布修订</span>
                    )}
                  </div>

                  <div className="textbook-panel-actions">
                    <button className="space-button" onClick={() => void openUpdate(document)}>
                      更新
                    </button>
                    <button
                      className="space-button"
                      onClick={() =>
                        setOpenPanel(
                          panelOpen && openPanel?.kind === 'edit'
                            ? null
                            : { kind: 'edit', documentId: document.documentId },
                        )
                      }
                      aria-expanded={panelOpen && openPanel?.kind === 'edit'}
                    >
                      编辑分类
                    </button>
                    <button
                      className="space-button"
                      disabled={!revision}
                      onClick={() =>
                        setOpenPanel(
                          panelOpen && openPanel?.kind === 'source'
                            ? null
                            : { kind: 'source', documentId: document.documentId },
                        )
                      }
                      aria-expanded={panelOpen && openPanel?.kind === 'source'}
                    >
                      来源预览
                    </button>
                    {confirmDeleteId === document.documentId ? (
                      <>
                        <button
                          className="space-button danger"
                          onClick={() => void removeDocument(document)}
                          disabled={busyId === document.documentId}
                        >
                          {busyId === document.documentId ? '删除中…' : '确认删除'}
                        </button>
                        <button className="space-button" onClick={() => setConfirmDeleteId(null)}>
                          取消
                        </button>
                      </>
                    ) : (
                      <button
                        className="space-button"
                        onClick={() => setConfirmDeleteId(document.documentId)}
                        disabled={Boolean(document.deletedAt)}
                      >
                        删除
                      </button>
                    )}
                  </div>
                  {confirmDeleteId === document.documentId && (
                    <p className="textbook-hint" role="alert">
                      确认删除《{document.title}
                      》？删除后该教材不再可检索（原文修订保留用于历史引用），
                      向量清理由服务端异步完成。
                    </p>
                  )}

                  {panelOpen && openPanel?.kind === 'edit' && (
                    <DocumentEditForm
                      documentId={document.documentId}
                      taxonomy={index}
                      onSaved={() => {
                        setNotice(`已保存《${document.title}》的分类。`);
                        refresh();
                      }}
                      onConflictRefresh={refresh}
                      onCancel={() => setOpenPanel(null)}
                    />
                  )}
                  {panelOpen && openPanel?.kind === 'source' && revision && (
                    <DocumentSourcePreview
                      revisionId={revision.revisionId}
                      charCount={revision.charCount}
                    />
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </main>

      {importOpen && (
        <ImportPanel
          taxonomy={index}
          updateTarget={resolvedTarget}
          initialMetadata={updateSeed}
          initialMetadataError={updateSeedError}
          onClose={() => setImportOpen(false)}
          onTargetStale={refresh}
          onCommitted={(job) => {
            refresh();
            setImportOpen(false);
            setNotice(
              `已提交入库任务（任务 ${job.jobId}），进度以「入库任务」面板的服务端状态为准。`,
            );
          }}
        />
      )}
    </div>
  );
}

function LibraryMeta({ library, taxonomy }: { library: LibraryDetail; taxonomy: TaxonomyIndex }) {
  return (
    <>
      <div className="space-meta-row">
        <span className="space-chip">{LIBRARY_KIND_LABEL[library.kind]}</span>
        <span className="space-chip">库 {library.libraryId}</span>
        {library.gradeId && (
          <span className="space-chip">年级：{taxonomy.gradeLabel(library.gradeId)}</span>
        )}
        <span className="space-chip">学科：{taxonomy.subjectLabel(library.subjectId)}</span>
        <span className="space-chip">版本：{taxonomy.editionLabel(library.editionId)}</span>
        <span className="space-chip">书册 {library.documentCount}</span>
        <span className={`space-chip ${library.readyDocumentCount > 0 ? 'green' : ''}`}>
          已就绪 {library.readyDocumentCount}
        </span>
        <span className="space-chip">修订 r{library.revision}</span>
        {library.deletedAt && <span className="space-chip amber">已停用</span>}
      </div>
      <p className="space-description">
        可检索性以服务端已发布修订为准；「尚不可检索」表示当前没有可用的已发布修订或存在待入库修订。
      </p>
    </>
  );
}
