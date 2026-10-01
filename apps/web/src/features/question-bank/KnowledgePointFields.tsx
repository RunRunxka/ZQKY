'use client';

/**
 * 知识点选择控件（TEACHING-LOOP B3 · F10-QB）。
 *
 * 数据来自知识点库只读接口 `GET /api/v1/knowledge-points`（经 `@/services/knowledge-points-api`，
 * 不复制第二份客户端）：默认只列**在用**知识点（归档不能建立新关联；后端会 422，
 * 前端不提供该选项）。三态严格区分：读取失败显示错误码与重试入口，**不当空目录**；
 * 真正没有知识点时才显示空态。学科变化即重新读取（旧学科的选中项由调用方清理）。
 */

import { useState } from 'react';
import { RefreshCw, Search } from 'lucide-react';
import { listKnowledgePoints } from '@/services/knowledge-points-api';
import { useAsyncResource, type AsyncState } from './hooks';

/** 选择项：id/编码/名称 + 建立关联要用的当前修订与学科快照。 */
export interface KnowledgePointOption {
  id: string;
  code: string;
  name: string;
  subjectId: string;
  /** 当前固定内容修订；知识点异常缺修订时为 null（界面显示「修订未提供」，不猜造）。 */
  revisionId: string | null;
}

interface OptionsState {
  state: AsyncState<KnowledgePointOption[]>;
  reload: () => void;
}

/**
 * 知识点选项（在用；按学科 + 关键词）。`subjectId` 为空时列全部学科（后端支持，界面提示更精确）。
 * 读取失败原样暴露（调用方展示错误与重试），不返回空数组冒充。
 */
export function useKnowledgePointOptions(subjectId: string, query: string): OptionsState {
  const resource = useAsyncResource(async (signal) => {
    const list = await listKnowledgePoints(
      {
        subjectId: subjectId || undefined,
        status: 'active',
        q: query || undefined,
        limit: 200,
      },
      signal,
    );
    return list.items.map((item) => ({
      id: item.id,
      code: item.code,
      name: item.name,
      subjectId: item.subjectId,
      revisionId: item.revisionId,
    }));
  }, `qb-points|${subjectId}|${query}`);
  return { state: resource.state, reload: resource.reload };
}

function OptionNotice({
  state,
  onRetry,
}: {
  state: AsyncState<KnowledgePointOption[]>;
  onRetry: () => void;
}) {
  if (state.phase === 'loading') {
    return (
      <p className="qb-hint" role="status" data-testid="qb-knowledge-points-loading">
        正在读取知识点…
      </p>
    );
  }
  if (state.phase === 'failed') {
    return (
      <p className="space-banner error" role="status" data-testid="qb-knowledge-points-error">
        知识点读取失败（{state.error.code}）：{state.error.message} 知识点筛选与关联暂时不可用。
        <button className="space-button" type="button" onClick={onRetry}>
          <RefreshCw size={14} aria-hidden />
          重试读取知识点
        </button>
      </p>
    );
  }
  if (state.data.length === 0) {
    return (
      <p className="qb-hint" role="status" data-testid="qb-knowledge-points-empty">
        没有可用的在用知识点：请先到「知识点」页面创建并确认知识点。
      </p>
    );
  }
  return null;
}

export interface KnowledgePointSelectProps {
  id: string;
  /** 表单当前学科；空串 = 全部学科（列表可能很长，界面给出说明）。 */
  subjectId: string;
  value: string;
  /** 选中项（含当前修订与学科快照）；清空选择时为 null。 */
  onChange: (next: string, option: KnowledgePointOption | null) => void;
  disabled?: boolean;
  /** 筛选场景：额外提供「全部」选项。 */
  includeAll?: boolean;
  allLabel?: string;
  testId?: string;
}

/** 单选下拉：筛选与「添加一条关联」共用同一控件。 */
export function KnowledgePointSelect({
  id,
  subjectId,
  value,
  onChange,
  disabled = false,
  includeAll = false,
  allLabel = '全部知识点',
  testId,
}: KnowledgePointSelectProps) {
  const { state, reload } = useKnowledgePointOptions(subjectId, '');
  const ready = state.phase === 'ready' && state.data.length > 0;
  return (
    <div className="qb-point-select" data-testid={testId}>
      <label className="qb-field" htmlFor={id}>
        知识点
        <select
          id={id}
          className="space-select"
          value={value}
          disabled={disabled || !ready}
          onChange={(event) => {
            const next = event.target.value;
            const option =
              state.phase === 'ready' ? state.data.find((item) => item.id === next) ?? null : null;
            onChange(next, option);
          }}
        >
          {includeAll && <option value="">{allLabel}</option>}
          {!includeAll && <option value="">请选择知识点</option>}
          {state.phase === 'ready' &&
            state.data.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}（{item.code}）
              </option>
            ))}
        </select>
      </label>
      {!subjectId && state.phase === 'ready' && state.data.length > 0 && (
        <p className="qb-hint">未选学科：列出全部在用知识点，可用学科缩小范围。</p>
      )}
      {state.phase !== 'ready' && <OptionNotice state={state} onRetry={reload} />}
    </div>
  );
}

export interface KnowledgePointChecklistProps {
  idPrefix: string;
  subjectId: string;
  selected: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
}

/** 多选清单（补题用）：带关键词搜索；读取失败必须能重试，不把失败当空目录。 */
export function KnowledgePointChecklist({
  idPrefix,
  subjectId,
  selected,
  onChange,
  disabled = false,
}: KnowledgePointChecklistProps) {
  const [draftQuery, setDraftQuery] = useState('');
  const [appliedQuery, setAppliedQuery] = useState('');
  const { state, reload } = useKnowledgePointOptions(subjectId, appliedQuery);

  function toggle(id: string, checked: boolean) {
    onChange(
      checked ? [...selected.filter((item) => item !== id), id] : selected.filter((item) => item !== id),
    );
  }

  return (
    <div className="qb-point-checklist" data-testid={`${idPrefix}-point-checklist`}>
      <form
        className="qb-point-search"
        onSubmit={(event) => {
          event.preventDefault();
          setAppliedQuery(draftQuery.trim());
        }}
      >
        <label className="qb-field qb-filter-keyword" htmlFor={`${idPrefix}-point-q`}>
          搜索知识点
          <input
            id={`${idPrefix}-point-q`}
            value={draftQuery}
            placeholder="名称或编码"
            disabled={disabled}
            onChange={(event) => setDraftQuery(event.target.value)}
          />
        </label>
        <button className="space-button" type="submit" disabled={disabled}>
          <Search size={14} aria-hidden />
          搜索
        </button>
      </form>

      <OptionNotice state={state} onRetry={reload} />

      {state.phase === 'ready' && state.data.length > 0 && (
        <ul className="qb-point-list">
          {state.data.map((item) => (
            <li key={item.id}>
              <label className="qb-check">
                <input
                  type="checkbox"
                  checked={selected.includes(item.id)}
                  disabled={disabled}
                  onChange={(event) => toggle(item.id, event.target.checked)}
                />
                {item.name}（{item.code}）
              </label>
            </li>
          ))}
        </ul>
      )}
      {state.phase === 'ready' && appliedQuery && state.data.length === 0 && (
        <p className="qb-hint" role="status">
          没有匹配「{appliedQuery}」的在用知识点。
        </p>
      )}

      {selected.length > 0 && (
        <div className="space-meta-row" data-testid={`${idPrefix}-point-selected`}>
          {selected.map((id) => (
            <span key={id} className="space-chip blue">
              {state.phase === 'ready'
                ? (state.data.find((item) => item.id === id)?.name ?? id)
                : id}
            </span>
          ))}
          <button
            className="space-button"
            type="button"
            disabled={disabled}
            onClick={() => onChange([])}
          >
            清空选择
          </button>
        </div>
      )}
    </div>
  );
}
