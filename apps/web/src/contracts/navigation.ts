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
