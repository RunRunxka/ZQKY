'use client';
/**
 * 中栏「生成教案」面板（R7-FE）。
 *
 * - 输入：课程名称 + 知识点（`GET /knowledge-points?scope=subject`）+ 学情来源
 *   （分析报告 `GET /analysis-runs` / 上传学情文件 assetRef（.docx/.pdf/.txt/.md，文本按上限
 *   截断后作为固定数据发给模型；成绩表类由服务端 422 并指引走「分析报告」来源）/ 不指定）
 *   + 教师要求；
 * - 触发 `POST /lesson-plans/generation-stream`（归档 SSE 协议），文本从上到下按模块流式到达，
 *   每个模块的文本即时解析成字段（逐格）并在预览中高亮为候选；
 * - **候选态**：只有教师点「采用」才写进草稿；可中断，已收到的内容保留为候选；
 * - 模型档位取自 `/model-catalog` 的默认对话档案（本页不调整思考强度）。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Check, ChevronDown, FileUp, LoaderCircle, Sparkles, Square, Upload, X } from 'lucide-react';
import { ApiError } from '@/services/api-client';
import { streamLessonModules, type LessonStreamModule } from '@/services/lesson-stream';
import { listKnowledgePoints } from '@/services/knowledge-points-api';
import { listAnalysisRuns } from '@/services/learning-analysis-api';
import { loadModelCatalog } from '@/services/model-settings-api';
import { uploadLessonSource } from '@/services/lesson-plans-api';
import type { LessonPlanData, LessonStreamModuleKey } from '@/contracts/lesson-plans';
import { LESSON_STREAM_MODULE_KEYS } from '@/contracts/lesson-plans';
import { newId } from '../model/lesson-data';
import { describeError } from '../services/errors';
import type { LessonCandidate } from '../model/store';
import { SettingCard } from './SettingCard';

export interface GeneratePanelServices {
  streamModules: typeof streamLessonModules;
  loadCatalog: typeof loadModelCatalog;
  listPoints: typeof listKnowledgePoints;
  listRuns: typeof listAnalysisRuns;
  uploadSource: (file: File) => Promise<{ assetRef: string; fileName: string }>;
}

const defaultServices: GeneratePanelServices = {
  streamModules: streamLessonModules,
  loadCatalog: loadModelCatalog,
  listPoints: listKnowledgePoints,
  listRuns: listAnalysisRuns,
  uploadSource: uploadLessonSource,
};

const STREAM_MODULE_LABELS: Record<LessonStreamModuleKey, string> = {
  analysis: '教学分析',
  objectives: '教学目标',
  strategy: '教学策略',
  process: '教学过程',
  exercises: '练习与作业',
  evaluation: '评价反馈',
  reflection: '教学反思',
};

interface KnowledgeOption {
  id: string;
  name: string;
}

type SourceMode = 'none' | 'run' | 'file';

export function GeneratePanel({
  data,
  candidate,
  onStartCandidate,
  onDelta,
  onModuleState,
  onFinishCandidate,
  onClearCandidate,
  onAdopt,
  parsePreview,
  services = defaultServices,
  open,
  onOpenChange,
}: {
  data: LessonPlanData;
  candidate: LessonCandidate | null;
  onStartCandidate: (requestId: string, modules: Array<{ key: string; label: string }>) => void;
  onDelta: (key: string, delta: string) => void;
  onModuleState: (key: string, state: 'pending' | 'streaming' | 'done' | 'error', message?: string) => void;
  onFinishCandidate: (status: LessonCandidate['status'], message?: string) => void;
  onClearCandidate: () => void;
  onAdopt: (keys?: string[]) => string[];
  /** 已解析字段（用于「逐格」摘要展示）。 */
  parsePreview: (key: string) => { labels: string[]; unparsed: number };
  services?: GeneratePanelServices;
  /** 展开状态（由工作台的 dock 控制）；不传时组件自管。 */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [localOpen, setLocalOpen] = useState(true);
  const expanded = open ?? localOpen;
  const setExpanded = (next: boolean) => {
    setLocalOpen(next);
    onOpenChange?.(next);
  };
  const [courseName, setCourseName] = useState(
    () => data.basic?.courseName || data.title || '',
  );
  const [points, setPoints] = useState<KnowledgeOption[]>([]);
  const [pointsError, setPointsError] = useState<string | null>(null);
  const [pointsLoading, setPointsLoading] = useState(true);
  const [pointQuery, setPointQuery] = useState('');
  const [selectedPoints, setSelectedPoints] = useState<string[]>([]);

  const [runs, setRuns] = useState<Array<{ runId: string; label: string; ready: boolean }>>([]);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [runsLoading, setRunsLoading] = useState(true);
  const [sourceMode, setSourceMode] = useState<SourceMode>('none');
  const [analysisRunId, setAnalysisRunId] = useState('');
  const [uploaded, setUploaded] = useState<{ assetRef: string; fileName: string } | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const [requirements, setRequirements] = useState('');
  const [moduleKeys, setModuleKeys] = useState<LessonStreamModuleKey[]>([...LESSON_STREAM_MODULE_KEYS]);
  const [status, setStatus] = useState<'idle' | 'starting' | 'streaming' | 'done' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let alive = true;
    void services
      .listPoints({ scope: 'subject', limit: 50 }, controller.signal)
      .then((page) => {
        if (!alive) return;
        setPoints(page.items.map((item) => ({ id: item.id, name: item.name })));
        setPointsError(null);
      })
      .catch((error: unknown) => {
        if (!alive) return;
        if (error instanceof ApiError && error.code === 'ABORT_ERR') return;
        setPointsError(describeError(error));
      })
      .finally(() => alive && setPointsLoading(false));
    void services
      .listRuns({ limit: 20 }, controller.signal)
      .then((page) => {
        if (!alive) return;
        setRuns(
          page.items.map((run) => ({
            runId: run.runId,
            label: `${run.paperTitle ?? `报告 ${run.runId.slice(0, 8)}`} · ${run.createdAt.slice(0, 10)}`,
            ready: run.reportReady !== false,
          })),
        );
        setRunsError(null);
      })
      .catch((error: unknown) => {
        if (!alive) return;
        setRunsError(describeError(error));
      })
      .finally(() => alive && setRunsLoading(false));
    return () => {
      alive = false;
      controller.abort();
    };
  }, [services]);

  const filteredPoints = useMemo(() => {
    const query = pointQuery.trim().toLowerCase();
    const list = query ? points.filter((point) => point.name.toLowerCase().includes(query)) : points;
    return list.slice(0, 40);
  }, [pointQuery, points]);

  const effectiveModules = useMemo(
    () => moduleKeys.filter((key) => key !== 'exercises' || !moduleKeys.includes('evaluation')),
    [moduleKeys],
  );

  const start = useCallback(async () => {
    setMessage(null);
    setStatus('starting');
    let modelProfileId: string | null = null;
    try {
      const catalog = await services.loadCatalog();
      modelProfileId = catalog.defaultChatProfileId;
    } catch (error) {
      setStatus('error');
      setMessage(`模型目录读取失败：${describeError(error)}`);
      return;
    }
    if (!modelProfileId) {
      setStatus('error');
      setMessage('未配置可用的对话模型档位，请先在设置中连接模型。');
      return;
    }
    const requestId = newId();
    const streamModules = effectiveModules as LessonStreamModule[];
    onStartCandidate(
      requestId,
      streamModules.map((key) => ({ key, label: STREAM_MODULE_LABELS[key] })),
    );
    const controller = new AbortController();
    abortRef.current = controller;
    setStatus('streaming');
    try {
      await services.streamModules(
        {
          requestId,
          modelProfileId,
          courseName: courseName.trim() || data.title || '（未命名教案）',
          requirements: requirements.trim() || undefined,
          analysisRunId: sourceMode === 'run' && analysisRunId ? analysisRunId : undefined,
          sourceAssetRef: sourceMode === 'file' && uploaded ? uploaded.assetRef : undefined,
          selectedKnowledgePointIds: selectedPoints,
          modules: streamModules,
          signal: controller.signal,
        },
        {
          onModuleStart: (key) => onModuleState(key, 'streaming'),
          onModuleDelta: (key, delta) => onDelta(key, delta),
          onModuleError: (key, errorMessage) => onModuleState(key, 'error', errorMessage),
          onModuleDone: (key) => onModuleState(key, 'done'),
          onEnd: () => onFinishCandidate('done'),
          onError: (error) => {
            onFinishCandidate('error', error.message);
            setStatus('error');
            setMessage(`${error.code}：${error.message}`);
          },
        },
      );
      setStatus((current) => (current === 'error' ? current : 'done'));
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        onFinishCandidate('interrupted', '已中断，收到的内容保留为候选。');
        setStatus('idle');
        setMessage('已中断生成，已收到的内容保留为候选；未采用前不会写进草稿。');
      } else {
        onFinishCandidate('error', describeError(error));
        setStatus('error');
        setMessage(describeError(error));
      }
    } finally {
      abortRef.current = null;
    }
  }, [
    analysisRunId,
    courseName,
    data.title,
    effectiveModules,
    onDelta,
    onFinishCandidate,
    onModuleState,
    onStartCandidate,
    requirements,
    selectedPoints,
    services,
    sourceMode,
    uploaded,
  ]);

  const streaming = status === 'streaming' || status === 'starting';
  const candidateKeys = candidate?.order ?? [];

  return (
    <SettingCard
      icon={Sparkles}
      title="生成教案"
      hint="AI 结果先进候选，采用后才写入草稿"
      testId="lw-generate-panel"
      ariaLabel="生成教案"
      className={`lw-generate-card ${expanded ? '' : 'collapsed'}`}
      action={
        <button
          type="button"
          className="lw-icon-button"
          aria-label={expanded ? '收起生成面板' : '展开生成面板'}
          aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}
        >
          <ChevronDown size={15} className={`lw-chevron ${expanded ? 'open' : ''}`} />
        </button>
      }
    >
      <div className="lw-generate-body" hidden={!expanded}>
      <label className="lw-field" htmlFor="lw-generate-course">
        <span>课程名称</span>
        <input
          id="lw-generate-course"
          data-testid="lw-generate-course"
          value={courseName}
          placeholder="如：荷塘月色"
          onChange={(event) => setCourseName(event.target.value)}
        />
      </label>

      <fieldset className="lw-source-group" data-testid="lw-source-group">
        <legend>学情来源</legend>
        <div className="lw-source-modes" role="radiogroup" aria-label="学情来源">
          {(
            [
              ['none', '不指定'],
              ['run', '分析报告'],
              ['file', '上传学情文件'],
            ] as Array<[SourceMode, string]>
          ).map(([mode, label]) => (
            <button
              key={mode}
              type="button"
              role="radio"
              aria-checked={sourceMode === mode}
              className={`lw-chip-select ${sourceMode === mode ? 'selected' : ''}`}
              data-testid={`lw-source-${mode}`}
              onClick={() => setSourceMode(mode)}
            >
              {label}
            </button>
          ))}
        </div>

        {sourceMode === 'run' && (
          <label className="lw-field" htmlFor="lw-analysis-run">
            <span>选择分析报告</span>
            <select
              id="lw-analysis-run"
              data-testid="lw-analysis-run-select"
              value={analysisRunId}
              onChange={(event) => setAnalysisRunId(event.target.value)}
            >
              <option value="">
                {runsLoading ? '正在读取学情报告…' : runs.length === 0 ? '暂无可选报告' : '请选择…'}
              </option>
              {runs.map((run) => (
                <option key={run.runId} value={run.runId} disabled={!run.ready}>
                  {run.label}
                  {run.ready ? '' : '（报告未就绪）'}
                </option>
              ))}
            </select>
            {runsError && (
              <small className="lw-error" data-testid="lw-analysis-run-error">
                学情报告读取失败：{runsError}
              </small>
            )}
          </label>
        )}

        {sourceMode === 'file' && (
          <div className="lw-upload">
            <label className="lw-button file" data-testid="lw-source-upload-label">
              <Upload size={15} aria-hidden />
              {uploading ? '正在上传…' : '一键导入学情分析文件'}
              <input
                type="file"
                data-testid="lw-source-upload"
                accept=".docx,.pdf,.txt,.md"
                disabled={uploading}
                onChange={async (event) => {
                  const file = event.target.files?.[0];
                  event.target.value = '';
                  if (!file) return;
                  setUploading(true);
                  setUploadError(null);
                  try {
                    const result = await services.uploadSource(file);
                    setUploaded(result);
                  } catch (error) {
                    setUploaded(null);
                    setUploadError(describeError(error));
                  } finally {
                    setUploading(false);
                  }
                }}
              />
            </label>
            <small className="lw-note" data-testid="lw-source-upload-hint">
              支持 .docx / .pdf / .txt / .md 的学情说明或学情分析报告；文本会作为固定数据发给模型
              （超长按上限截断并标注）。成绩表（.xlsx/.csv）请先在「学情分析」导入并确认成绩、
              生成学情报告，再改用上面的「分析报告」来源——学生以代称进模型，原始姓名/学号不外发。
            </small>
            {uploaded && (
              <span className="lw-file-chip" data-testid="lw-source-file-chip">
                <FileUp size={14} aria-hidden />
                {uploaded.fileName}
                <button
                  type="button"
                  className="lw-icon-button"
                  aria-label="移除已上传的学情文件"
                  onClick={() => setUploaded(null)}
                >
                  <X size={13} />
                </button>
              </span>
            )}
            {uploadError && (
              <small className="lw-error" data-testid="lw-source-upload-error">
                上传失败：{uploadError}
              </small>
            )}
          </div>
        )}
      </fieldset>

      <fieldset className="lw-source-group">
        <legend>知识点（最多 50 个）</legend>
        <input
          className="lw-search"
          data-testid="lw-kp-search"
          value={pointQuery}
          placeholder="搜索知识点"
          aria-label="搜索知识点"
          onChange={(event) => setPointQuery(event.target.value)}
        />
        {pointsLoading && <p className="lw-note" role="status">正在读取知识点…</p>}
        {pointsError && (
          <p className="lw-error" data-testid="lw-kp-error">
            知识点读取失败：{pointsError}
          </p>
        )}
        {selectedPoints.length > 0 && (
          <div className="lw-selected-points">
            {selectedPoints.map((id) => (
              <span key={id} className="lw-chip">
                {points.find((point) => point.id === id)?.name ?? id}
                <button
                  type="button"
                  className="lw-icon-button"
                  aria-label={`移除知识点 ${points.find((point) => point.id === id)?.name ?? id}`}
                  onClick={() => setSelectedPoints((current) => current.filter((item) => item !== id))}
                >
                  <X size={13} />
                </button>
              </span>
            ))}
          </div>
        )}
        <ul className="lw-point-list" data-testid="lw-kp-list">
          {filteredPoints.map((point) => {
            const checked = selectedPoints.includes(point.id);
            return (
              <li key={point.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={!checked && selectedPoints.length >= 50}
                    data-testid={`lw-kp-option-${point.id}`}
                    onChange={() =>
                      setSelectedPoints((current) =>
                        current.includes(point.id)
                          ? current.filter((item) => item !== point.id)
                          : [...current, point.id],
                      )
                    }
                  />
                  <span>{point.name}</span>
                </label>
              </li>
            );
          })}
        </ul>
      </fieldset>

      <label className="lw-field" htmlFor="lw-requirements">
        <span>
          教师要求<small>（可选，最多 4000 字）</small>
        </span>
        <textarea
          id="lw-requirements"
          data-testid="lw-requirements"
          rows={3}
          maxLength={4000}
          value={requirements}
          placeholder="如：突出对比阅读，控制在 40 分钟，联系本地资源。"
          onChange={(event) => setRequirements(event.target.value)}
        />
      </label>

      <fieldset className="lw-source-group">
        <legend>生成模块</legend>
        <div className="lw-module-chips">
          {LESSON_STREAM_MODULE_KEYS.map((key) => {
            const active = moduleKeys.includes(key);
            return (
              <button
                key={key}
                type="button"
                aria-pressed={active}
                className={`lw-chip-select ${active ? 'selected' : ''}`}
                data-testid={`lw-module-key-${key}`}
                onClick={() =>
                  setModuleKeys((current) =>
                    current.includes(key) ? current.filter((item) => item !== key) : [...current, key],
                  )
                }
              >
                {STREAM_MODULE_LABELS[key]}
              </button>
            );
          })}
        </div>
      </fieldset>

      <div className="lw-generate-actions">
        <button
          type="button"
          className="lw-button primary"
          data-testid="lw-generate-button"
          disabled={streaming || effectiveModules.length === 0}
          onClick={() => void start()}
        >
          {streaming ? <LoaderCircle size={15} className="lw-spin" aria-hidden /> : <Sparkles size={15} aria-hidden />}
          {streaming ? '正在生成…' : candidate ? '重新生成' : '生成教案'}
        </button>
        {streaming && (
          <button
            type="button"
            className="lw-button"
            data-testid="lw-stream-abort"
            onClick={() => abortRef.current?.abort()}
          >
            <Square size={14} aria-hidden />
            中断
          </button>
        )}
        {candidate && !streaming && (
          <>
            <button
              type="button"
              className="lw-button primary"
              data-testid="lw-candidate-adopt-all"
              onClick={() => onAdopt()}
            >
              <Check size={15} aria-hidden />
              采用全部
            </button>
            <button
              type="button"
              className="lw-button"
              data-testid="lw-candidate-discard"
              onClick={onClearCandidate}
            >
              丢弃候选
            </button>
          </>
        )}
      </div>

      {(message || candidate) && (
        <div className="lw-stream-status" data-testid="lw-stream-status" role="status" aria-live="polite">
          {message && (
            <p className={status === 'error' ? 'lw-error' : 'lw-note'}>
              {status === 'error' && <AlertCircle size={14} aria-hidden />} {message}
            </p>
          )}
          {candidate && (
            <ul className="lw-candidate-list">
              {candidateKeys.map((key) => {
                const item = candidate.modules[key];
                if (!item) return null;
                const summary = parsePreview(key);
                return (
                  <li key={key} data-testid={`lw-candidate-${key}`}>
                    <span className={`lw-candidate-state ${item.state}`}>
                      {item.state === 'done'
                        ? '已完成'
                        : item.state === 'streaming'
                          ? '生成中'
                          : item.state === 'error'
                            ? '失败'
                            : '等待'}
                    </span>
                    <strong>{item.label}</strong>
                    <span className="lw-candidate-meta">
                      {summary.labels.length > 0
                        ? `已填充：${summary.labels.join('、')}`
                        : item.text.trim()
                          ? '等待识别字段'
                          : '尚无内容'}
                      {summary.unparsed > 0 ? `（${summary.unparsed} 行未识别，保留在候选原文）` : ''}
                    </span>
                    {item.state === 'error' && item.message && (
                      <span className="lw-error">{item.message}</span>
                    )}
                    <button
                      type="button"
                      className="lw-button small"
                      disabled={item.text.trim().length === 0}
                      data-testid={`lw-candidate-adopt-${key}`}
                      onClick={() => onAdopt([key])}
                    >
                      采用
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {candidate && <p className="lw-note">候选内容已在右侧预览中以「AI 候选」标注，采用前不影响草稿。</p>}
        </div>
      )}
      </div>
    </SettingCard>
  );
}
