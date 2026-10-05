'use client';
import { useEffect, useState } from 'react';
import { useLessonEditor } from '../model/EditorContext';
import { useLessonDocument } from '../model/DocumentContext';
import { DocumentsPanel } from './DocumentsPanel';
import { SourcePanel, initialGenerationInputs } from './SourcePanel';
import { ProposalPanel } from './ProposalPanel';
import { allowedLessonFields } from '@/contracts/lesson-plans';
import { stablePayloadKey } from '@/features/assessments/hooks';
export function ServerControls() {
  const editor = useLessonEditor(), doc = useLessonDocument();
  const [inputs, setInputs] = useState(initialGenerationInputs);
  const server = editor.server;
  useEffect(() => { if (server?.ready && server.cache && stablePayloadKey(server.cache.context) !== stablePayloadKey(doc.selection.context)) doc.setSelection({ ...doc.selection, context: structuredClone(server.cache.context) }); }, [server, doc]);
  return <div className="lesson-server-controls">
    <div className="lesson-provenance" aria-label="教案正文来源"><span>{editor.sourceLabel}</span><small>{editor.history?.source ?? (server?.dirty ? server.cache?.source : doc.view?.currentRevision.source) ?? '本地规则 / 人工编辑'} · {editor.history?.reviewState ?? doc.view?.currentRevision.reviewState ?? '本地稿'}</small>{server && <small>固定学情 {server.cache?.context?.analysisRunId ?? '未关联'} → 教案 {server.cache?.serverRevisionId} → 调整建议 {doc.candidateId ?? doc.view?.currentRevision.acceptedProposalId ?? '尚未生成'}</small>}</div>
    {server && <div className="lesson-sync-actions"><span role="status">{editor.saveStatus}</span><button className="button subtle" disabled={server.busy || server.syncState === 'cache_error' || (server.syncState === 'conflict' && !server.unknown)} onClick={() => void server.save()}>{server.unknown && server.cache?.operations.save ? '重试原保存包' : '保存后台稿'}</button><button className="button subtle" disabled={server.busy} onClick={() => void server.refreshLatest()}>读取后台最新版本</button></div>}
    {server?.syncState === 'cache_error' && <div className="lesson-actions"><button className="button primary" disabled={server.busy || server.exclusive || !server.canRetryRecovery} onClick={() => void server.retryRecoveryWrite()}>重试恢复缓存</button>{server.readBlocked && <p className="lesson-help">原缓存读取失败，不能覆盖。可先用“导出教案→备份草稿”保留当前正文；正文JSON不包含后台原操作包，请修复存储后再恢复会话。</p>}</div>}
    {server?.error && <p className="lesson-inline-error" role="alert">{server.error.message}</p>}{server?.notice && <p className="lesson-help" role="status">{server.notice}</p>}
    {server?.syncState === 'conflict' && <details className="lesson-server-panel" open><summary>版本冲突：人工对照</summary><div className="lesson-panel-body"><p>本机基于 v{server.cache?.serverRevision} · {server.cache?.serverRevisionId}；可信后台读取 v{server.latest?.revision} · {server.latest?.currentRevisionId}。</p><p>新写暂停。明确采用后台基线后可保留本机正文另存，或恢复后台正文；不会自动合并。</p>{allowedLessonFields.map((field) => <div className="lesson-diff-columns" key={field}><div><strong>本机 {field}</strong><pre>{JSON.stringify(editor.data[field], null, 2)}</pre></div><div><strong>后台 {field}</strong><pre>{JSON.stringify(server.latest?.currentRevision.data[field], null, 2)}</pre></div></div>)}<div className="lesson-actions"><button className="button primary" disabled={server.busy || server.unknown || !server.latest || server.latest.revision <= (server.cache?.serverRevision ?? 0)} onClick={() => server.chooseLatest(true)}>明确采用后台基线，保留本机正文</button><button className="button subtle" disabled={server.busy || server.unknown || !server.latest || server.latest.revision <= (server.cache?.serverRevision ?? 0)} onClick={() => server.chooseLatest(false)}>明确恢复后台正文</button></div></div></details>}
    <DocumentsPanel /><SourcePanel value={inputs} onChange={setInputs} />{server && <ProposalPanel inputs={inputs} />}
  </div>;
}
