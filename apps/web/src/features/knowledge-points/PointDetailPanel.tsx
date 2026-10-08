'use client';

/**
 * 知识点详情与编辑。
 *
 * - 名称/说明/父级/排序/别名一次提交，**空白表示不修改**，清空走显式勾选
 *   （`clearFields`），界面对两者给出不同说明（见 `./point-form` 的 actions/hints）；
 * - 改名由服务端追加修订，界面显示 `version` / `revisionId` / 编辑锁 `revision`；
 * - 409 冲突：显示「当前版本 N，已刷新为最新，请重试」，**保留用户的编辑**并给出
 *   「用服务端最新值覆盖表单」出口（不强制覆盖，也不静默丢弃）；
 * - 422：用 `details.issues` 定位字段并逐条显示；
 * - 读取失败显示错误与重试，不显示空态；
 * - **彻底删除**与归档是两回事：删除是物理删除、不可恢复；被引用（教材依据 / 原卷题目 /
 *   题库正式题或草稿）或仍有子节点时服务端 409 拒绝，界面把 `details.counts` 逐项列成
 *   原因清单，并给出「改为归档」出口——绝不把「删不掉」显示成失败或静默重试。
 */

import { useEffect, useMemo, useState } from 'react';
import { Archive, RefreshCw, RotateCcw, Save, Trash2, X } from 'lucide-react';
import type { ErrorIssue } from '@/contracts/api';
import type { KnowledgePointReferenceCount, KnowledgePointView } from '@/contracts/knowledge';
import { Modal } from '@/components/ui/Modal';
import {
  archiveKnowledgePoint,
  deleteKnowledgePoint,
  getKnowledgePoint,
  listKnowledgePoints,
  restoreKnowledgePoint,
  updateKnowledgePoint,
} from '@/services/knowledge-points-api';
import { asApiError, useAsyncResource } from './hooks';
import {
  KNOWLEDGE_POINT_IN_USE_CODE,
  knowledgeStatusLabel,
  parseKnowledgeReferenceCounts,
  referenceCountLabel,
} from './labels';
import {
  PARENT_CLEAR,
  PARENT_UNCHANGED,
  planPointUpdate,
  splitAliases,
  type PointClearFlags,
  type PointUpdateValues,
} from './point-form';
import { TextbookLinksPanel } from './TextbookLinksPanel';

const ZERO_CLEAR: PointClearFlags = { description: false, aliases: false };

function valuesFrom(point: KnowledgePointView): PointUpdateValues {
  return {
    name: point.name,
    description: point.description,
    parentId: PARENT_UNCHANGED,
    sortOrder: String(point.sortOrder),
    aliasesText: point.aliases.join('、'),
  };
}

export function PointDetailPanel({
  pointId,
  onPointPatched,
  onLoaded,
  onDeleted,
}: {
  pointId: string;
  onPointPatched: (next: KnowledgePointView) => void;
  /** 详情读取/保存后把权威对象交给父级（用于「AI 候选」引用同学科与教材依据）。 */
  onLoaded?: (next: KnowledgePointView) => void;
  /** 彻底删除成功后通知父级：刷新列表并取消选中（父级未提供时本地显示已删除态）。 */
  onDeleted?: (pointId: string) => void;
}) {
  const point = useAsyncResource(
    (signal) => getKnowledgePoint(pointId, signal),
    `kp-detail|${pointId}`,
  );
  // 最近一次成功读取的权威对象：重新读取（含 409 后刷新）期间继续显示，不清空表单
  const loaded = point.lastData;
  const pointError = point.state.phase === 'failed' ? point.state.error : null;
  const refreshing = point.state.phase === 'loading' && loaded !== null;

  const [form, setForm] = useState<PointUpdateValues | null>(null);
  const [clear, setClear] = useState<PointClearFlags>(ZERO_CLEAR);
  const [formFor, setFormFor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [issues, setIssues] = useState<ErrorIssue[]>([]);
  const [conflict, setConflict] = useState<{ revision: number | null; message: string } | null>(
    null,
  );
  const [notice, setNotice] = useState<string | null>(null);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [archiveBusy, setArchiveBusy] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  /** 彻底删除：是否已在本地确认删除成功（父级未接管选中时也不至于继续显示已删知识点）。 */
  const [deleted, setDeleted] = useState(false);
  /** 彻底删除被拒（409）的原因：服务端 message + 逐项引用计数（缺 counts 时为 null）。 */
  const [deleteBlock, setDeleteBlock] = useState<{
    message: string;
    counts: KnowledgePointReferenceCount[] | null;
  } | null>(null);

  // 表单只在「对象身份变化」时从服务端初始化：409 冲突后重新读取不会冲掉用户输入。
  useEffect(() => {
    if (!loaded) return;
    if (formFor === loaded.id) return;
    setForm(valuesFrom(loaded));
    setClear(ZERO_CLEAR);
    setFormFor(loaded.id);
    setErrorText(null);
    setIssues([]);
    setConflict(null);
    setNotice(null);
  }, [loaded, formFor]);

  // 把权威对象交给父级（父级用 id+revision+version 去重，不会形成循环）。
  useEffect(() => {
    if (loaded) onLoaded?.(loaded);
  }, [loaded, onLoaded]);

  const parentCandidates = useAsyncResource(
    (signal) =>
      loaded
        ? listKnowledgePoints(
            { subjectId: loaded.subjectId, status: 'active', limit: 200 },
            signal,
          ).then((list) => list.items)
        : Promise.resolve([] as KnowledgePointView[]),
    `kp-parents|${pointId}|${loaded?.subjectId ?? ''}`,
  );
  const parents =
    parentCandidates.state.phase === 'ready'
      ? parentCandidates.state.data.filter(
          (item) => item.id !== loaded?.id && item.status === 'active',
        )
      : [];

  const plan = useMemo(
    () => (loaded && form ? planPointUpdate(loaded, form, clear) : null),
    [loaded, form, clear],
  );

  function resetFormFrom(next: KnowledgePointView) {
    setForm(valuesFrom(next));
    setClear(ZERO_CLEAR);
  }

  async function save() {
    if (!loaded || !form || !plan) return;
    if (plan.errors.length > 0) {
      setErrorText('请先修正表单问题再保存。');
      return;
    }
    if (!plan.request) {
      setErrorText('没有可提交的修改：留空的字段表示不修改。');
      return;
    }
    setBusy(true);
    setErrorText(null);
    setIssues([]);
    setNotice(null);
    const targetId = loaded.id;
    try {
      const next = await updateKnowledgePoint(targetId, plan.request);
      setConflict(null);
      resetFormFrom(next);
      setNotice(
        `已保存：内容版本 v${next.version}，修订 ${next.revisionId ?? '（无）'}（编辑锁 r${next.revision}）。`,
      );
      onPointPatched(next);
      // 让头部 chip（版本/修订/编辑锁）与资源缓存一致：重新读取服务端权威对象
      point.reload();
    } catch (cause) {
      const error = asApiError(cause);
      if (error.status === 409) {
        // 不强制覆盖：保留用户输入，重新读取服务端最新版本供比较
        setConflict({
          revision: error.details?.currentRevision ?? null,
          message: error.message,
        });
        point.reload();
      } else if (error.status === 422) {
        setIssues(error.details?.issues ?? []);
        setErrorText(`保存失败（${error.code}）：${error.message}`);
      } else {
        setErrorText(`保存失败（${error.code}）：${error.message} 已填内容保留，可直接重试。`);
      }
    } finally {
      setBusy(false);
    }
  }

  async function setArchived(next: boolean) {
    if (!loaded) return;
    setArchiveBusy(true);
    setErrorText(null);
    try {
      const updated = next
        ? await archiveKnowledgePoint(loaded.id, loaded.revision)
        : await restoreKnowledgePoint(loaded.id, loaded.revision);
      setArchiveOpen(false);
      resetFormFrom(updated);
      setNotice(
        next
          ? '已归档：历史引用保留；新关联/教材依据在恢复前不可选。'
          : '已恢复：该知识点可以重新被关联与引用。',
      );
      onPointPatched(updated);
      point.reload();
    } catch (cause) {
      const error = asApiError(cause);
      setArchiveOpen(false);
      if (error.status === 409) {
        setConflict({
          revision: error.details?.currentRevision ?? null,
          message: error.message,
        });
        point.reload();
      } else {
        setErrorText(`${next ? '归档' : '恢复'}失败（${error.code}）：${error.message}`);
      }
    } finally {
      setArchiveBusy(false);
    }
  }

  /**
   * 彻底删除：二次确认后按当前 `revision` 提交（乐观锁）。
   * - 成功 → 通知父级刷新列表并取消选中；父级未接管时本地切到「已删除」态；
   * - 409 `KNOWLEDGE_POINT_IN_USE` → 逐项渲染引用计数（有 counts 时）与「改为归档」出口；
   * - 409 `REVISION_CONFLICT` → 与保存冲突同一套处理：刷新取最新值，不静默重试；
   * - 其他失败 → 保留页面原状并给出错误码与可重试说明。
   */
  async function remove() {
    if (!loaded) return;
    setDeleteBusy(true);
    setErrorText(null);
    setDeleteBlock(null);
    try {
      await deleteKnowledgePoint(loaded.id, loaded.revision);
      setDeleteOpen(false);
      setDeleted(true);
      setNotice(`已彻底删除知识点「${loaded.name}」（物理删除，不可恢复）。`);
      onDeleted?.(loaded.id);
    } catch (cause) {
      const error = asApiError(cause);
      setDeleteOpen(false);
      if (error.status === 409 && error.code === KNOWLEDGE_POINT_IN_USE_CODE) {
        setDeleteBlock({
          message: error.message,
          counts: parseKnowledgeReferenceCounts(error.details),
        });
      } else if (error.status === 409) {
        setConflict({
          revision: error.details?.currentRevision ?? null,
          message: error.message,
        });
        point.reload();
      } else {
        setErrorText(
          `彻底删除失败（${error.code}）：${error.message} 没有删除任何数据，可重试或改用归档。`,
        );
      }
    } finally {
      setDeleteBusy(false);
    }
  }

  if (!loaded) {
    // 首次读取：加载中显示骨架；失败显示错误与重试（绝不显示空态）
    if (pointError) {
      return (
        <section className="kp-detail">
          <div className="space-banner error" role="alert">
            <div className="space-banner-row">
              <span>
                知识点详情读取失败（{pointError.code}）：{pointError.message}
              </span>
              <button className="space-button" onClick={point.reload}>
                <RefreshCw size={13} aria-hidden />
                重试
              </button>
            </div>
          </div>
        </section>
      );
    }
    return (
      <section className="kp-detail" aria-busy="true" aria-label="正在读取知识点详情">
        <div className="space-skeleton" style={{ height: 96 }} aria-hidden />
        <div className="space-skeleton" style={{ height: 220 }} aria-hidden />
      </section>
    );
  }

  if (deleted) {
    return (
      <section className="kp-detail" data-testid="kp-deleted">
        <div className="space-banner info" role="status">
          <strong>该知识点已彻底删除</strong>
          <span>
            物理删除已完成、不可恢复；相关教材依据与别名随之删除。列表与选中状态已刷新，
            请从左侧选择其他知识点。
          </span>
        </div>
      </section>
    );
  }

  if (!form || !plan) {
    return (
      <section className="kp-detail" aria-busy="true" aria-label="正在准备知识点表单">
        <div className="space-skeleton" style={{ height: 96 }} aria-hidden />
      </section>
    );
  }

  const aliasList = splitAliases(form.aliasesText);
  const aliasesDiffer =
    !clear.aliases &&
    aliasList.length > 0 &&
    aliasList.join('\u0000') !== loaded.aliases.join('\u0000');

  return (
    <section className="kp-detail" aria-label="知识点详情">
      <header className="kp-detail-head">
        <div>
          <h2>{loaded.name}</h2>
          <div className="space-meta-row">
            <span className="space-chip blue">{loaded.code}</span>
            <span className="space-chip">学科 {loaded.subjectId}</span>
            <span
              className={loaded.status === 'archived' ? 'space-chip amber' : 'space-chip green'}
            >
              {knowledgeStatusLabel(loaded.status)}
            </span>
            <span className="space-chip">版本 v{loaded.version}</span>
            <span className="space-chip">编辑锁 r{loaded.revision}</span>
            {loaded.revisionId && (
              <span className="space-chip" data-testid="kp-revision-id">
                修订 {loaded.revisionId}
              </span>
            )}
            {loaded.parentCode && <span className="space-chip">父级 {loaded.parentCode}</span>}
          </div>
        </div>
        <div className="kp-detail-actions">
          <button className="space-button" disabled={archiveBusy} onClick={point.reload}>
            <RefreshCw size={13} aria-hidden />
            重新读取
          </button>
          {loaded.status === 'active' ? (
            <button
              className="space-button danger"
              disabled={archiveBusy}
              onClick={() => setArchiveOpen(true)}
            >
              <Archive size={13} aria-hidden />
              归档
            </button>
          ) : (
            <button
              className="space-button"
              disabled={archiveBusy}
              onClick={() => void setArchived(false)}
            >
              <RotateCcw size={13} aria-hidden />
              恢复
            </button>
          )}
          <button
            className="space-button danger"
            disabled={archiveBusy || deleteBusy}
            data-testid="kp-delete-open"
            onClick={() => {
              setDeleteBlock(null);
              setDeleteOpen(true);
            }}
          >
            <Trash2 size={13} aria-hidden />
            彻底删除
          </button>
        </div>
      </header>

      {refreshing && (
        <p className="kp-hint" role="status" data-testid="kp-refreshing">
          正在重新读取服务端最新值…（表单内容会保留）
        </p>
      )}

      {pointError && (
        <div className="space-banner error" role="alert" data-testid="kp-refresh-failed">
          <div className="space-banner-row">
            <span>
              重新读取失败（{pointError.code}）：{pointError.message}
              页面仍显示上一次成功读取的数据，你的输入未被清空。
            </span>
            <button className="space-button" onClick={point.reload}>
              <RefreshCw size={13} aria-hidden />
              重试
            </button>
          </div>
        </div>
      )}

      {notice && (
        <p className="space-banner info" role="status" data-testid="kp-detail-notice">
          {notice}
        </p>
      )}

      {conflict && (
        <div className="space-banner error" role="alert" data-testid="kp-conflict">
          <strong>当前版本 {conflict.revision ?? '未知'}，已刷新为最新，请重试。</strong>
          <span>{conflict.message}</span>
          <span>
            服务端最新：名称「{loaded.name}」、说明「{loaded.description || '（空）'}」、别名
            {loaded.aliases.length > 0 ? `「${loaded.aliases.join('、')}」` : '（无）'}（版本 v
            {loaded.version}，编辑锁 r{loaded.revision}）。你的输入不会被覆盖。
          </span>
          <div className="kp-actions">
            <button className="space-button" onClick={() => resetFormFrom(loaded)}>
              用服务端最新值覆盖表单
            </button>
            <button className="space-button" disabled={busy} onClick={() => void save()}>
              保留我的修改并重试
            </button>
          </div>
        </div>
      )}

      {errorText && (
        <p className="space-banner error" role="alert">
          {errorText}
        </p>
      )}

      {deleteBlock && (
        <div className="space-banner error" role="alert" data-testid="kp-delete-blocked">
          <strong>不能彻底删除：「{loaded.name}」仍在使用中</strong>
          <span>{deleteBlock.message}</span>
          {deleteBlock.counts ? (
            <ul className="kp-issue-list" data-testid="kp-delete-counts">
              {deleteBlock.counts.map((item) => (
                <li key={`${item.library}-${item.key}`}>{referenceCountLabel(item)}</li>
              ))}
            </ul>
          ) : (
            <span>
              服务端没有给出逐项引用计数（可能是子节点或其他引用）：原因以上述说明为准，
              不在此处编造计数。
            </span>
          )}
          <span>
            先解除上述引用（在原卷 / 题库 / 教材依据里移除该知识点的关联）后再来删除；
            只想把它从在用列表里收起来时用「归档」——归档保留历史引用且可恢复。
          </span>
          <div className="kp-actions">
            <button
              className="space-button danger"
              disabled={archiveBusy}
              data-testid="kp-delete-to-archive"
              onClick={() => setArchiveOpen(true)}
            >
              <Archive size={13} aria-hidden />
              改为归档
            </button>
            <button
              className="space-button"
              onClick={() => {
                setDeleteBlock(null);
                point.reload();
              }}
            >
              重新读取最新状态
            </button>
          </div>
        </div>
      )}

      {issues.length > 0 && (
        <ul className="kp-issue-list">
          {issues.map((issue, index) => (
            <li key={`${issue.code}-${index}`}>
              {(issue.row ? `第 ${issue.row} 行 · ` : '') +
                (issue.field ? `字段 ${issue.field}：` : '')}
              {issue.code}：{issue.message}
            </li>
          ))}
        </ul>
      )}

      <div className="kp-form">
        <label className="kp-field">
          <span className="kp-field-label">名称（改名会追加内容修订）</span>
          <input
            value={form.name}
            aria-label="名称"
            disabled={busy}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </label>

        <label className="kp-field">
          <span className="kp-field-label">说明</span>
          <textarea
            value={form.description}
            aria-label="说明"
            rows={3}
            disabled={busy || clear.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
          />
        </label>
        <label className="space-toggle">
          <input
            type="checkbox"
            checked={clear.description}
            disabled={busy}
            aria-label="清空说明"
            onChange={(event) => setClear({ ...clear, description: event.target.checked })}
          />
          清空说明（提交后为空；留空不勾选 = 不修改）
        </label>

        <div className="kp-form-row">
          <label className="kp-field">
            <span className="kp-field-label">父级知识点</span>
            <select
              className="space-select"
              value={form.parentId}
              aria-label="父级知识点"
              disabled={busy}
              onChange={(event) => setForm({ ...form, parentId: event.target.value })}
            >
              <option value={PARENT_UNCHANGED}>
                不修改（当前：{loaded.parentCode ?? (loaded.parentId ? loaded.parentId : '无父级')}
                ）
              </option>
              <option value={PARENT_CLEAR}>清空父级</option>
              {parents.map((parent) => (
                <option key={parent.id} value={parent.id}>
                  {parent.code} · {parent.name}
                </option>
              ))}
            </select>
          </label>
          <label className="kp-field kp-field-narrow">
            <span className="kp-field-label">排序（留空不修改）</span>
            <input
              type="number"
              min={0}
              value={form.sortOrder}
              aria-label="排序"
              disabled={busy}
              onChange={(event) => setForm({ ...form, sortOrder: event.target.value })}
            />
          </label>
        </div>

        <label className="kp-field">
          <span className="kp-field-label">别名（用「、」「,」「;」或换行分隔）</span>
          <textarea
            value={form.aliasesText}
            aria-label="别名"
            rows={2}
            disabled={busy || clear.aliases}
            onChange={(event) => setForm({ ...form, aliasesText: event.target.value })}
          />
        </label>
        <label className="space-toggle">
          <input
            type="checkbox"
            checked={clear.aliases}
            disabled={busy}
            aria-label="清空全部别名"
            onChange={(event) => setClear({ ...clear, aliases: event.target.checked })}
          />
          清空全部别名（留空不勾选 = 不修改）
        </label>

        {aliasList.length > 0 && !clear.aliases && (
          <div className="kp-alias-row" aria-label="别名（可逐条移除）">
            {aliasList.map((alias) => (
              <span key={alias} className="space-chip">
                {alias}
                <button
                  className="kp-alias-remove"
                  aria-label={`移除别名 ${alias}`}
                  disabled={busy}
                  onClick={() =>
                    setForm({
                      ...form,
                      aliasesText: aliasList.filter((item) => item !== alias).join('、'),
                    })
                  }
                >
                  <X size={11} aria-hidden />
                </button>
              </span>
            ))}
          </div>
        )}
        {aliasesDiffer && (
          <p className="kp-hint">
            别名将改为：{aliasList.join('、')}（服务端会校验重复与数量上限 32）。
          </p>
        )}

        <div className="kp-plan">
          <span className="kp-field-label">本次提交</span>
          {plan.actions.length === 0 ? (
            <span className="kp-hint">没有可提交的修改：留空的字段表示不修改。</span>
          ) : (
            <ul>
              {plan.actions.map((action) => (
                <li key={action}>{action}</li>
              ))}
            </ul>
          )}
          {plan.errors.map((error) => (
            <p key={error} className="kp-error-text">
              {error}
            </p>
          ))}
          {plan.hints.map((hint) => (
            <p key={hint} className="kp-hint">
              {hint}
            </p>
          ))}
        </div>

        <div className="kp-actions">
          <button
            className="space-button primary"
            disabled={busy || plan.errors.length > 0 || plan.request === null}
            onClick={() => void save()}
          >
            <Save size={14} aria-hidden />
            {busy ? '保存中…' : '保存修改'}
          </button>
          <button className="space-button" disabled={busy} onClick={() => resetFormFrom(loaded)}>
            放弃我的修改
          </button>
        </div>
      </div>

      <TextbookLinksPanel point={loaded} onPointChanged={onPointPatched} />

      {archiveOpen && (
        <Modal title="归档知识点" onClose={() => setArchiveOpen(false)}>
          <p className="kp-hint">
            归档「{loaded.name}
            」后：历史引用与修订保留；该知识点不能再被新的题目关联或新增教材依据，
            需要用「恢复」重新启用。确认归档？
          </p>
          <div className="kp-actions">
            <button
              className="space-button danger"
              disabled={archiveBusy}
              onClick={() => void setArchived(true)}
            >
              {archiveBusy ? '归档中…' : '确认归档'}
            </button>
            <button
              className="space-button"
              disabled={archiveBusy}
              onClick={() => setArchiveOpen(false)}
            >
              取消
            </button>
          </div>
        </Modal>
      )}

      {deleteOpen && (
        <Modal title="彻底删除知识点" onClose={() => setDeleteOpen(false)}>
          <p className="kp-hint">
            将<strong>物理删除</strong>知识点「{loaded.name}」（编码 {loaded.code}
            ）及其修订与别名，<strong>不可恢复</strong>，也不会进入归档。
          </p>
          <p className="kp-hint">
            仍被引用时服务端会拒绝并逐项给出原因（教材依据 / 原卷题目 / 题库正式题 / 题库草稿），
            删除因此不会破坏历史引用。
          </p>
          <div className="kp-actions">
            <button
              className="space-button danger"
              disabled={deleteBusy}
              data-testid="kp-delete-confirm"
              onClick={() => void remove()}
            >
              {deleteBusy ? '删除中…' : '确认彻底删除'}
            </button>
            <button
              className="space-button"
              disabled={deleteBusy}
              onClick={() => setDeleteOpen(false)}
            >
              取消
            </button>
          </div>
        </Modal>
      )}
    </section>
  );
}
