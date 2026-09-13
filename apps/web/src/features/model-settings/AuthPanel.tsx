'use client';

import { useEffect, useRef, useState } from 'react';
import { AlertCircle, Check, Loader2, LogOut, RefreshCw, ShieldCheck, X } from 'lucide-react';
import {
  AUTH_STATE_LABELS,
  type AuthActionResult,
  type AuthStatus,
  type ModelConnectionView,
} from '@/contracts/model-settings';
import { cancelAuth, getAuthStatus, logoutAuth, startAuth } from '@/services/model-settings-api';

/**
 * 认证状态面板：四态（未连接/等待授权/已连接/需要处理）。
 *
 * 只在供应商确实使用托管认证时出现。轮询仅在 authorizing 期间进行；取消后不会
 * 被迟到的回调复活（后端按 operationId + 取消标记判定）；不可用时如实说明原因
 * 和下一步，不显示一个点了没反应的按钮。
 */
export function AuthPanel({
  connection,
  onChanged,
}: {
  connection: ModelConnectionView;
  onChanged: () => void;
}) {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [action, setAction] = useState<AuthActionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const epoch = useRef(0);

  const providerId = connection.providerId;
  const usesManagedAuth = providerId === 'openai_codex' || providerId === 'github_copilot';

  useEffect(() => {
    if (!usesManagedAuth) return;
    const current = ++epoch.current;
    void getAuthStatus(connection.id)
      .then((next) => {
        if (current === epoch.current) setStatus(next);
      })
      .catch(() => {
        if (current === epoch.current) setStatus(null);
      });
    const requestEpoch = epoch;
    return () => {
      requestEpoch.current++;
    };
  }, [connection.id, usesManagedAuth]);

  // authorizing 期间轮询；到达终态即停，避免无意义请求
  useEffect(() => {
    if (!usesManagedAuth || status?.connection !== 'authorizing') return;
    const current = epoch.current;
    const timer = window.setInterval(() => {
      void getAuthStatus(connection.id)
        .then((next) => {
          if (current !== epoch.current) return;
          setStatus(next);
          if (next.connection !== 'authorizing') onChanged();
        })
        .catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [usesManagedAuth, status?.connection, connection.id, onChanged]);

  if (!usesManagedAuth) return null;

  async function run(fn: () => Promise<AuthActionResult>) {
    if (busy) return;
    setBusy(true);
    setAction(null);
    try {
      const result = await fn();
      setAction(result);
      if (result.status) setStatus(result.status);
      onChanged();
    } catch (error) {
      setAction({
        ok: false,
        message: error instanceof Error ? error.message : '操作失败，请重试。',
      });
    } finally {
      setBusy(false);
    }
  }

  const state = status?.connection ?? 'disconnected';
  const unavailable = status?.available === false;

  return (
    <section className="detail-section auth-section" aria-label="认证状态">
      <h3>认证</h3>
      <div className="auth-row">
        <span className={`auth-state auth-state-${state}`}>
          {state === 'connected' && <ShieldCheck size={14} />}
          {state === 'authorizing' && <Loader2 size={14} className="spin" />}
          {state === 'disconnected' && <AlertCircle size={14} />}
          {state === 'error' && <AlertCircle size={14} />}
          {AUTH_STATE_LABELS[state]}
        </span>
        {status?.userLabel && <span className="auth-account">{status.userLabel}</span>}
        {status?.note && <span className="auth-note">{status.note}</span>}
      </div>

      {unavailable && status?.unavailableReason && (
        <p className="settings-feedback error" role="status">
          {status.unavailableReason}
        </p>
      )}

      {status?.connection === 'authorizing' && status.authorizeUrl && (
        <p className="settings-hint">
          在浏览器中打开授权页面完成登录（剩余约 {status.expiresIn ?? 0} 秒）。
          <a href={status.authorizeUrl} target="_blank" rel="noreferrer">
            打开授权页面
          </a>
        </p>
      )}

      <div className="auth-actions">
        {state !== 'connected' && !unavailable && (
          <button
            className="button primary"
            disabled={busy}
            onClick={() => void run(() => startAuth(connection.id))}
          >
            {state === 'authorizing' ? '重新开始授权' : '开始授权'}
          </button>
        )}
        {state === 'authorizing' && (
          <button
            className="button subtle"
            disabled={busy}
            onClick={() => void run(() => cancelAuth(connection.id))}
          >
            <X size={14} />
            取消授权
          </button>
        )}
        {state === 'connected' && (
          <>
            <button
              className="button subtle"
              disabled={busy}
              onClick={() => void run(() => getAuthStatus(connection.id).then((s) => ({ ok: true, status: s })))}
            >
              <RefreshCw size={14} />
              刷新状态
            </button>
            <button
              className="button subtle danger"
              disabled={busy}
              onClick={() => void run(() => logoutAuth(connection.id))}
            >
              <LogOut size={14} />
              断开连接
            </button>
          </>
        )}
      </div>

      {action && !action.ok && (
        <div className="settings-feedback error" role="alert">
          <strong>{action.errorCode ?? '操作失败'}</strong>
          {action.message}
          {action.nextSteps && (
            <ul>
              {action.nextSteps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {action?.ok && (
        <p className="settings-feedback success" role="status">
          <Check size={14} />
          已更新认证状态
        </p>
      )}
    </section>
  );
}
