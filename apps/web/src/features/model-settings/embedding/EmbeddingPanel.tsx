'use client';

/**
 * Embedding 模型面板（设置页「模型与连接」内的独立区域，无 props）。
 *
 * 三个真实来源：
 * - 当前模型/索引状态：`GET /textbook-index/status`（重建期间按服务端状态轮询）；
 * - 可用配置：`GET /embedding-models` + `POST /embedding-probes`（实测）+ `POST /embedding-profiles`（保存）；
 * - 重建：`POST /textbook-index/rebuilds`（`submissionId` 幂等键：请求级重试复用，新意图换新 id）。
 *
 * 配置生命周期：`POST /embedding-profiles/{id}/retire`（停用：不再用于新的重建，历史索引代保留）
 * 与 `DELETE /embedding-profiles/{id}`（受守卫硬删：被索引代引用时服务端 409
 * `EMBEDDING_PROFILE_IN_USE`，原样显示服务端 message 并提示改用停用，列表不变）。
 *
 * 口径：检测通过只代表接口能力（维度/身份/稳定性），不代表检索质量已验收；
 * Qdrant 或本机模型不可用时如实显示原因，不回退、不伪造成功。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type {
  EmbeddingModelCandidate,
  EmbeddingProfileList,
  EmbeddingProfileView,
  EmbeddingProbeView,
  IndexStatusView,
} from '@/contracts/textbook';
// 页内共享样式：只读引入既有共享层（space-*）与教材模块的字段类同源实现见 embedding.css
import '@/components/layout/space.css';
import {
  cancelJob,
  createEmbeddingProfile,
  deleteEmbeddingProfile,
  getIndexStatus,
  listEmbeddingModels,
  listEmbeddingProfiles,
  probeEmbeddingModel,
  retireEmbeddingProfile,
  startRebuild,
} from '@/services/textbook-api';
import {
  asApiError,
  errorText,
  useAsyncResource,
  usePolling,
  type AsyncState,
} from '@/features/textbook/hooks';
import { newSubmissionId } from '@/features/textbook/ids';
import { isJobActive, jobStateLabel, progressPercent } from '@/features/textbook/labels';
import './styles/embedding.css';

/** 重建状态轮询间隔（≥1s；只在存在进行中任务时轮询）。 */
const REBUILD_POLL_MS = 2000;

type ProbeState =
  | { phase: 'idle' }
  | { phase: 'busy'; modelName: string }
  | { phase: 'ready'; modelName: string; view: EmbeddingProbeView }
  | { phase: 'failed'; modelName: string; message: string };

function candidateLabel(candidate: EmbeddingModelCandidate): string {
  const size = candidate.parameterSize ? ` · ${candidate.parameterSize}` : '';
  return `${candidate.name}${size}`;
}

export function EmbeddingPanel() {
  const models = useAsyncResource((signal) => listEmbeddingModels(signal), 'embedding-models');
  const profiles = useAsyncResource(
    (signal) => listEmbeddingProfiles(signal),
    'embedding-profiles',
  );

  const [statusState, setStatusState] = useState<AsyncState<IndexStatusView>>({ phase: 'loading' });
  const [statusPollError, setStatusPollError] = useState<string | null>(null);
  const [probe, setProbe] = useState<ProbeState>({ phase: 'idle' });
  const [queryPrefix, setQueryPrefix] = useState('');
  const [documentPrefix, setDocumentPrefix] = useState('');
  const [normalization, setNormalization] = useState<'none' | 'l2'>('none');
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [profileId, setProfileId] = useState('');
  const [rebuildBusy, setRebuildBusy] = useState(false);
  const [rebuildError, setRebuildError] = useState<string | null>(null);
  const [rebuildSubmitted, setRebuildSubmitted] = useState(false);
  const [profileActionId, setProfileActionId] = useState<string | null>(null);
  const [profileActionError, setProfileActionError] = useState<{
    profileId: string;
    message: string;
  } | null>(null);
  const rebuildSubmissionRef = useRef<string | null>(null);

  const loadStatus = useCallback(async (background: boolean) => {
    if (!background) setStatusState({ phase: 'loading' });
    try {
      const data = await getIndexStatus();
      setStatusState({ phase: 'ready', data });
      setStatusPollError(null);
    } catch (error) {
      if (background) setStatusPollError(errorText(error));
      else setStatusState({ phase: 'failed', error: asApiError(error) });
    }
  }, []);

  useEffect(() => {
    void loadStatus(false);
  }, [loadStatus]);

  const rebuildJob = statusState.phase === 'ready' ? statusState.data.rebuildJob : null;
  const rebuilding = Boolean(rebuildJob && isJobActive(rebuildJob.state));
  usePolling(() => loadStatus(true), rebuilding, REBUILD_POLL_MS);

  const profilesData: AsyncState<EmbeddingProfileList> = profiles.state;
  const activeProfileId = statusState.phase === 'ready' ? statusState.data.activeProfileId : null;

  // 配置选择默认跟随当前生效配置；用户一旦手选则不再覆盖
  useEffect(() => {
    if (profileId) return;
    const available = profilesData.phase === 'ready' ? profilesData.data.profiles : [];
    const preferred =
      available.find((item) => item.profileId === activeProfileId) ??
      available.find((item) => !item.retiredAt && item.installed) ??
      available[0];
    if (preferred) setProfileId(preferred.profileId);
  }, [profileId, profilesData, activeProfileId]);

  const current = statusState.phase === 'ready' ? statusState.data : null;
  const modelList = models.state.phase === 'ready' ? models.state.data : null;
  const profileList = profilesData.phase === 'ready' ? profilesData.data.profiles : [];
  const selectedProfile = profileList.find((item) => item.profileId === profileId) ?? null;
  const usable = Boolean(current?.activeProfileId) && Boolean(current?.qdrantAvailable);

  const rebuildPercent = useMemo(() => {
    if (!rebuildJob) return 0;
    return progressPercent(rebuildJob.progress.chunksDone, rebuildJob.progress.chunksTotal);
  }, [rebuildJob]);

  async function detect(candidate: EmbeddingModelCandidate) {
    setProbe({ phase: 'busy', modelName: candidate.name });
    setSaveNotice(null);
    setSaveError(null);
    try {
      const view = await probeEmbeddingModel({ modelName: candidate.name });
      setProbe({ phase: 'ready', modelName: candidate.name, view });
    } catch (error) {
      setProbe({ phase: 'failed', modelName: candidate.name, message: errorText(error) });
    }
  }

  async function saveProfile() {
    if (probe.phase !== 'ready') return;
    setSaveBusy(true);
    setSaveError(null);
    setSaveNotice(null);
    try {
      const saved = await createEmbeddingProfile({
        modelName: probe.modelName,
        queryPrefix,
        documentPrefix,
        normalization,
      });
      setSaveNotice(
        saved
          ? `已保存 Embedding 配置（${saved.modelName} · ${saved.dimensions} 维）。`
          : '已保存 Embedding 配置；配置列表以服务端返回为准。',
      );
      profiles.reload();
      await loadStatus(false);
    } catch (error) {
      setSaveError(errorText(error));
    } finally {
      setSaveBusy(false);
    }
  }

  async function beginRebuild() {
    if (!profileId) {
      setRebuildError('请先选择要使用的 Embedding 配置。');
      return;
    }
    // 同一次点击的请求级重试复用同一提交键；新意图（重新发起）换新键
    rebuildSubmissionRef.current = rebuildSubmissionRef.current ?? newSubmissionId();
    setRebuildBusy(true);
    setRebuildError(null);
    try {
      await startRebuild({ submissionId: rebuildSubmissionRef.current, profileId });
      rebuildSubmissionRef.current = null;
      setRebuildSubmitted(true);
      await loadStatus(true);
    } catch (error) {
      setRebuildError(errorText(error));
    } finally {
      setRebuildBusy(false);
    }
  }

  function restartRebuild() {
    rebuildSubmissionRef.current = null;
    setRebuildSubmitted(false);
    void beginRebuild();
  }

  async function cancelRebuild(jobId: string) {
    setRebuildBusy(true);
    setRebuildError(null);
    try {
      await cancelJob(jobId);
      await loadStatus(true);
    } catch (error) {
      setRebuildError(`取消重建失败：${errorText(error)}`);
    } finally {
      setRebuildBusy(false);
    }
  }

  /**
   * 停用配置（二次确认）：服务端幂等；停用后不再用于新的入库与重建，历史索引代保留。
   * 成功后刷新配置列表取服务端权威的 `retiredAt`；失败不改列表，只显示原因。
   */
  async function retireProfile(item: EmbeddingProfileView) {
    const confirmed = window.confirm(
      `停用 Embedding 配置「${item.modelName} · ${item.dimensions} 维」？停用后不能再用于新的重建，历史索引代保留。`,
    );
    if (!confirmed) return;
    setProfileActionId(item.profileId);
    setProfileActionError(null);
    try {
      await retireEmbeddingProfile(item.profileId);
      profiles.reload();
    } catch (error) {
      const apiError = asApiError(error);
      setProfileActionError({
        profileId: item.profileId,
        message: `停用配置失败（${apiError.code}）：${apiError.message}`,
      });
    } finally {
      setProfileActionId(null);
    }
  }

  /**
   * 受守卫删除（二次确认）：仅当没有任何索引代引用该配置才允许硬删。
   * 被引用时服务端 409 `EMBEDDING_PROFILE_IN_USE`：原样显示服务端 message（提示改用停用），
   * 列表保持不变。成功后刷新配置列表；若删掉的正是当前选中项，清空选择让列表重新选默认值。
   */
  async function removeProfile(item: EmbeddingProfileView) {
    const confirmed = window.confirm(
      `删除 Embedding 配置「${item.modelName} · ${item.dimensions} 维」？仅当没有任何索引代引用该配置时可删除；被引用时请改用停用。`,
    );
    if (!confirmed) return;
    setProfileActionId(item.profileId);
    setProfileActionError(null);
    try {
      await deleteEmbeddingProfile(item.profileId);
      setProfileId((current) => (current === item.profileId ? '' : current));
      profiles.reload();
    } catch (error) {
      const apiError = asApiError(error);
      setProfileActionError({
        profileId: item.profileId,
        message: `删除配置失败（${apiError.code}）：${apiError.message}`,
      });
    } finally {
      setProfileActionId(null);
    }
  }

  return (
    <div className="embedding-panel">
      {/* ===== 当前模型 ===== */}
      <section className="embedding-section" aria-labelledby="embedding-current">
        <h3 id="embedding-current">当前 Embedding 模型</h3>
        {statusState.phase === 'loading' && (
          <div className="space-skeleton" style={{ height: 84 }} aria-hidden />
        )}
        {statusState.phase === 'failed' && (
          <div className="space-banner error" role="alert">
            索引状态读取失败（{statusState.error.code}）：{statusState.error.message}
            <div className="embedding-actions">
              <button className="space-button" onClick={() => void loadStatus(false)}>
                重试读取索引状态
              </button>
            </div>
          </div>
        )}
        {current && (
          <>
            <div className="space-meta-row">
              <span className={`space-chip ${usable ? 'green' : 'amber'}`}>
                {usable ? '可用' : '不可用'}
              </span>
              <span className="space-chip">模型：{current.activeProfileName ?? '未配置'}</span>
              <span className="space-chip">实测维度：{current.activeProfileDimensions ?? '—'}</span>
              <span className="space-chip">配置 {current.activeProfileId ?? '—'}</span>
              <span className={`space-chip ${current.qdrantAvailable ? 'green' : 'amber'}`}>
                向量库：{current.qdrantAvailable ? '可用' : '不可用'}
              </span>
            </div>
            <div className="space-meta-row">
              <span className="space-chip">索引代：{current.activeGenerationId ?? '无'}</span>
              {current.generation && (
                <>
                  <span className="space-chip">代状态：{current.generation.state}</span>
                  <span className="space-chip">块 {current.generation.chunkTotal}</span>
                  <span className="space-chip">教材 {current.generation.documentTotal}</span>
                  <span className="space-chip">
                    发布：{current.generation.publishedAt ?? '未发布'}
                  </span>
                </>
              )}
              <span className="space-chip">历史代数 {current.generationCount}</span>
              <span className={`space-chip ${current.scopeReady ? 'green' : 'amber'}`}>
                任教范围：{current.scopeReady ? '已就绪' : '未就绪'}
              </span>
            </div>
            {!current.qdrantAvailable && (
              <div className="space-banner error" role="alert">
                向量库（Qdrant）不可用：{current.qdrantReason ?? '（服务端未提供原因）'}
                。检索与重建在向量库恢复前不会成功，界面不会据此显示空结果或成功。
              </div>
            )}
            {!current.activeProfileId && (
              <p className="space-banner info" role="note">
                还没有生效的 Embedding 配置：先在下方「检测」并「保存配置」，再发起重建。
              </p>
            )}
            {current.scopeReason && (
              <p className="textbook-hint">任教范围说明：{current.scopeReason}</p>
            )}
          </>
        )}
      </section>

      {/* ===== 可用配置 ===== */}
      <section className="embedding-section" aria-labelledby="embedding-models">
        <h3 id="embedding-models">可用配置</h3>
        <p className="textbook-hint">
          只列举本机已安装模型；检测会真实调用本机 Embedding
          接口并核对维度、非零、有限与身份稳定性。
          <strong>检测通过只代表接口能力，不代表检索质量已验收</strong>
          （检索质量需在真实语料上验收）。
        </p>

        {models.state.phase === 'loading' && (
          <div className="space-skeleton" style={{ height: 72 }} aria-hidden />
        )}
        {models.state.phase === 'failed' && (
          <div className="space-banner error" role="alert">
            模型列表读取失败（{models.state.error.code}）：{models.state.error.message}
            <div className="embedding-actions">
              <button className="space-button" onClick={models.reload}>
                重试读取模型列表
              </button>
            </div>
          </div>
        )}
        {modelList && (
          <>
            <div className="space-meta-row">
              <span className="space-chip">本机地址：{modelList.baseUrl}</span>
              <span className={`space-chip ${modelList.available ? 'green' : 'amber'}`}>
                {modelList.available ? '服务可用' : '服务不可用'}
              </span>
            </div>
            {!modelList.available && (
              <div className="space-banner error" role="alert">
                本机 Embedding 服务不可用：{modelList.reason ?? '（服务端未提供原因）'}
              </div>
            )}
            {modelList.models.length === 0 ? (
              <p className="space-banner info" role="note">
                {modelList.available
                  ? '本机没有已安装模型：请先在 Ollama 等本机服务中安装 Embedding 模型。'
                  : '服务不可用时无法列举模型；下方列表不会显示占位候选。'}
              </p>
            ) : (
              <ul className="embedding-model-list">
                {modelList.models.map((candidate) => (
                  <li className="embedding-model-item" key={candidate.name}>
                    <div className="embedding-model-head">
                      <strong>{candidateLabel(candidate)}</strong>
                      <span
                        className={`space-chip ${candidate.isEmbeddingCapable ? 'green' : 'amber'}`}
                      >
                        {candidate.isEmbeddingCapable ? 'Embedding 模型' : '非 Embedding 模型'}
                      </span>
                    </div>
                    <div className="space-meta-row">
                      <span className="space-chip">家族 {candidate.family || '—'}</span>
                      <span className="space-chip">摘要 {candidate.digest.slice(0, 12)}…</span>
                      <button
                        className="space-button"
                        onClick={() => void detect(candidate)}
                        disabled={probe.phase === 'busy'}
                      >
                        {probe.phase === 'busy' && probe.modelName === candidate.name
                          ? '检测中…'
                          : '检测'}
                      </button>
                    </div>
                    {probe.phase === 'failed' && probe.modelName === candidate.name && (
                      <div className="space-banner error" role="alert">
                        检测失败（{candidate.name}）：{probe.message}
                        <div className="embedding-actions">
                          <button className="space-button" onClick={() => void detect(candidate)}>
                            重试检测
                          </button>
                        </div>
                      </div>
                    )}
                    {probe.phase === 'ready' && probe.modelName === candidate.name && (
                      <div className="embedding-probe">
                        <div className="space-meta-row">
                          <span className="space-chip blue">实测维度 {probe.view.dimensions}</span>
                          <span className="space-chip">距离 {probe.view.distance}</span>
                          <span className="space-chip">样本 {probe.view.sampleCount}</span>
                          <span className={`space-chip ${probe.view.nonZero ? 'green' : 'amber'}`}>
                            {probe.view.nonZero ? '非零通过' : '存在零向量'}
                          </span>
                          <span className={`space-chip ${probe.view.finite ? 'green' : 'amber'}`}>
                            {probe.view.finite ? '有限值通过' : '存在非有限值'}
                          </span>
                          <span
                            className={`space-chip ${probe.view.stableDigest ? 'green' : 'amber'}`}
                          >
                            {probe.view.stableDigest ? '身份稳定' : '身份变化'}
                          </span>
                          <span className="space-chip">
                            模型身份 {probe.view.modelManifestDigest.slice(0, 12)}…
                          </span>
                          {probe.view.alreadyConfigured && (
                            <span className="space-chip blue">
                              已配置
                              {probe.view.existingProfileId
                                ? `（${probe.view.existingProfileId}）`
                                : ''}
                            </span>
                          )}
                        </div>
                        <div className="embedding-prefix-form">
                          <label className="textbook-field">
                            <span>查询前缀</span>
                            <input
                              value={queryPrefix}
                              maxLength={200}
                              onChange={(event) => setQueryPrefix(event.target.value)}
                              placeholder="一般为空；模型要求时填写"
                            />
                          </label>
                          <label className="textbook-field">
                            <span>文档前缀</span>
                            <input
                              value={documentPrefix}
                              maxLength={200}
                              onChange={(event) => setDocumentPrefix(event.target.value)}
                              placeholder="一般为空"
                            />
                          </label>
                          <label className="textbook-field">
                            <span>归一化</span>
                            <select
                              className="space-select"
                              value={normalization}
                              onChange={(event) =>
                                setNormalization(event.target.value === 'l2' ? 'l2' : 'none')
                              }
                            >
                              <option value="none">不归一化</option>
                              <option value="l2">L2 归一化</option>
                            </select>
                          </label>
                          <button
                            className="space-button primary"
                            onClick={() => void saveProfile()}
                            disabled={saveBusy}
                          >
                            {saveBusy ? '保存中…' : '保存配置'}
                          </button>
                        </div>
                        <p className="textbook-hint">
                          检测通过只代表该模型的接口能力（维度/身份/稳定性）符合要求，不代表检索质量已验收。
                        </p>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}

        {saveError && (
          <div className="space-banner error" role="alert">
            保存配置失败：{saveError}
          </div>
        )}
        {saveNotice && (
          <p className="space-banner info" role="status">
            {saveNotice}
          </p>
        )}

        <h4 className="embedding-subhead">已保存配置</h4>
        {profilesData.phase === 'loading' && (
          <div className="space-skeleton" style={{ height: 64 }} aria-hidden />
        )}
        {profilesData.phase === 'failed' && (
          <div className="space-banner error" role="alert">
            配置列表读取失败（{profilesData.error.code}）：{profilesData.error.message}
            <div className="embedding-actions">
              <button className="space-button" onClick={profiles.reload}>
                重试读取已保存配置
              </button>
            </div>
          </div>
        )}
        {profilesData.phase === 'ready' && profileList.length === 0 && (
          <p className="textbook-hint">还没有已保存的 Embedding 配置。</p>
        )}
        {profilesData.phase === 'ready' && profileList.length > 0 && (
          <ul className="embedding-profile-list">
            {profileList.map((item) => (
              <li className="embedding-profile-item" key={item.profileId}>
                <label className="textbook-check">
                  <input
                    type="radio"
                    name="embedding-profile"
                    checked={profileId === item.profileId}
                    onChange={() => setProfileId(item.profileId)}
                  />
                  {item.modelName} · {item.dimensions} 维
                </label>
                <div className="space-meta-row">
                  <span className="space-chip">配置 {item.profileId}</span>
                  <span className="space-chip">指纹 {item.fingerprint.slice(0, 12)}…</span>
                  <span className={`space-chip ${item.isActive ? 'green' : ''}`}>
                    {item.isActive ? '当前生效' : '未生效'}
                  </span>
                  <span className={`space-chip ${item.installed ? 'green' : 'amber'}`}>
                    {item.installed ? '本机已安装' : '本机缺失'}
                  </span>
                  {item.retiredAt && (
                    <span className="space-chip amber">已停用 {item.retiredAt}</span>
                  )}
                </div>
                <div className="embedding-actions">
                  {!item.retiredAt && (
                    <button
                      className="space-button"
                      aria-label={`停用配置 ${item.profileId}`}
                      disabled={profileActionId === item.profileId}
                      onClick={() => void retireProfile(item)}
                    >
                      {profileActionId === item.profileId ? '处理中…' : '停用'}
                    </button>
                  )}
                  <button
                    className="space-button danger"
                    aria-label={`删除配置 ${item.profileId}`}
                    disabled={profileActionId === item.profileId}
                    onClick={() => void removeProfile(item)}
                  >
                    删除
                  </button>
                </div>
                {profileActionError?.profileId === item.profileId && (
                  <div className="space-banner error" role="alert">
                    {profileActionError.message}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ===== 重建 ===== */}
      <section className="embedding-section" aria-labelledby="embedding-rebuild">
        <h3 id="embedding-rebuild">重建并切换</h3>
        <p className="textbook-hint">
          重建使用所选配置对本机全部教材重新向量化；发布是原子的，旧索引代在新代完成前继续可用。
        </p>
        <div className="space-meta-row">
          <span className="space-chip">
            当前配置：
            {selectedProfile
              ? `${selectedProfile.modelName} · ${selectedProfile.dimensions} 维`
              : '未选择'}
          </span>
          {selectedProfile && !selectedProfile.installed && (
            <span className="space-chip amber">该配置模型本机缺失</span>
          )}
        </div>
        <div className="embedding-actions">
          <button
            className="space-button primary"
            onClick={() => void beginRebuild()}
            disabled={rebuildBusy || !profileId || rebuilding}
          >
            {rebuildBusy ? '提交中…' : rebuilding ? '重建进行中…' : '开始重建'}
          </button>
          <button className="space-button" onClick={() => void loadStatus(true)}>
            刷新状态
          </button>
        </div>
        {rebuildError && (
          <div className="space-banner error" role="alert">
            {rebuildError}
            <div className="embedding-actions">
              <button
                className="space-button"
                onClick={() => void beginRebuild()}
                disabled={rebuildBusy}
              >
                重试提交（同一提交键）
              </button>
            </div>
          </div>
        )}
        {rebuildSubmitted && !rebuildJob && (
          <p className="space-banner info" role="status">
            已提交重建请求；任务视图以服务端返回为准，稍后刷新状态即可看到阶段与进度。
          </p>
        )}
        {statusPollError && (
          <div className="space-banner error" role="alert">
            状态轮询失败（显示的是上一次成功读取的结果）：{statusPollError}
            <div className="embedding-actions">
              <button className="space-button" onClick={() => void loadStatus(true)}>
                立即刷新
              </button>
            </div>
          </div>
        )}

        {rebuildJob && (
          <div className="embedding-rebuild">
            <div className="space-meta-row">
              <span className={`space-chip ${rebuildJob.state === 'failed' ? 'amber' : 'blue'}`}>
                阶段：{jobStateLabel(rebuildJob.state)}
              </span>
              <span className="space-chip">任务 {rebuildJob.jobId}</span>
              <span className="space-chip">
                已完成教材 {rebuildJob.progress.documentsDone}/{rebuildJob.progress.documentsTotal}
              </span>
              <span className="space-chip">
                已完成块 {rebuildJob.progress.chunksDone}/{rebuildJob.progress.chunksTotal}
              </span>
              <span className="space-chip">第 {rebuildJob.attempt} 次尝试</span>
              {rebuildJob.targetGenerationId && (
                <span className="space-chip">目标索引代 {rebuildJob.targetGenerationId}</span>
              )}
            </div>
            <div
              className="embedding-progress"
              role="progressbar"
              aria-label="重建分块进度"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={rebuildPercent}
            >
              <div style={{ width: `${rebuildPercent}%` }} />
            </div>
            {rebuildJob.errorCode || rebuildJob.errorMessage ? (
              <p className="embedding-error">
                失败原因：{rebuildJob.errorCode ? `${rebuildJob.errorCode} · ` : ''}
                {rebuildJob.errorMessage ?? '（服务端未提供说明）'}
              </p>
            ) : null}
            <div className="embedding-actions">
              {isJobActive(rebuildJob.state) && (
                <button
                  className="space-button"
                  onClick={() => void cancelRebuild(rebuildJob.jobId)}
                  disabled={rebuildBusy}
                >
                  取消重建
                </button>
              )}
              {rebuildJob.state === 'failed' && (
                <button
                  className="space-button"
                  onClick={restartRebuild}
                  disabled={rebuildBusy || !profileId}
                >
                  重新发起
                </button>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
