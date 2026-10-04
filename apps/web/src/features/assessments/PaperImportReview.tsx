'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  PaperBlockPatch, PaperConfirmRequest, PaperConfirmResult, PaperImportView, PaperItemInput,
  PaperIssuePatch, PaperIssueResolution, PaperRevisionContentView,
} from '@/contracts/papers';
import { CONTENT_LOSS_ISSUE_CODES } from '@/contracts/papers';
import type { ContentBlock, RichContentV2 } from '@/contracts/teaching-loop';
import { RichBlocks, RichContentRenderer } from '@/components/ui/RichContentRenderer';
import {
  applyPaperProposal, confirmPaper, createPaperProposal, getPaper, getPaperAsset,
  getPaperProposal, getPaperRevisionContent, patchPaperDraft, rejectPaperProposal,
} from '@/services/assessments-api';
import { listKnowledgePoints } from '@/services/knowledge-points-api';
import { listProfiles } from '@/services/model-settings-api';
import { useObservedJob } from '@/services/use-workflow-job';
import { asApiError, useAsyncResource, useFrozenSubmission } from './hooks';
import { formatScoreUnits, issueLocationLabel, scoredLeafItems } from './labels';
import type { SelectedPaper } from './PapersPanel';

function rich(content: Record<string, unknown>): RichContentV2 {
  return {
    version: 2,
    sharedMaterials: (content.sharedMaterials ?? []) as RichContentV2['sharedMaterials'],
    stemBlocks: (content.stemBlocks ?? []) as ContentBlock[],
    optionBlocks: (content.optionBlocks ?? {}) as RichContentV2['optionBlocks'],
    answerBlocks: (content.answerBlocks ?? []) as ContentBlock[],
    explanationBlocks: (content.explanationBlocks ?? []) as ContentBlock[],
    assets: (content.assets ?? []) as RichContentV2['assets'],
    origin: (content.origin ?? { originalAssetId: '', originalSha256: '', sourceLocator: {} }) as RichContentV2['origin'],
  };
}

function inputs(revision: PaperRevisionContentView): PaperItemInput[] {
  return revision.items.map((item) => ({ itemId: item.itemId, parentItemId: item.parentItemId,
    questionNo: item.questionNo, ordinal: item.ordinal, isScored: item.isScored,
    maxScore: item.maxScore ?? (item.maxScoreUnits === null ? null : formatScoreUnits(item.maxScoreUnits)),
    content: item.content, sourceLocator: item.sourceLocator,
    knowledge: item.knowledge.map((link) => ({ knowledgePointId: link.knowledgePointId, role: link.role })),
  }));
}
function blockInputs(revision: PaperRevisionContentView): PaperBlockPatch[] {
  return revision.blocks.map((block) => ({ blockId: block.blockId, disposition: block.disposition,
    itemId: block.itemId, excludeReason: block.excludeReason }));
}

/** 完整原件校对，既有富内容在修改题号/满分/关联时原样保留。 */
export function PaperImportReview({ initial, onSelected, onChanged }: {
  initial: PaperImportView;
  onSelected: (paper: SelectedPaper) => void;
  onChanged: () => void;
}) {
  const [paper, setPaper] = useState(initial.paper);
  const [revision, setRevision] = useState(initial.revision);
  const [title, setTitle] = useState(initial.revision.title);
  const [items, setItems] = useState(() => inputs(initial.revision));
  const [blocks, setBlocks] = useState(() => blockInputs(initial.revision));
  const [issueEdits, setIssueEdits] = useState<Record<string, PaperIssuePatch>>({});
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ReturnType<typeof asApiError> | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [blockPage, setBlockPage] = useState(0);
  const [itemPage, setItemPage] = useState(0);
  const [knowledgeSearch, setKnowledgeSearch] = useState('');
  const [modelId, setModelId] = useState('');
  const [proposalSelections, setProposalSelections] = useState<Record<string, string>>({});
  const operation = useRef({ mounted: false, epoch: 0 });
  useEffect(() => {
    const state = operation.current;
    state.mounted = true;
    return () => { state.mounted = false; state.epoch += 1; };
  }, []);
  const confirmation = useFrozenSubmission<PaperConfirmRequest, PaperConfirmResult>();
  const job = useObservedJob('teaching');
  const knowledge = useAsyncResource((signal) => listKnowledgePoints({ subjectId: revision.subjectId,
    status: 'active', q: knowledgeSearch, limit: 200 }, signal), `paper-knowledge|${revision.subjectId}|${knowledgeSearch}`);
  const profiles = useAsyncResource(() => listProfiles(), 'paper-proposal-models');
  const proposalId = job.view?.state === 'succeeded' && typeof job.view.result?.proposalId === 'string'
    ? job.view.result.proposalId : null;
  const proposal = useAsyncResource((signal) => proposalId ? getPaperProposal(proposalId, signal) : Promise.resolve(null),
    `paper-proposal|${proposalId ?? 'none'}`);
  const loadAsset = useCallback(async (id: string, signal: AbortSignal) =>
    (await getPaperAsset(revision.paperId, revision.paperRevisionId, id, signal)).blob,
  [revision.paperId, revision.paperRevisionId]);
  const locked = busy || confirmation.busy || confirmation.phase === 'unknown';
  const readOnly = revision.state === 'confirmed';

  function editItem(index: number, change: Partial<PaperItemInput>) {
    setItems((previous) => previous.map((item, current) => current === index ? { ...item, ...change } : item));
    setDirty(true);
  }
  function editBlock(index: number, change: Partial<PaperBlockPatch>) {
    setBlocks((previous) => previous.map((block, current) => current === index ? { ...block, ...change } : block));
    setDirty(true);
  }
  function selectRevision(content: PaperRevisionContentView) {
    onSelected({ paperId: content.paperId, paperRevisionId: content.paperRevisionId, title: content.title,
      totalScoreUnits: content.totalScoreUnits, scoredLeafCount: scoredLeafItems(content.items).length });
  }
  async function readCurrent(resetEdits: boolean, fixedRevisionId?: string) {
    const currentPaper = await getPaper(paper.paperId);
    const id = fixedRevisionId ?? currentPaper.currentRevisionId;
    if (!id) throw new Error('原卷没有可读取的修订');
    const currentRevision = await getPaperRevisionContent(paper.paperId, id);
    return { currentPaper, currentRevision, resetEdits };
  }
  function applyRead(current: Awaited<ReturnType<typeof readCurrent>>) {
    setPaper(current.currentPaper);
    setRevision(current.currentRevision);
    if (current.resetEdits) {
      setTitle(current.currentRevision.title);
      setItems(inputs(current.currentRevision));
      setBlocks(blockInputs(current.currentRevision));
      setIssueEdits({});
      setDirty(false);
    }
  }
  async function mutate(run: () => Promise<unknown>, success: string, resetEdits = true) {
    if (busy) return;
    const token = ++operation.current.epoch;
    setBusy(true); setError(null); setNotice(null);
    try {
      await run();
      const current = await readCurrent(resetEdits);
      if (!operation.current.mounted || token !== operation.current.epoch) return;
      applyRead(current);
      setNotice(success);
      onChanged();
    } catch (cause) {
      if (operation.current.mounted && token === operation.current.epoch) setError(asApiError(cause));
    } finally {
      if (operation.current.mounted && token === operation.current.epoch) setBusy(false);
    }
  }
  async function save() {
    job.reset();
    await mutate(() => patchPaperDraft(paper.paperId, { expectedRevision: paper.revision,
      title: title.trim(), items, blocks, issues: Object.values(issueEdits) }), '已保存原卷草稿并读回当前版本。');
  }
  async function confirm() {
    const payload = confirmation.phase === 'unknown' && confirmation.frozen
      ? confirmation.frozen.payload : { expectedRevision: paper.revision, submissionId: '' };
    const result = await confirmation.submit(payload, (frozen) => confirmPaper(paper.paperId,
      { ...frozen.payload, submissionId: frozen.submissionId }));
    if (!result) return;
    const token = ++operation.current.epoch;
    try {
      const current = await readCurrent(true, result.paperRevisionId);
      if (!operation.current.mounted || token !== operation.current.epoch) return;
      applyRead(current); selectRevision(current.currentRevision); onChanged();
    } catch (cause) {
      if (operation.current.mounted && token === operation.current.epoch) setError(asApiError(cause));
    }
  }
  function attach(blockIndex: number, itemIndex: number, shared: boolean) {
    const source = revision.blocks[blockIndex];
    const item = items[itemIndex];
    if (!source || !item) return;
    const content = rich(item.content ?? {});
    const block = source.content as unknown as ContentBlock;
    const updated: RichContentV2 = shared
      ? { ...content, sharedMaterials: [...content.sharedMaterials.filter((material) => material.id !== source.blockId),
        { id: source.blockId, blocks: [block] }] }
      : { ...content, stemBlocks: [...content.stemBlocks.filter((current) => current.id !== block.id), block] };
    editItem(itemIndex, { content: updated as unknown as Record<string, unknown> });
    editBlock(blockIndex, { disposition: shared ? 'shared_material' : 'item',
      itemId: shared ? null : item.itemId, excludeReason: null });
  }
  function editIssue(issueId: string, patch: PaperIssuePatch) {
    setIssueEdits((previous) => ({ ...previous, [issueId]: patch })); setDirty(true);
  }
  async function startProposal() {
    if (!modelId || dirty || locked) return;
    const token = ++operation.current.epoch;
    setBusy(true); setError(null); job.reset();
    try {
      const receipt = await createPaperProposal(paper.paperId, { modelProfileId: modelId, expectedRevision: paper.revision });
      if (operation.current.mounted && token === operation.current.epoch) job.adopt(receipt);
    } catch (cause) {
      if (operation.current.mounted && token === operation.current.epoch) setError(asApiError(cause));
    } finally {
      if (operation.current.mounted && token === operation.current.epoch) setBusy(false);
    }
  }

  return <section className="assessments-subpanel" aria-label="原卷校对与固定修订阅读" data-testid="paper-import-review">
    <h3>{revision.state === 'confirmed' ? '固定原卷修订' : '原卷校对'}：{revision.title}</h3>
    <p className="assessments-hint">修订 v{revision.version} · 编辑版本 r{paper.revision} · {revision.paperRevisionId} · 满分 {formatScoreUnits(revision.totalScoreUnits)}。
      {readOnly ? ' 此修订只读。' : ' 草稿保存后再确认；题号保留完整路径，只有叶子计分。'}</p>
    {initial.warnings.map((warning, index) => <p className="space-banner info" key={index}>{warning}</p>)}
    {notice && <p className="space-banner info" role="status">{notice}</p>}
    {(error ?? confirmation.error) && <div className="space-banner error" role="alert" data-testid="paper-review-error">
      {(error ?? confirmation.error)?.code}：{(error ?? confirmation.error)?.message} 编辑已保留。
      {(error ?? confirmation.error)?.status === 409 && <p>当前版本 {(error ?? confirmation.error)?.details?.currentRevision ?? '未知'}，请刷新对照。</p>}
      {((error ?? confirmation.error)?.details?.issues ?? []).map((issue, index) => <p key={index}>{issueLocationLabel(issue)}{issue.code}：{issue.message}</p>)}
    </div>}
    {confirmation.unknownNotice && <p className="space-banner error" role="alert">{confirmation.unknownNotice}</p>}
    {confirmation.result && <p className="space-banner info" role="status" data-testid="paper-confirm-result">
      {confirmation.result.replayed ? '已确认原卷（重放）' : '已确认原卷'}：{confirmation.result.paperRevisionId}，计分叶 {confirmation.result.scoredLeafCount}。
    </p>}
    <div className="assessments-actions">
      {readOnly ? <button className="space-button primary" onClick={() => selectRevision(revision)}>选用此固定修订</button> : <>
        <button className="space-button" disabled={locked || !dirty} onClick={() => void save()} data-testid="paper-save-draft">保存原卷草稿</button>
        <button className="space-button primary" disabled={busy || confirmation.busy || dirty}
          onClick={() => void confirm()} data-testid="paper-confirm">{confirmation.phase === 'unknown' ? '重试原卷确认' : '确认原卷入库'}</button>
      </>}
      <button className="space-button" disabled={locked} onClick={() => void mutate(() => Promise.resolve(),
        dirty ? '已刷新服务端对照；本地编辑保留，请核对后保存。' : '已刷新原卷对照。', !dirty)}>刷新原卷对照</button>
      {dirty && <span className="space-chip amber">有未保存原卷校对</span>}
    </div>
    <label className="assessments-field"><span>原卷修订标题</span><input className="assessments-input" aria-label="原卷修订标题"
      value={title} disabled={locked || readOnly} onChange={(event) => { setTitle(event.target.value); setDirty(true); }} /></label>

    <section aria-label="题目校对">
      <h4>题目与知识点</h4>
      {!readOnly && <>
        <label className="assessments-field"><span>搜索本学科知识点</span><input className="assessments-input" aria-label="原卷知识点搜索" value={knowledgeSearch} onChange={(event) => setKnowledgeSearch(event.target.value)} /></label>
        {knowledge.state.phase === 'failed' && <p role="alert">知识点读取失败（{knowledge.state.error.code}）；已有关联保留。<button className="space-button" onClick={knowledge.reload}>重试知识点</button></p>}
        {knowledge.state.phase === 'ready' && knowledge.lastData?.items.length === 0 && <p className="assessments-hint">当前学科或搜索条件下没有可选知识点；请先建立知识点或调整搜索。</p>}
        <button className="space-button" disabled={locked} onClick={() => {
          const itemId = `manual-${crypto.randomUUID()}`;
          setItems((previous) => [...previous, { itemId, questionNo: '', ordinal: previous.length + 1,
            parentItemId: null, isScored: true, maxScore: '', content: rich({}) as unknown as Record<string, unknown>, knowledge: [] }]);
          setItemPage(Math.floor(items.length / 10)); setDirty(true);
        }}>新增题目</button>
      </>}
      {items.slice(itemPage * 10, (itemPage + 1) * 10).map((item, offset) => {
        const index = itemPage * 10 + offset;
        const content = rich(item.content ?? {});
        const label = item.questionNo || `新题${index + 1}`;
        return <fieldset key={item.itemId} className="assessments-subpanel" aria-label={`题 ${label} 校对`}>
          <legend>题 {label}</legend>
          <RichContentRenderer content={content} loadAsset={loadAsset} assetScope={revision.paperRevisionId} />
          {!readOnly && <div className="assessments-form">
            <label className="assessments-field"><span>完整题号</span><input className="assessments-input" aria-label={`题 ${label} 题号`} value={item.questionNo} disabled={locked} onChange={(event) => editItem(index, { questionNo: event.target.value })} /></label>
            <label className="assessments-field"><span>父题（容器不计分）</span><select className="space-select" aria-label={`题 ${label} 父题`} value={item.parentItemId ?? ''} disabled={locked} onChange={(event) => editItem(index, { parentItemId: event.target.value || null })}>
              <option value="">无父题</option>{items.filter((parent) => parent.itemId !== item.itemId).map((parent) => <option key={parent.itemId} value={parent.itemId ?? ''}>{parent.questionNo || parent.itemId}</option>)}
            </select></label>
            <label className="assessments-check"><input type="checkbox" aria-label={`题 ${label} 计分叶`} checked={item.isScored} disabled={locked} onChange={(event) => editItem(index, { isScored: event.target.checked, maxScore: event.target.checked ? item.maxScore ?? '' : null })} />计分叶</label>
            <label className="assessments-field"><span>满分</span><input className="assessments-input assessments-input-narrow" aria-label={`题 ${label} 满分`} value={item.maxScore ?? ''} disabled={locked || !item.isScored} onChange={(event) => editItem(index, { maxScore: event.target.value })} /></label>
            <label className="assessments-field"><span>正式知识点（可多选）</span><select className="space-select" multiple aria-label={`题 ${label} 知识点`} value={(item.knowledge ?? []).map((link) => link.knowledgePointId)} disabled={locked}
              onChange={(event) => editItem(index, { knowledge: Array.from(event.target.selectedOptions).map((option) => ({ knowledgePointId: option.value,
                role: item.knowledge?.find((link) => link.knowledgePointId === option.value)?.role ?? 'primary' })) })}>
              {(knowledge.lastData?.items ?? []).map((point) => <option key={point.id} value={point.id}>{point.code} · {point.name}</option>)}
              {(item.knowledge ?? []).filter((link) => !knowledge.lastData?.items.some((point) => point.id === link.knowledgePointId)).map((link) => <option key={link.knowledgePointId} value={link.knowledgePointId}>{revision.items.find((original) => original.itemId === item.itemId)?.knowledge.find((original) => original.knowledgePointId === link.knowledgePointId)?.knowledgeNameSnapshot ?? link.knowledgePointId}（已有）</option>)}
            </select></label>
            {(item.knowledge ?? []).map((link) => <label className="assessments-field" key={link.knowledgePointId}><span>关联角色 {link.knowledgePointId}</span><select className="space-select" value={link.role ?? 'primary'} disabled={locked} aria-label={`题 ${label} ${link.knowledgePointId} 角色`}
              onChange={(event) => editItem(index, { knowledge: item.knowledge?.map((current) => current.knowledgePointId === link.knowledgePointId ? { ...current, role: event.target.value as 'primary' | 'secondary' } : current) })}><option value="primary">主要</option><option value="secondary">次要</option></select></label>)}
            {content.stemBlocks.filter((block) => block.kind === 'paragraph').map((block) => <label className="assessments-field" key={block.id}><span>题面段落</span><textarea className="assessments-input" aria-label={`题 ${label} 段落 ${block.id}`} disabled={locked} value={block.text}
              onChange={(event) => editItem(index, { content: { ...content, stemBlocks: content.stemBlocks.map((current) => current.id === block.id ? { ...block, text: event.target.value } : current) } })} /></label>)}
            <button className="space-button" disabled={locked} onClick={() => editItem(index, { content: { ...content,
              stemBlocks: [...content.stemBlocks, { id: `paragraph-${crypto.randomUUID()}`, kind: 'paragraph', text: '' }] } })}>为题 {label} 增加题面段落</button>
          </div>}
          {(revision.items.find((original) => original.itemId === item.itemId)?.knowledge ?? []).map((link) => <span className="space-chip" key={link.knowledgePointId}>{link.knowledgeNameSnapshot} · {link.role}</span>)}
        </fieldset>;
      })}
      <div className="assessments-actions"><button className="space-button" disabled={itemPage === 0} onClick={() => setItemPage((value) => value - 1)}>上一页题目</button><span>{items.length} 题</span><button className="space-button" disabled={(itemPage + 1) * 10 >= items.length} onClick={() => setItemPage((value) => value + 1)}>下一页题目</button></div>
    </section>

    <section aria-label="完整原文块"><h4>完整原文与共同材料</h4>
      {revision.blocks.slice(blockPage * 20, (blockPage + 1) * 20).map((source, offset) => {
        const index = blockPage * 20 + offset;
        const edit = blocks[index];
        return <article key={source.blockId} className="assessments-subpanel" data-testid={`paper-source-${source.blockId}`}>
          <h5>原文块 {source.ordinal} · {source.kind}</h5><p className="assessments-meta">来源 {JSON.stringify(source.locator)}</p>
          <RichBlocks blocks={[source.content as unknown as ContentBlock]} loadAsset={loadAsset} assetScope={revision.paperRevisionId} />
          {!readOnly && edit && <div className="assessments-form">
            <label className="assessments-field"><span>原文块处置</span><select className="space-select" aria-label={`原文块 ${source.ordinal} 处置`} value={edit.disposition} disabled={locked} onChange={(event) => editBlock(index, { disposition: event.target.value as PaperBlockPatch['disposition'], itemId: null, excludeReason: null })}>
              <option value="unassigned">待归属</option><option value="item">归属题目</option><option value="shared_material">共同材料</option><option value="excluded">有依据排除</option></select></label>
            {edit.disposition === 'item' && <label className="assessments-field"><span>归属题目</span><select className="space-select" aria-label={`原文块 ${source.ordinal} 归属题目`} value={edit.itemId ?? ''} disabled={locked} onChange={(event) => editBlock(index, { itemId: event.target.value || null })}><option value="">选择题目</option>{items.map((item) => <option key={item.itemId} value={item.itemId ?? ''}>{item.questionNo || item.itemId}</option>)}</select></label>}
            {edit.disposition === 'excluded' && <label className="assessments-field"><span>排除依据</span><input className="assessments-input" aria-label={`原文块 ${source.ordinal} 排除依据`} value={edit.excludeReason ?? ''} disabled={locked} onChange={(event) => editBlock(index, { excludeReason: event.target.value })} /></label>}
            <label className="assessments-field"><span>加入题面或关联共同材料</span><select className="space-select" aria-label={`原文块 ${source.ordinal} 加入题面`} value="" disabled={locked} onChange={(event) => { if (event.target.value) attach(index, Number(event.target.value), false); }}><option value="">将本块加入题目…</option>{items.map((item, itemIndex) => <option key={item.itemId} value={String(itemIndex)}>{item.questionNo || item.itemId}</option>)}</select></label>
            <label className="assessments-field"><span>本题必要共同材料</span><select className="space-select" aria-label={`原文块 ${source.ordinal} 关联共同材料`} value="" disabled={locked} onChange={(event) => { if (event.target.value) attach(index, Number(event.target.value), true); }}><option value="">将本块关联为共同材料…</option>{items.map((item, itemIndex) => <option key={item.itemId} value={String(itemIndex)}>{item.questionNo || item.itemId}</option>)}</select></label>
          </div>}
        </article>;
      })}
      <div className="assessments-actions"><button className="space-button" disabled={blockPage === 0} onClick={() => setBlockPage((value) => value - 1)}>上一页原文</button><span>共 {revision.blocks.length} 个原文块</span><button className="space-button" disabled={(blockPage + 1) * 20 >= revision.blocks.length} onClick={() => setBlockPage((value) => value + 1)}>下一页原文</button></div>
    </section>

    <section aria-label="原卷问题处置"><h4>解析问题与明确处置</h4>
      {revision.issues.length === 0 && <p className="assessments-hint">没有解析问题。确认仍由服务端核题面、共同材料与计分叶关联。</p>}
      {revision.issues.map((issue) => {
        const edit = issueEdits[issue.issueId];
        const resolution = edit?.resolution;
        const setResolution = (next: PaperIssueResolution) => editIssue(issue.issueId, {
          issueId: issue.issueId, status: next.kind === 'exclude' ? 'excluded' : 'resolved', resolution: next });
        return <article className="assessments-subpanel" key={issue.issueId}><p>{issue.code} · {issue.severity} · {issue.status}：{issue.message} 来源 {JSON.stringify(issue.locator)}</p>
          {!readOnly && issue.status === 'open' && <div className="assessments-form">
            <label className="assessments-field"><span>结构化处置</span><select className="space-select" aria-label={`问题 ${issue.issueId} 处置`} value={resolution?.kind ?? ''} disabled={locked} onChange={(event) => {
              if (!event.target.value) { setIssueEdits((previous) => { const next = { ...previous }; delete next[issue.issueId]; return next; }); return; }
              setResolution({ kind: event.target.value as PaperIssueResolution['kind'] });
            }}><option value="">保持未处理</option><option value="supplement_text">补录实际文本</option><option value="supplement_asset">补录受管图片</option>{!CONTENT_LOSS_ISSUE_CODES.includes(issue.code) && <option value="exclude">有明确依据排除</option>}</select></label>
            {resolution && resolution.kind !== 'exclude' && <label className="assessments-field"><span>补录目标块</span><select className="space-select" aria-label={`问题 ${issue.issueId} 补录目标块`} value={resolution.targetBlockId ?? ''} disabled={locked} onChange={(event) => setResolution({ ...resolution, targetBlockId: event.target.value })}><option value="">选择目标块</option>{revision.blocks.filter((block) => resolution.kind !== 'supplement_text' || block.kind === 'paragraph').map((block) => <option key={block.blockId} value={block.blockId}>原文块 {block.ordinal}</option>)}</select></label>}
            {resolution?.kind === 'supplement_text' && <label className="assessments-field"><span>实际补录文本</span><textarea className="assessments-input" aria-label={`问题 ${issue.issueId} 补录文本`} value={resolution.text ?? ''} disabled={locked} onChange={(event) => setResolution({ ...resolution, text: event.target.value })} /></label>}
            {resolution?.kind === 'supplement_asset' && <label className="assessments-field"><span>本卷受管图片</span><select className="space-select" aria-label={`问题 ${issue.issueId} 补录图片`} value={resolution.assetId ?? ''} disabled={locked} onChange={(event) => setResolution({ ...resolution, assetId: event.target.value })}><option value="">选择已受管图片</option>{revision.blocks.filter((block) => block.kind === 'image').map((block) => <option key={block.blockId} value={String(block.content.assetId)}>原文块 {block.ordinal} 图片</option>)}</select></label>}
            {resolution?.kind === 'exclude' && <label className="assessments-field"><span>排除理由</span><input className="assessments-input" aria-label={`问题 ${issue.issueId} 排除理由`} value={resolution.reason ?? ''} disabled={locked} onChange={(event) => setResolution({ ...resolution, reason: event.target.value })} /></label>}
          </div>}
        </article>;
      })}
    </section>

    {!readOnly && <section aria-label="AI知识点关联建议"><h4>AI知识点关联建议（教师审核后应用）</h4>
      <label className="assessments-field"><span>明确模型</span><select className="space-select" aria-label="原卷建议模型" value={modelId} disabled={locked || job.observing} onChange={(event) => setModelId(event.target.value)}><option value="">请选择模型</option>{(profiles.lastData ?? []).map((profile) => <option key={profile.id} value={profile.id}>{profile.displayName}</option>)}</select></label>
      {profiles.state.phase === 'failed' && <p role="alert">模型读取失败（{profiles.state.error.code}）。<button className="space-button" onClick={profiles.reload}>重试模型</button></p>}
      {profiles.state.phase === 'ready' && profiles.lastData?.length === 0 && <p className="assessments-hint">尚无可选模型；先在模型与连接设置中建立可用模型，再生成建议。</p>}
      <button className="space-button" disabled={!modelId || dirty || locked || job.observing} onClick={() => void startProposal()}>生成关联建议</button>
      {job.view && <p role="status">建议任务：{job.view.state} · attempt {job.view.attempt}{job.pendingLabel ? ` · ${job.pendingLabel}` : ''}</p>}
      {job.view && <div className="assessments-actions"><button className="space-button" disabled={!!job.pending || !['queued', 'running'].includes(job.view.state)} onClick={job.cancel}>取消建议任务</button><button className="space-button" disabled={!!job.pending || !['failed', 'cancelled', 'interrupted'].includes(job.view.state)} onClick={job.retry}>重试建议任务</button></div>}
      {(job.actionError || job.view?.error) && <p role="alert">{job.actionError?.message ?? job.view?.error?.message}</p>}
      {job.observationNotice && <p role="status">{job.observationNotice}</p>}
      {proposal.state.phase === 'failed' && <p role="alert">建议读取失败（{proposal.state.error.code}）。<button className="space-button" onClick={proposal.reload}>重试读取建议</button></p>}
      {proposal.lastData && <div><p>候选：{proposal.lastData.state}{proposal.lastData.stale ? ' · 已过期，请重新生成' : ''}</p>
        {proposal.lastData.items.map((suggestion) => <div key={suggestion.itemId}><p>题 {suggestion.questionNo}：{suggestion.proposedName ?? suggestion.knowledgePointId ?? '待确认知识点'}；依据 {suggestion.evidence.join('；')}{suggestion.ambiguity ? '（存在歧义，需复核）' : ''}</p>
          <select className="space-select" aria-label={`题 ${suggestion.questionNo} 建议确认知识点`} value={proposalSelections[suggestion.itemId] ?? ''} onChange={(event) => setProposalSelections((previous) => ({ ...previous, [suggestion.itemId]: event.target.value }))}><option value="">不选用</option>{(knowledge.lastData?.items ?? []).map((point) => <option key={point.id} value={point.id}>{point.name}</option>)}</select></div>)}
        <button className="space-button" disabled={locked || dirty || proposal.lastData.stale || proposal.lastData.state !== 'pending' || !Object.values(proposalSelections).some(Boolean)} onClick={() => {
          const candidate = proposal.lastData;
          if (!candidate) return;
          void mutate(() => applyPaperProposal(candidate.proposalId, { expectedRevision: paper.revision,
            selections: Object.entries(proposalSelections).filter(([, point]) => point).map(([itemId, knowledgePointId]) => ({ itemId, knowledgePointId })) }), '已审核应用知识点建议，仍需确认原卷。').then(proposal.reload);
        }}>审核应用所选建议</button>
        <button className="space-button" disabled={locked || proposal.lastData.state !== 'pending'} onClick={() => {
          const candidate = proposal.lastData;
          if (!candidate) return;
          void mutate(() => rejectPaperProposal(candidate.proposalId, { expectedRevision: paper.revision, selections: [] }), '已拒绝该候选。', false).then(proposal.reload);
        }}>拒绝本批建议</button>
      </div>}
    </section>}
  </section>;
}
