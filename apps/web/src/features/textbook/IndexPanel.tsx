'use client';

/**
 * 索引与嵌入面板（R10-FE 2026-10-13）：补上「首次建立嵌入档案 + 发布首个索引代」的界面入口。
 *
 * 背景：教材「提交入库」要求当前已有**已发布的索引代**（新修订并入该代，检索按代限定范围），
 * 而空库首启不会自动建代（需真实探测 Embedding 模型）——此前只有归档脚本/API 能做，
 * 前端没有入口，于是全新环境里导入必然 409 `INDEX_NOT_READY`（死路，用户 2026-10-13 撞到）。
 *
 * 面板三件事：
 * 1) 显示 `GET /textbook-index/status` 的真实状态（索引代 / 嵌入档案 / Qdrant 可达 / 可检索范围 / 重建任务）；
 * 2) 「建立嵌入档案」：列本机 Ollama 模型（默认 bge-m3）→ 探针 → 保存配置；若还没有活动索引代，
 *    接着发起一次受控重建（空库即发布一个空索引代）；
 * 3) 「受控重建」：选已有配置发起（换模型 / 重算全量）。
 *
 * 纪律：模型服务不可达、探针失败、保存冲突等一律**原样显示服务端 code 与 message**，
 * 不伪造成功、不假装可用；重建任务状态以服务端为准（轮询有界，未完成时保留刷新入口）。
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { LoaderCircle, RefreshCw, Sparkles } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import type {
  EmbeddingModelList,
  EmbeddingProfileList,
  EmbeddingSource,
  IndexStatusView,
  JobView,
} from '@/contracts/textbook';
import {
  createEmbeddingProfile,
  getIndexStatus,
  listEmbeddingModels,
  listEmbeddingProfiles,
  startRebuild,
} from '@/services/textbook-api';
import { asApiError, useAsyncResource } from './hooks';
import { newSubmissionId } from './ids';
import { jobStateLabel } from './labels';

/** 首选本机嵌入模型（Ollama 默认）。 */
const PREFERRED_MODEL = 'bge-m3';
/** 云端首选模型与默认维度（百炼 text-embedding-v4）。 */
const PREFERRED_CLOUD_MODEL = 'text-embedding-v4';
const PREFERRED_CLOUD_DIMENSIONS = 1024;

export interface IndexPanelServices {
  getIndexStatus: typeof getIndexStatus;
  listEmbeddingModels: typeof listEmbeddingModels;
  listEmbeddingProfiles: typeof listEmbeddingProfiles;
  createEmbeddingProfile: typeof createEmbeddingProfile;
  startRebuild: typeof startRebuild;
}

const defaultServices: IndexPanelServices = {
  getIndexStatus,
  listEmbeddingModels,
  listEmbeddingProfiles,
  createEmbeddingProfile,
  startRebuild,
};

export function IndexPanel({
  services = defaultServices,
  onClose,
  onChanged,
}: {
  services?: IndexPanelServices;
  onClose: () => void;
  /** 状态变化后通知外层（如刷新库列表/提示可入库）。 */
  onChanged?: () => void;
}) {
  const status = useAsyncResource((signal) => services.getIndexStatus(signal), 'textbook-index-status');
  const profiles = useAsyncResource(
    (signal) => services.listEmbeddingProfiles(signal),
    'textbook-embedding-profiles',
  );
  const models = useAsyncResource(
    (signal) => services.listEmbeddingModels(signal),
    'textbook-embedding-models',
  );

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [source, setSource] = useState<EmbeddingSource>('local');
  const [modelName, setModelName] = useState('');
  const [connectionId, setConnectionId] = useState('');
  const [cloudModel, setCloudModel] = useState(PREFERRED_CLOUD_MODEL);
  const [cloudDimensions, setCloudDimensions] = useState(PREFERRED_CLOUD_DIMENSIONS);
  const [rebuildProfileId, setRebuildProfileId] = useState('');
  const [job, setJob] = useState<JobView | null>(null);

  // 本模块的 useAsyncResource 是三态联合（loading/ready/failed），没有 lastData：
  // 刷新期间回到 loading，不保留上一次数据（与 LibraryBrowser 同口径）。
  const view: IndexStatusView | null = status.state.phase === 'ready' ? status.state.data : null;
  const modelList: EmbeddingModelList | null = models.state.phase === 'ready' ? models.state.data : null;
  const profileList: EmbeddingProfileList | null =
    profiles.state.phase === 'ready' ? profiles.state.data : null;

  /* 模型下拉默认值：优先 bge-m3，其次第一个「具备 embedding 能力」的本机模型。 */
  useEffect(() => {
    if (modelName) return;
    const candidates = (modelList?.models ?? []).filter((item) => item.isEmbeddingCapable);
    if (candidates.length === 0) return;
    const preferred = candidates.find((item) => item.name === PREFERRED_MODEL) ?? candidates[0];
    setModelName(preferred.name);
  }, [modelList, modelName]);

  const cloudConnections = useMemo(
    () => modelList?.cloudConnections ?? [],
    [modelList],
  );
  const cloudModels = useMemo(() => modelList?.cloudModels ?? [], [modelList]);

  /* 来源默认值：有可用的百炼连接时默认云端，否则保持本机。 */
  useEffect(() => {
    if (cloudConnections.some((item) => item.ready)) setSource('cloud');
  }, [cloudConnections]);

  /* 云端连接默认值：优先可调用连接，否则第一个。 */
  useEffect(() => {
    if (connectionId) return;
    const first = cloudConnections.find((item) => item.ready) ?? cloudConnections[0];
    if (first) setConnectionId(first.connectionId);
  }, [cloudConnections, connectionId]);

  const activeCloudModel =
    cloudModels.find((item) => item.name === cloudModel) ?? cloudModels[0] ?? null;

  /* 维度默认值：模型切换后若当前维度不受支持，落回默认 1024（或该模型首项）。 */
  useEffect(() => {
    if (!activeCloudModel) return;
    if (activeCloudModel.dimensions.includes(cloudDimensions)) return;
    setCloudDimensions(
      activeCloudModel.dimensions.includes(PREFERRED_CLOUD_DIMENSIONS)
        ? PREFERRED_CLOUD_DIMENSIONS
        : activeCloudModel.dimensions[0],
    );
  }, [activeCloudModel, cloudDimensions]);

  /* 重建配置下拉默认值：现有（未停用）配置里的第一个。 */
  useEffect(() => {
    if (rebuildProfileId) return;
    const available = (profileList?.profiles ?? []).find((profile) => !profile.retiredAt);
    if (available) setRebuildProfileId(available.profileId);
  }, [profileList, rebuildProfileId]);

  const reloadAll = useCallback(() => {
    status.reload();
    profiles.reload();
    models.reload();
  }, [models, profiles, status]);

  /** 有界轮询重建任务：读到终态或超时即停，未完成时保留「刷新」。 */
  const pollRebuild = useCallback(async () => {
    for (let attempt = 0; attempt < 20; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      try {
        const next = await services.getIndexStatus();
        setJob(next.rebuildJob);
        if (next.rebuildJob === null || next.activeGenerationId !== null) {
          status.reload();
          profiles.reload();
          onChanged?.();
          return;
        }
      } catch (cause) {
        setError(`读取索引状态失败（${asApiError(cause).code}）：${asApiError(cause).message}`);
        return;
      }
    }
    status.reload();
  }, [onChanged, profiles, services, status]);

  /** 建立嵌入档案（探针 + 保存）→ 若无活动索引代则顺手发起一次重建发布首个空代。 */
  async function createProfileAndMaybePublish() {
    if (busy !== null) return;
    if (source === 'local' && !modelName) return;
    if (source === 'cloud' && (!connectionId || !cloudModel)) return;
    setBusy('profile');
    setError(null);
    setNotice(null);
    try {
      const created = await services.createEmbeddingProfile(
        source === 'cloud'
          ? {
              modelName: cloudModel,
              source: 'cloud',
              connectionId,
              dimensions: cloudDimensions,
            }
          : { modelName, source: 'local' },
      );
      const label = created?.providerLabel ? `${created.providerLabel} · ` : '';
      setNotice(
        created
          ? `已保存嵌入档案（${label}${created.modelName} · ${created.dimensions} 维）${
              created.digestKind === 'declared' ? '；云端身份为声明式记录，非权重哈希' : ''
            }。`
          : '嵌入档案已存在（同指纹），直接复用。',
      );
      profiles.reload();
      const latest = await services.getIndexStatus();
      if (latest.activeGenerationId === null) {
        if (
          !window.confirm(
            '还没有已发布的教材索引代。现在发起一次受控重建来发布（当前没有已入库教材时，会发布一个空的起始索引代）？',
          )
        ) {
          status.reload();
          return;
        }
        const profileId = created?.profileId ?? latest.activeProfileId;
        if (!profileId) {
          setError('服务端未返回可用的嵌入配置 id；请刷新后重试。');
          return;
        }
        const started = await services.startRebuild({
          submissionId: newSubmissionId(),
          profileId,
        });
        setJob(started);
        setNotice('已排队受控重建：完成后将发布可检索的索引代（进度见下表）。');
        await pollRebuild();
        if (latest.activeGenerationId === null) {
          const after = await services.getIndexStatus().catch(() => null);
          if (after?.activeGenerationId) {
            setNotice('索引代已发布：现在可以导入教材并在第 4 步提交入库。');
          }
        }
      }
      status.reload();
      onChanged?.();
    } catch (cause) {
      const issue = asApiError(cause);
      setError(`建立嵌入档案失败（${issue.code}）：${issue.message}`);
    } finally {
      setBusy(null);
    }
  }

  /** 受控重建：换模型或重算全量（服务端闸门会拒绝并说明原因）。 */
  async function rebuild() {
    if (busy !== null || !rebuildProfileId) return;
    const target = (profileList?.profiles ?? []).find((item) => item.profileId === rebuildProfileId);
    const isCloud = target?.adapter === 'dashscope';
    if (
      !window.confirm(
        isCloud
          ? `发起受控重建到「${target?.providerLabel ?? '云端'} · ${target?.modelName ?? ''}」？` +
              '重建会把现有教材切块发送给云供应商并可能产生费用；期间新入库会被拒绝，' +
              '完成前检索仍使用旧索引代。'
          : '发起受控重建？重建期间新入库提交会被拒绝；完成前检索仍使用旧索引代。',
      )
    ) {
      return;
    }
    setBusy('rebuild');
    setError(null);
    setNotice(null);
    try {
      const started = await services.startRebuild({
        submissionId: newSubmissionId(),
        profileId: rebuildProfileId,
      });
      setJob(started);
      setNotice('已排队受控重建（进度见下表）。');
      await pollRebuild();
    } catch (cause) {
      const issue = asApiError(cause);
      setError(`发起重建失败（${issue.code}）：${issue.message}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <Modal title="索引与嵌入" onClose={onClose}>
      <div className="textbook-index-panel" data-testid="textbook-index-panel">
        {status.state.phase === 'failed' && (
          <p className="space-banner error" role="alert" data-testid="textbook-index-status-error">
            索引状态读取失败（{status.state.error.code}）：{status.state.error.message}
            <button className="space-button" onClick={status.reload}>
              重试
            </button>
          </p>
        )}

        {view && (
          <div className="textbook-index-status" data-testid="textbook-index-status">
            <p>
              <strong>当前索引代</strong>：
              {view.generation
                ? `${view.generation.generationId.slice(0, 8)}…（${view.generation.state}）· 书册 ${view.generation.documentTotal} · 切块 ${view.generation.chunkTotal}`
                : '还没有已发布的索引代'}
            </p>
            <p>
              <strong>嵌入档案</strong>：
              {view.activeProfileName
                ? `${view.activeProfileName} · ${view.activeProfileDimensions ?? '?'} 维`
                : '还没有配置'}
            </p>
            <p>
              <strong>向量库（Qdrant）</strong>：
              {view.qdrantAvailable ? '可达' : `不可达：${view.qdrantReason ?? '原因未知'}`}
            </p>
            <p>
              <strong>可检索范围</strong>：
              {view.scopeReady ? '已就绪' : `未就绪：${view.scopeReason ?? '原因未知'}`}
            </p>
            {view.rebuildJob && (
              <p data-testid="textbook-index-rebuild-status">
                <strong>重建任务</strong>：{jobStateLabel(job?.state ?? view.rebuildJob.state)}
                {`（任务 ${(job?.jobId ?? view.rebuildJob.jobId).slice(0, 8)}…）`}
              </p>
            )}
            <button className="space-button" onClick={reloadAll}>
              <RefreshCw size={13} aria-hidden /> 刷新状态
            </button>
          </div>
        )}

        {view && view.activeGenerationId === null && (
          <p className="space-banner info" role="note" data-testid="textbook-index-no-generation">
            还没有已发布的索引代：教材「提交入库」会一直失败（INDEX_NOT_READY）。
            先建立嵌入档案并发布起始索引代，再导入教材。
          </p>
        )}

        <section className="textbook-index-section" aria-label="建立嵌入档案">
          <h3>建立嵌入档案</h3>
          <p className="textbook-hint">
            选择嵌入来源：云端用已配置的阿里云百炼连接（默认 text-embedding-v4），本机用
            Ollama（默认 bge-m3）。保存前都会真实探测一次（返回向量维度与连通性）。
          </p>
          <div className="textbook-index-form">
            <label className="textbook-field">
              <span>来源</span>
              <select
                className="space-select"
                aria-label="嵌入来源"
                data-testid="textbook-embedding-source"
                value={source}
                disabled={busy !== null}
                onChange={(event) => setSource(event.target.value as EmbeddingSource)}
              >
                <option value="cloud">云端 · 阿里云百炼</option>
                <option value="local">本机 · Ollama</option>
              </select>
            </label>
          </div>

          {source === 'cloud' && (
            <>
              {cloudConnections.length === 0 ? (
                <p className="space-banner info" role="note" data-testid="textbook-embedding-no-connection">
                  还没有百炼连接：请先到「设置 → 模型与连接」添加阿里云百炼（DashScope）连接并保存
                  API Key，再回到这里选择云端来源。
                </p>
              ) : (
                <div className="textbook-index-form">
                  <label className="textbook-field">
                    <span>连接</span>
                    <select
                      className="space-select"
                      aria-label="百炼连接"
                      data-testid="textbook-embedding-connection"
                      value={connectionId}
                      disabled={busy !== null}
                      onChange={(event) => setConnectionId(event.target.value)}
                    >
                      {cloudConnections.map((item) => (
                        <option key={item.connectionId} value={item.connectionId}>
                          {item.displayName}
                          {item.ready ? '' : '（缺少凭证）'}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="textbook-field">
                    <span>模型</span>
                    <select
                      className="space-select"
                      aria-label="云端嵌入模型"
                      data-testid="textbook-embedding-cloud-model"
                      value={activeCloudModel?.name ?? ''}
                      disabled={busy !== null}
                      onChange={(event) => setCloudModel(event.target.value)}
                    >
                      {cloudModels.map((item) => (
                        <option key={item.name} value={item.name}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="textbook-field">
                    <span>维度</span>
                    <select
                      className="space-select"
                      aria-label="云端向量维度"
                      data-testid="textbook-embedding-cloud-dimensions"
                      value={String(cloudDimensions)}
                      disabled={busy !== null}
                      onChange={(event) => setCloudDimensions(Number(event.target.value))}
                    >
                      {(activeCloudModel?.dimensions ?? []).map((value) => (
                        <option key={value} value={String(value)}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              )}
              <p className="textbook-hint" data-testid="textbook-embedding-cloud-notice">
                保存只发送两条固定短样例用于探测；已有教材只有在你确认「受控重建」后才会上传切块。
                使用云端索引后，教材切块与检索问题都会发送给阿里云百炼，并可能产生费用；
                使用前请确认教材内容可以外发。
              </p>
            </>
          )}

          {source === 'local' && modelList && !modelList.available && (
            <p className="space-banner error" role="alert" data-testid="textbook-embedding-unavailable">
              本机嵌入服务不可达（{modelList.baseUrl}）：{modelList.reason ?? '原因未知'}
              <button className="space-button" onClick={models.reload}>
                重试
              </button>
            </p>
          )}
          {models.state.phase === 'failed' && (
            <p className="space-banner error" role="alert">
              嵌入模型列表读取失败（{models.state.error.code}）：{models.state.error.message}
              <button className="space-button" onClick={models.reload}>
                重试
              </button>
            </p>
          )}
          {source === 'local' && modelList?.available && (
            <div className="textbook-index-form">
              <label className="textbook-field">
                <span>模型</span>
                <select
                  className="space-select"
                  aria-label="嵌入模型"
                  data-testid="textbook-embedding-model"
                  value={modelName}
                  disabled={busy !== null}
                  onChange={(event) => setModelName(event.target.value)}
                >
                  {modelList.models
                    .filter((item) => item.isEmbeddingCapable)
                    .map((item) => (
                      <option key={item.name} value={item.name}>
                        {item.name}（{item.family} · {item.parameterSize}）
                      </option>
                    ))}
                </select>
              </label>
            </div>
          )}

          {((source === 'local' && modelList?.available) ||
            (source === 'cloud' && cloudConnections.length > 0)) && (
            <div className="textbook-index-form">
              <button
                className="space-button primary"
                data-testid="textbook-embedding-save"
                disabled={
                  busy !== null ||
                  (source === 'local' ? !modelName : !connectionId || !cloudModel)
                }
                onClick={() => void createProfileAndMaybePublish()}
              >
                {busy === 'profile' ? (
                  <LoaderCircle size={14} className="lw-spin" aria-hidden />
                ) : (
                  <Sparkles size={14} aria-hidden />
                )}
                {busy === 'profile' ? '检测并保存中…' : '检测并保存配置'}
              </button>
            </div>
          )}
        </section>

        <section className="textbook-index-section" aria-label="受控重建">
          <h3>受控重建</h3>
          <p className="textbook-hint">
            换嵌入模型或重算全量时用；重建期间新入库会被拒绝，检索仍用旧索引代。
            已有教材要迁移到云端向量空间，必须在这里手动发起并再次确认。
          </p>
          {profileList && profileList.profiles.filter((item) => !item.retiredAt).length === 0 && (
            <p className="textbook-hint">还没有可用配置：先在上面的「建立嵌入档案」保存一个。</p>
          )}
          {profileList && profileList.profiles.filter((item) => !item.retiredAt).length > 0 && (
            <div className="textbook-index-form">
              <label className="textbook-field">
                <span>配置</span>
                <select
                  className="space-select"
                  aria-label="重建配置"
                  data-testid="textbook-rebuild-profile"
                  value={rebuildProfileId}
                  disabled={busy !== null}
                  onChange={(event) => setRebuildProfileId(event.target.value)}
                >
                  {profileList.profiles
                    .filter((item) => !item.retiredAt)
                    .map((item) => (
                      <option key={item.profileId} value={item.profileId}>
                        {item.providerLabel ? `${item.providerLabel} · ` : '本机 · '}
                        {item.modelName}（{item.dimensions} 维）
                        {item.installed ? '' : '（当前不可用）'}
                        {item.profileId === profileList.activeProfileId ? '（当前）' : ''}
                      </option>
                    ))}
                </select>
              </label>
              <button
                className="space-button"
                data-testid="textbook-rebuild-start"
                disabled={busy !== null || !rebuildProfileId}
                onClick={() => void rebuild()}
              >
                {busy === 'rebuild' ? '发起中…' : '发起受控重建'}
              </button>
            </div>
          )}
        </section>

        {notice && (
          <p className="space-banner info" role="status" data-testid="textbook-index-notice">
            {notice}
          </p>
        )}
        {error && (
          <p className="space-banner error" role="alert" data-testid="textbook-index-error">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}
