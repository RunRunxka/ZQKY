'use client';

/**
 * `/assessments` 施测与成绩工作区（TEACHING-LOOP B3 · F20-I）。
 *
 * 五步：**名单 → 原卷 → 施测 → 成绩 → 历史**。步骤只是导航（各步骤面板保持挂载、用
 * `hidden` 隐藏），这样成绩校对期间的草稿不因切步骤被清空；但**切换施测**会以 `key`
 * 重挂载成绩/历史面板，使在途请求与旧施测的编辑一起失效（操作身份 + 观察代次）。
 *
 * 真实数据全部来自 FastAPI（名单/原卷/施测/成绩端点）；本页不伪造任何"已入库"状态。
 */

import { useEffect, useRef, useState } from 'react';
import { useEntrance } from '@/components/motion/useEntrance';
import '@/components/layout/space.css';
import '@/features/assessments/styles/assessments.css';
import { getAssessment } from '@/services/assessments-api';
import { RosterPanel } from './RosterPanel';
import { PapersPanel, type SelectedPaper } from './PapersPanel';
import { AssessmentsPanel } from './AssessmentsPanel';
import { ScorePanel } from './ScorePanel';
import { HistoryPanel } from './HistoryPanel';
import { shortId } from './labels';

type Step = 'roster' | 'paper' | 'assessment' | 'score' | 'history';

const STEPS: { id: Step; label: string }[] = [
  { id: 'roster', label: '1 名单' },
  { id: 'paper', label: '2 原卷' },
  { id: 'assessment', label: '3 施测' },
  { id: 'score', label: '4 成绩' },
  { id: 'history', label: '5 历史' },
];

export function AssessmentsWorkspace({ initialAssessmentId, initialStep }: { initialAssessmentId?: string; initialStep?: 'score' | 'history' } = {}) {
  const pageRef = useRef<HTMLDivElement>(null);
  const rosterPanelRef = useRef<HTMLElement>(null);
  const paperPanelRef = useRef<HTMLElement>(null);
  const assessmentPanelRef = useRef<HTMLElement>(null);
  const scorePanelRef = useRef<HTMLElement>(null);
  const historyPanelRef = useRef<HTMLElement>(null);
  const [step, setStep] = useState<Step>(initialStep ?? 'roster');
  /** 到过的步骤才挂载面板：没看过的重面板（大矩阵/大批次）不参与首屏渲染。 */
  const [visited, setVisited] = useState<Set<Step>>(() => new Set<Step>([initialStep ?? 'roster']));
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [selectedClassName, setSelectedClassName] = useState<string | null>(null);
  const [selectedPaper, setSelectedPaper] = useState<SelectedPaper | null>(null);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<string | null>(initialAssessmentId ?? null);
  /** 施测标题：选择时随 id 一起回传；深链进入时由 `getAssessment()` 回读，失败保持短号回落。 */
  const [selectedAssessmentTitle, setSelectedAssessmentTitle] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  const [rosterRefreshToken, setRosterRefreshToken] = useState(0);

  useEntrance(pageRef, { preset: 'page' });
  useEntrance(rosterPanelRef, { preset: 'panel', enabled: step === 'roster' });
  useEntrance(paperPanelRef, { preset: 'panel', enabled: step === 'paper' });
  useEntrance(assessmentPanelRef, { preset: 'panel', enabled: step === 'assessment' });
  useEntrance(scorePanelRef, { preset: 'panel', enabled: step === 'score' });
  useEntrance(historyPanelRef, { preset: 'panel', enabled: step === 'history' });

  function go(next: Step) {
    setVisited((prev) => (prev.has(next) ? prev : new Set(prev).add(next)));
    setStep(next);
  }

  function selectClass(classId: string, name?: string) {
    setSelectedClassId(classId || null);
    setSelectedClassName(name || null);
  }

  /** 选择/取消选择施测：标题随回传（缺标题时由下面的深链回读补，没有就显示短号）。 */
  function selectAssessment(assessmentId: string | null, title?: string | null) {
    setSelectedAssessmentId(assessmentId || null);
    setSelectedAssessmentTitle(title || null);
  }

  /**
   * 深链（`?assessmentId=`）只给 id：回读一次标题用于状态条。
   * 读取失败不伪造名称，保持「施测 <短号>」并保留原 id 可用。
   */
  useEffect(() => {
    if (!selectedAssessmentId || selectedAssessmentTitle) return;
    const controller = new AbortController();
    let active = true;
    getAssessment(selectedAssessmentId, controller.signal).then(
      (detail) => {
        if (active) setSelectedAssessmentTitle(detail?.assessment?.title ?? null);
      },
      () => {
        /* 回读失败：状态条退回短号，不猜测标题 */
      },
    );
    return () => {
      active = false;
      controller.abort();
    };
  }, [selectedAssessmentId, selectedAssessmentTitle]);

  const classChipText = selectedClassName
    ?? (selectedClassId ? `未命名班级（${shortId(selectedClassId)}）` : '未选择');
  const paperChipText = selectedPaper
    ? `${selectedPaper.title} · v${selectedPaper.version}`
    : '未选用';
  const assessmentChipText = selectedAssessmentTitle
    ?? (selectedAssessmentId ? `施测 ${shortId(selectedAssessmentId)}` : '未选择');
  const contextIdText = [
    selectedClassId ? `班级 ${shortId(selectedClassId)}` : null,
    selectedPaper ? `原卷修订 ${shortId(selectedPaper.paperRevisionId)}` : null,
    selectedAssessmentId ? `施测 ${shortId(selectedAssessmentId)}` : null,
  ].filter((entry): entry is string => entry !== null);

  /** 复制完整 ID（不是短号）；剪贴板不可用或被拒时静默，文本仍可手动选中复制。 */
  async function copyContextIds() {
    const text = [
      selectedClassId ? `classId=${selectedClassId}` : null,
      selectedPaper ? `paperRevisionId=${selectedPaper.paperRevisionId}` : null,
      selectedAssessmentId ? `assessmentId=${selectedAssessmentId}` : null,
    ].filter((entry): entry is string => entry !== null).join('\n');
    try {
      if (!navigator.clipboard?.writeText) return;
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      /* 复制失败：不报错、不改状态；ID 文本保留可选 */
    }
  }

  return (
    <div ref={pageRef} className="space-page assessments-page">
      <header className="space-header" data-motion-reveal>
        <h1>施测与成绩</h1>
        <p className="space-description">
          按「名单 → 原卷 → 施测 → 成绩 → 历史」完成一次真实测评闭环：成绩只接受教师原始
          小题得分表，0 / 空白 / 缺考 / 免考严格区分，确认后的成绩修订不可变；修正生成新版本并保留审计。
        </p>
      </header>

      <main className="space-content">
        <nav className="space-tabs" role="tablist" aria-label="施测与成绩步骤" data-motion-reveal>
          {STEPS.map((entry) => (
            <button
              key={entry.id}
              role="tab"
              id={`assessments-tab-${entry.id}`}
              aria-selected={step === entry.id}
              aria-controls={`assessments-panel-${entry.id}`}
              className={step === entry.id ? 'current' : ''}
              data-testid={`assessments-tab-${entry.id}`}
              onClick={() => go(entry.id)}
            >
              {entry.label}
            </button>
          ))}
        </nav>

        <div className="assessments-context" aria-live="polite" data-motion-reveal>
          <span className="space-chip blue" data-testid="assessments-context-class">
            班级：{classChipText}
          </span>
          <span className="space-chip blue" data-testid="assessments-context-paper">
            原卷：{paperChipText}
          </span>
          <span className="space-chip blue" data-testid="assessments-context-assessment">
            施测：{assessmentChipText}
          </span>
        </div>
        <div className="assessments-meta assessments-context-meta" data-testid="assessments-context-ids">
          {contextIdText.length > 0 ? (
            <>
              <span>ID：{contextIdText.join(' · ')}</span>
              <button
                type="button"
                className="space-button"
                data-testid="assessments-copy-ids"
                onClick={() => void copyContextIds()}
              >
                {copied ? '已复制' : '复制 ID'}
              </button>
            </>
          ) : (
            <span>ID：尚未选择班级 / 原卷 / 施测</span>
          )}
        </div>

        <section
          ref={rosterPanelRef}
          role="tabpanel"
          id="assessments-panel-roster"
          aria-labelledby="assessments-tab-roster"
          hidden={step !== 'roster'}
        >
          {visited.has('roster') && (
          <RosterPanel
            selectedClassId={selectedClassId}
            onSelectClass={(classId, name) => selectClass(classId, name)}
            refreshToken={refreshToken}
            onChanged={() => setRosterRefreshToken((value) => value + 1)}
          />
          )}
        </section>

        <section
          ref={paperPanelRef}
          role="tabpanel"
          id="assessments-panel-paper"
          aria-labelledby="assessments-tab-paper"
          hidden={step !== 'paper'}
        >
          {visited.has('paper') && (
            <PapersPanel
              selected={selectedPaper}
              onSelect={setSelectedPaper}
              refreshToken={refreshToken}
            />
          )}
        </section>

        <section
          ref={assessmentPanelRef}
          role="tabpanel"
          id="assessments-panel-assessment"
          aria-labelledby="assessments-tab-assessment"
          hidden={step !== 'assessment'}
        >
          {visited.has('assessment') && (
          <AssessmentsPanel
            key={`assessment|${selectedClassId ?? 'none'}|${selectedPaper?.paperRevisionId ?? 'none'}`}
            selectedPaper={selectedPaper}
            classId={selectedClassId}
            className={selectedClassName}
            selectedAssessmentId={selectedAssessmentId}
            onSelectAssessment={selectAssessment}
            onOpenScore={() => go('score')}
            refreshToken={refreshToken}
            rosterRefreshToken={rosterRefreshToken}
            onChanged={() => setRefreshToken((value) => value + 1)}
          />
          )}
        </section>

        <section
          ref={scorePanelRef}
          role="tabpanel"
          id="assessments-panel-score"
          aria-labelledby="assessments-tab-score"
          hidden={step !== 'score'}
        >
          {visited.has('score') && selectedAssessmentId ? (
            <ScorePanel
              key={`score|${selectedAssessmentId}`}
              assessmentId={selectedAssessmentId}
              onOpenHistory={() => go('history')}
              refreshToken={refreshToken}
              onChanged={() => setRefreshToken((value) => value + 1)}
            />
          ) : !visited.has('score') && selectedAssessmentId ? null : (
            <p className="space-empty" data-testid="assessments-score-need-assessment">
              <strong>未选择施测</strong>
              <span>先在「施测」步骤创建或选择一个施测，再导入成绩表。</span>
            </p>
          )}
        </section>

        <section
          ref={historyPanelRef}
          role="tabpanel"
          id="assessments-panel-history"
          aria-labelledby="assessments-tab-history"
          hidden={step !== 'history'}
        >
          {visited.has('history') && selectedAssessmentId ? (
            <HistoryPanel
              key={`history|${selectedAssessmentId}`}
              assessmentId={selectedAssessmentId}
              refreshToken={refreshToken}
              onChanged={() => setRefreshToken((value) => value + 1)}
            />
          ) : !visited.has('history') && selectedAssessmentId ? null : (
            <p className="space-empty" data-testid="assessments-history-need-assessment">
              <strong>未选择施测</strong>
              <span>先在「施测」步骤选择一个施测，再查看修订与只读矩阵。</span>
            </p>
          )}
        </section>
      </main>
    </div>
  );
}
