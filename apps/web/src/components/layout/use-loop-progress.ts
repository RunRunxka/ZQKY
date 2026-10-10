'use client';

/**
 * 传递带数据装配（F2-LOOP）：把 `services/loop-progress` 的读取包成组件生命周期，
 * 并按「本页工位」（focusStation）给出本页视角的主按钮。
 *
 * - effect 内发起读取，卸载/重载即 abort；迟到的结果一律不写状态；
 * - 首次读取显示「读取中…」，任何来源失败都只降级为对应工位「未知」，不把失败当空数据；
 * - 不轮询、不设定时器：状态只在挂载 / 学科变化 / 显式 reload 时读取；
 * - 不传本页工位时，主按钮与派生结果逐字一致（向后兼容）。
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  deriveLoopProgress,
  loadLoopSnapshot,
  pendingLoopProgress,
  type LoopActionView,
  type LoopProgress,
  type LoopProgressServices,
  type LoopStationId,
  type LoopStationView,
} from '@/services/loop-progress';

/** 本页工位：单个 id 或一组 id（本页能推进 / 产出的工位）。 */
export type LoopStationFocus = LoopStationId | readonly LoopStationId[] | null;

export interface UseLoopProgressOptions {
  /** 有学科上下文的页面传入；没有时按全学科读取（读数不小、也不猜）。 */
  subjectId?: string | null;
  /** 本页工位：传了才启用本页视角（工位高亮 + 主按钮补齐）；缺省与既有行为完全一致。 */
  focusStation?: LoopStationFocus;
  services?: LoopProgressServices;
}

export interface LoopProgressState {
  /** 已按本页工位视角调整主按钮的最终视图。 */
  progress: LoopProgress;
  /** 归一化后的本页工位（渲染高亮与 aria-current 用）；缺省为空数组。 */
  focusIds: readonly LoopStationId[];
  /** 首次读取中：所有工位显示「读取中…」，不给任何结论。 */
  loading: boolean;
  /** 至少一个来源读取失败：对应工位显示「未知」，整条带照常渲染。 */
  degraded: boolean;
  reload: () => void;
}

/** 本页工位归一化：单工位与工位数组都收；去重，空 / 缺省＝不启用本页视角。 */
export function normalizeFocusStations(focus: LoopStationFocus | undefined): readonly LoopStationId[] {
  if (focus === null || focus === undefined) return [];
  const list: readonly LoopStationId[] = typeof focus === 'string' ? [focus] : focus;
  return [...new Set(list)];
}

/** 缺口一句话＝派生层写进工位 title 的「为什么还没产出」（`{工位名}：可开始 · {原因}`）。 */
const TITLE_SEPARATOR = ' · ';

/**
 * 取缺口工位 title 里的那句话说给主按钮：
 * 派生层已把口径写好（`{工位名}：可开始 · {原因}`），这里沿用同一句话，不另维护一份文案；
 * 万一格式变化，退回不猜造的兜底说法，不把 title 整段塞进按钮。
 */
function gapSentence(station: LoopStationView): string {
  const prefix = `${station.name}：`;
  const body = station.title.startsWith(prefix) ? station.title.slice(prefix.length) : '';
  const at = body.lastIndexOf(TITLE_SEPARATOR);
  const sentence = at === -1 ? '' : body.slice(at + TITLE_SEPARATOR.length);
  return sentence || '还没有产出';
}

/**
 * 本页视角的主按钮（纯函数，单测直接喂派生结果）。
 *
 * - 不传本页工位（focusIds 为空）：原样返回，行为与既有实现完全一致；
 * - 本页最早的未产出工位「缺前置」（它前面还有没产出的工位）＝本页不可达：主按钮改为
 *   `缺「{缺口工位名}」：{一句话}` ＋「去补齐」，指向能补齐这个缺口的模块页
 *   （缺口＝链上第一个没有产出物的工位，href 沿用该工位既有规则）；
 * - 本页工位可开始 / 已完成（缺口就在本页工位自己，或在下游）时维持「下一步 · X」；
 * - 读取中与读取失败一律不当缺口：保留既有的「正在读取… / 重新读取」，不猜造缺失，
 *   也不把「本页工位到缺口之间有一段没读到」说成确认的缺口。
 */
export function applyFocusAction(
  stations: readonly LoopStationView[],
  action: LoopActionView,
  focusIds: readonly LoopStationId[],
): LoopActionView {
  if (focusIds.length === 0) return action;
  if (action.kind !== 'next' && action.kind !== 'blocked') return action;
  const focus = new Set(focusIds);
  // 本页最早的未产出工位：只有它「缺前置」才算本页不可达（它自己可开始时本页仍能做事）。
  const gatedIndex = stations.findIndex((station) => focus.has(station.id) && station.state !== 'done');
  if (gatedIndex === -1 || stations[gatedIndex].state !== 'blocked') return action;
  // 缺口＝链上第一个没有产出物的工位；它的 href 就是能补齐该缺口的模块页。
  const gapIndex = stations.findIndex((station) => station.state !== 'done');
  const gap = gapIndex === -1 ? null : stations[gapIndex];
  if (!gap || gap.state !== 'ready') return action;
  // 本页工位到缺口之间只要有一段读取失败，就不断言「缺」：失败仍留在带子上可见，主按钮保留既有行为。
  if (stations.slice(0, gatedIndex).some((station) => station.state === 'unknown')) return action;
  const focusNames = stations.filter((station) => focus.has(station.id)).map((station) => station.name).join(' / ');
  return {
    kind: 'blocked',
    title: `缺「${gap.name}」：${gapSentence(gap)}`,
    note: `补齐后本页「${focusNames}」才能继续`,
    label: '去补齐',
    href: gap.href,
  };
}

export function useLoopProgress({ subjectId = null, focusStation = null, services }: UseLoopProgressOptions = {}): LoopProgressState {
  const [base, setBase] = useState<LoopProgress>(pendingLoopProgress);
  const [loading, setLoading] = useState(true);
  const [degraded, setDegraded] = useState(false);
  const [tick, setTick] = useState(0);
  const servicesRef = useRef(services);
  servicesRef.current = services;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    const injected = servicesRef.current;
    loadLoopSnapshot({
      subjectId,
      ...(injected ? { services: injected } : {}),
      signal: controller.signal,
    }).then(
      (snapshot) => {
        if (!active) return;
        setBase(deriveLoopProgress(snapshot));
        setDegraded([snapshot.papers, snapshot.assessments, snapshot.runs, snapshot.practices, snapshot.lessons].some((entry) => entry === null));
        setLoading(false);
      },
      () => {
        /* 中止或意外异常：保持当前显示，不改写状态 */
      },
    );
    return () => {
      active = false;
      controller.abort();
    };
  }, [subjectId, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  const focusIds = normalizeFocusStations(focusStation);
  const action = applyFocusAction(base.stations, base.action, focusIds);
  // 不启用本页视角（或本页视角不改写主按钮）时保持派生结果的对象身份。
  const progress = action === base.action ? base : { ...base, action };
  return { progress, focusIds, loading, degraded, reload };
}

export default useLoopProgress;
