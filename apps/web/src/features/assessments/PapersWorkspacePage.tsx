'use client';

/**
 * 试卷管理独立页（`/assessments/papers`，R5-FE 2026-10-11；R10-FE 2026-10-12 去归档）。
 *
 * 版面（对齐用户参考图）：操作行 = 「导入试卷」（主色，接受 DOCX / PDF 文本层）+
 * 「删除试卷」（红描边，作用于当前选中行）；表格列 = 试卷名称 / 科目 / 操作
 * （浏览 = 查看拆题与知识点分类结果、编辑 = 打开导入审阅面板、删除）。
 * **表格下方**是「AI 试题知识点分类」卡：Chart.js 环状图 + 含百分比的图例，
 * 数据取自 `GET /papers/{id}/knowledge-distribution`。
 *
 * 范围（用户明确裁定）：本模块不做成绩分析、不显示试卷内容、不提供整卷内容阅读器；
 * AI 结果只进候选、教师确认才落库（草稿 → 确认原卷入库）。扫描件等无法解析的原卷，
 * 后端给什么错误就原样显示什么错误。
 *
 * R10-FE 用户裁定「舍弃所有归档功能，只留删除」：已归档开关、归档/恢复按钮与「改为归档」
 * 兜底全部移除；DELETE 的 409（`PAPER_IN_USE` / `PAPER_HAS_CONFIRMED_REVISION`）明细原样展示。
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { Eye, FileUp, Pencil, RefreshCw, Trash2 } from 'lucide-react';
import type { PaperImportView, PaperView } from '@/contracts/papers';
import {
  createPaperImport,
  deletePaper,
  getPaper,
  getPaperRevisionContent,
  listPapers,
  paperKnowledgeDistribution,
} from '@/services/assessments-api';
import { fetchTextbookTaxonomy } from '@/services/textbook-api';
import { Modal } from '@/components/ui/Modal';
import { useEntrance } from '@/components/motion/useEntrance';
import '@/components/layout/space.css';
import '@/features/assessments/styles/assessments.css';
import { asApiError, useAsyncResource } from './hooks';
import {
  PAPER_REFERENCE_LABELS,
  nameOrShortId,
  paperRevisionStateLabel,
  paperStateChipClass,
  referenceCounts,
  shortId,
  subjectText,
} from './labels';
import { DeleteGuardNotice, type DeleteGuardState } from './DeleteGuardNotice';
import { KnowledgeDonut } from './KnowledgeDonut';
import { PaperImportReview } from './PaperImportReview';
import { PaperStructurePanel } from './PaperStructurePanel';

export function PapersWorkspacePage() {
  const pageRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLElement>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null);
  const [editing, setEditing] = useState<PaperImportView | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [writeBusyId, setWriteBusyId] = useState<string | null>(null);
  const [writeError, setWriteError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [deleteGuard, setDeleteGuard] = useState<DeleteGuardState | null>(null);

  /** 只取活跃试卷（R10-FE：归档功能已移除，界面不再提供已归档视图）。 */
  const papers = useAsyncResource(
    (signal) => listPapers({ status: 'active', limit: 200 }, signal),
    `assessments-papers|${refreshToken}`,
  );
  const taxonomy = useAsyncResource(fetchTextbookTaxonomy, 'assessments-paper-taxonomy');

  const items: PaperView[] = useMemo(() => papers.lastData?.items ?? [], [papers.lastData]);
  /**
   * 当前选中的试卷：显式选择优先；未选择（或所选试卷已不在列表里）时回落到第一份。
   * 只读派生，避免列表刷新后选中一份不存在的试卷。
   */
  const selectedPaper = useMemo(() => {
    if (items.length === 0) return null;
    return items.find((item) => item.paperId === selectedPaperId) ?? items[0];
  }, [items, selectedPaperId]);

  const distribution = useAsyncResource(
    (signal) => {
      const paperId = selectedPaper?.paperId;
      return paperId ? paperKnowledgeDistribution(paperId, signal) : Promise.resolve([]);
    },
    `paper-distribution|${selectedPaper?.paperId ?? 'none'}`,
  );

  useEntrance(pageRef, { preset: 'page' });
  useEntrance(listRef, { preset: 'panel' });

  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const subjects = taxonomy.lastData?.subjects ?? null;
  const subjectsFailed = taxonomy.state.phase === 'failed';

  function reload() {
    setRefreshToken((value) => value + 1);
  }

  /**
   * 彻底删除试卷（受引用守卫的物理删除，二次确认）：
   * 被施测引用 409 `PAPER_IN_USE` 或存在已确认修订 409 `PAPER_HAS_CONFIRMED_REVISION` 时，
   * 把服务端 message 与 `details.counts` 逐项显示在组件内错误区（R10-FE：不再给「改为归档」）；
   * 乐观锁冲突 / 404 按既有错误区呈现（不伪装成引用问题）。
   */
  async function deletePaperItem(paper: PaperView) {
    if (writeBusyId !== null) return;
    if (
      !window.confirm(
        `彻底删除试卷「${paper.title}」？这是物理删除、不可恢复；已有已确认修订或已被施测引用时会被拒绝并列出原因。`,
      )
    ) {
      return;
    }
    setWriteBusyId(paper.paperId);
    setWriteError(null);
    setDeleteGuard(null);
    setNotice(null);
    try {
      await deletePaper(paper.paperId, paper.revision);
      if (!mounted.current) return;
      if (selectedPaperId === paper.paperId) setSelectedPaperId(null);
      if (editing?.paper.paperId === paper.paperId) setEditing(null);
      setNotice(`已彻底删除试卷「${paper.title}」：物理删除完成，不可恢复。`);
      reload();
    } catch (cause) {
      if (!mounted.current) return;
      const error = asApiError(cause);
      if (
        error.status === 409 &&
        (error.code === 'PAPER_IN_USE' || error.code === 'PAPER_HAS_CONFIRMED_REVISION')
      ) {
        setDeleteGuard({
          targetId: paper.paperId,
          error,
          reasons: referenceCounts(error.details, PAPER_REFERENCE_LABELS),
        });
      } else {
        setWriteError(`彻底删除试卷失败（${error.code}）：${error.message}`);
      }
    } finally {
      if (mounted.current) setWriteBusyId(null);
    }
  }

  /** 编辑：先选中该行，再重新读取草稿视图并打开审阅面板。 */
  async function browseThenEdit(paper: PaperView) {
    setSelectedPaperId(paper.paperId);
    setWriteError(null);
    const revisionId = paper.currentRevisionId;
    if (!revisionId) return;
    if (writeBusyId !== null) return;
    setWriteBusyId(paper.paperId);
    try {
      const [current, revision] = await Promise.all([
        getPaper(paper.paperId),
        getPaperRevisionContent(paper.paperId, revisionId),
      ]);
      if (!mounted.current) return;
      setEditing({ paper: current, revision, warnings: [] });
    } catch (cause) {
      if (!mounted.current) return;
      const error = asApiError(cause);
      setWriteError(`读取试卷草稿失败（${error.code}）：${error.message}`);
    } finally {
      if (mounted.current) setWriteBusyId(null);
    }
  }

  const selectedName =
    selectedPaper && (selectedPaper.title.trim() || shortId(selectedPaper.paperId));

  return (
    <div ref={pageRef} className="space-page assessments-page">
      <header className="space-header" data-motion-reveal>
        <div className="space-header-row">
          <h1>试卷管理</h1>
          <div className="assessments-actions">
            <button className="space-button" onClick={reload}>
              <RefreshCw size={13} aria-hidden /> 刷新
            </button>
          </div>
        </div>
        <p className="space-description">
          导入教师原卷（DOCX / PDF 文本层）→ 校对拆题并回答 AI 的知识点分类建议 → 确认入库；
          表格下方的环状图按知识点给出占比。本页不显示试卷正文，也不做成绩分析。
        </p>
      </header>

      <main className="space-content">
        <section className="assessments-subpanel" ref={listRef} aria-label="试卷列表">
          <div className="assessments-subpanel-head">
            <h2 className="assessments-card-title">试卷列表</h2>
            {papers.lastData && <span className="space-chip">共 {papers.lastData.total} 份</span>}
          </div>

          <div className="assessments-actions" role="group" aria-label="试卷操作">
            <button
              className="space-button primary"
              disabled={writeBusyId !== null}
              data-testid="assessments-paper-import"
              onClick={() => setImportOpen(true)}
            >
              <FileUp size={14} aria-hidden /> 导入试卷
            </button>
            <button
              className="space-button danger"
              disabled={writeBusyId !== null || !selectedPaper}
              data-testid="assessments-paper-delete-selected"
              title={selectedName ? `彻底删除「${selectedName}」` : '先选择一份试卷'}
              onClick={() => selectedPaper && void deletePaperItem(selectedPaper)}
            >
              <Trash2 size={14} aria-hidden /> 删除试卷
              {selectedName ? `（${selectedName}）` : ''}
            </button>
          </div>

          {taxonomy.state.phase === 'failed' && (
            <p className="space-banner error" role="alert" data-testid="assessments-paper-taxonomy-error">
              学科字典读取失败（{taxonomy.state.error.code}）：{taxonomy.state.error.message}
              科目列按短号显示；导入与列表不受影响。
              <button className="space-button" onClick={taxonomy.reload}>
                重试读取字典
              </button>
            </p>
          )}

          {papers.state.phase === 'failed' && (
            <p className="space-banner error" role="alert" data-testid="assessments-papers-error">
              试卷列表读取失败（{papers.state.error.code}）：{papers.state.error.message}
              {papers.lastData ? ' 下方仍显示上一次成功读取的列表。' : ' 这不是空列表。'}
              <button className="space-button" onClick={papers.reload}>
                重试读取试卷
              </button>
            </p>
          )}

          {papers.state.phase === 'ready' && items.length === 0 && (
            <p className="space-empty" data-testid="assessments-papers-empty">
              <strong>还没有试卷</strong>
              <span>用「导入试卷」上传一份 DOCX 或带文本层的 PDF，校对拆题并确认后即可使用。</span>
            </p>
          )}

          {items.length > 0 && (
            <div className="assessments-table-wrap" tabIndex={0} aria-label="试卷列表表格，可横向滚动">
              <table className="assessments-table">
                <caption className="visually-hidden">试卷列表（名称、科目与操作）</caption>
                <thead>
                  <tr>
                    <th scope="col">试卷名称</th>
                    <th scope="col">科目</th>
                    <th scope="col">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((paper) => {
                    const isSelected = selectedPaper?.paperId === paper.paperId;
                    return (
                      <tr
                        key={paper.paperId}
                        aria-selected={isSelected}
                        data-testid={`assessments-paper-${paper.paperId}`}
                      >
                        <td>
                          <div className="assessments-row-actions">
                            <strong>{paper.title}</strong>
                            <span className={paperStateChipClass(paper.currentState)}>
                              {paper.currentState
                                ? paperRevisionStateLabel(paper.currentState)
                                : '无修订'}
                            </span>
                            <span className="space-chip">修订 v{paper.version}</span>
                            {paper.blockingIssueCount > 0 && (
                              <span className="space-chip amber">
                                阻断问题 {paper.blockingIssueCount}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="assessments-subject-cell">
                          {subjectText(paper.subjectId, subjects, subjectsFailed)}
                        </td>
                        <td>
                          <div className="assessments-row-actions">
                            <button
                              className="assessments-link-button"
                              data-testid={`assessments-paper-browse-${paper.paperId}`}
                              aria-pressed={isSelected}
                              onClick={() => setSelectedPaperId(paper.paperId)}
                            >
                              <Eye size={12} aria-hidden /> 浏览
                            </button>
                            {paper.currentRevisionId ? (
                              <button
                                className="assessments-link-button"
                                disabled={writeBusyId !== null}
                                data-testid={`assessments-paper-edit-${paper.paperId}`}
                                onClick={() => void browseThenEdit(paper)}
                              >
                                <Pencil size={12} aria-hidden /> 编辑
                              </button>
                            ) : (
                              <span className="assessments-hint">无修订可编辑</span>
                            )}
                            <button
                              className="assessments-link-button danger"
                              disabled={writeBusyId !== null}
                              data-testid={`assessments-paper-delete-${paper.paperId}`}
                              onClick={() => void deletePaperItem(paper)}
                            >
                              <Trash2 size={12} aria-hidden /> 删除
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {writeError && (
            <p className="space-banner error" role="alert" data-testid="assessments-paper-write-error">
              {writeError}
            </p>
          )}
          {notice && (
            <p className="space-banner info" role="status" data-testid="assessments-paper-notice">
              {notice}
            </p>
          )}
          {deleteGuard && (
            <DeleteGuardNotice
              state={deleteGuard}
              targetName={nameOrShortId(
                items.find((item) => item.paperId === deleteGuard.targetId)?.title,
                deleteGuard.targetId,
              )}
              testId="assessments-paper-delete-guard"
            />
          )}
        </section>

        {selectedPaper ? (
          <>
            <section className="assessments-subpanel" aria-label="AI 试题知识点分类">
              <div className="assessments-subpanel-head">
                <h3>AI 试题知识点分类</h3>
                <span className="space-chip">{selectedPaper.title}</span>
                <span className="space-chip">
                  {subjectText(selectedPaper.subjectId, subjects, subjectsFailed)}
                </span>
              </div>
              {distribution.state.phase === 'failed' && (
                <p className="space-banner error" role="alert" data-testid="assessments-distribution-error">
                  知识点占比读取失败（{distribution.state.error.code}）：
                  {distribution.state.error.message}
                  {distribution.lastData
                    ? ' 下方仍显示上一次成功读取的占比。'
                    : ' 这不等同于「没有知识点关联」。'}
                  <button className="space-button" onClick={distribution.reload}>
                    重试读取占比
                  </button>
                </p>
              )}
              {distribution.state.phase === 'loading' && !distribution.lastData && (
                <p className="assessments-hint">正在读取知识点占比…</p>
              )}
              {distribution.lastData && <KnowledgeDonut distribution={distribution.lastData} />}
            </section>
            <PaperStructurePanel paper={selectedPaper} />
            <p className="assessments-hint">
              「浏览」选中一行即可查看它的拆题结构与知识点占比；「编辑」打开导入审阅面板，
              校对后必须显式确认才入库；AI 的知识点建议只进候选，教师审核应用后仍是草稿。
            </p>
          </>
        ) : (
          items.length === 0 &&
          papers.state.phase === 'ready' && (
            <p className="assessments-hint" data-testid="assessments-paper-no-selection">
              导入第一份试卷后，这里会显示「AI 试题知识点分类」环状图与拆题结构。
            </p>
          )
        )}

        {editing && (
          <PaperImportReview
            key={`${editing.paper.paperId}|${editing.revision.paperRevisionId}`}
            initial={editing}
            onChanged={reload}
            onClose={() => setEditing(null)}
          />
        )}
      </main>

      {importOpen && (
        <ImportPaperDialog
          subjects={subjects}
          subjectsFailed={subjectsFailed}
          onRetryTaxonomy={taxonomy.reload}
          onClose={() => setImportOpen(false)}
          onImported={(imported) => {
            setImportOpen(false);
            setSelectedPaperId(imported.paper.paperId);
            setEditing(imported);
            setNotice(
              `已导入「${imported.paper.title}」：请在校对面板确认拆题与知识点后点击「确认原卷入库」。`,
            );
            reload();
          }}
        />
      )}
    </div>
  );
}

/** 导入试卷：DOCX / PDF 文本层；学科必填（决定知识点分类的学科范围）。 */
function ImportPaperDialog({
  subjects,
  subjectsFailed,
  onRetryTaxonomy,
  onClose,
  onImported,
}: {
  subjects: readonly { id: string; label: string }[] | null;
  subjectsFailed: boolean;
  onRetryTaxonomy: () => void;
  onClose: () => void;
  onImported: (imported: PaperImportView) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [subjectId, setSubjectId] = useState('');
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!file || !subjectId || busy) return;
    setBusy(true);
    setError(null);
    try {
      const imported = await createPaperImport(file, {
        subjectId,
        title: title.trim() || undefined,
      });
      onImported(imported);
    } catch (cause) {
      const issue = asApiError(cause);
      // 扫描件/无法解析等后端错误原样显示（不翻译、不猜测、不降级成"导入成功"）
      setError(
        `导入试卷失败（${issue.code}）：${issue.message} 已选文件与学科保留，可修正后重试。`,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="导入试卷" onClose={onClose}>
      <form
        className="assessments-form"
        aria-label="导入试卷"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <label className="assessments-field">
          <span>试卷文件（DOCX / PDF 文本层）</span>
          <input
            className="assessments-input"
            type="file"
            accept=".docx,.pdf"
            aria-label="试卷文件"
            disabled={busy}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <label className="assessments-field">
          <span>学科</span>
          <select
            className="space-select"
            aria-label="试卷学科"
            value={subjectId}
            disabled={busy || !subjects || subjects.length === 0}
            onChange={(event) => setSubjectId(event.target.value)}
          >
            <option value="">请选择学科</option>
            {(subjects ?? []).map((subject) => (
              <option key={subject.id} value={subject.id}>
                {subject.label}
              </option>
            ))}
          </select>
        </label>
        <label className="assessments-field">
          <span>标题（可选）</span>
          <input
            className="assessments-input"
            aria-label="导入试卷标题"
            value={title}
            disabled={busy}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        {subjectsFailed && (
          <p className="space-banner error" role="alert">
            学科字典读取失败——没有学科无法导入试卷（知识点分类按学科范围）。
            <button className="space-button" type="button" onClick={onRetryTaxonomy}>
              重试读取学科
            </button>
          </p>
        )}
        {error && (
          <p className="space-banner error" role="alert" data-testid="assessments-paper-import-error">
            {error}
          </p>
        )}
        <p className="assessments-hint">
          扫描件（没有文本层）无法解析：后端会返回明确错误，这里原样显示，不会生成空的
          「导入成功」。
        </p>
        <div className="assessments-form-footer">
          <button className="space-button" type="button" disabled={busy} onClick={onClose}>
            取消
          </button>
          <button className="space-button primary" type="submit" disabled={busy || !file || !subjectId}>
            {busy ? '解析中…' : '上传并校对'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
