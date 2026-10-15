/** 外观主题偏好：跟随系统 / 浅色 / 深色。存于本地浏览器，不宣称云端同步。 */
export type ThemePreference = 'system' | 'light' | 'dark';

export const THEME_STORAGE_KEY = 'zqky.theme';

/** 读取失败（隐私窗口、站点数据被清）一律回落到跟随系统，不影响页面渲染。 */
export function readThemePreference(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return stored === 'light' || stored === 'dark' ? stored : 'system';
  } catch {
    return 'system';
  }
}

/** 写入失败时返回 false，由调用方提示「无法保存」，且不改变当前界面。 */
export function writeThemePreference(preference: ThemePreference): boolean {
  try {
    if (preference === 'system') {
      window.localStorage.removeItem(THEME_STORAGE_KEY);
    } else {
      window.localStorage.setItem(THEME_STORAGE_KEY, preference);
    }
    return true;
  } catch {
    return false;
  }
}

/** 把偏好落到根节点：system 时移除属性，让 CSS 的 prefers-color-scheme 生效。 */
export function applyThemePreference(preference: ThemePreference): void {
  const root = document.documentElement;
  if (preference === 'system') {
    delete root.dataset.theme;
  } else {
    root.dataset.theme = preference;
  }
}

/**
 * 绘制前的初始化脚本（由根布局内联到 <head>）。与 readThemePreference 保持同一键名与取值，
 * 只做一件事：在首帧前设置 data-theme，避免深色用户先看到浅色闪烁。
 */
export const THEME_BOOT_SCRIPT = `(function(){try{var v=window.localStorage.getItem('${THEME_STORAGE_KEY}');if(v==='light'||v==='dark'){document.documentElement.dataset.theme=v;}}catch(e){}})();`;

/** 当前生效的主题是否为深色：显式 data-theme 优先，否则跟随系统。仅在客户端生命周期内调用。 */
export function resolvedThemeIsDark(): boolean {
  const attribute = document.documentElement.dataset.theme;
  if (attribute === 'dark') return true;
  if (attribute === 'light') return false;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches === true;
}
