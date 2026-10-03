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

import { useState } from 'react';
import '@/components/layout/space.css';
import '@/features/assessments/styles/assessments.css';
import { RosterPanel } from './RosterPanel';
import { PapersPanel, type SelectedPaper } from './PapersPanel';
import { AssessmentsPanel } from './AssessmentsPanel';
import { ScorePanel } from './ScorePanel';
import { HistoryPanel } from './HistoryPanel';

type Step = 'roster' | 'paper' | 'assessment' | 'score' | 'history';

const STEPS: { id: Step; label: string }[] = [
  { id: 'roster', label: '1 名单' },
  { id: 'paper', label: '2 原卷' },
  { id: 'assessment', label: '3 施测' },
  { id: 'score', label: '4 成绩' },
  { id: 'history', label: '5 历史' },
];

export function AssessmentsWorkspace({ initialAssessmentId, initialStep }: { initialAssessmentId?: string; initialStep?: 'score' | 'history' } = {}) {
  const [step, setStep] = useState<Step>(initialStep ?? 'roster');
  /** 到过的步骤才挂载面板：没看过的重面板（大矩阵/大批次）不参与首屏渲染。 */
  const [visited, setVisited] = useState<Set<Step>>(() => new Set<Step>([initialStep ?? 'roster']));
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [selectedClassName, setSelectedClassName] = useState<string | null>(null);
  const [selectedPaper, setSelectedPaper] = useState<SelectedPaper | null>(null);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<string | null>(initialAssessmentId ?? null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [rosterRefreshToken, setRosterRefreshToken] = useState(0);

  function go(next: Step) {
    setVisited((prev) => (prev.has(next) ? prev : new Set(prev).add(next)));
    setStep(next);
  }

  function selectClass(classId: string, name?: string) {
    setSelectedClassId(classId);
    setSelectedClassName(name ?? null);
  }

  return (
    <div className="space-page assessments-page">
      <header className="space-header">
        <h1>施测与成绩</h1>
        <p className="space-description">
          按「名单 → 原卷 → 施测 → 成绩 → 历史」完成一次真实测评闭环：成绩只接受教师原始
          小题得分表，0 / 空白 / 缺考 / 免考严格区分，确认后的成绩修订不可变；修正生成新版本并保留审计。
        </p>
      </header>

      <main className="space-content">
        <nav className="space-tabs" role="tablist" aria-label="施测与成绩步骤">
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

        <div className="assessments-context" aria-live="polite">
          <span className="space-chip">
            班级：{selectedClassName ?? selectedClassId ?? '未选择'}
          </span>
          <span className="space-chip">
            原卷：{selectedPaper ? selectedPaper.title : '未选用'}
          </span>
          <span className="space-chip">
            施测：{selectedAssessmentId ?? '未选择'}
          </span>
        </div>

        <section
          role="tabpanel"
          id="assessments-panel-roster"
          aria-labelledby="assessments-tab-roster"
          hidden={step !== 'roster'}
        >
          {visited.has('roster') && (
          <RosterPanel
            selectedClassId={selectedClassId}
            onSelectClass={(classId) => selectClass(classId)}
            refreshToken={refreshToken}
            onChanged={() => setRosterRefreshToken((value) => value + 1)}
          />
          )}
        </section>

        <section
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
            onSelectAssessment={setSelectedAssessmentId}
            onOpenScore={() => go('score')}
            refreshToken={refreshToken}
            rosterRefreshToken={rosterRefreshToken}
            onChanged={() => setRefreshToken((value) => value + 1)}
          />
          )}
        </section>

        <section
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
