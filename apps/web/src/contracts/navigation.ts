import type { LucideIcon } from 'lucide-react';

/**
 * 模块业务状态：
 * - planned：业务未实现，可进入规划介绍页；
 * - local：真实的本机编辑/存储能力，不代表云端服务；
 * - ready：对应业务已实现（是否已配置、连接成功另行判断）。
 */
export type ModuleStatus = 'planned' | 'local' | 'ready';

export interface ModulePlan {
  /** 用途简介，说明该模块完成后提供什么 */
  summary: string;
  /** 以后接入的能力清单，全部为规划描述 */
  capabilities: string[];
}

interface NavigationBase {
  id: string;
  label: string;
  path: string;
  position: 'main' | 'bottom';
  /** 展开导航与手机导航中的分组标题；不填则不显示分组标题 */
  group?: string;
  /** 不进侧栏（如仅从 /space 仪表盘进入的规划页），但保持路由与 [planned] 解析可用 */
  hidden?: boolean;
  /**
   * 全站唯一主页入口。有且仅有一个条目声明；WorkspaceShell 品牌按钮、404/错误页
   * 返回入口与默认标题都从这里派生，不各自硬编码路径。
   */
  home?: boolean;
  /**
   * 隐藏直达页的可见父菜单：桌面侧栏不渲染隐藏项时，用它决定标记哪一条可见菜单为当前。
   * 手机抽屉会直接渲染隐藏项本身，因此抽屉标记该项而非父项（任一界面都只有一个 aria-current）。
   */
  parentPath?: string;
  icon: LucideIcon;
  /** 单侧栏布局的参考图标；功能、名称和路由仍来自同一条目。 */
  sidebarIcon?: LucideIcon;
}

export type PlannedNavigationItem = NavigationBase & {
  status: 'planned';
  plan: ModulePlan;
};

export type ImplementedNavigationItem = NavigationBase & {
  status: 'local' | 'ready';
  plan?: ModulePlan;
};

export type NavigationItem = PlannedNavigationItem | ImplementedNavigationItem;
