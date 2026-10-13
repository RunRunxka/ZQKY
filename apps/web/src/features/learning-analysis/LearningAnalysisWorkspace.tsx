'use client';

/**
 * `/learning-analysis` 学情分析页（R6-FE 2026-10-11）。
 *
 * 结构：顶部筛选（班级 / 试卷 / 时间粒度 + 导入小题分 + **删除该施测**）→ 报告列表与所选报告 →
 * 五图（各自独立的数据源、错误与重试）→ AI 评价与导出分析报告。
 *
 * 数据全部来自 FastAPI；读取失败按卡片显示原因与重试，不当空目录、不静默空图。
 * 公共壳与滚动容器由 layout 的 `ModuleWorkspaceShell` 统一提供（业务根由总控登记），
 * 本页不自包 WorkspaceShell。
 *
 * R10-BE（2026-10-13）：新增「删除该施测」——施测是成绩链的所有者，删除会级联删掉它自己的
 * 整条链（人次/导入/修订与小题分/报告/派生练习/转换/成绩模板导出）；确认文案按类别点名后果，
 * 成功回执逐项显示服务端级联计数，被教案冻结血缘引用时 409 逐项列出原因（详见 docs/API.md 删除语义）。
 *
 * 归档差异（R6 裁定）：
 * - 报告由后端创建（`POST /assessments/{id}/analysis-runs`）不在本卡范围，本页只读取既有报告；
 * - 趋势图为红色柱状图（覆盖归档的折线）；
 * - 班级筛选经服务端 `GET /assessments?classId=`（收窄试卷）；时间粒度按报告创建时间在
 *   已读取的报告页内过滤，并在界面上显式说明（后端暂无时间查询参数）。
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { FileSpreadsheet, RefreshCw, Trash2 } from 'lucide-react';
import { useEntrance } from '@/components/motion/useEntrance';
import { learningAnalysisApi, type LearningAnalysisApi } from '@/services/learning-analysis-api';
import { asApiError, useAsyncResource } from './score-hooks';
import { ASSESSMENT_COUNT_LABELS, referenceCounts, shortId } from './score-labels';
import { DeleteGuardNotice, type DeleteGuardState } from './DeleteGuardNotice';
import {
  DistributionCard,
  ItemHeatmapCard,
  ItemTrendCard,
  KnowledgeRankingCard,
  StudentKnowledgeCard,
} from './ScoreCharts';
import { AiCommentaryPanel } from './AiCommentaryPanel';
import { ScoreImportPanel } from './ScoreImportPanel';
import '@/components/layout/space.css';
import './styles/learning-analysis.css';

const RUNS_PAGE_SIZE = 20;
/** 时间粒度（本卡口径：报告创建时间的范围过滤；选项文案不做日/周/月聚合）。 */
const TIME_RANGES: readonly { id: string; label: string; days: number | null }[] = [
  { id: 'all', label: '不限时间', days: null },
  { id: '7d', label: '近 7 天', days: 7 },
  { id: '30d', label: '近 30 天', days: 30 },
  { id: '90d', label: '近 90 天', days: 90 },
];

export interface LearningAnalysisWorkspaceProps {
  initialAssessmentId?: string | null;
  initialRunId?: string | null;
  /** 可注入测试替身；默认走真实 API。 */
  services?: LearningAnalysisApi;
}

/** 报告展示名（名称优先）：原卷标题 + 创建时间；都缺失才回落 runId 短号，不伪造名称。 */
function reportLabel(run: { paperTitle?: string | null; createdAt?: string | null; runId: string }): string {
  const title = typeof run.paperTitle === 'string' ? run.paperTitle.trim() : '';
  const stamp = run.createdAt ? run.createdAt.slice(0, 10) : '';
  if (title && stamp) return `${title} · ${stamp}`;
  if (title) return title;
  return stamp || shortId(run.runId);
}

/**
 * 删除施测的二次确认文案（R10-BE）：把**会一起删掉的东西按类别点名**——
 * 施测是成绩链的所有者，删除即删除整条链，且不可恢复。
 */
function deleteConfirmText(title: string, heldOn: string): string {
  return (
    `彻底删除施测「${title}」（${heldOn}）？\n\n` +
    '这会连同它自己的整条数据链一起物理删除、不可恢复：\n' +
    '参测人次 → 成绩导入批次 → 成绩修订与小题分 → 学情报告 → 由报告派生的练习（含导出件）→ ' +
    '练习回流转换与成绩模板导出。\n\n' +
    '学生档案、班级名单、试卷原件与教案不受影响；教案里由本报告生成过的来源指针会被置空。\n' +
    '只想改成绩或删报告请用其它入口，不要继续。'
  );
}

/** 删除成功回执（R10-BE）：只列**实际删到**的项（计数 0 的不提），服务端数字原样呈现。 */
function deleteReceiptText(title: string, receipt: Record<string, unknown>): string {
  const parts = Object.entries(ASSESSMENT_COUNT_LABELS)
    .map(([key, label]) => ({ label, count: receipt[key] }))
    .filter((entry): entry is { label: string; count: number } =>
      typeof entry.count === 'number' && entry.count > 0,
    )
    .map((entry) => `${entry.label} ${entry.count}`);
  const cascade = parts.length > 0 ? `级联删除：${parts.join('、')}。` : '该施测下没有成绩与报告数据。';
  return `已彻底删除施测「${title}」：${cascade}物理删除完成，不可恢复。`;
}

export function LearningAnalysisWorkspace({
  initialAssessmentId = null,
  initialRunId = null,
  services = learningAnalysisApi,
}: LearningAnalysisWorkspaceProps) {
  const pageRef = useRef<HTMLDivElement>(null);
  useEntrance(pageRef, { preset: 'page' });

  const [classId, setClassId] = useState('');
  const [assessmentId, setAssessmentId] = useState(initialAssessmentId ?? '');
  const [timeRange, setTimeRange] = useState('all');
  /** 时间粒度的截止时间戳：在事件里计算（渲染期不调用 Date.now，保持组件纯）。 */
  const [timeCutoff, setTimeCutoff] = useState<number | null>(null);
  const [runId, setRunId] = useState<string | null>(initialRunId);
  const [runsOffset, setRunsOffset] = useState(0);
  const [showImport, setShowImport] = useState(false);
  /** 删除施测（R10-BE）：忙碌、错误、被引用守卫、成功回执四个独立状态。 */
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteGuard, setDeleteGuard] = useState<DeleteGuardState | null>(null);
  const [deleteReceipt, setDeleteReceipt] = useState<string | null>(null);

  const classes = useAsyncResource((signal) => services.listClasses({ limit: 200 }, signal), 'la-classes');
  const assessments = useAsyncResource(
    (signal) => services.listAssessments({ classId: classId || undefined, limit: 100 }, signal),
    `la-assessments|${classId}`,
  );
  const runs = useAsyncResource(
    (signal) =>
      services.listAnalysisRuns(
        { assessmentId: assessmentId || undefined, offset: runsOffset, limit: RUNS_PAGE_SIZE },
        signal,
      ),
    `la-runs|${assessmentId}|${runsOffset}`,
  );
  const run = useAsyncResource(
    (signal) => (runId ? services.getAnalysisRun(runId, signal) : Promise.resolve(null)),
    `la-run|${runId ?? 'none'}`,
  );
  const runView = run.lastData;

  const visibleRuns = useMemo(() => {
    const items = runs.lastData?.items ?? [];
    if (timeCutoff === null) return items;
    return items.filter((item) => {
      const created = Date.parse(item.createdAt ?? '');
      // 时间无法判读的报告不静默丢弃：保留并交由列表自身显示。
      return !Number.isFinite(created) || created >= timeCutoff;
    });
  }, [runs.lastData, timeCutoff]);

  // 有报告时默认选中最新一份（列表按后端返回顺序）；筛选变化清空后同样回落。
  useEffect(() => {
    if (runId === null && visibleRuns.length > 0) setRunId(visibleRuns[0].runId);
  }, [runId, visibleRuns]);

  function resetRunSelection() {
    setRunId(null);
    setRunsOffset(0);
  }

  /** 时间粒度：在事件里算截止时间戳（选项文案不做日/周/月聚合）。 */
  function applyTimeRange(id: string) {
    const days = TIME_RANGES.find((entry) => entry.id === id)?.days ?? null;
    setTimeRange(id);
    setTimeCutoff(days === null ? null : Date.now() - days * 24 * 60 * 60 * 1000);
    setRunsOffset(0);
  }

  /** 当前选中的施测（下拉里选中那条；没有选中时为 null，删除入口据此禁用）。 */
  const selectedAssessment = useMemo(
    () =>
      (assessments.lastData?.items ?? []).find((item) => item.assessmentId === assessmentId) ?? null,
    [assessments.lastData, assessmentId],
  );

  /**
   * 彻底删除当前选中的施测（R10-BE：施测是成绩链的所有者，删除即删整条链）。
   *
   * 二次确认里按类别点名会被删掉的数据；成功 200 回执带级联计数，逐项展示；
   * 被教案冻结生成血缘引用 → 409 `ASSESSMENT_IN_USE`，逐项列出原因（不显示成功回执）；
   * 乐观锁 409 / 404 走普通错误区（不伪装成引用问题）。删除后清空筛选并刷新列表与报告。
   */
  async function deleteSelectedAssessment() {
    if (deleteBusy || !selectedAssessment) return;
    const target = selectedAssessment;
    if (!window.confirm(deleteConfirmText(target.title, target.heldOn))) return;
    setDeleteBusy(true);
    setDeleteError(null);
    setDeleteGuard(null);
    setDeleteReceipt(null);
    try {
      const receipt = await services.deleteAssessment(target.assessmentId, target.revision);
      setDeleteReceipt(
        deleteReceiptText(target.title, receipt as unknown as Record<string, unknown>),
      );
      // 施测已不存在：清空筛选与选中报告，收起导入面板，再刷新列表（报告链已随之消失）
      setAssessmentId('');
      setRunId(null);
      setRunsOffset(0);
      setShowImport(false);
      assessments.reload();
      runs.reload();
    } catch (cause) {
      const error = asApiError(cause);
      if (error.status === 409 && error.code === 'ASSESSMENT_IN_USE') {
        setDeleteGuard({
          targetId: target.assessmentId,
          error,
          reasons: referenceCounts(error.details, ASSESSMENT_COUNT_LABELS),
        });
      } else {
        setDeleteError(`删除施测失败（${error.code}）：${error.message}`);
      }
    } finally {
      setDeleteBusy(false);
    }
  }

  const classesFailed = classes.state.phase === 'failed';
  const reportReady = Boolean(runView?.reportReady);

  return (
    <div ref={pageRef} className="space-page learning-analysis-page">
      <header className="space-header" data-motion-reveal>
        <div className="space-header-row">
          <h1>学情分析</h1>
          <div className="la-actions">
            <button
              className="space-button"
              onClick={() => {
                runs.reload();
                run.reload();
              }}
            >
              <RefreshCw size={13} aria-hidden /> 刷新报告
            </button>
          </div>
        </div>
        <p className="space-description">
          从一次已确认的小题分成绩单出发，结合知识点库生成班级学情图表与 AI 评价；
          AI 结果只是候选，教师确认后才落库。图表依据固定版本，不计算长期掌握概率。
        </p>
      </header>

      <main className="space-content">
        <section className="la-filter-bar" aria-label="学情筛选">
          <label className="la-field">
            班级
            <select
              className="space-select"
              aria-label="班级筛选"
              value={classId}
              onChange={(event) => {
                setClassId(event.target.value);
                setAssessmentId('');
                resetRunSelection();
                setShowImport(false);
              }}
            >
              <option value="">全部班级</option>
              {(classes.lastData?.items ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            {classesFailed && (
              <span className="la-hint" role="alert">
                班级目录读取失败（{classes.state.phase === 'failed' ? classes.state.error.code : ''}）：
                班级筛选暂不可用，未把它当成空名单。
                <button className="space-button" onClick={classes.reload}>
                  重试
                </button>
              </span>
            )}
          </label>

          <label className="la-field">
            试卷
            <select
              className="space-select"
              aria-label="试卷筛选"
              value={assessmentId}
              onChange={(event) => {
                setAssessmentId(event.target.value);
                resetRunSelection();
              }}
            >
              <option value="">全部试卷</option>
              {(assessments.lastData?.items ?? []).map((item) => (
                <option key={item.assessmentId} value={item.assessmentId}>
                  {item.title} · {item.heldOn}
                </option>
              ))}
            </select>
          </label>

          <label className="la-field">
            时间粒度
            <select
              className="space-select"
              aria-label="时间粒度筛选"
              value={timeRange}
              onChange={(event) => applyTimeRange(event.target.value)}
            >
              {TIME_RANGES.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.label}
                </option>
              ))}
            </select>
          </label>

          <div className="la-filter-actions">
            <button
              className="space-button primary"
              aria-expanded={showImport}
              aria-controls="learning-analysis-import"
              onClick={() => setShowImport((value) => !value)}
            >
              <FileSpreadsheet size={13} aria-hidden /> {showImport ? '收起导入面板' : '导入小题分'}
            </button>
            <button
              className="space-button danger"
              data-testid="la-assessment-delete"
              disabled={deleteBusy || !selectedAssessment}
              title={
                selectedAssessment
                  ? `删除施测「${selectedAssessment.title}」及其整条成绩链`
                  : '先在上面的「试卷」下拉里选择一场施测'
              }
              onClick={() => void deleteSelectedAssessment()}
            >
              <Trash2 size={13} aria-hidden />
              {deleteBusy ? '删除中…' : '删除该施测'}
            </button>
          </div>
        </section>

        <p className="la-hint">
          班级筛选走服务端：只列出该班参测的试卷；试卷筛选只列出该试卷的分析报告。
          时间粒度按报告创建时间在已读取的报告页内过滤（后端暂未提供时间查询参数），界面不隐藏该口径。
          「删除该施测」作用于上面「试卷」下拉里选中的那一场（删除即删除，不可恢复）。
        </p>

        {deleteReceipt && (
          <p className="space-banner info" role="status" data-testid="la-assessment-delete-receipt">
            {deleteReceipt}
          </p>
        )}
        {deleteError && (
          <p className="space-banner error" role="alert" data-testid="la-assessment-delete-error">
            {deleteError}
          </p>
        )}
        {deleteGuard && (
          <DeleteGuardNotice
            state={deleteGuard}
            targetName={
              (assessments.lastData?.items ?? []).find(
                (item) => item.assessmentId === deleteGuard.targetId,
              )?.title ?? `施测 ${shortId(deleteGuard.targetId)}`
            }
            testId="la-assessment-delete-guard"
          />
        )}

        {assessments.state.phase === 'failed' && (
          <div className="space-banner error" role="alert" data-testid="la-assessments-error">
            试卷列表读取失败（{assessments.state.error.code}）：{assessments.state.error.message}
            <div className="la-actions">
              <button className="space-button" onClick={assessments.reload}>
                重试
              </button>
            </div>
          </div>
        )}

        {showImport && (
          <div id="learning-analysis-import" className="la-section">
            <ScoreImportPanel
              assessmentId={assessmentId || null}
              onClose={() => setShowImport(false)}
              onChanged={() => {
                runs.reload();
                run.reload();
              }}
            />
          </div>
        )}

        <section className="la-section" aria-label="分析报告">
          <h2>分析报告</h2>
          <p className="la-hint">
            报告由后端在一次已确认成绩上创建（固定版本，不随成绩修正而变）；本页只读取既有报告，
            不在此页创建。R10-FE：归档功能已舍弃——本页不提供归档/恢复操作；历史数据里已归档的
            报告仍按后端返回只读展示（标「已归档（只读）」）。
          </p>

          {runs.state.phase === 'failed' && (
            <div className="space-banner error" role="alert" data-testid="la-runs-error">
              报告列表读取失败（{runs.state.error.code}）：{runs.state.error.message} 未把它当成空目录。
              <div className="la-actions">
                <button className="space-button" onClick={runs.reload}>
                  重试
                </button>
              </div>
            </div>
          )}
          {runs.state.phase === 'ready' && (runs.lastData?.items.length ?? 0) === 0 && (
            <p className="space-empty" data-testid="la-runs-empty">
              <strong>该筛选下还没有分析报告</strong>
              <span>先在该试卷上导入并确认小题分成绩单，或到报告创建入口生成报告后再回到本页。</span>
            </p>
          )}
          {runs.state.phase === 'ready' &&
            (runs.lastData?.items.length ?? 0) > 0 &&
            visibleRuns.length === 0 && (
              <p className="space-empty" data-testid="la-runs-time-empty">
                <strong>当前时间粒度下没有报告</strong>
                <span>已读取的报告都早于所选时间范围；把时间粒度改为「不限时间」可查看全部。</span>
              </p>
            )}

          <ul className="la-run-list">
            {visibleRuns.map((item) => (
              <li key={item.runId}>
                <button
                  type="button"
                  className={item.runId === runId ? 'la-run-item current' : 'la-run-item'}
                  aria-pressed={item.runId === runId}
                  data-testid={`la-run-${item.runId}`}
                  onClick={() => setRunId(item.runId)}
                >
                  <strong>{reportLabel(item)}</strong>
                  <span className="la-meta">
                    {item.reportReady ? '已准备' : '尚未准备'} · 人次{' '}
                    {item.selectionSnapshot?.participantCount ?? '—'} · 报告 {shortId(item.runId)}
                    {item.archivedAt ? ' · 已归档（只读）' : ''}
                  </span>
                </button>
              </li>
            ))}
          </ul>

          {runs.lastData && runs.lastData.total > RUNS_PAGE_SIZE && (
            <div className="la-actions">
              <button
                className="space-button"
                disabled={runsOffset === 0}
                onClick={() => setRunsOffset((value) => Math.max(0, value - RUNS_PAGE_SIZE))}
              >
                上一页报告
              </button>
              <button
                className="space-button"
                disabled={runsOffset + RUNS_PAGE_SIZE >= runs.lastData.total}
                onClick={() => setRunsOffset((value) => value + RUNS_PAGE_SIZE)}
              >
                下一页报告
              </button>
            </div>
          )}

          {run.state.phase === 'failed' && (
            <div className="space-banner error" role="alert" data-testid="la-run-error">
              所选报告读取失败（{run.state.error.code}）：{run.state.error.message}
              <div className="la-actions">
                <button className="space-button" onClick={run.reload}>
                  重试
                </button>
              </div>
            </div>
          )}
          {run.state.phase === 'loading' && runId && (
            <p className="la-hint" role="status">
              正在读取所选报告…
            </p>
          )}
          {runView && (
            <div className="la-run-detail" data-testid="la-run-detail">
              <h3>{reportLabel(runView)}</h3>
              <p className="la-meta">
                成绩修订 {shortId(runView.scoreRevisionId)} · 原卷修订 {shortId(runView.paperRevisionId)} ·
                创建 {runView.createdAt?.slice(0, 10) || '—'}
                {runView.archivedAt ? ' · 已归档（只读）' : ''}
              </p>
              {runView.selectionSnapshot && (
                <p className="la-hint">
                  后端记录：{runView.selectionSnapshot.uniqueStudentCount} 名学生 ·{' '}
                  {runView.selectionSnapshot.participantCount} 人次 · {runView.selectionSnapshot.leafCount}{' '}
                  计分叶；空白/缺考/免考与有效 0 分区分，不补 0。
                </p>
              )}
              {!reportReady && (
                <p className="space-banner" role="status" data-testid="la-run-not-ready">
                  该报告尚未准备好，暂不读取图表与 AI 评价；准备完成后刷新本页即可。
                </p>
              )}
            </div>
          )}
        </section>

        {runId && reportReady && (
          <>
            <section className="la-section" aria-label="学情图表">
              <h2>学情图表</h2>
              <p className="la-hint">
                五张图各自读取数据源；任一来源失败只影响该卡（显示原因与重试），不影响其他卡，
                也不会画成空图。
              </p>
              <div className="la-charts-grid">
                <ItemTrendCard runId={runId} />
                <ItemHeatmapCard runId={runId} />
                <KnowledgeRankingCard runId={runId} />
                <DistributionCard runId={runId} />
                <StudentKnowledgeCard runId={runId} />
              </div>
            </section>

            <section className="la-section" aria-label="AI 评价与导出">
              <AiCommentaryPanel runId={runId} services={services} />
            </section>
          </>
        )}
      </main>
    </div>
  );
}

export default LearningAnalysisWorkspace;
