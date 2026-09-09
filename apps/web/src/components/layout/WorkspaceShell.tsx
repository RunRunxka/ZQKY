'use client';
import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { BookOpen, ChevronRight, Menu, PanelLeftClose, PanelLeftOpen, X } from 'lucide-react';
import { groupMainNavigation, navigation } from '@/services/navigation';
import type { NavigationItem } from '@/contracts/navigation';

const mainGroups = groupMainNavigation();
const bottomItems = navigation.filter((n) => n.position === 'bottom');

/** 可访问名称与提示统一携带规划状态，展开、收起和手机导航保持一致 */
function accessibleName(item: NavigationItem) {
  return item.status === 'planned' ? `${item.label}（规划中）` : item.label;
}

function NavButton({
  item,
  current,
  onNavigate,
  sidebarLayout,
}: {
  item: NavigationItem;
  current: boolean;
  onNavigate: () => void;
  sidebarLayout?: boolean;
}) {
  const Icon = (sidebarLayout && item.sidebarIcon) || item.icon;
  return (
    <button
      className={`global-nav-item ${current ? 'current' : ''}`}
      title={accessibleName(item)}
      aria-label={accessibleName(item)}
      aria-current={current ? 'page' : undefined}
      onClick={onNavigate}
    >
      <Icon size={20} />
      <span>
        {item.label}
        {item.status === 'planned' && <small>规划中</small>}
      </span>
    </button>
  );
}

export function WorkspaceShell({
  children,
  headerActions,
  pageTitle,
  className = '',
  sidebarContent,
  sidebarLayout = false,
  beforeNavigate,
  onNavigationError,
}: {
  children: ReactNode;
  headerActions?: ReactNode;
  pageTitle: string;
  className?: string;
  sidebarContent?: ReactNode;
  sidebarLayout?: boolean;
  beforeNavigate?: () => Promise<void>;
  onNavigationError?: (message: string) => void;
}) {
  const [expanded, setExpanded] = useState(sidebarLayout);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const mobileNavRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname(),
    router = useRouter();

  useEffect(() => {
    if (mobileNavOpen) mobileNavRef.current?.focus();
  }, [mobileNavOpen]);

  async function navigate(path: string) {
    if (path === pathname) return;
    try {
      await beforeNavigate?.();
      router.push(path);
    } catch {
      onNavigationError?.('草稿保存失败，请先备份后再离开页面。');
    }
  }

  function navigateFromMenu(path: string) {
    setMobileNavOpen(false);
    void navigate(path);
  }

  function renderGroupItems(items: NavigationItem[], fromMenu: boolean) {
    return items
      .filter((item) => !item.hidden)
      .map((item) => (
        <NavButton
          key={item.id}
          item={item}
          sidebarLayout={sidebarLayout}
          current={
            pathname === item.path || (item.path === '/chat' && pathname.startsWith('/chat/'))
          }
          onNavigate={fromMenu ? () => navigateFromMenu(item.path) : () => void navigate(item.path)}
        />
      ));
  }

  return (
    <div className={`app-shell ${className} ${expanded ? 'nav-expanded' : ''}`}>
      <header className="app-header">
        <button
          className="mobile-nav-toggle"
          aria-label="打开功能导航"
          aria-expanded={mobileNavOpen}
          aria-controls="mobile-nav-panel"
          onClick={() => setMobileNavOpen(true)}
        >
          <Menu size={20} />
        </button>
        <button
          className="brand"
          aria-label="返回教案工作台"
          onClick={() => void navigate('/lesson-plans')}
        >
          <span className="brand-mark">
            <BookOpen size={21} />
          </span>
          <strong>智启课源</strong>
          <span className="brand-divider" />
        </button>
        <div className="breadcrumb">
          备课空间
          <ChevronRight size={14} />
          <span>{pageTitle}</span>
        </div>
        {headerActions}
      </header>
      <nav className="global-nav" aria-label="项目功能导航">
        {sidebarLayout && (
          <button
            className="sidebar-brand"
            aria-label="返回教案工作台"
            onClick={() => void navigate('/lesson-plans')}
          >
            <BookOpen size={22} strokeWidth={1.65} />
            <strong>智启课源</strong>
          </button>
        )}
        <button
          className="nav-toggle"
          aria-label={expanded ? '收起项目导航' : '展开项目导航'}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? <PanelLeftClose size={19} /> : <PanelLeftOpen size={19} />}
        </button>
        <div className="nav-items">
          {mainGroups.map((group, index) => (
            <Fragment key={group.label || `group-${index}`}>
              {group.label && <div className="nav-group-label">{group.label}</div>}
              {renderGroupItems(group.items, false)}
            </Fragment>
          ))}
        </div>
        {sidebarContent && <div className="sidebar-content">{sidebarContent}</div>}
        <div className="nav-bottom">
          {renderGroupItems(bottomItems, false)}
          <div className="avatar" title="本地工作台">
            教
          </div>
        </div>
      </nav>
      {mobileNavOpen && (
        <>
          <div className="mobile-nav-backdrop" onClick={() => setMobileNavOpen(false)} />
          <div
            id="mobile-nav-panel"
            ref={mobileNavRef}
            className="mobile-nav-panel"
            role="dialog"
            aria-modal="true"
            aria-label="功能导航"
            tabIndex={-1}
            onKeyDown={(event) => {
              if (event.key === 'Escape') setMobileNavOpen(false);
            }}
          >
            <div className="mobile-nav-head">
              <strong>功能导航</strong>
              <button
                className="icon-button"
                aria-label="关闭功能导航"
                onClick={() => setMobileNavOpen(false)}
              >
                <X size={18} />
              </button>
            </div>
            {mainGroups.map((group, index) => (
              <div className="mobile-nav-group" key={group.label || `group-${index}`}>
                {group.label && <div className="mobile-nav-group-label">{group.label}</div>}
                {renderGroupItems(group.items, true)}
              </div>
            ))}
            <div className="mobile-nav-group">{renderGroupItems(bottomItems, true)}</div>
            <div className="mobile-nav-footnote">未实现模块均处于规划中</div>
          </div>
        </>
      )}
      {children}
    </div>
  );
}
