'use client';
import { useCallback, useEffect, useState } from 'react';
import {
  CircleCheck,
  CircleSlash,
  Download,
  PackageOpen,
  ShieldCheck,
  ShieldAlert,
  Trash2,
} from 'lucide-react';
import { SpaceMain } from './SpaceMain';
import './styles/space-sections.css';
import {
  CLI_CATALOG,
  installCliApp,
  listCliApps,
  setCliAppEnabled,
  subscribeCliApps,
  uninstallCliApp,
  type CliApp,
} from '@/services/cli-apps-store';

const RUNTIME_LABEL: Record<string, string> = {
  python: 'Python',
  node: 'Node.js',
  none: '无需运行时',
};

export function CliAppsSection() {
  const [apps, setApps] = useState<CliApp[]>([]);
  const [tab, setTab] = useState<'installed' | 'store'>('installed');
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setApps(listCliApps());
  }, []);

  useEffect(() => {
    refresh();
    return subscribeCliApps(refresh);
  }, [refresh]);

  function handleInstall(entryId: string) {
    const app = installCliApp(entryId);
    if (!app) {
      setError('安装失败：目录中不存在该应用或它已在已装列表中。');
      return;
    }
    setError(null);
    setNotice(`已在本地登记「${app.displayName}」（模拟安装，不下载或执行任何程序）。`);
  }

  function handleUninstall(app: CliApp) {
    if (!window.confirm(`卸载「${app.displayName}」？仅移除本地记录。`)) return;
    if (uninstallCliApp(app.id)) {
      setNotice(`已移除「${app.displayName}」的本地记录。`);
      setError(null);
    } else {
      setError('卸载失败：记录不存在或已被移除。');
    }
  }

  const installedIds = new Set(apps.map((app) => app.id));

  return (
    /* B-R05-EXT5-I2：space-sections-page 为本批四子页视觉作用域修饰类；
       页面根 space-page 由 SpaceMain 提供（v1 已交付，不动）。 */
    <div className="space-sections-page">
      <SpaceMain
        title="CLI 应用"
        description="教学小工具的目录与本地安装记录（本地演示，不连接远程部署服务）。"
      >
      <div className="space-tabs" role="tablist" aria-label="CLI 应用视图">
        <button
          role="tab"
          aria-selected={tab === 'installed'}
          className={tab === 'installed' ? 'current' : ''}
          onClick={() => setTab('installed')}
        >
          已安装 ({apps.length})
        </button>
        <button
          role="tab"
          aria-selected={tab === 'store'}
          className={tab === 'store' ? 'current' : ''}
          onClick={() => setTab('store')}
        >
          应用目录 ({CLI_CATALOG.length})
        </button>
      </div>

      <div className="space-banner info" role="note">
        本地演示目录：「安装」仅在本机登记一条记录并持久保存，不会下载、安装或执行任何程序。
      </div>
      {notice && (
        <div className="space-banner info" role="status">
          {notice}
        </div>
      )}
      {error && (
        <div className="space-banner error" role="alert">
          {error}
        </div>
      )}

      {tab === 'installed' ? (
        apps.length === 0 ? (
          <div className="space-empty">
            <strong>还没有安装任何 CLI 应用</strong>
            <span>到「应用目录」了解每个工具的用途，再决定是否在本地登记。</span>
            <button className="space-button primary" onClick={() => setTab('store')}>
              <PackageOpen size={14} />
              打开应用目录
            </button>
          </div>
        ) : (
          <div className="space-card-grid">
            {apps.map((app) => (
              <article className="space-cli-card" key={app.id}>
                <div className="space-card-title">
                  {app.displayName}
                  {app.trust === 'first-party' ? (
                    <span className="space-chip green">
                      <ShieldCheck size={12} />
                      内置
                    </span>
                  ) : (
                    <span className="space-chip amber">
                      <ShieldAlert size={12} />
                      第三方
                    </span>
                  )}
                </div>
                <p className="space-card-body">{app.description}</p>
                <div className="space-meta-row">
                  <span className="space-chip">{app.category}</span>
                  <span className="space-chip">{RUNTIME_LABEL[app.runtime] ?? app.runtime}</span>
                  <span className="space-chip">v{app.version}</span>
                  <span className="space-chip">{app.toolName}</span>
                </div>
                <div className="space-meta-row">
                  <span>安装于 {new Date(app.installedAt).toLocaleDateString('zh-CN')}</span>
                </div>
                <div className="space-card-actions">
                  {/* 启停状态徽标色：按钮名「已启用/已停用」为 e2e 锚点，仅补
                      space-sections-state-on/off 状态色（绿系/灰系），不改形态 */}
                  <button
                    className={`space-button ${app.enabled ? 'space-sections-state-on' : 'space-sections-state-off'}`}
                    aria-pressed={app.enabled}
                    onClick={() => setCliAppEnabled(app.id, !app.enabled)}
                  >
                    {app.enabled ? <CircleCheck size={14} /> : <CircleSlash size={14} />}
                    {app.enabled ? '已启用' : '已停用'}
                  </button>
                  <button
                    className="space-button danger"
                    onClick={() => handleUninstall(app)}
                  >
                    <Trash2 size={14} />
                    卸载
                  </button>
                </div>
              </article>
            ))}
          </div>
        )
      ) : (
        <div className="space-card-grid">
          {CLI_CATALOG.map((entry) => {
            const installed = installedIds.has(entry.id);
            return (
              <article className="space-cli-card" key={entry.id}>
                <div className="space-card-title">
                  {entry.displayName}
                  {entry.trust === 'first-party' ? (
                    <span className="space-chip green">
                      <ShieldCheck size={12} />
                      内置
                    </span>
                  ) : (
                    <span className="space-chip amber">
                      <ShieldAlert size={12} />
                      第三方
                    </span>
                  )}
                </div>
                <p className="space-card-body">{entry.description}</p>
                <div className="space-meta-row">
                  <span className="space-chip">{entry.category}</span>
                  <span className="space-chip">{RUNTIME_LABEL[entry.runtime] ?? entry.runtime}</span>
                  <span className="space-chip">v{entry.version}</span>
                </div>
                <div className="space-explanation">
                  <p>运行要求：{entry.requires}</p>
                  <p>{entry.installNotes}</p>
                </div>
                <div className="space-card-actions">
                  <button
                    className="space-button primary"
                    disabled={installed}
                    onClick={() => handleInstall(entry.id)}
                  >
                    <Download size={14} />
                    {installed ? '已安装' : '安装（本地登记）'}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      <p className="space-footnote">
        参考产品的 CLI 安装为服务器部署流程；此处为本地演示形态，记录真实存在但不含执行能力。
      </p>
      </SpaceMain>
    </div>
  );
}
