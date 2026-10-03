'use client';

import { useEffect, useRef, useState } from 'react';
import { RefreshCw, Upload } from 'lucide-react';
import type { PaperImportView, PaperView } from '@/contracts/papers';
import { createPaperImport, getPaper, getPaperRevisionContent, listPapers } from '@/services/assessments-api';
import { fetchTextbookTaxonomy } from '@/services/textbook-api';
import { asApiError, useAsyncResource } from './hooks';
import { formatScoreUnits, paperRevisionStateLabel, paperStatusLabel } from './labels';
import { PaperImportReview } from './PaperImportReview';

export interface SelectedPaper {
  paperId: string;
  paperRevisionId: string;
  title: string;
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
  const operation = useRef({ mounted: false, epoch: 0 });
  useEffect(() => {
    const state = operation.current;
    state.mounted = true;
    return () => { state.mounted = false; state.epoch += 1; };
  }, []);
  const papers = useAsyncResource((signal) => listPapers({ status: 'active', limit: 100 }, signal),
    `assessments-papers|${refreshToken}`);
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
        paperRevisionId: revision.paperRevisionId, title: revision.title,
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
      <div className="assessments-subpanel-head"><h3>原卷修订</h3><button className="space-button" onClick={papers.reload}><RefreshCw size={13} aria-hidden /> 刷新</button></div>
      <p className="assessments-hint">成绩固定到已确认修订的计分叶与满分。草稿先校对确认；已选用修订可独立阅读自己的标题和内容。</p>
      {papers.state.phase === 'failed' && <p className="space-banner error" role="alert" data-testid="assessments-papers-error">
        原卷列表读取失败（{papers.state.error.code}）：{papers.state.error.message}<button className="space-button" onClick={papers.reload}>重试</button></p>}
      {items.length === 0 && papers.state.phase === 'ready' && <p className="space-empty" data-testid="assessments-papers-empty"><strong>还没有原卷</strong><span>在上方上传一份DOCX原卷并完成校对。</span></p>}
      <ul className="assessments-list" aria-label="原卷列表">{items.map((paper) => {
        const confirmed = paper.currentState === 'confirmed' && Boolean(paper.currentRevisionId);
        const isSelected = selected?.paperRevisionId === paper.currentRevisionId;
        return <li key={paper.paperId}><div className={isSelected ? 'assessments-card current' : 'assessments-card'} data-testid={`assessments-paper-${paper.paperId}`}>
          <div className="assessments-card-head"><strong>{paper.title}</strong><span className="space-chip">{paperStatusLabel(paper.status)}</span><span className={confirmed ? 'space-chip green' : 'space-chip amber'}>{paper.currentState ? paperRevisionStateLabel(paper.currentState) : '无修订'}</span></div>
          <div className="space-meta-row"><span className="space-chip">修订 v{paper.version}</span><span className="space-chip">计分叶 {paper.scoredLeafCount}</span><span className="space-chip">满分 {formatScoreUnits(paper.totalScoreUnits)}</span>
            {paper.blockingIssueCount > 0 && <span className="space-chip amber">阻断问题 {paper.blockingIssueCount}</span>}
            {paper.currentRevisionId && <span className="space-chip" data-testid={`assessments-paper-revision-${paper.paperId}`}>revisionId {paper.currentRevisionId}</span>}</div>
          <div className="assessments-actions"><button className="space-button" disabled={busy || !paper.currentRevisionId} onClick={() => void open(paper)}>{confirmed ? '阅读固定修订' : '打开原卷校对'}</button>
            <button className="space-button primary" disabled={!confirmed || busy} aria-pressed={isSelected} data-testid={`assessments-select-paper-${paper.paperId}`}
              onClick={() => void open(paper, paper.currentRevisionId, true)}>{isSelected ? '已选用该修订' : confirmed ? '选用该修订' : '草稿不可选用'}</button></div>
        </div></li>;
      })}</ul>
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
