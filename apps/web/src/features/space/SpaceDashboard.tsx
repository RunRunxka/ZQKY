'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowUpRight, FileQuestion, MessagesSquare, NotebookPen, Plug, TerminalSquare, UserRoundCog, Blocks, type LucideIcon } from 'lucide-react';
import { SpaceMain } from './SpaceMain';
import { createIdbChatRepository } from '@/services/chat-repository';
import { listCliApps } from '@/services/cli-apps-store';
import { readExtensions } from '@/services/extension-catalog';
import { readPersonas } from '@/services/persona-catalog';
import { listNotebookEntries, listQuizBank } from '@/services/space-store';

interface DashboardTile {
  key: string;
  href: string;
  icon: LucideIcon;
  title: string;
  blurb: string;
  /** 计数单位（对照参考 unit：跟随实时数字展示，如"段对话"） */
  unit?: string;
  load: () => Promise<number> | number;
}

/**
 * 分组磁贴（对照参考 SpaceDashboard 的 DASHBOARD_GROUPS，中文文案 + 本地计数）。
 * whisper 磁贴在参考中由树外插件提供且按能力门控，本地无该能力，按参考行为隐藏。
 */
const DASHBOARD_GROUPS: { label: string; tiles: DashboardTile[] }[] = [
  {
    label: '会话与资料',
    tiles: [
      {
        key: 'chat_history',
        href: '/space/chat-history',
        icon: MessagesSquare,
        title: '会话历史',
        blurb: '全部学习问答会话，可搜索、归档与重开。',
        unit: '段对话',
        load: async () => {
          const real = createIdbChatRepository('zhiqikeyuan-chat');
          return (await real.list()).length;
        },
      },
      {
        key: 'notebooks',
        href: '/notebooks',
        icon: NotebookPen,
        title: '笔记本',
        blurb: '保存研究报告与学习笔记，支持查看与编辑。',
        unit: '个笔记本',
        load: () => listNotebookEntries().length,
      },
      {
        key: 'question_bank',
        href: '/space/questions',
        icon: FileQuestion,
        title: '题库',
        blurb: '出题产物沉淀于此，可筛选、标记与归类。',
        unit: '道题',
        load: () => listQuizBank().length,
      },
    ],
  },
  {
    label: '个性化',
    tiles: [
      {
        key: 'personas',
        href: '/space/personas',
        icon: UserRoundCog,
        title: '角色目录',
        blurb: '为问答选择讲解人设，可新建与编辑。',
        unit: '个预设',
        load: () => {
          try {
            return readPersonas().length;
          } catch {
            return 0;
          }
        },
      },
      {
        key: 'cli_apps',
        href: '/space/cli-apps',
        icon: TerminalSquare,
        title: 'CLI 应用',
        blurb: '教学小工具目录与本地安装记录（演示）。',
        unit: '个应用',
        load: () => listCliApps().length,
      },
      {
        key: 'skills',
        href: '/settings#skills',
        icon: Blocks,
        title: '技能',
        blurb: '技能统一在设置中管理，聊天内选择使用。',
        unit: '个技能',
        load: () => {
          try {
            return readExtensions().filter((e) => e.kind === 'skill').length;
          } catch {
            return 0;
          }
        },
      },
      {
        key: 'mcp',
        href: '/settings#mcp',
        icon: Plug,
        title: 'MCP 服务',
        blurb: 'MCP 服务器统一在设置中管理。',
        unit: '个服务',
        load: () => {
          try {
            return readExtensions().filter((e) => e.kind === 'mcp').length;
          } catch {
            return 0;
          }
        },
      },
    ],
  },
];

export function SpaceDashboard() {
  const [counts, setCounts] = useState<Record<string, number | '—'>>({});

  useEffect(() => {
    let alive = true;
    void (async () => {
      const entries = await Promise.all(
        DASHBOARD_GROUPS.flatMap((group) => group.tiles).map(async (tile) => {
          try {
            return [tile.key, await tile.load()] as const;
          } catch {
            return [tile.key, '—'] as const;
          }
        }),
      );
      if (alive) setCounts(Object.fromEntries(entries));
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <SpaceMain
      title="学习空间"
      description="会话、题库、笔记与个性化能力的统一入口。"
    >
      {DASHBOARD_GROUPS.map((group) => (
        <section className="space-group" key={group.label} aria-label={group.label}>
          <h2 className="space-group-label">{group.label}</h2>
          <div className="space-tiles">
            {group.tiles.map((tile) => {
              const Icon = tile.icon;
              const count = counts[tile.key];
              const loaded = count !== undefined;
              return (
                <Link className="space-tile" href={tile.href} key={tile.key}>
                  <span className="space-tile-head">
                    <span className="space-tile-icon" aria-hidden>
                      <Icon size={18} strokeWidth={1.7} />
                    </span>
                    <span className="space-tile-heading">
                      <span className="space-tile-title">{tile.title}</span>
                      {tile.unit && (
                        <span className="space-tile-count">
                          {loaded ? (
                            <>
                              <strong className="space-tile-number">{(count as number).toLocaleString()}</strong>
                              <span className="space-tile-unit">{tile.unit}</span>
                            </>
                          ) : (
                            <span className="space-tile-skeleton" aria-label="计数加载中" />
                          )}
                        </span>
                      )}
                    </span>
                    <ArrowUpRight size={16} className="space-tile-arrow" aria-hidden />
                  </span>
                  <span className="space-tile-blurb">{tile.blurb}</span>
                </Link>
              );
            })}
          </div>
        </section>
      ))}
    </SpaceMain>
  );
}
