'use client';

/**
 * 原卷（试卷）导入草稿的校对与确认面板（R5-FE 2026-10-11，沿用归档 `PaperImportReview`）。
 *
 * 保留的归档语义（一条不省）：
 * - 草稿 PATCH 用 `expectedRevision` 乐观锁；409 显示服务端 `currentRevision` 并**保留编辑**；
 * - 确认入库是**逻辑确认**（冻结 `submissionId` + 原样载荷），结果未知时重试复用同一标识，
 *   不会因为重试重复入库；422 的 `details.issues` 逐条按行/列定位显示；
 * - AI 知识点关联建议**只进候选**：生成任务 → 教师逐题审核 → 应用/拒绝；应用后仍是草稿，
 *   必须再显式「确认原卷入库」才落库；模型由教师显式选择，前端不代选、失败原因原样展示；
 * - 内容损失类问题（`CONTENT_LOSS_ISSUE_CODES`）只能「补录」，不能仅以排除放行。
 *
 * 本模块的范围裁定（R5-FE）：**不提供整卷内容阅读器**。因此这里只呈现**结构**——
 * 题号 / 父题 / 计分叶 / 满分 / 知识点关联 / 原文块类型与处置 / 解析问题与结构化处置，
 * 以及每道题、每个块的**结构摘要**（块数量、文本字数、是否含受管图片）。题面正文、图片与公式
 * 一律不渲染；`content` 字段只在保存草稿时**原样回传**（不改写服务端持久化内容）。
 */

import { useEffect, useRef, useState } from 'react';
import type {
  PaperBlockPatch,
  PaperConfirmRequest,
  PaperConfirmResult,
  PaperImportView,
  PaperItemInput,
  PaperIssuePatch,
  PaperIssueResolution,
  PaperRevisionContentView,
} from '@/contracts/papers';
import { CONTENT_LOSS_ISSUE_CODES } from '@/contracts/papers';
import {
  applyPaperProposal,
  confirmPaper,
  createPaperProposal,
  getPaper,
  getPaperProposal,
  getPaperRevisionContent,
  patchPaperDraft,
  rejectPaperProposal,
} from '@/services/assessments-api';
import { listKnowledgePoints } from '@/services/knowledge-points-api';
import { listProfiles } from '@/services/model-settings-api';
import { useTeachingJob } from './jobs';
import { asApiError, useAsyncResource, useFrozenSubmission } from './hooks';
import { formatScoreUnits, issueLocationLabel, scoredLeafItems, shortId } from './labels';

const ITEMS_PER_PAGE = 10;
const BLOCKS_PER_PAGE = 20;

/**
 * 新建小题时使用的空内容骨架：与后端 `RichContentV2` 同形（与归档 `rich({})` 等价），
 * 只是把一个「还没有内容的小题」表达清楚，不发明字段。
 */
function emptyRichContent(): Record<string, unknown> {
  return {
    version: 2,
    sharedMaterials: [],
    stemBlocks: [],
    optionBlocks: {},
    answerBlocks: [],
    explanationBlocks: [],
    assets: [],
    origin: { originalAssetId: '', originalSha256: '', sourceLocator: {} },
  };
}

function blockTextLength(block: unknown): number | null {
  if (!block || typeof block !== 'object') return null;
  const text = (block as { text?: unknown }).text;
  return typeof text === 'string' ? text.length : null;
}

function blockCount(content: Record<string, unknown>, key: string): number {
  const value = content[key];
  if (Array.isArray(value)) return value.length;
  if (value && typeof value === 'object') return Object.keys(value).length;
  return 0;
}

/** 小题内容的结构摘要（只给数量，不给正文）：题面/选项/答案/解析/共同材料/受管图片。 */
export function itemContentSummary(content: Record<string, unknown> | undefined): string {
  const source = content ?? {};
  const parts = [
    `题面 ${blockCount(source, 'stemBlocks')} 块`,
    `选项 ${blockCount(source, 'optionBlocks')} 组`,
    `答案 ${blockCount(source, 'answerBlocks')} 块`,
    `解析 ${blockCount(source, 'explanationBlocks')} 块`,
  ];
  const shared = blockCount(source, 'sharedMaterials');
  const assets = blockCount(source, 'assets');
  if (shared > 0) parts.push(`共同材料 ${shared} 组`);
  if (assets > 0) parts.push(`受管图片 ${assets} 张`);
  return parts.join(' · ');
}

/** 原文块的结构摘要：只说明块的类型与规模，不显示原文。 */
export function blockShapeText(block: {
  kind: string;
  content: Record<string, unknown>;
}): string {
  if (block.kind === 'paragraph') {
    const length = blockTextLength(block.content);
    return length === null ? '段落文本（长度未知）' : `段落文本 ${length} 字`;
  }
  if (block.kind === 'table') {
    const rows = blockCount(block.content, 'rows');
    const cells = blockCount(block.content, 'cells');
    return rows > 0 ? `表格 ${rows} 行` : cells > 0 ? `表格 ${cells} 个单元格` : '表格';
  }
  if (block.kind === 'formula') return '公式块（按原文保存，不在此渲染）';
  if (block.kind === 'image') {
    const assetId = block.content.assetId;
    return typeof assetId === 'string' && assetId !== ''
      ? '受管图片（不在此渲染）'
      : '图片块（服务端未给出受管资产）';
  }
  return '未知块类型（按原文保存）';
}

function inputs(revision: PaperRevisionContentView): PaperItemInput[] {
  return revision.items.map((item) => ({
    itemId: item.itemId,
    parentItemId: item.parentItemId,
    questionNo: item.questionNo,
    ordinal: item.ordinal,
    isScored: item.isScored,
    maxScore:
      item.maxScore ?? (item.maxScoreUnits === null ? null : formatScoreUnits(item.maxScoreUnits)),
    // content / sourceLocator 原样回传：本模块不改写服务端持久化内容
    content: item.content,
    sourceLocator: item.sourceLocator,
    knowledge: item.knowledge.map((link) => ({
      knowledgePointId: link.knowledgePointId,
      role: link.role,
    })),
  }));
}

function blockInputs(revision: PaperRevisionContentView): PaperBlockPatch[] {
  return revision.blocks.map((block) => ({
    blockId: block.blockId,
    disposition: block.disposition,
    itemId: block.itemId,
    excludeReason: block.excludeReason,
  }));
}

export function PaperImportReview({
  initial,
  onChanged,
  onClose,
}: {
  initial: PaperImportView;
  onChanged: () => void;
  onClose: () => void;
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
    return () => {
      state.mounted = false;
      state.epoch += 1;
    };
  }, []);
  const confirmation = useFrozenSubmission<PaperConfirmRequest, PaperConfirmResult>();
  const job = useTeachingJob();
  const knowledge = useAsyncResource(
    (signal) =>
      listKnowledgePoints(
        { subjectId: revision.subjectId, status: 'active', q: knowledgeSearch, limit: 200 },
        signal,
      ),
    `paper-knowledge|${revision.subjectId}|${knowledgeSearch}`,
  );
  const profiles = useAsyncResource(() => listProfiles(), 'paper-proposal-models');
  const proposalId =
    job.view?.state === 'succeeded' && typeof job.view.result?.proposalId === 'string'
      ? job.view.result.proposalId
      : null;
  const proposal = useAsyncResource(
    (signal) => (proposalId ? getPaperProposal(proposalId, signal) : Promise.resolve(null)),
    `paper-proposal|${proposalId ?? 'none'}`,
  );
  const locked = busy || confirmation.busy || confirmation.phase === 'unknown';
  const readOnly = revision.state === 'confirmed';
  const itemsTotal = items.length;
  /** 本地新增（服务端还没保存过）的小题数：提示「待保存」。 */
  const localNewItems = items.filter(
    (item) => item.itemId && !revision.items.some((original) => original.itemId === item.itemId),
  ).length;

  function editItem(index: number, change: Partial<PaperItemInput>) {
    setItems((previous) =>
      previous.map((item, current) => (current === index ? { ...item, ...change } : item)),
    );
    setDirty(true);
  }
  function editBlock(index: number, change: Partial<PaperBlockPatch>) {
    setBlocks((previous) =>
      previous.map((block, current) => (current === index ? { ...block, ...change } : block)),
    );
    setDirty(true);
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
    setBusy(true);
    setError(null);
    setNotice(null);
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
    await mutate(
      () =>
        patchPaperDraft(paper.paperId, {
          expectedRevision: paper.revision,
          title: title.trim(),
          items,
          blocks,
          issues: Object.values(issueEdits),
        }),
      '已保存试卷草稿并读回当前版本。',
    );
  }
  async function confirm() {
    const payload =
      confirmation.phase === 'unknown' && confirmation.frozen
        ? confirmation.frozen.payload
        : { expectedRevision: paper.revision, submissionId: '' };
    const result = await confirmation.submit(payload, (frozen) =>
      confirmPaper(paper.paperId, { ...frozen.payload, submissionId: frozen.submissionId }),
    );
    if (!result) return;
    const token = ++operation.current.epoch;
    try {
      const current = await readCurrent(true, result.paperRevisionId);
      if (!operation.current.mounted || token !== operation.current.epoch) return;
      applyRead(current);
      onChanged();
    } catch (cause) {
      if (operation.current.mounted && token === operation.current.epoch) setError(asApiError(cause));
    }
  }
  function editIssue(issueId: string, patch: PaperIssuePatch) {
    setIssueEdits((previous) => ({ ...previous, [issueId]: patch }));
    setDirty(true);
  }
  async function startProposal() {
    if (!modelId || dirty || locked) return;
    const token = ++operation.current.epoch;
    setBusy(true);
    setError(null);
    job.reset();
    try {
      const receipt = await createPaperProposal(paper.paperId, {
        modelProfileId: modelId,
        expectedRevision: paper.revision,
      });
      if (operation.current.mounted && token === operation.current.epoch) job.adopt(receipt);
    } catch (cause) {
      if (operation.current.mounted && token === operation.current.epoch) setError(asApiError(cause));
    } finally {
      if (operation.current.mounted && token === operation.current.epoch) setBusy(false);
    }
  }

  const displayedError = error ?? confirmation.error;
  const pageItems = items.slice(itemPage * ITEMS_PER_PAGE, (itemPage + 1) * ITEMS_PER_PAGE);
  const pageBlocks = revision.blocks.slice(
    blockPage * BLOCKS_PER_PAGE,
    (blockPage + 1) * BLOCKS_PER_PAGE,
  );

  return (
    <section
      className="assessments-subpanel"
      aria-label="原卷草稿校对与确认"
      data-testid="paper-import-review"
    >
      <div className="assessments-subpanel-head">
        <h3>{readOnly ? '固定原卷修订' : '原卷校对'}：{revision.title}</h3>
        <span className={readOnly ? 'space-chip green' : 'space-chip amber'}>
          {readOnly ? '已确认（只读）' : '草稿'}
        </span>
        <button className="space-button" onClick={onClose} data-testid="paper-review-close">
          关闭校对面板
        </button>
      </div>
      <p className="assessments-meta" title={`修订 ${revision.paperRevisionId}`}>
        修订 v{revision.version} · 编辑版本 r{paper.revision} · {shortId(revision.paperRevisionId)} ·
        满分 {formatScoreUnits(revision.totalScoreUnits)} · 计分叶{' '}
        {scoredLeafItems(revision.items).length} 个。
        {readOnly
          ? ' 此修订只读：已确认的修订不可再改。'
          : ' 草稿保存后再确认；题号保留完整路径，只有叶子计分。'}
      </p>
      <p className="assessments-hint">
        本页只呈现拆题结构与知识点关联，不显示试卷正文、图片与公式；每题的正文内容以服务端持久化
        快照为准，保存草稿时原样回传，不在前端改写。
      </p>
      {initial.warnings.map((warning, index) => (
        <p className="space-banner info" key={index}>
          {warning}
        </p>
      ))}
      {notice && (
        <p className="space-banner info" role="status">
          {notice}
        </p>
      )}
      {displayedError && (
        <div className="space-banner error" role="alert" data-testid="paper-review-error">
          {displayedError.code}：{displayedError.message} 编辑已保留。
          {displayedError.status === 409 && (
            <p>
              当前版本 {displayedError.details?.currentRevision ?? '未知'}，请刷新对照后再保存，不会静默覆盖。
            </p>
          )}
          {(displayedError.details?.issues ?? []).map((issue, index) => (
            <p key={index}>
              {issueLocationLabel(issue)}
              {issue.code}：{issue.message}
            </p>
          ))}
        </div>
      )}
      {confirmation.unknownNotice && (
        <p className="space-banner error" role="alert">
          {confirmation.unknownNotice}
        </p>
      )}
      {confirmation.result && (
        <p
          className="space-banner info"
          role="status"
          title={`修订 ${confirmation.result.paperRevisionId}`}
          data-testid="paper-confirm-result"
        >
          {confirmation.result.replayed ? '已确认原卷（重放）' : '已确认原卷'}：
          {shortId(confirmation.result.paperRevisionId)}，计分叶 {confirmation.result.scoredLeafCount}。
        </p>
      )}
      <div className="assessments-actions">
        {readOnly ? (
          <span className="space-chip green">该修订已确认入库</span>
        ) : (
          <>
            <button
              className="space-button"
              disabled={locked || !dirty}
              onClick={() => void save()}
              data-testid="paper-save-draft"
            >
              {busy ? '保存中…' : '保存试卷草稿'}
            </button>
            <button
              className="space-button primary"
              disabled={busy || confirmation.busy || dirty}
              title={dirty ? '有未保存的校对，先保存草稿再确认' : undefined}
              onClick={() => void confirm()}
              data-testid="paper-confirm"
            >
              {confirmation.phase === 'unknown' ? '重试原卷确认' : '确认原卷入库'}
            </button>
          </>
        )}
        <button
          className="space-button"
          disabled={locked}
          onClick={() =>
            void mutate(
              () => Promise.resolve(),
              dirty
                ? '已刷新服务端对照；本地编辑保留，请核对后保存。'
                : '已刷新原卷对照。',
              !dirty,
            )
          }
        >
          刷新原卷对照
        </button>
        {dirty && <span className="space-chip amber">有未保存的校对</span>}
      </div>

      <label className="assessments-field">
        <span>试卷修订标题</span>
        <input
          className="assessments-input"
          aria-label="原卷修订标题"
          value={title}
          disabled={locked || readOnly}
          onChange={(event) => {
            setTitle(event.target.value);
            setDirty(true);
          }}
        />
      </label>

      <section aria-label="题目校对">
        <div className="assessments-subpanel-head">
          <h4>题目与知识点</h4>
          <span className="space-chip">共 {itemsTotal} 题</span>
          {localNewItems > 0 && <span className="space-chip amber">{localNewItems} 题待保存</span>}
        </div>
        {!readOnly && (
          <>
            <label className="assessments-field">
              <span>搜索本学科知识点</span>
              <input
                className="assessments-input"
                aria-label="原卷知识点搜索"
                value={knowledgeSearch}
                onChange={(event) => setKnowledgeSearch(event.target.value)}
              />
            </label>
            {knowledge.state.phase === 'failed' && (
              <p className="assessments-error" role="alert">
                知识点读取失败（{knowledge.state.error.code}）：{knowledge.state.error.message}
                已有关联保留，不会因为读取失败而被清空。
                <button className="space-button" onClick={knowledge.reload}>
                  重试知识点
                </button>
              </p>
            )}
            {knowledge.state.phase === 'ready' && knowledge.lastData?.items.length === 0 && (
              <p className="assessments-hint">
                当前学科或搜索条件下没有可选知识点；请先建立知识点或调整搜索。
              </p>
            )}
            <div className="assessments-actions">
              <button
                className="space-button"
                disabled={locked}
                data-testid="paper-add-item"
                onClick={() => {
                  const itemId = `manual-${crypto.randomUUID()}`;
                  setItems((previous) => [
                    ...previous,
                    {
                      itemId,
                      questionNo: '',
                      ordinal: previous.length + 1,
                      parentItemId: null,
                      isScored: true,
                      maxScore: '',
                      content: emptyRichContent(),
                      knowledge: [],
                    },
                  ]);
                  setItemPage(Math.floor(items.length / ITEMS_PER_PAGE));
                  setDirty(true);
                }}
              >
                新增题目
              </button>
              <span className="assessments-hint">
                解析漏掉整题时在这里补一个空题，填好题号与分值后再保存草稿。
              </span>
            </div>
          </>
        )}
        {pageItems.map((item, offset) => {
          const index = itemPage * ITEMS_PER_PAGE + offset;
          const label = item.questionNo || `新题${index + 1}`;
          const original = revision.items.find((entry) => entry.itemId === item.itemId);
          return (
            <fieldset
              key={item.itemId ?? index}
              className="assessments-subpanel"
              aria-label={`题 ${label} 校对`}
              data-testid={`paper-item-${item.itemId ?? index}`}
            >
              <legend>题 {label}</legend>
              <p className="assessments-meta" data-testid={`paper-item-summary-${item.itemId ?? index}`}>
                结构：{itemContentSummary(item.content)}（正文不在此渲染）
              </p>
              {original && original.knowledge.length > 0 && (
                <p className="assessments-actions">
                  已关联：
                  {original.knowledge.map((link) => (
                    <span className="space-chip" key={link.knowledgePointId}>
                      {link.knowledgeNameSnapshot} · {link.role} · {link.source}
                    </span>
                  ))}
                </p>
              )}
              {!readOnly && (
                <div className="assessments-form">
                  <label className="assessments-field">
                    <span>完整题号</span>
                    <input
                      className="assessments-input"
                      aria-label={`题 ${label} 题号`}
                      value={item.questionNo}
                      disabled={locked}
                      onChange={(event) => editItem(index, { questionNo: event.target.value })}
                    />
                  </label>
                  <label className="assessments-field">
                    <span>父题（容器不计分）</span>
                    <select
                      className="space-select"
                      aria-label={`题 ${label} 父题`}
                      value={item.parentItemId ?? ''}
                      disabled={locked}
                      onChange={(event) =>
                        editItem(index, { parentItemId: event.target.value || null })
                      }
                    >
                      <option value="">无父题</option>
                      {items
                        .filter((parent) => parent.itemId !== item.itemId)
                        .map((parent) => (
                          <option key={parent.itemId ?? ''} value={parent.itemId ?? ''}>
                            {parent.questionNo || parent.itemId}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label className="assessments-check">
                    <input
                      type="checkbox"
                      aria-label={`题 ${label} 计分叶`}
                      checked={item.isScored}
                      disabled={locked}
                      onChange={(event) =>
                        editItem(index, {
                          isScored: event.target.checked,
                          maxScore: event.target.checked ? item.maxScore ?? '' : null,
                        })
                      }
                    />
                    <span>计分叶</span>
                  </label>
                  <label className="assessments-field">
                    <span>满分</span>
                    <input
                      className="assessments-input assessments-input-narrow"
                      aria-label={`题 ${label} 满分`}
                      value={item.maxScore ?? ''}
                      disabled={locked || !item.isScored}
                      onChange={(event) => editItem(index, { maxScore: event.target.value })}
                    />
                  </label>
                  <label className="assessments-field">
                    <span>正式知识点（可多选）</span>
                    <select
                      className="space-select"
                      multiple
                      aria-label={`题 ${label} 知识点`}
                      value={(item.knowledge ?? []).map((link) => link.knowledgePointId)}
                      disabled={locked}
                      onChange={(event) =>
                        editItem(index, {
                          knowledge: Array.from(event.target.selectedOptions).map((option) => ({
                            knowledgePointId: option.value,
                            role:
                              item.knowledge?.find(
                                (link) => link.knowledgePointId === option.value,
                              )?.role ?? 'primary',
                          })),
                        })
                      }
                    >
                      {(knowledge.lastData?.items ?? []).map((point) => (
                        <option key={point.id} value={point.id}>
                          {point.code} · {point.name}
                        </option>
                      ))}
                      {(item.knowledge ?? [])
                        .filter(
                          (link) =>
                            !knowledge.lastData?.items.some(
                              (point) => point.id === link.knowledgePointId,
                            ),
                        )
                        .map((link) => (
                          <option key={link.knowledgePointId} value={link.knowledgePointId}>
                            {original?.knowledge.find(
                              (entry) => entry.knowledgePointId === link.knowledgePointId,
                            )?.knowledgeNameSnapshot ?? link.knowledgePointId}
                            （已有）
                          </option>
                        ))}
                    </select>
                  </label>
                  {(item.knowledge ?? []).map((link) => (
                    <label className="assessments-field" key={link.knowledgePointId}>
                      <span>关联角色 {link.knowledgePointId}</span>
                      <select
                        className="space-select"
                        value={link.role ?? 'primary'}
                        disabled={locked}
                        aria-label={`题 ${label} ${link.knowledgePointId} 角色`}
                        onChange={(event) =>
                          editItem(index, {
                            knowledge: item.knowledge?.map((current) =>
                              current.knowledgePointId === link.knowledgePointId
                                ? {
                                    ...current,
                                    role: event.target.value as 'primary' | 'secondary',
                                  }
                                : current,
                            ),
                          })
                        }
                      >
                        <option value="primary">主要</option>
                        <option value="secondary">次要</option>
                      </select>
                    </label>
                  ))}
                </div>
              )}
            </fieldset>
          );
        })}
        <div className="assessments-actions">
          <button
            className="space-button"
            disabled={itemPage === 0}
            onClick={() => setItemPage((value) => value - 1)}
          >
            上一页题目
          </button>
          <span className="assessments-meta">
            第 {itemPage + 1} / {Math.max(1, Math.ceil(itemsTotal / ITEMS_PER_PAGE))} 页 · 共{' '}
            {itemsTotal} 题
          </span>
          <button
            className="space-button"
            disabled={(itemPage + 1) * ITEMS_PER_PAGE >= itemsTotal}
            onClick={() => setItemPage((value) => value + 1)}
          >
            下一页题目
          </button>
        </div>
      </section>

      <section aria-label="完整原文块">
        <div className="assessments-subpanel-head">
          <h4>原文块与处置</h4>
          <span className="space-chip">共 {revision.blocks.length} 块</span>
        </div>
        {pageBlocks.map((source, offset) => {
          const index = blockPage * BLOCKS_PER_PAGE + offset;
          const edit = blocks[index];
          return (
            <article
              key={source.blockId}
              className="assessments-subpanel"
              data-testid={`paper-source-${source.blockId}`}
            >
              <h5>
                原文块 {source.ordinal} · {source.kind}
              </h5>
              <p className="assessments-meta">
                结构：{blockShapeText(source)} · 来源 {JSON.stringify(source.locator)}
              </p>
              {!readOnly && edit && (
                <div className="assessments-form">
                  <label className="assessments-field">
                    <span>原文块处置</span>
                    <select
                      className="space-select"
                      aria-label={`原文块 ${source.ordinal} 处置`}
                      value={edit.disposition}
                      disabled={locked}
                      onChange={(event) =>
                        editBlock(index, {
                          disposition: event.target.value as PaperBlockPatch['disposition'],
                          itemId: null,
                          excludeReason: null,
                        })
                      }
                    >
                      <option value="unassigned">待归属</option>
                      <option value="item">归属题目</option>
                      <option value="shared_material">共同材料</option>
                      <option value="excluded">有依据排除</option>
                    </select>
                  </label>
                  {edit.disposition === 'item' && (
                    <label className="assessments-field">
                      <span>归属题目</span>
                      <select
                        className="space-select"
                        aria-label={`原文块 ${source.ordinal} 归属题目`}
                        value={edit.itemId ?? ''}
                        disabled={locked}
                        onChange={(event) =>
                          editBlock(index, { itemId: event.target.value || null })
                        }
                      >
                        <option value="">选择题目</option>
                        {items.map((item) => (
                          <option key={item.itemId ?? ''} value={item.itemId ?? ''}>
                            {item.questionNo || item.itemId}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  {edit.disposition === 'excluded' && (
                    <label className="assessments-field">
                      <span>排除依据</span>
                      <input
                        className="assessments-input"
                        aria-label={`原文块 ${source.ordinal} 排除依据`}
                        value={edit.excludeReason ?? ''}
                        disabled={locked}
                        onChange={(event) =>
                          editBlock(index, { excludeReason: event.target.value })
                        }
                      />
                    </label>
                  )}
                </div>
              )}
            </article>
          );
        })}
        <div className="assessments-actions">
          <button
            className="space-button"
            disabled={blockPage === 0}
            onClick={() => setBlockPage((value) => value - 1)}
          >
            上一页原文
          </button>
          <span className="assessments-meta">
            第 {blockPage + 1} / {Math.max(1, Math.ceil(revision.blocks.length / BLOCKS_PER_PAGE))} 页
          </span>
          <button
            className="space-button"
            disabled={(blockPage + 1) * BLOCKS_PER_PAGE >= revision.blocks.length}
            onClick={() => setBlockPage((value) => value + 1)}
          >
            下一页原文
          </button>
        </div>
      </section>

      <section aria-label="原卷问题处置">
        <div className="assessments-subpanel-head">
          <h4>解析问题与明确处置</h4>
          <span className="space-chip">{revision.issues.length} 条</span>
        </div>
        {revision.issues.length === 0 && (
          <p className="assessments-hint">
            没有解析问题。确认仍由服务端核题面、共同材料与计分叶关联。
          </p>
        )}
        {revision.issues.map((issue) => {
          const edit = issueEdits[issue.issueId];
          const resolution = edit?.resolution;
          const setResolution = (next: PaperIssueResolution) =>
            editIssue(issue.issueId, {
              issueId: issue.issueId,
              status: next.kind === 'exclude' ? 'excluded' : 'resolved',
              resolution: next,
            });
          return (
            <article className="assessments-subpanel" key={issue.issueId}>
              <p className="assessments-meta">
                {issue.code} · {issue.severity} · {issue.status}：{issue.message} 来源{' '}
                {JSON.stringify(issue.locator)}
              </p>
              {!readOnly && issue.status === 'open' && (
                <div className="assessments-form">
                  <label className="assessments-field">
                    <span>结构化处置</span>
                    <select
                      className="space-select"
                      aria-label={`问题 ${issue.issueId} 处置`}
                      value={resolution?.kind ?? ''}
                      disabled={locked}
                      onChange={(event) => {
                        if (!event.target.value) {
                          setIssueEdits((previous) => {
                            const next = { ...previous };
                            delete next[issue.issueId];
                            return next;
                          });
                          return;
                        }
                        setResolution({
                          kind: event.target.value as PaperIssueResolution['kind'],
                        });
                      }}
                    >
                      <option value="">保持未处理</option>
                      <option value="supplement_text">补录实际文本</option>
                      <option value="supplement_asset">补录受管图片</option>
                      {!CONTENT_LOSS_ISSUE_CODES.includes(issue.code) && (
                        <option value="exclude">有明确依据排除</option>
                      )}
                    </select>
                  </label>
                  {resolution && resolution.kind !== 'exclude' && (
                    <label className="assessments-field">
                      <span>补录目标块</span>
                      <select
                        className="space-select"
                        aria-label={`问题 ${issue.issueId} 补录目标块`}
                        value={resolution.targetBlockId ?? ''}
                        disabled={locked}
                        onChange={(event) =>
                          setResolution({ ...resolution, targetBlockId: event.target.value })
                        }
                      >
                        <option value="">选择目标块</option>
                        {revision.blocks
                          .filter(
                            (block) =>
                              resolution.kind !== 'supplement_text' || block.kind === 'paragraph',
                          )
                          .map((block) => (
                            <option key={block.blockId} value={block.blockId}>
                              原文块 {block.ordinal}
                            </option>
                          ))}
                      </select>
                    </label>
                  )}
                  {resolution?.kind === 'supplement_text' && (
                    <label className="assessments-field">
                      <span>实际补录文本</span>
                      <textarea
                        className="assessments-input"
                        aria-label={`问题 ${issue.issueId} 补录文本`}
                        value={resolution.text ?? ''}
                        disabled={locked}
                        onChange={(event) =>
                          setResolution({ ...resolution, text: event.target.value })
                        }
                      />
                    </label>
                  )}
                  {resolution?.kind === 'supplement_asset' && (
                    <label className="assessments-field">
                      <span>本卷受管图片</span>
                      <select
                        className="space-select"
                        aria-label={`问题 ${issue.issueId} 补录图片`}
                        value={resolution.assetId ?? ''}
                        disabled={locked}
                        onChange={(event) =>
                          setResolution({ ...resolution, assetId: event.target.value })
                        }
                      >
                        <option value="">选择已受管图片</option>
                        {revision.blocks
                          .filter(
                            (block) =>
                              block.kind === 'image' &&
                              typeof block.content.assetId === 'string' &&
                              block.content.assetId !== '',
                          )
                          .map((block) => (
                            <option key={block.blockId} value={String(block.content.assetId)}>
                              原文块 {block.ordinal} 图片
                            </option>
                          ))}
                      </select>
                    </label>
                  )}
                  {resolution?.kind === 'exclude' && (
                    <label className="assessments-field">
                      <span>排除理由</span>
                      <input
                        className="assessments-input"
                        aria-label={`问题 ${issue.issueId} 排除理由`}
                        value={resolution.reason ?? ''}
                        disabled={locked}
                        onChange={(event) =>
                          setResolution({ ...resolution, reason: event.target.value })
                        }
                      />
                    </label>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </section>

      {!readOnly && (
        <section aria-label="AI知识点关联建议">
          <div className="assessments-subpanel-head">
            <h4>AI 知识点关联建议（教师审核后应用）</h4>
            <span className="space-chip">只进候选，不自动入库</span>
          </div>
          <label className="assessments-field">
            <span>明确模型</span>
            <select
              className="space-select"
              aria-label="原卷建议模型"
              value={modelId}
              disabled={locked || job.observing}
              onChange={(event) => setModelId(event.target.value)}
            >
              <option value="">请选择模型</option>
              {(profiles.lastData ?? []).map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.displayName}
                </option>
              ))}
            </select>
          </label>
          {profiles.state.phase === 'failed' && (
            <p className="assessments-error" role="alert">
              模型读取失败（{profiles.state.error.code}）：{profiles.state.error.message}
              <button className="space-button" onClick={profiles.reload}>
                重试模型
              </button>
            </p>
          )}
          {profiles.state.phase === 'ready' && profiles.lastData?.length === 0 && (
            <p className="assessments-hint">
              尚无可选模型；先在模型与连接设置中建立可用模型，再生成建议。
            </p>
          )}
          <div className="assessments-actions">
            <button
              className="space-button"
              disabled={!modelId || dirty || locked || job.observing}
              title={dirty ? '先保存草稿，再让 AI 基于最新版本生成建议' : undefined}
              onClick={() => void startProposal()}
            >
              生成关联建议
            </button>
          </div>
          {job.view && (
            <p className="assessments-job-line" role="status">
              建议任务：{job.view.state} · attempt {job.view.attempt}
              {job.pendingLabel ? ` · ${job.pendingLabel}` : ''}
            </p>
          )}
          {job.view && (
            <div className="assessments-actions">
              <button
                className="space-button"
                disabled={!!job.pending || !['queued', 'running'].includes(job.view.state)}
                onClick={job.cancel}
              >
                取消建议任务
              </button>
              <button
                className="space-button"
                disabled={
                  !!job.pending ||
                  !['failed', 'cancelled', 'interrupted'].includes(job.view.state)
                }
                onClick={job.retry}
              >
                重试建议任务
              </button>
            </div>
          )}
          {(job.actionError || job.view?.error) && (
            <p className="assessments-error" role="alert">
              {job.actionError?.message ?? job.view?.error?.message}
            </p>
          )}
          {job.observationNotice && (
            <p className="assessments-job-line" role="status">
              {job.observationNotice}
            </p>
          )}
          {proposal.state.phase === 'failed' && (
            <p className="assessments-error" role="alert">
              建议读取失败（{proposal.state.error.code}）：{proposal.state.error.message}
              <button className="space-button" onClick={proposal.reload}>
                重试读取建议
              </button>
            </p>
          )}
          {proposal.lastData && (
            <div>
              <p className="assessments-meta">
                候选：{proposal.lastData.state}
                {proposal.lastData.stale ? ' · 已过期，请重新生成' : ''} · 共{' '}
                {proposal.lastData.items.length} 题
              </p>
              {proposal.lastData.items.map((suggestion) => (
                <div key={suggestion.itemId} className="paper-item-row">
                  <span className="paper-item-no">题 {suggestion.questionNo}</span>
                  <span className="assessments-hint">
                    {suggestion.proposedName ?? suggestion.knowledgePointId ?? '待确认知识点'}；依据{' '}
                    {suggestion.evidence.join('；')}
                    {suggestion.ambiguity ? '（存在歧义，需复核）' : ''}
                  </span>
                  <select
                    className="space-select"
                    aria-label={`题 ${suggestion.questionNo} 建议确认知识点`}
                    value={proposalSelections[suggestion.itemId] ?? ''}
                    disabled={locked}
                    onChange={(event) =>
                      setProposalSelections((previous) => ({
                        ...previous,
                        [suggestion.itemId]: event.target.value,
                      }))
                    }
                  >
                    <option value="">不选用</option>
                    {(knowledge.lastData?.items ?? []).map((point) => (
                      <option key={point.id} value={point.id}>
                        {point.name}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
              <div className="assessments-actions">
                <button
                  className="space-button"
                  disabled={
                    locked ||
                    dirty ||
                    proposal.lastData.stale ||
                    proposal.lastData.state !== 'pending' ||
                    !Object.values(proposalSelections).some(Boolean)
                  }
                  onClick={() => {
                    const candidate = proposal.lastData;
                    if (!candidate) return;
                    void mutate(
                      () =>
                        applyPaperProposal(candidate.proposalId, {
                          expectedRevision: paper.revision,
                          selections: Object.entries(proposalSelections)
                            .filter(([, point]) => point)
                            .map(([itemId, knowledgePointId]) => ({ itemId, knowledgePointId })),
                        }),
                      '已审核应用知识点建议，仍需确认原卷。',
                    ).then(proposal.reload);
                  }}
                >
                  审核应用所选建议
                </button>
                <button
                  className="space-button"
                  disabled={locked || proposal.lastData.state !== 'pending'}
                  onClick={() => {
                    const candidate = proposal.lastData;
                    if (!candidate) return;
                    void mutate(
                      () =>
                        rejectPaperProposal(candidate.proposalId, {
                          expectedRevision: paper.revision,
                          selections: [],
                        }),
                      '已拒绝该候选。',
                      false,
                    ).then(proposal.reload);
                  }}
                >
                  拒绝本批建议
                </button>
              </div>
            </div>
          )}
        </section>
      )}
    </section>
  );
}
