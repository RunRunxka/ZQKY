'use client';
import { useEffect, useRef, useState } from 'react';
import { WorkspaceShell } from '@/components/layout/WorkspaceShell';
import { ModelSettingsPanel } from '@/features/model-settings/ModelSettingsPanel';
import { deleteBlob, putBlob } from '@/components/layout/wallpaper-store';
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
  const [glass, setGlass] = useState(false);
  const [blur, setBlur] = useState(16);
  const [frost, setFrost] = useState(60);
  const [scheme, setScheme] = useState<'light' | 'dark'>('light');
  const [bgSource, setBgSource] = useState<'ambient' | 'wallpaper'>('ambient');
  const [wallpaper, setWallpaper] = useState('');
  const [wpBlur, setWpBlur] = useState(0);
  const [wpFrost, setWpFrost] = useState(0);
  const [videoBrightness, setVideoBrightness] = useState(45);
  const imageInput = useRef<HTMLInputElement>(null);
  const videoInput = useRef<HTMLInputElement>(null);
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    try {
      setReduced(window.localStorage.getItem('zqky.motion') === 'reduced');
      setGlass(window.localStorage.getItem('zqky.glass') === 'on');
      setBlur(Number(window.localStorage.getItem('zqky.glass-blur')) || 16);
      setFrost(Number(window.localStorage.getItem('zqky.glass-frost')) || 60);
      setScheme(window.localStorage.getItem('zqky.glass-scheme') === 'dark' ? 'dark' : 'light');
      setBgSource(window.localStorage.getItem('zqky.glass-bg') === 'wallpaper' ? 'wallpaper' : 'ambient');
      setWallpaper(window.localStorage.getItem('zqky.glass-wallpaper') ?? '');
      setWpBlur(Number(window.localStorage.getItem('zqky.glass-wallpaper-blur')) || 0);
      setWpFrost(Number(window.localStorage.getItem('zqky.glass-wallpaper-frost')) || 0);
      setVideoBrightness(Number(window.localStorage.getItem('zqky.glass-video-brightness')) || 45);
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
  const saveGlass = (
    key:
      | 'on'
      | 'blur'
      | 'frost'
      | 'scheme'
      | 'bg'
      | 'wallpaper'
      | 'wpBlur'
      | 'wpFrost'
      | 'videoBrightness',
    value: number | boolean | 'light' | 'dark' | 'ambient' | 'wallpaper' | string,
  ) => {
    try {
      switch (key) {
        case 'on': {
          window.localStorage.setItem('zqky.glass', value ? 'on' : 'off');
          document.documentElement.dataset.glass = value ? 'on' : 'off';
          break;
        }
        case 'blur': {
          window.localStorage.setItem('zqky.glass-blur', String(value));
          document.documentElement.style.setProperty('--glass-blur', `${value}px`);
          break;
        }
        case 'frost': {
          window.localStorage.setItem('zqky.glass-frost', String(value));
          document.documentElement.style.setProperty('--glass-alpha', String(0.3 + (value as number) / 100 * 0.5));
          break;
        }
        case 'scheme': {
          const next = value === 'dark' ? 'dark' : 'light';
          window.localStorage.setItem('zqky.glass-scheme', next);
          document.documentElement.dataset.glassScheme = next;
          break;
        }
        case 'bg': {
          const next = value === 'wallpaper' ? 'wallpaper' : 'ambient';
          window.localStorage.setItem('zqky.glass-bg', next);
          break;
        }
        case 'wallpaper': {
          const previous = window.localStorage.getItem('zqky.glass-wallpaper') ?? '';
          window.localStorage.setItem('zqky.glass-wallpaper', String(value));
          if (previous.startsWith('idb:') && value !== previous) {
            void deleteBlob(previous.slice(4));
          }
          break;
        }
        case 'wpBlur': {
          window.localStorage.setItem('zqky.glass-wallpaper-blur', String(value));
          document.documentElement.style.setProperty('--glass-wallpaper-blur', `${value}px`);
          break;
        }
        case 'wpFrost': {
          window.localStorage.setItem('zqky.glass-wallpaper-frost', String(value));
          document.documentElement.style.setProperty('--glass-wallpaper-frost', String((value as number) / 100));
          break;
        }
        case 'videoBrightness': {
          window.localStorage.setItem('zqky.glass-video-brightness', String(value));
          document.documentElement.style.setProperty('--glass-video-dim', String(((100 - (value as number)) / 100) * 0.65));
          break;
        }
      }
      // 同页同步：GlassThemePreference / GlassBackdrop 监听该事件即时生效。
      window.dispatchEvent(new Event('zqky:glass-change'));
      setNotice('外观偏好已保存。');
    } catch {
      setNotice('无法保存显示偏好。');
    }
  };
  const pickImage = (file: File | undefined) => {
    if (!file) return;
    void (async () => {
      try {
        // 图片也走 IndexedDB blob：不受 localStorage 5MB 配额限制，
        // 也避免多 MB data URL 的写入/读取卡顿。
        const ref = await putBlob(file);
        setWallpaper(ref);
        saveGlass('wallpaper', ref);
      } catch {
        setNotice('壁纸保存失败，请重试。');
      }
    })();
  };
  const pickVideo = async (file: File | undefined) => {
    if (!file) return;
    try {
      const ref = await putBlob(file);
      setWallpaper(ref);
      saveGlass('wallpaper', ref);
    } catch {
      setNotice('视频保存失败，请重试。');
    }
  };
  const removeWallpaper = () => {
    setWallpaper('');
    saveGlass('wallpaper', '');
  };
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
            <label className="settings-toggle">
              <input
                type="checkbox"
                checked={glass}
                onChange={(e) => {
                  const next = e.target.checked;
                  setGlass(next);
                  saveGlass('on', next);
                }}
              />
              玻璃质感主题
            </label>
            <p className="settings-hint">开启后顶栏、侧边栏与弹层呈现磨砂玻璃效果，并叠加流体背景。</p>
            {glass && (
              <div className="settings-sliders">
                <div className="settings-scheme" role="radiogroup" aria-label="玻璃配色">
                  <label>
                    <input
                      type="radio"
                      name="zqky-glass-scheme"
                      checked={scheme === 'light'}
                      onChange={() => {
                        setScheme('light');
                        saveGlass('scheme', 'light');
                      }}
                    />
                    浅色玻璃
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="zqky-glass-scheme"
                      checked={scheme === 'dark'}
                      onChange={() => {
                        setScheme('dark');
                        saveGlass('scheme', 'dark');
                      }}
                    />
                    深色玻璃
                  </label>
                </div>
                <div className="settings-scheme" role="radiogroup" aria-label="背景来源">
                  <label>
                    <input
                      type="radio"
                      name="zqky-glass-bg"
                      checked={bgSource === 'ambient'}
                      onChange={() => {
                        setBgSource('ambient');
                        saveGlass('bg', 'ambient');
                      }}
                    />
                    环境光
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="zqky-glass-bg"
                      checked={bgSource === 'wallpaper'}
                      onChange={() => {
                        setBgSource('wallpaper');
                        saveGlass('bg', 'wallpaper');
                      }}
                    />
                    壁纸
                  </label>
                </div>
                {bgSource === 'wallpaper' && (
                  <>
                    <div className="settings-toolbar">
                      <button onClick={() => imageInput.current?.click()}>选择图片</button>
                      <button onClick={() => videoInput.current?.click()}>选择视频</button>
                      {wallpaper && <button onClick={removeWallpaper}>移除壁纸</button>}
                    </div>
                    <input
                      ref={imageInput}
                      type="file"
                      accept="image/*"
                      hidden
                      onChange={(e) => {
                        pickImage(e.target.files?.[0]);
                        e.target.value = '';
                      }}
                    />
                    <input
                      ref={videoInput}
                      type="file"
                      accept="video/*"
                      hidden
                      onChange={(e) => {
                        void pickVideo(e.target.files?.[0]);
                        e.target.value = '';
                      }}
                    />
                    <label className="settings-slider">
                      <span>
                        壁纸模糊度 <em>{wpBlur}px</em>
                      </span>
                      <input
                        type="range"
                        min={0}
                        max={40}
                        value={wpBlur}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          setWpBlur(v);
                          saveGlass('wpBlur', v);
                        }}
                      />
                    </label>
                    <label className="settings-slider">
                      <span>
                        壁纸磨砂度 <em>{wpFrost}%</em>
                      </span>
                      <input
                        type="range"
                        min={0}
                        max={100}
                        value={wpFrost}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          setWpFrost(v);
                          saveGlass('wpFrost', v);
                        }}
                      />
                    </label>
                    {wallpaper.startsWith('idb:') || wallpaper.startsWith('data:video/') ? (
                      <label className="settings-slider">
                        <span>
                          视频亮度 <em>{videoBrightness}%</em>
                        </span>
                        <input
                          type="range"
                          min={0}
                          max={100}
                          value={videoBrightness}
                          onChange={(e) => {
                            const v = Number(e.target.value);
                            setVideoBrightness(v);
                            saveGlass('videoBrightness', v);
                          }}
                        />
                      </label>
                    ) : null}
                  </>
                )}
                <label className="settings-slider">
                  <span>
                    模糊度 <em>{blur}px</em>
                  </span>
                  <input
                    type="range"
                    min={0}
                    max={40}
                    value={blur}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setBlur(v);
                      saveGlass('blur', v);
                    }}
                  />
                </label>
                <label className="settings-slider">
                  <span>
                    磨砂度 <em>{frost}%</em>
                  </span>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={frost}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setFrost(v);
                      saveGlass('frost', v);
                    }}
                  />
                </label>
              </div>
            )}
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
