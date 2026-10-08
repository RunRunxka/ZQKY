'use client';

/**
 * `/knowledge-points` 知识点页：知识点（列表/父树/详情与编辑/教材依据）、表格导入校对、
 * AI 候选、教材提取四个页签。真实数据全部来自 FastAPI（B1 知识点接口 + B0 统一任务客户端），
 * 学科与年级来自 `GET /api/v1/textbook-taxonomy`（不存在 /subjects 接口）。
 *
 * 页签面板保持挂载（用 `hidden` 隐藏）：AI 候选/教材提取任务成功或切页签时，
 * 任务状态与资料输入不会因为切换页签被清空。
 */

import { useCallback, useRef, useState } from 'react';
import { useEntrance } from '@/components/motion/useEntrance';
import type { KnowledgePointStatus, KnowledgePointView } from '@/contracts/knowledge';
import '@/components/layout/space.css';
import '@/features/knowledge-points/styles/knowledge-points.css';
import { fetchTextbookTaxonomy } from '@/services/textbook-api';
import type { ObserveJobOptions } from '@/services/workflow-jobs-api';
import { CreatePointDialog } from './CreatePointDialog';
import { ExtractionPanel } from './ExtractionPanel';
import { ImportPanel } from './ImportPanel';
import { PointBrowser } from './PointBrowser';
import { PointDetailPanel } from './PointDetailPanel';
import { SuggestionPanel } from './SuggestionPanel';
import { useAsyncResource } from './hooks';

type Tab = 'points' | 'imports' | 'suggestion' | 'extract';

const TABS: { id: Tab; label: string }[] = [
  { id: 'points', label: '知识点' },
  { id: 'imports', label: '表格导入' },
  { id: 'suggestion', label: 'AI 候选' },
  { id: 'extract', label: '教材提取' },
];

export function KnowledgePointsWorkspace({
  polling,
}: {
  /** 测试注入点：透传给 AI 候选 / 教材提取任务的 `observeJob`。 */
  polling?: Pick<ObserveJobOptions, 'sleep' | 'now'>;
} = {}) {
  const pageRef = useRef<HTMLDivElement>(null);
  const pointsPanelRef = useRef<HTMLElement>(null);
  const importsPanelRef = useRef<HTMLElement>(null);
  const suggestionPanelRef = useRef<HTMLElement>(null);
  const extractPanelRef = useRef<HTMLElement>(null);
  const taxonomy = useAsyncResource((signal) => fetchTextbookTaxonomy(signal), 'kp-taxonomy');
  const subjects = taxonomy.state.phase === 'ready' ? taxonomy.state.data.subjects : [];
  /** 年级字典：不可用时（读取失败）传空数组，列表与提取面板各自降级并说明。 */
  const grades = taxonomy.state.phase === 'ready' ? taxonomy.state.data.grades : [];

  const [tab, setTab] = useState<Tab>('points');
  const [subjectId, setSubjectId] = useState('');
  const [status, setStatus] = useState<'' | KnowledgePointStatus>('');
  const [listRefresh, setListRefresh] = useState(0);
  const [selectedPointId, setSelectedPointId] = useState<string | null>(null);
  const [selectedPoint, setSelectedPoint] = useState<KnowledgePointView | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedImportId, setSelectedImportId] = useState<string | null>(null);
  const [importRefresh, setImportRefresh] = useState(0);

  useEntrance(pageRef, { preset: 'page' });
  useEntrance(pointsPanelRef, { preset: 'panel', enabled: tab === 'points' });
  useEntrance(importsPanelRef, { preset: 'panel', enabled: tab === 'imports' });
  useEntrance(suggestionPanelRef, { preset: 'panel', enabled: tab === 'suggestion' });
  useEntrance(extractPanelRef, { preset: 'panel', enabled: tab === 'extract' });

  const rememberPoint = useCallback((next: KnowledgePointView) => {
    // 只有内容真正变化时才更新，避免 effect → setState → 渲染 的循环。
    setSelectedPoint((prev) =>
      prev &&
      prev.id === next.id &&
      prev.revision === next.revision &&
      prev.version === next.version &&
      prev.status === next.status
        ? prev
        : next,
    );
  }, []);

  function openBatch(importId: string) {
    setSelectedImportId(importId);
    setImportRefresh((value) => value + 1);
    setTab('imports');
  }

  return (
    <div ref={pageRef} className="space-page knowledge-points-page">
      <header className="space-header" data-motion-reveal>
        <h1>知识点</h1>
        <p className="space-description">
          知识点是学科内的稳定身份（编码唯一、内容按修订追加）；可人工建立、表格导入或由 AI
          提出候选， 候选与导入都必须逐行校对、整批确认后才写入正式表。
        </p>
      </header>

      <main className="space-content">
        <div className="space-tabs" role="tablist" aria-label="知识点视图" data-motion-reveal>
          {TABS.map((item) => (
            <button
              key={item.id}
              role="tab"
              id={`kp-tab-${item.id}`}
              aria-selected={tab === item.id}
              aria-controls={`kp-panel-${item.id}`}
              className={tab === item.id ? 'current' : ''}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <section
          ref={pointsPanelRef}
          role="tabpanel"
          id="kp-panel-points"
          aria-labelledby="kp-tab-points"
          hidden={tab !== 'points'}
          className="kp-panel"
        >
          <div className="space-bank-layout kp-points-layout">
            <div className="space-bank-main">
              <PointBrowser
                subjects={subjects}
                taxonomyReady={taxonomy.state.phase === 'ready'}
                grades={grades}
                subjectId={subjectId}
                status={status}
                selectedPointId={selectedPointId}
                onSubjectChange={setSubjectId}
                onStatusChange={setStatus}
                onSelect={(pointId) => setSelectedPointId(pointId)}
                onCreate={() => setCreateOpen(true)}
                refreshToken={listRefresh}
              />
            </div>
            <div className="kp-detail-column">
              {selectedPointId ? (
                <PointDetailPanel
                  key={selectedPointId}
                  pointId={selectedPointId}
                  onPointPatched={(next) => {
                    rememberPoint(next);
                    setListRefresh((value) => value + 1);
                  }}
                  onLoaded={rememberPoint}
                  onDeleted={() => {
                    // 彻底删除成功：取消选中并刷新列表（不留下指向已删知识点的详情缓存）
                    setSelectedPointId(null);
                    setSelectedPoint(null);
                    setListRefresh((value) => value + 1);
                  }}
                />
              ) : (
                <div className="space-empty">
                  <strong>未选择知识点</strong>
                  <span>从左侧列表或父树中选择一个知识点，查看详情、编辑、别名与教材依据。</span>
                </div>
              )}
            </div>
          </div>
          {taxonomy.state.phase === 'failed' && (
            <p className="space-banner error" role="alert">
              学科字典读取失败（{taxonomy.state.error.code}）：{taxonomy.state.error.message}
              可以手动填写学科 id；这不会把字典当成空列表。
              <button className="space-button" onClick={taxonomy.reload}>
                重试
              </button>
            </p>
          )}
        </section>

        <section
          ref={importsPanelRef}
          role="tabpanel"
          id="kp-panel-imports"
          aria-labelledby="kp-tab-imports"
          hidden={tab !== 'imports'}
          className="kp-panel"
        >
          <ImportPanel
            subjects={subjects}
            taxonomyReady={taxonomy.state.phase === 'ready'}
            defaultSubjectId={subjectId}
            selectedImportId={selectedImportId}
            onSelectImport={setSelectedImportId}
            refreshToken={importRefresh}
            onConfirmed={() => setListRefresh((value) => value + 1)}
          />
        </section>

        <section
          ref={suggestionPanelRef}
          role="tabpanel"
          id="kp-panel-suggestion"
          aria-labelledby="kp-tab-suggestion"
          hidden={tab !== 'suggestion'}
          className="kp-panel"
        >
          <SuggestionPanel
            subjects={subjects}
            taxonomyReady={taxonomy.state.phase === 'ready'}
            defaultSubjectId={subjectId}
            selectedPoint={selectedPoint}
            onOpenBatch={openBatch}
            polling={polling}
          />
        </section>

        <section
          ref={extractPanelRef}
          role="tabpanel"
          id="kp-panel-extract"
          aria-labelledby="kp-tab-extract"
          hidden={tab !== 'extract'}
          className="kp-panel"
        >
          <ExtractionPanel
            subjects={subjects}
            grades={grades}
            taxonomyReady={taxonomy.state.phase === 'ready'}
            defaultSubjectId={subjectId}
            onOpenBatch={openBatch}
            polling={polling}
          />
        </section>
      </main>

      {createOpen && (
        <CreatePointDialog
          subjects={subjects}
          taxonomyReady={taxonomy.state.phase === 'ready'}
          defaultSubjectId={subjectId}
          onClose={() => setCreateOpen(false)}
          onCreated={(created) => {
            setCreateOpen(false);
            setSelectedPointId(created.id);
            rememberPoint(created);
            setListRefresh((value) => value + 1);
            setTab('points');
          }}
        />
      )}
    </div>
  );
}
