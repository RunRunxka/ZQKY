'use client';
import { useEffect, useRef, useState } from 'react';
import { WorkspaceShell } from '@/components/layout/WorkspaceShell';
import { ModelSettingsPanel } from '@/features/model-settings/ModelSettingsPanel';
import { ExtensionManager } from './ExtensionManager';
import './settings.css';
const sections = [
  { id: 'appearance', title: '外观', description: '显示与减少动画' },
  { id: 'models', title: '模型与连接', description: '连接、模型目录与默认模型' },
  { id: 'mcp', title: 'MCP', description: '扩展能力 · 服务管理' },
  { id: 'skills', title: 'Skills', description: '扩展能力 · 技能管理' },
  { id: 'about', title: '关于', description: '实现状态与版本' },
];
export function SettingsWorkspace() {
  const [query, setQuery] = useState('');
  const [active, setActive] = useState('appearance');
  const [reduced, setReduced] = useState(false);
  const [notice, setNotice] = useState('');
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    try {
      setReduced(window.localStorage.getItem('zqky.motion') === 'reduced');
    } catch {
      /* system preference remains available */
    }
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
      <div className="settings-workspace">
        <nav className="settings-index" aria-label="设置分类">
          <h1>设置</h1>
          <input
            aria-label="搜索设置"
            placeholder="搜索设置…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {sections
            .filter((section) =>
              `${section.title}${section.description}`.toLowerCase().includes(query.toLowerCase()),
            )
            .map((section) => (
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
                {section.title}
                <small>{section.description}</small>
              </a>
            ))}
        </nav>
        <div className="settings-document" ref={container}>
          <section id="appearance">
            <h2>外观</h2>
            <p>控制工作台的动态效果。</p>
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
              减少动画
            </label>
            <p role="status">{notice}</p>
          </section>
          <section id="models">
            <h2>模型与连接</h2>
            <ModelSettingsPanel />
          </section>
          <section id="mcp">
            <h2>MCP</h2>
            <ExtensionManager kind="mcp" />
          </section>
          <section id="skills">
            <h2>Skills</h2>
            <ExtensionManager kind="skill" />
          </section>
          <section id="about">
            <h2>关于智启课源</h2>
            <p>
              界面参考 DeepTutor v1.6.5。模型管理保留现有真实服务；MCP 与 Skills
              当前为本地模拟管理。其余复刻能力正在实施。
            </p>
          </section>
        </div>
      </div>
    </WorkspaceShell>
  );
}
