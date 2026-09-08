import { beforeEach, describe, expect, it } from 'vitest';
import {
  CLI_CATALOG,
  installCliApp,
  listCliApps,
  setCliAppEnabled,
  uninstallCliApp,
} from './cli-apps-store';

/**
 * S5-A CLI 应用本地仓储：目录安装（本地登记）、启用/停用、卸载、幂等。
 */

describe('S5-A cli-apps-store', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('安装：写入已装列表并持久化；同 id 幂等拒绝', () => {
    const app = installCliApp('cli-mental-math');
    expect(app).not.toBeNull();
    expect(app!.displayName).toBe('口算题生成器');
    expect(app!.enabled).toBe(true);
    expect(listCliApps()).toHaveLength(1);
    // 重复安装返回 null 且不新增
    expect(installCliApp('cli-mental-math')).toBeNull();
    expect(listCliApps()).toHaveLength(1);
    // 目录中不存在的 id
    expect(installCliApp('nope')).toBeNull();
  });

  it('启用/停用切换生效，未知名单不抛错', () => {
    installCliApp('cli-text-stats');
    setCliAppEnabled('cli-text-stats', false);
    expect(listCliApps()[0]!.enabled).toBe(false);
    setCliAppEnabled('cli-text-stats', true);
    expect(listCliApps()[0]!.enabled).toBe(true);
    expect(() => setCliAppEnabled('missing', false)).not.toThrow();
  });

  it('卸载：移除本地记录；不存在时返回 false', () => {
    installCliApp('cli-pinyin-mark');
    expect(uninstallCliApp('cli-pinyin-mark')).toBe(true);
    expect(listCliApps()).toHaveLength(0);
    expect(uninstallCliApp('cli-pinyin-mark')).toBe(false);
  });

  it('目录为静态演示数据，含多种运行时与信任级别', () => {
    expect(CLI_CATALOG.length).toBeGreaterThanOrEqual(5);
    expect(CLI_CATALOG.some((e) => e.trust === 'third-party')).toBe(true);
    expect(CLI_CATALOG.some((e) => e.runtime === 'none')).toBe(true);
  });
});
