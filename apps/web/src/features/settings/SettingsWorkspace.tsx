'use client';
import { useEffect, useRef, useState } from 'react';
import { Info, Palette, Plug, X } from 'lucide-react';
import { WorkspaceShell } from '@/components/layout/WorkspaceShell';
import { useEntrance } from '@/components/motion/useEntrance';
import {
  applyThemePreference,
  readThemePreference,
  writeThemePreference,
  type ThemePreference,
} from '@/components/layout/theme-preference';
import { ModelSettingsPanel } from '@/features/model-settings/ModelSettingsPanel';
import './settings.css';
import './styles/settings-extend.css';
const sections = [
  { id: 'appearance', title: '外观', description: '显示主题与减少动画', icon: Palette },
  { id: 'models', title: '模型与连接', description: '连接、模型目录与默认模型', icon: Plug },
  { id: 'about', title: '关于', description: '实现状态与版本', icon: Info },
];
export function SettingsWorkspace() {
  const entranceRef = useRef<HTMLDivElement>(null);
  useEntrance(entranceRef, { preset: 'page' });
  const [query, setQuery] = useState('');
  const [active, setActive] = useState('appearance');
  const [reduced, setReduced] = useState(false);
  const [theme, setTheme] = useState<ThemePreference>('system');
  const [notice, setNotice] = useState('');
  const container = useRef<HTMLDivElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const filteredSections = sections.filter((section) =>
    `${section.title}${section.description}`.toLowerCase().includes(query.toLowerCase()),
  ).length;
  useEffect(() => {
    try {
      setReduced(window.localStorage.getItem('zqky.motion') === 'reduced');
    } catch {
      /* system preference remains available */
    }
    setTheme(readThemePreference());
    const navigate = () => {
      const id = location.hash.slice(1);
      if (!sections.some((section) => section.id === id)) return;
      setActive(id);
      document.getElementById(id)?.scrollIntoView({ behavior: 'instant', block: 'start' });
    };
    navigate();
    const frame = requestAnimationFrame(navigate);
    window.addEventListener('hashchange', navigate);
    const root = container.current;
    const updateActive = () => {
      if (!root) return;
      const top = root.getBoundingClientRect().top;
      let current = sections[0].id;
      let distance = Infinity;
      sections.forEach(({ id }) => {
        const node = document.getElementById(id);
        if (node) {
          const nextDistance = Math.abs(node.getBoundingClientRect().top - top - 24);
          if (nextDistance < distance) {
            distance = nextDistance;
            current = id;
          }
        }
      });
      setActive(current);
    };
    root?.addEventListener('scroll', updateActive, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      root?.removeEventListener('scroll', updateActive);
      window.removeEventListener('hashchange', navigate);
    };
  }, []);
  return (
    <WorkspaceShell pageTitle="设置">
      <div className="settings-workspace settings-page" ref={entranceRef}>
        <nav className="settings-index" aria-label="设置分类">
          <h1 data-motion-reveal>设置</h1>
          <div className="settings-search">
            <input
              ref={searchInput}
              aria-label="搜索设置"
              placeholder="搜索设置…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {query && (
              <button
                type="button"
                aria-label="清除搜索"
                onClick={() => {
                  setQuery('');
                  searchInput.current?.focus();
                }}
              >
                <X aria-hidden="true" />
              </button>
            )}
          </div>
          {sections
            .filter((section) =>
              `${section.title}${section.description}`.toLowerCase().includes(query.toLowerCase()),
            )
            .map((section) => {
              const Icon = section.icon;
              return (
                <a
                  key={section.id}
                  href={`#${section.id}`}
                  aria-current={active === section.id ? 'location' : undefined}
                  onClick={(event) => {
                    event.preventDefault();
                    history.pushState(null, '', `#${section.id}`);
                    setActive(section.id);
                    document
                      .getElementById(section.id)
                      ?.scrollIntoView({
                        behavior:
                          reduced || matchMedia('(prefers-reduced-motion: reduce)').matches
                            ? 'instant'
                            : 'smooth',
                        block: 'start',
                      });
                  }}
                >
                  <Icon className="settings-nav-icon" aria-hidden="true" />
                  <span className="settings-nav-text">
                    {section.title}
                    <small>{section.description}</small>
                  </span>
                </a>
              );
            })}
          {filteredSections === 0 && (
            <p className="settings-search-empty">没有匹配的设置项</p>
          )}
        </nav>
        <div className="settings-document" ref={container}>
          <section id="appearance" className="settings-panel" data-motion-reveal>
            <h2>外观</h2>
            <p>控制工作台的显示主题与动态效果。</p>
            <div className="settings-theme-options" role="radiogroup" aria-label="显示主题">
              {(
                [
                  ['system', '跟随系统'],
                  ['light', '浅色'],
                  ['dark', '深色'],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={theme === value}
                  className={theme === value ? 'button primary' : 'button subtle'}
                  onClick={() => {
                    if (!writeThemePreference(value)) {
                      setNotice('无法保存显示偏好。');
                      return;
                    }
                    applyThemePreference(value);
                    setTheme(value);
                    setNotice('显示偏好已保存。');
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <label className="settings-toggle">
              <input
                type="checkbox"
                checked={reduced}
                onChange={(e) => {
                  const next = e.target.checked;
                  try {
                    window.localStorage.setItem('zqky.motion', next ? 'reduced' : 'system');
                    document.documentElement.dataset.motion = next ? 'reduced' : 'system';
                    setReduced(next);
                    setNotice('显示偏好已保存。');
                  } catch {
                    setNotice('无法保存显示偏好。');
                  }
                }}
              />
              <span className="settings-toggle-track" aria-hidden="true">
                <span className="settings-toggle-thumb" />
              </span>
              减少动画
            </label>
            <p role="status" className="settings-notice">
              {notice}
            </p>
          </section>
          <section id="models">
            <h2>模型与连接</h2>
            <ModelSettingsPanel />
          </section>
          <section id="about" className="settings-panel">
            <h2>关于智启课源</h2>
            <p>
              当前为推倒重做后的最小骨架：对话 + 教学 Agent 编排 + 模型配置。
              历史完整产品（教学闭环全量）已归档为 git tag archive-full-v1-20261011。
            </p>
          </section>
        </div>
      </div>
    </WorkspaceShell>
  );
}
