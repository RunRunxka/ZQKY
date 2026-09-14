'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Bookmark,
  BookmarkCheck,
  CheckCheck,
  CircleCheck,
  CircleDashed,
  FolderInput,
  FolderOutput,
  Layers,
  RefreshCw,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import { useSourceSessionLink } from './useSourceSessionLink';
import { SpaceMain } from './SpaceMain';
import {
  addQuizCategory,
  listQuizBank,
  listQuizCategories,
  loadDemoQuizEntries,
  removeQuizCategory,
  removeQuizEntries,
  renameQuizCategory,
  updateQuizEntry,
  type QuizBankEntry,
  type QuizCategory,
} from '@/services/space-store';

/** 范围（对照参考 BankScope 判别联合，本地形态） */
type BankScope =
  | { kind: 'all' | 'wrong' | 'unresolved' | 'bookmarked' | 'uncategorized' }
  | { kind: 'category'; categoryId: string };

const KIND_LABEL: Record<string, string> = {
  选择题: '选择',
  填空题: '填空',
  概念题: '概念',
  简答题: '简答',
  写作题: '写作',
};

function matchesScope(entry: QuizBankEntry, scope: BankScope): boolean {
  if (scope.kind === 'all') return true;
  if (scope.kind === 'category') return entry.categoryId === scope.categoryId;
  if (scope.kind === 'wrong') return entry.lastAnswer?.correct === false;
  if (scope.kind === 'unresolved') return !entry.resolved;
  if (scope.kind === 'bookmarked') return !!entry.bookmarked;
  return !entry.categoryId; // uncategorized
}


/**
 * 来源会话链接（R-10）：只有条目带可靠 sessionId 且该会话仍存在时才渲染真实深链。
 * 缺 sessionId → 不渲染；会话已删除 → 提示来源不可用并保留原内容（不猜测绑定）。
 * 演示条目（source='demo'）没有真实来源，直接不渲染。
 */
function SourceSessionLink({ entry }: { entry: QuizBankEntry }) {
  // messageId 只用于会话内定位；demo 条目没有真实来源，两者都不传
  const isDemo = entry.source === 'demo';
  const sourceLink = useSourceSessionLink(
    isDemo ? null : entry.sessionId,
    isDemo ? null : entry.messageId,
  );
  if (sourceLink.status === 'ready') {
    return (
      <Link className="space-button" href={sourceLink.href}>
        查看出处会话
      </Link>
    );
  }
  if (sourceLink.status === 'unavailable') {
    return <span className="space-chip">来源会话已不存在</span>;
  }
  return null;
}

export function QuestionBankSection() {
  const [entries, setEntries] = useState<QuizBankEntry[]>([]);
  const [categories, setCategories] = useState<QuizCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [scope, setScope] = useState<BankScope>({ kind: 'all' });
  const [queryInput, setQueryInput] = useState('');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<'recent' | 'oldest'>('recent');
  const [selection, setSelection] = useState<ReadonlySet<string>>(() => new Set());
  const [busyIds, setBusyIds] = useState<ReadonlySet<string>>(() => new Set());
  const [managerOpen, setManagerOpen] = useState(false);
  const [newCategory, setNewCategory] = useState('');
  const [batchCategoryId, setBatchCategoryId] = useState('');

  // 参考实现 250ms 防抖搜索
  useEffect(() => {
    const timer = setTimeout(() => setQuery(queryInput.trim()), 250);
    return () => clearTimeout(timer);
  }, [queryInput]);

  const load = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true);
    setError(null);
    try {
      setEntries(listQuizBank());
      setCategories(listQuizCategories());
    } catch {
      setError('题库数据无法读取（本地存储异常），原数据未修改。');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function withPending(id: string, run: () => void) {
    setBusyIds((prev) => new Set(prev).add(id));
    try {
      run();
    } finally {
      setBusyIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  function toggleBookmark(id: string) {
    const entry = entries.find((e) => e.id === id);
    if (!entry) return;
    withPending(id, () => updateQuizEntry(id, { bookmarked: !entry.bookmarked }));
    void load(true);
  }

  function toggleResolved(id: string) {
    const entry = entries.find((e) => e.id === id);
    if (!entry) return;
    withPending(id, () => updateQuizEntry(id, { resolved: !entry.resolved }));
    void load(true);
  }

  function fileInto(categoryId: string | null, ids: string[]) {
    if (ids.length === 0) return;
    withPending(ids[0]!, () => {
      for (const id of ids) updateQuizEntry(id, { categoryId });
    });
    setSelection(new Set());
    void load(true);
  }

  async function handleDelete(ids: string[]) {
    const label = ids.length === 1 ? '这道题' : `这 ${ids.length} 道题`;
    if (!window.confirm(`从题库删除${label}？删除后无法恢复。`)) return;
    removeQuizEntries(ids);
    setSelection(new Set());
    await load(true);
  }

  function handleLoadDemo() {
    const { added, skipped } = loadDemoQuizEntries();
    setNotice(
      added > 0
        ? `已载入 ${added} 道演示题目${skipped ? `，${skipped} 道已存在跳过` : ''}。演示题目来自本地样例，不来自真实出题。`
        : '演示题目已全部在库中，未重复添加。',
    );
    void load(true);
  }

  async function handleAddCategory() {
    const name = newCategory.trim();
    if (!name) return;
    const category = addQuizCategory(name);
    if (!category) {
      setError('分类名称为空或已存在。');
      return;
    }
    setError(null);
    setNewCategory('');
    await load(true);
  }

  const stats = useMemo(() => {
    let wrong = 0;
    let unresolved = 0;
    let bookmarked = 0;
    let uncategorized = 0;
    for (const entry of entries) {
      if (entry.lastAnswer?.correct === false) wrong += 1;
      if (!entry.resolved) unresolved += 1;
      if (entry.bookmarked) bookmarked += 1;
      if (!entry.categoryId) uncategorized += 1;
    }
    return { total: entries.length, wrong, unresolved, bookmarked, uncategorized };
  }, [entries]);

  const categoryCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const entry of entries) {
      if (entry.categoryId) counts.set(entry.categoryId, (counts.get(entry.categoryId) ?? 0) + 1);
    }
    return counts;
  }, [entries]);

  const visible = useMemo(() => {
    const q = query.toLowerCase();
    const list = entries.filter((entry) => {
      if (!matchesScope(entry, scope)) return false;
      if (q && !`${entry.question}\n${entry.topic}\n${entry.explanation}`.toLowerCase().includes(q))
        return false;
      return true;
    });
    list.sort((a, b) =>
      sort === 'recent' ? b.savedAt.localeCompare(a.savedAt) : a.savedAt.localeCompare(b.savedAt),
    );
    return list;
  }, [entries, scope, query, sort]);

  const scopeItems: { label: string; count: number; active: boolean; onClick: () => void }[] = [
    { label: '全部', count: stats.total, active: scope.kind === 'all', onClick: () => setScope({ kind: 'all' }) },
    { label: '答错', count: stats.wrong, active: scope.kind === 'wrong', onClick: () => setScope({ kind: 'wrong' }) },
    { label: '未掌握', count: stats.unresolved, active: scope.kind === 'unresolved', onClick: () => setScope({ kind: 'unresolved' }) },
    { label: '书签', count: stats.bookmarked, active: scope.kind === 'bookmarked', onClick: () => setScope({ kind: 'bookmarked' }) },
    { label: '未分类', count: stats.uncategorized, active: scope.kind === 'uncategorized', onClick: () => setScope({ kind: 'uncategorized' }) },
    ...categories.map((category) => ({
      label: category.name,
      count: categoryCounts.get(category.id) ?? 0,
      active: scope.kind === 'category' && scope.categoryId === category.id,
      onClick: () => setScope({ kind: 'category', categoryId: category.id }),
    })),
  ];

  const allVisibleSelected = visible.length > 0 && visible.every((e) => selection.has(e.id));

  return (
    <SpaceMain
      title="题库"
      description="聊天「智能出题」保存的题目与演示样例集中在这里，可标记、归类与回顾。"
      actions={
        <button className="space-button" onClick={() => void load(true)} disabled={loading}>
          <RefreshCw size={14} className={refreshing ? 'space-spin' : ''} />
          刷新
        </button>
      }
    >
      {notice && (
        <div className="space-banner info" role="status">
          <div className="space-banner-row">
            <span>{notice}</span>
            <button className="icon-button" aria-label="关闭提示" onClick={() => setNotice(null)}>
              <X size={14} />
            </button>
          </div>
        </div>
      )}
      {error && (
        <div className="space-banner error" role="alert">
          {error}
        </div>
      )}

      <div className="space-bank-layout">
        <nav className="space-scope-rail" aria-label="题库范围">
          {scopeItems.map((item) => (
            <button
              key={item.label}
              className={`space-scope-item ${item.active ? 'current' : ''}`}
              aria-pressed={item.active}
              onClick={item.onClick}
            >
              <span>{item.label}</span>
              <span className="count">{item.count}</span>
            </button>
          ))}
          <button
            className="space-scope-item"
            aria-expanded={managerOpen}
            onClick={() => setManagerOpen((open) => !open)}
          >
            <Layers size={14} />
            <span>管理分类</span>
          </button>
        </nav>

        <div className="space-bank-main">
          {managerOpen && (
            <section className="space-category-manager" aria-label="分类管理">
              <div className="space-category-row">
                <input
                  value={newCategory}
                  placeholder="新分类名称…"
                  aria-label="新分类名称"
                  onChange={(e) => setNewCategory(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void handleAddCategory();
                  }}
                />
                <button className="space-button primary" onClick={() => void handleAddCategory()}>
                  添加
                </button>
              </div>
              {categories.map((category) => (
                <div className="space-category-row" key={category.id}>
                  <input
                    defaultValue={category.name}
                    aria-label={`重命名分类 ${category.name}`}
                    onBlur={(e) => {
                      const name = e.target.value.trim();
                      if (name && name !== category.name) {
                        if (!renameQuizCategory(category.id, name)) setError('分类名称为空或已存在。');
                        void load(true);
                      }
                    }}
                  />
                  <span className="space-chip">{categoryCounts.get(category.id) ?? 0} 题</span>
                  <button
                    className="icon-button"
                    aria-label={`删除分类 ${category.name}`}
                    onClick={() => {
                      if (window.confirm(`删除分类「${category.name}」？分类内题目回到未分类。`)) {
                        removeQuizCategory(category.id);
                        if (scope.kind === 'category' && scope.categoryId === category.id)
                          setScope({ kind: 'all' });
                        void load(true);
                      }
                    }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
              <p className="space-footnote">删除分类不会删除题目，题目回到未分类。</p>
            </section>
          )}

          <div className="space-toolbar">
            <input
              className="space-search"
              type="search"
              placeholder="搜索题干、主题或解析…"
              aria-label="搜索题库"
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
            />
            <select
              className="space-select"
              aria-label="排序方式"
              value={sort}
              onChange={(e) => setSort(e.target.value === 'oldest' ? 'oldest' : 'recent')}
            >
              <option value="recent">最近保存</option>
              <option value="oldest">最早保存</option>
            </select>
            <button className="space-button" onClick={handleLoadDemo}>
              <Sparkles size={14} />
              载入演示题目
            </button>
          </div>

          {loading ? (
            <div aria-hidden>
              {[0, 1, 2].map((i) => (
                <div className="space-skeleton" key={i} style={{ height: 120 }} />
              ))}
            </div>
          ) : stats.total === 0 ? (
            <div className="space-empty">
              <strong>题库还是空的</strong>
              <span>在聊天中使用「智能出题」并保存题目，或先载入演示题目体验完整功能。</span>
              <button className="space-button primary" onClick={handleLoadDemo}>
                <Sparkles size={14} />
                载入演示题目
              </button>
            </div>
          ) : visible.length === 0 ? (
            <div className="space-empty">
              <strong>当前视图没有题目</strong>
              <span>换个范围或清空搜索词再试。</span>
            </div>
          ) : (
            <>
              {visible.map((entry) => {
                const busy = busyIds.has(entry.id);
                const userAnswer = entry.lastAnswer?.answer;
                const userWrong = entry.lastAnswer?.correct === false;
                const category = categories.find((c) => c.id === entry.categoryId);
                return (
                  <article
                    className={`space-question-card ${busy ? 'busy' : ''}`}
                    key={entry.id}
                    aria-busy={busy}
                  >
                    <div className="space-question-text">{entry.question}</div>
                    <div className="space-meta-row">
                      <span className="space-chip">{KIND_LABEL[entry.questionType] ?? entry.questionType}</span>
                      <span className="space-chip">{entry.difficulty}</span>
                      {entry.source === 'demo' ? (
                        <span className="space-chip amber">演示题目</span>
                      ) : (
                        <span className="space-chip blue">出题产物</span>
                      )}
                      <span className="space-chip">{entry.topic}</span>
                      {category && <span className="space-chip green">{category.name}</span>}
                      {entry.lastAnswer && (
                        <span className={`space-chip ${userWrong ? 'amber' : 'green'}`}>
                          {userWrong ? '上次答错' : '上次答对'}
                        </span>
                      )}
                    </div>
                    {entry.options && (
                      <ul className="space-question-options">
                        {Object.entries(entry.options).map(([key, text]) => (
                          <li
                            key={key}
                            className={`space-option ${key === entry.correctAnswer ? 'correct' : ''} ${
                              userWrong && userAnswer === key ? 'user-wrong' : ''
                            }`}
                          >
                            <span className="key">{key}</span>
                            <span>{text}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                    <details className="space-explanation">
                      <summary>参考答案与解析</summary>
                      <p>
                        <strong>答案：</strong>
                        {entry.options ? `${entry.correctAnswer}. ${entry.options[entry.correctAnswer] ?? ''}` : entry.correctAnswer}
                      </p>
                      <p>{entry.explanation}</p>
                      {entry.lastAnswer && (
                        <p>
                          <strong>你的作答：</strong>
                          {entry.lastAnswer.answer || '（跳过）'}
                        </p>
                      )}
                    </details>
                    <div className="space-question-actions">
                      <button
                        className="space-button"
                        aria-pressed={!!entry.bookmarked}
                        onClick={() => toggleBookmark(entry.id)}
                      >
                        {entry.bookmarked ? <BookmarkCheck size={14} /> : <Bookmark size={14} />}
                        {entry.bookmarked ? '已收藏' : '收藏'}
                      </button>
                      <button
                        className="space-button"
                        aria-pressed={!!entry.resolved}
                        onClick={() => toggleResolved(entry.id)}
                      >
                        {entry.resolved ? <CircleCheck size={14} /> : <CircleDashed size={14} />}
                        {entry.resolved ? '已掌握' : '标记掌握'}
                      </button>
                      <select
                        className="space-select"
                        aria-label="移动到分类"
                        value={entry.categoryId ?? ''}
                        onChange={(e) => fileInto(e.target.value || null, [entry.id])}
                      >
                        <option value="">未分类</option>
                        {categories.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                      <SourceSessionLink entry={entry} />
                      <button
                        className="space-button danger"
                        onClick={() => void handleDelete([entry.id])}
                      >
                        <Trash2 size={14} />
                        删除
                      </button>
                    </div>
                  </article>
                );
              })}
              <p className="space-footnote">
                共 {stats.total} 题，当前视图 {visible.length} 题。
              </p>
            </>
          )}

          {visible.length > 0 && (
            <div className="space-selection-bar">
              <button
                className="space-button"
                onClick={() =>
                  setSelection(allVisibleSelected ? new Set() : new Set(visible.map((e) => e.id)))
                }
              >
                {allVisibleSelected ? '取消全选' : '全选当前视图'}
              </button>
              {selection.size > 0 && (
                <>
                  <span>
                    已选 {selection.size} 题
                  </span>
                  <button
                    className="space-button"
                    onClick={() => {
                      for (const id of selection) updateQuizEntry(id, { resolved: true });
                      setSelection(new Set());
                      void load(true);
                    }}
                  >
                    <CheckCheck size={14} />
                    批量标为已掌握
                  </button>
                  <span className="space-toggle">
                    <FolderInput size={14} />
                    <select
                      className="space-select"
                      aria-label="批量归类"
                      value={batchCategoryId}
                      onChange={(e) => {
                        setBatchCategoryId('');
                        const value = e.target.value;
                        fileInto(value === '' || value === '__none__' ? null : value, [...selection]);
                      }}
                    >
                      <option value="">批量归类到…</option>
                      <option value="__none__">未分类</option>
                      {categories.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </span>
                  <button className="space-button" onClick={() => fileInto(null, [...selection])}>
                    <FolderOutput size={14} />
                    移出分类
                  </button>
                  <button className="space-button danger" onClick={() => void handleDelete([...selection])}>
                    <Trash2 size={14} />
                    删除所选
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </SpaceMain>
  );
}
