'use client';
/**
 * S5-A CLI 应用本地仓储（对照参考 /space/cli-apps 的 CliApp / CliCatalogEntry）。
 *
 * 参考实现为服务器端目录+安装管线（/api/space/cli-apps，管理员安装/卸载）。
 * 目标项目无部署服务，这里提供同构的本地模拟：静态演示目录 + localStorage
 * 已装列表。安装=本地记录（带"模拟安装"标识），不下载、不执行任何程序。
 * 与聊天扩展目录（extension-catalog）职责分离：CLI 应用不进入聊天输入区。
 */

const INSTALLED_KEY = 'zhiqikeyuan:cli-apps';
const EVENT = 'zqky:cli-apps';

export type CliRuntime = 'python' | 'node' | 'none';
export type CliTrust = 'first-party' | 'third-party';

/** 已安装的 CLI 应用（对照参考 CliApp） */
export interface CliApp {
  id: string;
  displayName: string;
  description: string;
  category: string;
  /** 调用名（对照参考 tool_name，本地仅作展示） */
  toolName: string;
  runtime: CliRuntime;
  version: string;
  trust: CliTrust;
  installedAt: string;
  enabled: boolean;
}

/** 目录条目（对照参考 CliCatalogEntry 的本地形态） */
export interface CliCatalogEntry {
  id: string;
  displayName: string;
  description: string;
  category: string;
  runtime: CliRuntime;
  version: string;
  trust: CliTrust;
  /** 运行要求说明（演示目录中如实标注为本地模拟） */
  requires: string;
  installNotes: string;
}

/** 演示目录（静态，与参考"Store"语义对应；不自动安装） */
export const CLI_CATALOG: CliCatalogEntry[] = [
  {
    id: 'cli-text-stats',
    displayName: '文本统计工具',
    description: '统计字数、段落数与常见标点分布，辅助作文讲评。',
    category: '语文教学',
    runtime: 'python',
    version: '1.2.0',
    trust: 'first-party',
    requires: '本地 Python 3（演示记录，不实际运行）',
    installNotes: '安装为本地记录：pip install zqky-text-stats（模拟）',
  },
  {
    id: 'cli-mental-math',
    displayName: '口算题生成器',
    description: '按年级与题型批量生成口算练习及答案页。',
    category: '数学教学',
    runtime: 'node',
    version: '2.0.1',
    trust: 'first-party',
    requires: '本地 Node.js 18+（演示记录，不实际运行）',
    installNotes: '安装为本地记录：npm i -g zqky-mental-math（模拟）',
  },
  {
    id: 'cli-pinyin-mark',
    displayName: '拼音标注工具',
    description: '为生字表与课文片段标注拼音，支持多音字提示。',
    category: '语文教学',
    runtime: 'python',
    version: '0.9.3',
    trust: 'third-party',
    requires: '本地 Python 3 与 pypinyin（演示记录，不实际运行）',
    installNotes: '安装为本地记录：pip install zqky-pinyin-mark（模拟）',
  },
  {
    id: 'cli-poem-lookup',
    displayName: '古诗文检索',
    description: '按作者、朝代或关键字检索篇目与名句出处。',
    category: '语文教学',
    runtime: 'node',
    version: '1.4.2',
    trust: 'third-party',
    requires: '本地 Node.js 18+（演示记录，不实际运行）',
    installNotes: '安装为本地记录：npm i -g zqky-poem-lookup（模拟）',
  },
  {
    id: 'cli-random-pick',
    displayName: '课堂随机点名',
    description: '读取名册随机抽取学生，支持跳过已提问名单。',
    category: '课堂管理',
    runtime: 'none',
    version: '1.0.0',
    trust: 'first-party',
    requires: '无需运行时（演示记录，不实际运行）',
    installNotes: '安装为本地记录，无外部依赖（模拟）',
  },
];

function readInstalled(): CliApp[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(INSTALLED_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? (parsed as CliApp[]) : [];
  } catch {
    return [];
  }
}

function writeInstalled(list: CliApp[]): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(INSTALLED_KEY, JSON.stringify(list));
  window.dispatchEvent(new Event(EVENT));
}

export function listCliApps(): CliApp[] {
  return readInstalled();
}

export function subscribeCliApps(listener: () => void): () => void {
  const storage = (event: StorageEvent) => {
    if (event.key === INSTALLED_KEY || event.key === null) listener();
  };
  window.addEventListener(EVENT, listener);
  window.addEventListener('storage', storage);
  return () => {
    window.removeEventListener(EVENT, listener);
    window.removeEventListener('storage', storage);
  };
}

/** 从目录安装（本地记录；同 id 幂等）。返回 null 表示目录中不存在或已安装。 */
export function installCliApp(entryId: string): CliApp | null {
  const entry = CLI_CATALOG.find((item) => item.id === entryId);
  if (!entry) return null;
  const list = readInstalled();
  if (list.some((app) => app.id === entry.id)) return null;
  const app: CliApp = {
    id: entry.id,
    displayName: entry.displayName,
    description: entry.description,
    category: entry.category,
    toolName: `cli_${entry.id.replace(/-/g, '_')}`,
    runtime: entry.runtime,
    version: entry.version,
    trust: entry.trust,
    installedAt: new Date().toISOString(),
    enabled: true,
  };
  list.push(app);
  writeInstalled(list);
  return app;
}

/** 卸载（移除本地记录）。返回是否确有删除。 */
export function uninstallCliApp(id: string): boolean {
  const list = readInstalled();
  const kept = list.filter((app) => app.id !== id);
  if (kept.length === list.length) return false;
  writeInstalled(kept);
  return true;
}

export function setCliAppEnabled(id: string, enabled: boolean): void {
  const list = readInstalled();
  const idx = list.findIndex((app) => app.id === id);
  if (idx === -1) return;
  list[idx] = { ...list[idx]!, enabled };
  writeInstalled(list);
}
