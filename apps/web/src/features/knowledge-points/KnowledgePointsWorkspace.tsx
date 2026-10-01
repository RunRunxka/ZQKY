'use client';

/**
 * `/knowledge-points` 知识点页：知识点（列表/父树/详情与编辑/教材依据）、表格导入校对、
 * AI 候选三个页签。真实数据全部来自 FastAPI（B1 知识点接口 + B0 统一任务客户端），
 * 学科来自 `GET /api/v1/textbook-taxonomy`（不存在 /subjects 接口）。
 *
 * 页签面板保持挂载（用 `hidden` 隐藏）：AI 候选任务成功后自动切到「表格导入」时，
 * 任务状态与资料输入不会因为切换页签被清空。
 */

import { useCallback, useState } from 'react';
import type { KnowledgePointStatus, KnowledgePointView } from '@/contracts/knowledge';
import '@/components/layout/space.css';
import '@/features/knowledge-points/styles/knowledge-points.css';
import { fetchTextbookTaxonomy } from '@/services/textbook-api';
import type { ObserveJobOptions } from '@/services/workflow-jobs-api';
import { CreatePointDialog } from './CreatePointDialog';
import { ImportPanel } from './ImportPanel';
import { PointBrowser } from './PointBrowser';
import { PointDetailPanel } from './PointDetailPanel';
import { SuggestionPanel } from './SuggestionPanel';
import { useAsyncResource } from './hooks';

type Tab = 'points' | 'imports' | 'suggestion';

const TABS: { id: Tab; label: string }[] = [
  { id: 'points', label: '知识点' },
  { id: 'imports', label: '表格导入' },
  { id: 'suggestion', label: 'AI 候选' },
];

export function KnowledgePointsWorkspace({
  polling,
}: {
  /** 测试注入点：透传给 AI 候选任务的 `observeJob`。 */
  polling?: Pick<ObserveJobOptions, 'sleep' | 'now'>;
} = {}) {
  const taxonomy = useAsyncResource((signal) => fetchTextbookTaxonomy(signal), 'kp-taxonomy');
  const subjects = taxonomy.state.phase === 'ready' ? taxonomy.state.data.subjects : [];

  const [tab, setTab] = useState<Tab>('points');
  const [subjectId, setSubjectId] = useState('');
  const [status, setStatus] = useState<'' | KnowledgePointStatus>('');
  const [listRefresh, setListRefresh] = useState(0);
  const [selectedPointId, setSelectedPointId] = useState<string | null>(null);
  const [selectedPoint, setSelectedPoint] = useState<KnowledgePointView | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedImportId, setSelectedImportId] = useState<string | null>(null);
  const [importRefresh, setImportRefresh] = useState(0);

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
    <div className="space-page knowledge-points-page">
      <header className="space-header">
        <h1>知识点</h1>
        <p className="space-description">
          知识点是学科内的稳定身份（编码唯一、内容按修订追加）；可人工建立、表格导入或由 AI
          提出候选， 候选与导入都必须逐行校对、整批确认后才写入正式表。
        </p>
      </header>

      <main className="space-content">
        <div className="space-tabs" role="tablist" aria-label="知识点视图">
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
