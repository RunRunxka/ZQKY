'use client';

/**
 * `/practices` 练习工作台（R8-FE 2026-10-12，需求 8 收尾模块）。
 *
 * 用户口径的三段式：
 * 1. 新建练习——来源一「学情分析报告」（显示其薄弱知识点，创建后按约束选拔题库固定题）
 *    与来源二「教师描述」（AI 出题进题库，待校对）可在同一屏组合；
 * 2. 生成后微调——题目列表富内容渲染 + 难度徽标，增删/排序/计分结构与约束编辑，
 *    保存草稿（CAS）与「按教师要求再生成」都走归档通道；
 * 3. 确认后才可导出——未审核草稿不能进入导出区；审核修订在「导出预览」按 A4 分页
 *    查看学生卷/教师卷并下载 docx / 成绩模板 xlsx。
 *
 * 数据全部来自 FastAPI（`/api/v1/...`）；读取失败显示原因与重试，不当空目录。
 * 公共壳与滚动容器由 layout 的 `ModuleWorkspaceShell` 统一提供（`practices` 业务根由总控登记，
 * 本卡不改导航与壳文件）；本页不自包 WorkspaceShell。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useEntrance } from '@/components/motion/useEntrance';
import type { PracticeSetView } from '@/contracts/b4';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { useAsyncResource } from '@/features/assessments/hooks';
import { CreatePracticePanel } from './CreatePracticePanel';
import { PracticeEditor } from './PracticeEditor';
import { PracticeExportPanel } from './PracticeExportPanel';
import { ErrorNotice, ReadNotice, nameOrShortId, shortId, stampText } from './ui';
import '@/components/layout/space.css';
import './practices.css';

const LIST_PAGE_SIZE = 20;

const STATE_LABEL: Record<string, string> = { draft: '草稿（未审核）', reviewed: '已审核（冻结）' };

export interface PracticesWorkspaceProps {
  services?: typeof b4Api;
  /** 直达某个练习集（页面从 URL `?practiceSetId=` 读取后传入）。 */
  initialPracticeSetId?: string | null;
}

export function PracticesWorkspace({ services = b4Api, initialPracticeSetId = null }: PracticesWorkspaceProps) {
  const pageRef = useRef<HTMLDivElement>(null);
  useEntrance(pageRef, { preset: 'page' });
  const [selectedId, setSelectedId] = useState<string | null>(initialPracticeSetId);
  const [offset, setOffset] = useState(0);
  const [tab, setTab] = useState<'edit' | 'export'>('edit');
  const [autoSuggest, setAutoSuggest] = useState(false);
  const [createLocked, setCreateLocked] = useState(false);
  const [editorLocked, setEditorLocked] = useState(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  // 从地址栏读一次直达参数（浏览器能力放在客户端生命周期内，SSR 不读 window）。
  useEffect(() => {
    if (initialPracticeSetId) return;
    const params = new URLSearchParams(window.location.search);
    const target = params.get('practiceSetId');
    if (target) setSelectedId(target);
  }, [initialPracticeSetId]);

  const list = useAsyncResource(
    (signal) => services.listPractices({ status: 'active', offset, limit: LIST_PAGE_SIZE }, signal),
    `practices-list|${offset}`,
  );
  const detail = useAsyncResource(
    (signal) => (selectedId ? services.getPractice(selectedId, signal) : Promise.resolve(null)),
    `practice-detail|${selectedId ?? 'none'}`,
  );
  const view: PracticeSetView | null = detail.lastData;
  const hasReviewedRevision = useMemo(
    () => (view ? view.revisions.some((revision) => revision.state === 'reviewed') : false),
    [view],
  );

  const onCreated = useCallback((created: PracticeSetView) => {
    setOffset(0);
    setSelectedId(created.practiceSetId);
    setTab('edit');
    setAutoSuggest(true);
  }, []);
  const reloadRef = useRef({ detail: detail.reload, list: list.reload });
  reloadRef.current = { detail: detail.reload, list: list.reload };
  const onSaved = useCallback((next: PracticeSetView) => {
    setSelectedId(next.practiceSetId);
    reloadRef.current.detail();
    reloadRef.current.list();
  }, []);

  const busy = createLocked || editorLocked;

  return (
    <div ref={pageRef} className="space-page practices-page">
      <header className="space-header" data-motion-reveal>
        <div className="space-header-row">
          <h1>练习</h1>
        </div>
        <p className="space-description">
          由导入学情或教师描述生成对应练习：报告决定目标知识点与排除原题依据，题库按约束选拔已确认题，
          教师描述可用 AI 补题（候选进题库，校对确认后才可选用）。生成后逐题微调，<strong>确认（审核）后才可导出</strong>
          学生卷 / 教师卷 / 成绩模板。
        </p>
      </header>

      <main className="space-content">
        <CreatePracticePanel services={services} onCreated={onCreated} onLocked={setCreateLocked} />

        <div className="practices-layout">
          <aside className="practices-list" aria-label="练习列表">
            <header className="practices-card-head">
              <h2>已有练习</h2>
              <p className="practices-hint">按创建时间倒序（服务端分页）。</p>
            </header>
            <ReadNotice resource={list} label="练习列表" />
            {list.state.phase === 'ready' && list.lastData?.items.length === 0 && (
              <p className="practices-hint" data-testid="practices-list-empty">
                还没有练习：用上面的「新建练习」创建第一份。
              </p>
            )}
            <ul className="practices-list-items">
              {(list.lastData?.items ?? []).map((item) => (
                <li key={item.practiceSetId}>
                  <button
                    type="button"
                    className={item.practiceSetId === selectedId ? 'current' : ''}
                    data-testid={`practices-list-item-${item.practiceSetId}`}
                    aria-current={item.practiceSetId === selectedId}
                    onClick={() => {
                      setSelectedId(item.practiceSetId);
                      setTab('edit');
                      setAutoSuggest(false);
                    }}
                  >
                    <strong>{item.title}</strong>
                    <span className="practices-meta">
                      {nameOrShortId(item.sourcePaperTitle, item.analysisRunId)} · {stampText(item.sourceCreatedAt ?? null)} ·{' '}
                      {STATE_LABEL[item.currentRevision.state] ?? item.currentRevision.state} · r{item.revision}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            {list.lastData && list.lastData.total > LIST_PAGE_SIZE && (
              <div className="practices-actions" aria-label="练习列表分页">
                <button className="space-button" disabled={offset === 0} onClick={() => setOffset((value) => Math.max(0, value - LIST_PAGE_SIZE))}>
                  上一页
                </button>
                <span className="practices-meta">
                  第 {Math.floor(offset / LIST_PAGE_SIZE) + 1} 页 / 共 {list.lastData.total} 条
                </span>
                <button
                  className="space-button"
                  disabled={offset + LIST_PAGE_SIZE >= list.lastData.total}
                  onClick={() => setOffset((value) => value + LIST_PAGE_SIZE)}
                >
                  下一页
                </button>
              </div>
            )}
          </aside>

          <section className="practices-detail" aria-label="当前练习">
            {!selectedId && (
              <p className="practices-hint" data-testid="practices-detail-empty">
                从左侧选择一份练习查看编辑与导出；新建后会自动打开新练习。
              </p>
            )}
            {selectedId && (
              <>
                <ReadNotice resource={detail} label="练习详情" />
                {detail.state.phase === 'failed' && (
                  <p className="practices-hint">读取失败不会切换为空练习：原选择保留，可重试读取。</p>
                )}
                {view && (
                  <>
                    <header className="practices-detail-head">
                      <div>
                        <h2>{view.title}</h2>
                        <p className="practices-meta">
                          来源报告 {nameOrShortId(view.sourcePaperTitle, view.analysisRunId)} · {stampText(view.sourceCreatedAt ?? null)} ·
                          学科 {view.subjectId} · 当前修订 v{view.currentRevision.version} ·{' '}
                          {STATE_LABEL[view.currentRevision.state] ?? view.currentRevision.state} · 编辑版本 r{view.revision}
                        </p>
                        <p className="practices-meta" title={`练习集 ${view.practiceSetId} · 修订 ${view.currentRevision.practiceRevisionId}`}>
                          练习集 {shortId(view.practiceSetId)} · 修订 {shortId(view.currentRevision.practiceRevisionId)}
                        </p>
                      </div>
                    </header>

                    <div className="practices-tabs" role="tablist" aria-label="练习视图">
                      <button
                        role="tab"
                        id="practices-view-edit"
                        aria-selected={tab === 'edit'}
                        aria-controls="practices-view-edit-panel"
                        className={tab === 'edit' ? 'current' : ''}
                        data-testid="practices-view-edit"
                        tabIndex={tab === 'edit' ? 0 : -1}
                        onClick={() => setTab('edit')}
                        onKeyDown={(event) => {
                          if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
                            event.preventDefault();
                            setTab('edit');
                          }
                        }}
                      >
                        编辑与微调
                      </button>
                      <button
                        role="tab"
                        id="practices-view-export"
                        aria-selected={tab === 'export'}
                        aria-controls="practices-view-export-panel"
                        className={tab === 'export' ? 'current' : ''}
                        data-testid="practices-view-export"
                        tabIndex={tab === 'export' ? 0 : -1}
                        onClick={() => setTab('export')}
                        onKeyDown={(event) => {
                          if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
                            event.preventDefault();
                            setTab('export');
                          }
                        }}
                      >
                        导出预览
                        {!hasReviewedRevision && <span className="practices-lock" aria-hidden> · 未确认</span>}
                      </button>
                    </div>

                    <div
                      id={tab === 'edit' ? 'practices-view-edit-panel' : 'practices-view-export-panel'}
                      role="tabpanel"
                      aria-labelledby={tab === 'edit' ? 'practices-view-edit' : 'practices-view-export'}
                    >
                      {tab === 'edit' ? (
                        <PracticeEditor
                          key={`${view.practiceSetId}|${view.currentRevision.practiceRevisionId}`}
                          view={view}
                          services={services}
                          onSaved={onSaved}
                          onLocked={setEditorLocked}
                          autoSuggest={autoSuggest}
                        />
                      ) : (
                        <PracticeExportPanel view={view} services={services} />
                      )}
                    </div>
                  </>
                )}
              </>
            )}
          </section>
        </div>

        {busy && (
          <p className="practices-meta" role="status">
            编辑或创建正在提交：未保存的编辑按练习保留在本机；请等待提交完成再切换，避免同一修订并发写入。
          </p>
        )}
        <ErrorNotice error={detail.state.phase === 'failed' ? detail.state.error : null} />
        <p className="space-footnote">
          练习集、修订、建议与产物都以服务端为准：任何一步失败都会显示具体原因与错误码，不会伪造成功，
          也不会把请求失败当成空列表。未保存的编辑按练习保留在本机，刷新后可恢复。
        </p>
      </main>
    </div>
  );
}
