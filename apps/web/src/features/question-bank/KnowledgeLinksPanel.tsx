'use client';

/**
 * 知识点关联区块（TEACHING-LOOP B3 · F10-QB）。
 *
 * 两种呈现必须**分开、不合并、不丢弃**：
 * 1. 正式关联（`knowledgeLinks`：知识点身份 + 修订 + 名称/学科快照；草稿关联还有来源）；
 * 2. 历史知识点标签（旧字段 `metadata.knowledgeTags`：纯文本标签，不参与正式关联与筛选）。
 *
 * 编辑语义（与后端一致）：
 * - 只有用户显式改动过（`touched`）才在 PATCH 里发送 `knowledgeLinks` 整表替换（空数组 = 清空）；
 * - 未改动且学科未变时缺省不发送 → 服务端复制旧关联；界面必须说明，不制造「已重写」的错觉；
 * - 学科变化且有冲突旧关联时，界面先说明「服务端会 422 要求显式替换/清空」，并把
 *   服务端返回的字段级错误（`knowledgeLinks[i]` 或消息中的知识点 id）显示到对应行。
 */

import {
  KNOWLEDGE_LINKS_MISSING_NOTICE,
  KNOWLEDGE_LINKS_SKIPPED_NOTICE,
  linkSourceLabel,
  roleLabel,
  subjectChangeNotice,
  type KnowledgeLinkRole,
  type KnowledgeLinkSource,
  type KnowledgeLinkView,
  type KnowledgeLinksRead,
  type LinkIssueLocation,
  type SubjectChangeState,
} from './knowledge-links';
import { KnowledgePointSelect } from './KnowledgePointFields';
import { LEGACY_TAGS_HINT, LEGACY_TAGS_TITLE } from './labels';

export { LEGACY_TAGS_HINT, LEGACY_TAGS_TITLE };

export function LegacyTagsBlock({ tags, testId = 'qb-legacy-tags' }: { tags: string[]; testId?: string }) {
  return (
    <div
      className="qb-legacy-tags"
      data-testid={testId}
      aria-label={LEGACY_TAGS_TITLE}
    >
      <h3 className="qb-links-subtitle">{LEGACY_TAGS_TITLE}</h3>
      <p className="qb-hint">{LEGACY_TAGS_HINT}</p>
      {tags.length > 0 ? (
        <div className="space-meta-row">
          {tags.map((tag, index) => (
            <span key={`${tag}-${index}`} className="space-chip qb-legacy-tag">
              {tag}
            </span>
          ))}
        </div>
      ) : (
        <p className="qb-hint">该内容没有历史标签。</p>
      )}
    </div>
  );
}

export interface KnowledgeLinksPanelProps {
  read: KnowledgeLinksRead;
  /** 编辑中的关联列表（未编辑时 = 服务端关联）。 */
  links: KnowledgeLinkView[];
  /** 用户是否显式改动过（决定 PATCH 是否发送整表替换）。 */
  touched: boolean;
  /** 可编辑（详情/草稿编辑态）。 */
  editable: boolean;
  disabled?: boolean;
  /** 表单当前学科（编辑态）。 */
  subjectId: string;
  /** 服务端原学科。 */
  originalSubjectId: string;
  /** 新学科冲突检测结果（由 `subjectChangeState` 计算，保证展示与请求语义一致）。 */
  subjectChange: SubjectChangeState;
  issues: LinkIssueLocation;
  legacyTags: string[];
  idPrefix: string;
  /** 新增关联的来源标注：草稿为 `human`，正式题修订关联没有来源字段（不传）。 */
  newLinkSource?: KnowledgeLinkSource;
  onAdd?: (link: KnowledgeLinkView) => void;
  onRemove?: (index: number) => void;
  onRoleChange?: (index: number, role: KnowledgeLinkRole) => void;
  onClear?: () => void;
  onReset?: () => void;
  legacyTestId?: string;
}

export function KnowledgeLinksPanel({
  read,
  links,
  touched,
  editable,
  disabled = false,
  subjectId,
  originalSubjectId,
  subjectChange,
  issues,
  legacyTags,
  idPrefix,
  newLinkSource,
  onAdd,
  onRemove,
  onRoleChange,
  onClear,
  onReset,
  legacyTestId,
}: KnowledgeLinksPanelProps) {
  const notice = subjectChangeNotice(subjectChange, touched);
  const canEdit = editable && !!onAdd && !!onRemove && !!onRoleChange && !!onClear;
  return (
    <section className="qb-links" aria-label="知识点关联" data-testid="qb-knowledge-links">
      <header className="qb-source-head">
        <h2>知识点关联</h2>
        <span className="space-chip" data-testid="qb-knowledge-link-count">
          {links.length} 条
        </span>
        {touched && (
          <span className="space-chip blue" data-testid="qb-knowledge-links-touched">
            已改动，保存时整表替换
          </span>
        )}
      </header>

      {read.status === 'missing' && (
        <p className="space-banner info" role="status" data-testid="qb-knowledge-links-missing">
          {KNOWLEDGE_LINKS_MISSING_NOTICE}
        </p>
      )}
      {read.status === 'provided' && read.skipped > 0 && (
        <p className="space-banner info" role="status" data-testid="qb-knowledge-links-skipped">
          {KNOWLEDGE_LINKS_SKIPPED_NOTICE(read.skipped)}
        </p>
      )}

      {links.length === 0 ? (
        <p className="qb-hint" role="status" data-testid="qb-knowledge-links-empty">
          {read.status === 'provided' ? '目前没有正式知识点关联。' : '未读取到正式知识点关联。'}
        </p>
      ) : (
        <ul className="qb-link-list">
          {links.map((link, index) => (
            <li
              key={`${link.knowledgePointId}-${index}`}
              className="qb-link-row"
              data-testid={`qb-knowledge-link-${index}`}
            >
              <div className="space-meta-row">
                <span className="space-chip blue">{link.knowledgeNameSnapshot || '（名称未提供）'}</span>
                <span className="space-chip">{roleLabel(link.role)}</span>
                <span className="space-chip">{linkSourceLabel(link.source)}</span>
                <span className="qb-block-locator">{link.knowledgePointId}</span>
              </div>
              <p className="qb-hint">
                学科快照：{link.subjectIdSnapshot || '未提供'} · 修订：{link.knowledgeRevisionId}
              </p>
              {issues.byIndex.has(index) && (
                <p
                  className="qb-warn-text"
                  role="alert"
                  data-testid={`qb-knowledge-link-issue-${index}`}
                >
                  {issues.byIndex.get(index)}
                </p>
              )}
              {canEdit && (
                <div className="qb-actions">
                  <label className="qb-field" htmlFor={`${idPrefix}-role-${index}`}>
                    角色
                    <select
                      id={`${idPrefix}-role-${index}`}
                      className="space-select"
                      value={link.role}
                      disabled={disabled}
                      onChange={(event) =>
                        onRoleChange?.(index, event.target.value as KnowledgeLinkRole)
                      }
                    >
                      <option value="primary">主知识点</option>
                      <option value="secondary">次要知识点</option>
                    </select>
                  </label>
                  <button
                    className="space-button"
                    type="button"
                    disabled={disabled}
                    data-testid={`qb-knowledge-link-remove-${index}`}
                    onClick={() => onRemove?.(index)}
                  >
                    移除关联
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {issues.general.length > 0 && (
        <ul
          className="qb-failure-list"
          role="alert"
          data-testid="qb-knowledge-links-general-issues"
        >
          {issues.general.map((item, index) => (
            <li key={`${item}-${index}`}>{item}</li>
          ))}
        </ul>
      )}

      {notice && (
        <p
          className={subjectChange.blocked ? 'space-banner error' : 'space-banner info'}
          role={subjectChange.blocked ? 'alert' : 'status'}
          data-testid="qb-knowledge-subject-change"
        >
          {notice}
        </p>
      )}

      {canEdit && !touched && !subjectChange.blocked && (
        <p className="qb-hint" role="status" data-testid="qb-knowledge-links-untouched">
          未改动知识点关联：保存时不会发送 knowledgeLinks，服务端会沿用旧正式关联（不改写、不清空）。
        </p>
      )}

      {canEdit && (
        <AddLinkRow
          idPrefix={idPrefix}
          subjectId={subjectId}
          disabled={disabled}
          existingIds={links.map((link) => link.knowledgePointId)}
          linkSource={newLinkSource}
          onAdd={onAdd}
        />
      )}

      {canEdit && (
        <div className="qb-actions">
          <button
            className="space-button"
            type="button"
            disabled={disabled || links.length === 0}
            data-testid="qb-knowledge-link-clear"
            onClick={onClear}
          >
            清空全部关联
          </button>
          {touched && (
            <button
              className="space-button"
              type="button"
              disabled={disabled}
              data-testid="qb-knowledge-links-reset"
              onClick={onReset}
            >
              恢复为服务端关联
            </button>
          )}
          {subjectChange.blocked && (
            <span className="qb-warn-text" data-testid="qb-knowledge-links-blocked">
              当前有 {subjectChange.conflictIndexes.length} 条旧关联与新学科
              {subjectChange.nextSubjectId || '（空）'}冲突：请显式替换或清空后再保存。
            </span>
          )}
        </div>
      )}

      {originalSubjectId !== subjectId.trim() && (
        <p className="qb-hint" data-testid="qb-knowledge-subject-diff">
          原学科：{originalSubjectId || '未设置'} → 新学科：{subjectId.trim() || '未设置'}
        </p>
      )}

      <LegacyTagsBlock tags={legacyTags} testId={legacyTestId} />
    </section>
  );
}

function AddLinkRow({
  idPrefix,
  subjectId,
  disabled,
  existingIds,
  linkSource,
  onAdd,
}: {
  idPrefix: string;
  subjectId: string;
  disabled: boolean;
  existingIds: string[];
  linkSource?: KnowledgeLinkSource;
  onAdd?: (link: KnowledgeLinkView) => void;
}) {
  return (
    <div className="qb-link-add" data-testid="qb-knowledge-link-add">
      <KnowledgePointSelect
        id={`${idPrefix}-point-add`}
        subjectId={subjectId}
        value=""
        disabled={disabled}
        testId="qb-knowledge-point-select"
        onChange={(pointId, option) => {
          if (!pointId || !option) return;
          if (existingIds.includes(pointId)) return;
          const link: KnowledgeLinkView = {
            knowledgePointId: option.id,
            knowledgeRevisionId: option.revisionId ?? '',
            knowledgeNameSnapshot: option.name,
            subjectIdSnapshot: option.subjectId,
            role: 'primary',
          };
          if (linkSource) link.source = linkSource;
          onAdd?.(link);
        }}
      />
      <p className="qb-hint">
        按当前学科列出在用知识点；归档知识点不能建立新关联（服务端会 422 拒绝）。
      </p>
    </div>
  );
}
