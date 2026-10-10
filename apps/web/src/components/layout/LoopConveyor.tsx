'use client';

/**
 * 闭环传递带（F2-LOOP · 方向 02 闭环传递带）。
 *
 * 一条带子里六个工位：原卷 → 成绩 → 学情报告 → 针对练习 → 回流对比 → 教案调整。
 * - 已完成：实心工位 + 产出物（真实版本与规模，如 `v2 · 34 人次`、`ready · 3 班`）；
 * - 可开始：空心工位 + 「可开始」（前置满足、尚未产出）；
 * - 缺前置：虚线工位 + 「缺前置」，连接线段断在没接上的那一段；
 * - 未知：来源读取失败时如实显示「未知」，不假装完成、也不判缺失。
 * 全带只有一个主按钮（右端）：可推进时是 `下一步 · {下一站名}`，否则指向能补齐的模块
 * （读取失败时就地「重新读取」）。缺前置/尚未到达的工位不跳转，只显示原因。
 *
 * 本页工位（`focusStation`，可选）：页面把自己能推进 / 产出的工位传进来后，多两件事——
 * - 对应工位加 `data-focus="true"`、`aria-current="step"` 与「本页」小标（与「可开始」的强调区分）；
 * - 本页工位因更早的缺口不可达时，主按钮改为 `缺「{缺口工位名}」：{一句话}` ＋「去补齐」，
 *   指向能补齐该缺口的模块页；本页工位可开始 / 已完成时维持原「下一步 · X」。
 * 不传 `focusStation` 时与既有行为完全一致。
 *
 * 状态来自 FastAPI 读接口（`services/loop-progress`）；本组件不做任何写操作、不伪造入库。
 */

import { GuardedLink } from '@/services/navigation-guard';
import type { LoopProgressServices, LoopStationView } from '@/services/loop-progress';
import { useLoopProgress, type LoopStationFocus } from './use-loop-progress';
import './loop-conveyor.css';

export interface LoopConveyorProps {
  /** 有学科上下文的页面传入学科 id；没有时按全学科读取。 */
  subjectId?: string | null;
  /**
   * 本页工位：单个工位 id 或一组 id（本页能推进 / 产出的工位，如成绩页 `['paper', 'score']`）。
   * 传了才启用本页视角（工位高亮 + 主按钮「缺「X」＋去补齐」）；缺省不传＝与既有行为完全一致。
   */
  focusStation?: LoopStationFocus;
  /** 测试/装配注入；缺省走真实前端服务。 */
  services?: LoopProgressServices;
  className?: string;
}

function StationCard({ station, focused }: { station: LoopStationView; focused: boolean }) {
  // 本页工位在 tooltip 与无障碍名里也说明身份：窄到放不下「本页」小标时（教案页紧凑栅格）
  // 仍有非颜色的文字依据，不把「本页」只挂在颜色上。
  const cardTitle = focused ? `本页工位 · ${station.title}` : station.title;
  const body = (
    <>
      <span className="loop-name">
        {station.name}
        {focused && (
          <span className="loop-focus-tag" data-testid={`loop-focus-tag-${station.id}`}>
            本页
          </span>
        )}
      </span>
      <span className="loop-artifact" data-testid={`loop-artifact-${station.id}`}>
        {station.artifact}
      </span>
      {station.reason && (
        <span className="loop-why" data-testid={`loop-why-${station.id}`}>
          {station.reason}
        </span>
      )}
    </>
  );
  // 已完成 / 可开始：可以跳到对应模块；缺前置与未知只显示原因，不跳转。
  if (station.state === 'done' || station.state === 'ready') {
    return (
      <GuardedLink className="loop-card" href={station.href} title={cardTitle}>
        {body}
      </GuardedLink>
    );
  }
  return (
    <div className="loop-card" title={cardTitle}>
      {body}
    </div>
  );
}

export function LoopConveyor({ subjectId = null, focusStation = null, services, className = '' }: LoopConveyorProps) {
  const { progress, focusIds, loading, degraded, reload } = useLoopProgress({ subjectId, focusStation, services });
  const { stations, action } = progress;
  const focus = new Set(focusIds);
  return (
    <section
      className={['loop-conveyor', className].filter(Boolean).join(' ')}
      data-testid="loop-conveyor"
      data-kind={action.kind}
      data-loading={loading ? 'true' : 'false'}
      data-degraded={degraded ? 'true' : 'false'}
      aria-label="教学闭环进度"
    >
      <ol className="loop-belt" data-testid="loop-belt" aria-label="教学闭环六工位">
        {stations.map((station, index) => {
          const focused = focus.has(station.id);
          return (
            <li
              key={station.id}
              className="loop-slot"
              data-testid={`loop-slot-${station.id}`}
              data-station={station.id}
              data-state={station.state}
              data-focus={focused ? 'true' : 'false'}
              aria-current={focused ? 'step' : undefined}
            >
              <StationCard station={station} focused={focused} />
              {station.linkAfter && (
                <span
                  className={`loop-link loop-link-${station.linkAfter}`}
                  data-testid={`loop-link-${station.id}`}
                  data-tone={station.linkAfter}
                  data-broken={station.linkAfter === 'broken' ? 'true' : 'false'}
                  aria-hidden="true"
                >
                  {station.linkAfter === 'broken' && (
                    <span className="loop-gap-badge" data-testid={`loop-gap-badge-${station.id}`} title={`缺口：${stations[index + 1]?.title ?? ''}`}>
                      缺
                    </span>
                  )}
                </span>
              )}
            </li>
          );
        })}
      </ol>
      <div className="loop-next" data-testid="loop-next" data-kind={action.kind}>
        <span className="loop-next-title" data-testid="loop-next-title">
          {action.title}
        </span>
        <span className="loop-next-note" data-testid="loop-next-note">
          {action.note}
        </span>
        <span className="loop-next-action" data-testid="loop-primary-action">
          {/* 全带唯一主按钮：能导航时是链接，读取中/重新读取时是就地按钮。 */}
          {action.href ? (
            <GuardedLink className="loop-primary" href={action.href}>
              {action.label}
            </GuardedLink>
          ) : (
            <button type="button" className="loop-primary" disabled={action.kind === 'pending'} onClick={reload}>
              {action.label}
            </button>
          )}
        </span>
      </div>
    </section>
  );
}

export default LoopConveyor;
