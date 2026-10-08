'use client';

import { useEffect, useRef, useState } from 'react';
import { RefreshCw, Upload } from 'lucide-react';
import type { PaperImportView, PaperView } from '@/contracts/papers';
import {
  archivePaper,
  createPaperImport,
  deletePaper,
  getPaper,
  getPaperRevisionContent,
  listPapers,
  restorePaper,
} from '@/services/assessments-api';
import { fetchTextbookTaxonomy } from '@/services/textbook-api';
import { asApiError, useAsyncResource } from './hooks';
import { formatScoreUnits, PAPER_REFERENCE_LABELS, paperRevisionStateLabel, paperStatusLabel, referenceCounts, shortId } from './labels';
import { DeleteGuardNotice, type DeleteGuardState } from './DeleteGuardNotice';
import { PaperImportReview } from './PaperImportReview';

export interface SelectedPaper {
  paperId: string;
  paperRevisionId: string;
  title: string;
  /** 固定修订的版本号（`修订 v{version}`；来自固定修订内容视图，不从列表项推断）。 */
  version: number;
  totalScoreUnits: number;
  scoredLeafCount: number;
}

/** 原卷的真实DOCX导入、源块校对、固定修订阅读与选用。 */
export function PapersPanel({ selected, onSelect, refreshToken }: {
  selected: SelectedPaper | null;
  onSelect: (paper: SelectedPaper | null) => void;
  refreshToken: number;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [subjectId, setSubjectId] = useState('');
  const [opened, setOpened] = useState<PaperImportView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** 「显示已归档」：默认只取活跃原卷；打开后不传 status（服务端默认口径 = 全部）。 */
  const [showArchived, setShowArchived] = useState(false);
  /** 归档/恢复的写操作身份（禁用按钮防重入）与错误提示。 */
  const [archiveBusyId, setArchiveBusyId] = useState<string | null>(null);
  const [writeError, setWriteError] = useState<string | null>(null);
  /** 彻底删除：被引用守卫 409 的原因清单 + 成功回执（写锁与归档/恢复分开，互不吞错）。 */
  const [deleteBusyId, setDeleteBusyId] = useState<string | null>(null);
  const [deleteGuard, setDeleteGuard] = useState<DeleteGuardState | null>(null);
  const [deleteNotice, setDeleteNotice] = useState<string | null>(null);
  const writeBusyRef = useRef(false);
  const deleteBusyRef = useRef(false);
  const operation = useRef({ mounted: false, epoch: 0 });
  useEffect(() => {
    const state = operation.current;
    state.mounted = true;
    return () => { state.mounted = false; state.epoch += 1; };
  }, []);
  const papers = useAsyncResource((signal) =>
    listPapers(showArchived ? { limit: 100 } : { status: 'active', limit: 100 }, signal),
    `assessments-papers|${refreshToken}|${showArchived ? 'all' : 'active'}`);
  const taxonomy = useAsyncResource(fetchTextbookTaxonomy, 'assessments-paper-taxonomy');
  const items: PaperView[] = papers.lastData?.items ?? [];

  async function upload() {
    if (!file || !subjectId || busy) return;
    const token = ++operation.current.epoch;
    setBusy(true);
    setError(null);
    try {
      const imported = await createPaperImport(file, { subjectId, title: title.trim() || undefined });
      if (!operation.current.mounted || token !== operation.current.epoch) return;
      setOpened(imported);
      setFile(null);
      papers.reload();
    } catch (cause) {
      if (operation.current.mounted && token === operation.current.epoch) {
        const issue = asApiError(cause);
        setError(`原卷导入失败（${issue.code}）：${issue.message} 已选文件与标题保留。`);
      }
    } finally {
      if (operation.current.mounted && token === operation.current.epoch) setBusy(false);
    }
  }

  async function open(paper: PaperView, revisionId = paper.currentRevisionId, select = false) {
    if (!revisionId) return;
    const token = ++operation.current.epoch;
    setBusy(true);
    setError(null);
    try {
      const current = await getPaper(paper.paperId);
      const revision = await getPaperRevisionContent(paper.paperId, revisionId);
      if (!operation.current.mounted || token !== operation.current.epoch) return;
      setOpened({ paper: current, revision, warnings: [] });
      if (select && revision.state === 'confirmed') onSelect({ paperId: revision.paperId,
        paperRevisionId: revision.paperRevisionId, title: revision.title, version: revision.version,
        totalScoreUnits: revision.totalScoreUnits, scoredLeafCount: paper.scoredLeafCount });
    } catch (cause) {
      if (operation.current.mounted && token === operation.current.epoch) {
        const issue = asApiError(cause);
        setError(`读取原卷失败（${issue.code}）：${issue.message}`);
      }
    } finally {
      if (operation.current.mounted && token === operation.current.epoch) setBusy(false);
    }
  }

  /**
   * 归档/恢复原卷（守卫式）：`expectedRevision` 用列表项的 paper.revision。
   * 归档后原卷仍可阅读、历史引用（施测/成绩）保留，但不能用于新的施测。
   */
  async function setArchived(paper: PaperView, archived: boolean) {
    if (writeBusyRef.current) return;
    if (
      archived &&
      !window.confirm(
        `归档原卷「${paper.title}」？归档后仍可阅读、历史引用保留，但不能再用它创建新施测。`,
      )
    ) {
      return;
    }
    const token = ++operation.current.epoch;
    writeBusyRef.current = true;
    setArchiveBusyId(paper.paperId);
    setWriteError(null);
    try {
      if (archived) await archivePaper(paper.paperId, { expectedRevision: paper.revision });
      else await restorePaper(paper.paperId, { expectedRevision: paper.revision });
      if (!operation.current.mounted || token !== operation.current.epoch) return;
      papers.reload();
    } catch (cause) {
      if (operation.current.mounted && token === operation.current.epoch) {
        const issue = asApiError(cause);
        setWriteError(`${archived ? '归档' : '恢复'}原卷失败（${issue.code}）：${issue.message}`);
      }
    } finally {
      writeBusyRef.current = false;
      if (operation.current.mounted) setArchiveBusyId(null);
    }
  }

  /**
   * 彻底删除原卷（受引用守卫的物理删除，二次确认）：
   * 被施测引用 409 `PAPER_IN_USE` 或存在已确认修订 409 `PAPER_HAS_CONFIRMED_REVISION` 时，
   * 把服务端 message 与 `details.counts` 逐项显示在组件内错误区，并给「改为归档」；
   * 乐观锁冲突 / 404 按既有错误区呈现。
   */
  async function deletePaperItem(paper: PaperView) {
    if (deleteBusyRef.current) return;
    if (
      !window.confirm(
        `彻底删除原卷「${paper.title}」？这是物理删除、不可恢复；已有已确认修订或已被施测引用时会被拒绝并列出原因。`,
      )
    ) {
      return;
    }
    const token = ++operation.current.epoch;
    deleteBusyRef.current = true;
    setDeleteBusyId(paper.paperId);
    setWriteError(null);
    setDeleteGuard(null);
    setDeleteNotice(null);
    try {
      await deletePaper(paper.paperId, paper.revision);
      if (!operation.current.mounted || token !== operation.current.epoch) return;
      // 被删原卷的固定修订若正被选用，清空选用，避免后续施测引用已不存在的修订。
      if (selected?.paperId === paper.paperId) onSelect(null);
      setDeleteNotice(`已彻底删除原卷「${paper.title}」：物理删除完成，不可恢复。`);
      papers.reload();
    } catch (cause) {
      if (!operation.current.mounted || token !== operation.current.epoch) return;
      const issue = asApiError(cause);
      if (
        issue.status === 409 &&
        (issue.code === 'PAPER_IN_USE' || issue.code === 'PAPER_HAS_CONFIRMED_REVISION')
      ) {
        setDeleteGuard({
          targetId: paper.paperId,
          error: issue,
          reasons: referenceCounts(issue.details, PAPER_REFERENCE_LABELS),
        });
      } else {
        setWriteError(`彻底删除原卷失败（${issue.code}）：${issue.message}`);
      }
    } finally {
      deleteBusyRef.current = false;
      if (operation.current.mounted) setDeleteBusyId(null);
    }
  }

  return <div className="assessments-panel" data-testid="assessments-papers-panel">
    <section className="assessments-subpanel" aria-label="导入原卷">
      <h3><Upload size={15} aria-hidden /> 导入教师原卷（DOCX）</h3>
      <p className="assessments-hint">完整原文、公式、图片、表格和共同材料均需校对；原卷不要求答案、解析或评分点。</p>
      <form className="assessments-form" aria-label="导入原卷" onSubmit={(event) => { event.preventDefault(); void upload(); }}>
        <label className="assessments-field"><span>原卷文件</span><input className="assessments-input" type="file"
          aria-label="原卷DOCX文件" accept=".docx" disabled={busy}
          onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
        <label className="assessments-field"><span>学科</span><select className="space-select" aria-label="原卷学科"
          value={subjectId} disabled={busy} onChange={(event) => setSubjectId(event.target.value)}>
          <option value="">请选择学科</option>
          {(taxonomy.lastData?.subjects ?? []).map((subject) => <option key={subject.id} value={subject.id}>{subject.label}</option>)}
        </select></label>
        <label className="assessments-field"><span>标题（可选）</span><input className="assessments-input" aria-label="导入原卷标题"
          value={title} disabled={busy} onChange={(event) => setTitle(event.target.value)} /></label>
        <button className="space-button primary" disabled={busy || !file || !subjectId} type="submit">{busy ? '处理中…' : '上传原卷并校对'}</button>
      </form>
      {taxonomy.state.phase === 'failed' && <p className="space-banner error" role="alert">学科读取失败（{taxonomy.state.error.code}）。
        <button className="space-button" onClick={taxonomy.reload}>重试学科</button></p>}
      {error && <p className="space-banner error" role="alert">{error}</p>}
    </section>

    <section className="assessments-subpanel" aria-label="已确认原卷修订">
      <div className="assessments-subpanel-head"><h3>原卷修订</h3>
        <div className="assessments-actions">
          <label className="assessments-check">
            <input type="checkbox" aria-label="显示已归档原卷" checked={showArchived}
              onChange={(event) => setShowArchived(event.target.checked)} />
            <span>显示已归档</span>
          </label>
          <button className="space-button" onClick={papers.reload}><RefreshCw size={13} aria-hidden /> 刷新</button>
        </div>
      </div>
      <p className="assessments-hint">成绩固定到已确认修订的计分叶与满分。草稿先校对确认；已选用修订可独立阅读自己的标题和内容。</p>
      {papers.state.phase === 'failed' && <p className="space-banner error" role="alert" data-testid="assessments-papers-error">
        原卷列表读取失败（{papers.state.error.code}）：{papers.state.error.message}<button className="space-button" onClick={papers.reload}>重试</button></p>}
      {items.length === 0 && papers.state.phase === 'ready' && <p className="space-empty" data-testid="assessments-papers-empty"><strong>还没有原卷</strong><span>在上方上传一份DOCX原卷并完成校对。</span></p>}
      <ul className="assessments-list" aria-label="原卷列表">{items.map((paper) => {
        const confirmed = paper.currentState === 'confirmed' && Boolean(paper.currentRevisionId);
        const isSelected = selected?.paperRevisionId === paper.currentRevisionId;
        const archived = paper.status === 'archived';
        return <li key={paper.paperId}><div className={isSelected ? 'assessments-card current' : 'assessments-card'} data-testid={`assessments-paper-${paper.paperId}`}>
          <div className="assessments-card-head"><strong>{paper.title}</strong><span className="space-chip">{paperStatusLabel(paper.status)}</span><span className={confirmed ? 'space-chip green' : 'space-chip amber'}>{paper.currentState ? paperRevisionStateLabel(paper.currentState) : '无修订'}</span></div>
          <div className="space-meta-row"><span className="space-chip">修订 v{paper.version}</span><span className="space-chip">计分叶 {paper.scoredLeafCount}</span><span className="space-chip">满分 {formatScoreUnits(paper.totalScoreUnits)}</span>
            {paper.blockingIssueCount > 0 && <span className="space-chip amber">阻断问题 {paper.blockingIssueCount}</span>}</div>
          <div className="assessments-actions">
            {archived && <span className="space-chip" data-testid={`assessments-paper-archived-${paper.paperId}`}>已归档</span>}
            {/* 修订号降为小字（完整值在 title；列表主文本只用标题/版本） */}
            {paper.currentRevisionId && (
              <span className="assessments-meta" title={paper.currentRevisionId} data-testid={`assessments-paper-revision-${paper.paperId}`}>
                修订号 {shortId(paper.currentRevisionId)}
              </span>
            )}
            <button className="space-button" disabled={busy || !paper.currentRevisionId} title={paper.currentRevisionId ? `固定修订 ${paper.currentRevisionId}` : undefined} onClick={() => void open(paper)}>{confirmed ? '阅读固定修订' : '打开原卷校对'}</button>
            <button className="space-button primary" disabled={!confirmed || busy || archived} aria-pressed={isSelected} data-testid={`assessments-select-paper-${paper.paperId}`}
              onClick={() => void open(paper, paper.currentRevisionId, true)}>{isSelected ? '已选用该修订' : confirmed ? '选用该修订' : '草稿不可选用'}</button>
            {archived ? (
              <button className="space-button" data-testid={`assessments-paper-restore-${paper.paperId}`}
                disabled={archiveBusyId !== null || deleteBusyId !== null} onClick={() => void setArchived(paper, false)}>
                {archiveBusyId === paper.paperId ? '恢复中…' : '恢复'}
              </button>
            ) : (
              <button className="space-button danger" data-testid={`assessments-paper-archive-${paper.paperId}`}
                disabled={archiveBusyId !== null || deleteBusyId !== null} onClick={() => void setArchived(paper, true)}>
                {archiveBusyId === paper.paperId ? '归档中…' : '归档'}
              </button>
            )}
            {/* 次级危险操作：物理删除只在"无施测引用且无已确认修订"时通过（归档对象同样受守卫） */}
            <button className="space-button danger" data-testid={`assessments-paper-delete-${paper.paperId}`}
              disabled={archiveBusyId !== null || deleteBusyId !== null} onClick={() => void deletePaperItem(paper)}>
              {deleteBusyId === paper.paperId ? '删除中…' : '彻底删除'}
            </button>
          </div>
        </div></li>;
      })}</ul>
      {writeError && <p className="space-banner error" role="alert" data-testid="assessments-paper-write-error">{writeError}</p>}
      {deleteNotice && <p className="space-banner info" role="status" data-testid="assessments-paper-delete-notice">{deleteNotice}</p>}
      {deleteGuard && (
        <DeleteGuardNotice
          state={deleteGuard}
          targetName={items.find((item) => item.paperId === deleteGuard.targetId)?.title ?? shortId(deleteGuard.targetId)}
          archiving={archiveBusyId === deleteGuard.targetId}
          testId="assessments-paper-delete-guard"
          onArchive={() => {
            const paper = items.find((item) => item.paperId === deleteGuard.targetId);
            if (paper) void setArchived(paper, true);
          }}
        />
      )}
      {selected && <p className="space-banner info" role="status" data-testid="assessments-paper-selected">已选用原卷「{selected.title}」（revision {selected.paperRevisionId}，计分叶 {selected.scoredLeafCount}，满分 {formatScoreUnits(selected.totalScoreUnits)}）。
        <button className="space-button" disabled={busy} onClick={() => {
          const paper = items.find((item) => item.paperId === selected.paperId);
          if (paper) void open(paper, selected.paperRevisionId);
        }}>阅读已选用固定修订</button></p>}
    </section>
    {opened && <PaperImportReview key={`${opened.paper.paperId}|${opened.revision.paperRevisionId}`}
      initial={opened} onSelected={onSelect} onChanged={papers.reload} />}
  </div>;
}
