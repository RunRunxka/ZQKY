/**
 * 教案工作台单实例 store（Zustand 工厂，沿用归档 `createLessonStore` 的形态）。
 *
 * 约定：
 * - 正文之外的编辑态（复制/回滚）只保存 `data` 与 `modules` 快照，样式与选中的模块不进历史；
 * - **候选（AI 生成结果）与正文彻底分离**：流式只写 `candidate`，教师「采用」才进 `data`（红线）；
 * - 任何内容改动都会 `revision + 1`，本地草稿与云端 autosave 以它作为触发信号。
 */
import { createStore, type StoreApi } from 'zustand/vanilla';
import type { LessonPlanData, LessonWorkbenchStyleWire } from '@/contracts/lesson-plans';
import { cloneLessonData, emptyLessonData, newId } from './lesson-data';
import {
  CUSTOM_MODULE_PREFIX,
  defaultModuleLayout,
  normalizeStyle,
  type LessonModuleEntry,
} from './modules';
import { applyFillToData, parseModuleText, type ModuleFillResult } from '../services/fill-parsers';

export interface CandidateModuleState {
  key: string;
  label: string;
  text: string;
  state: 'pending' | 'streaming' | 'done' | 'error';
  message?: string;
  /** 已采用：从候选移出，不再参与预览叠加。 */
  adopted?: boolean;
}

export interface LessonCandidate {
  requestId: string;
  status: 'streaming' | 'done' | 'error' | 'interrupted';
  order: string[];
  modules: Record<string, CandidateModuleState>;
  /** 出错/中断时保留原因，供界面如实提示。 */
  message?: string;
}

interface ContentSnapshot {
  data: LessonPlanData;
  modules: LessonModuleEntry[];
}

export interface LessonWorkbenchState {
  data: LessonPlanData;
  modules: LessonModuleEntry[];
  removed: LessonModuleEntry[];
  style: LessonWorkbenchStyleWire;
  activeModuleId: string;
  revision: number;
  past: ContentSnapshot[];
  future: ContentSnapshot[];
  candidate: LessonCandidate | null;

  setData: (patch: Partial<LessonPlanData>) => void;
  updateData: (updater: (data: LessonPlanData) => LessonPlanData) => void;
  replaceContent: (data: LessonPlanData, options?: { resetHistory?: boolean }) => void;
  setStyle: (patch: Partial<LessonWorkbenchStyleWire>) => void;
  setActiveModule: (id: string) => void;
  addCustomModule: (label: string) => string;
  renameCustomModule: (id: string, label: string) => void;
  setCustomBody: (id: string, body: string) => void;
  removeModule: (id: string) => void;
  restoreModule: (id: string) => void;
  moveModule: (id: string, delta: number) => void;
  reorderModule: (fromIndex: number, toIndex: number) => void;
  toggleHidden: (id: string) => void;
  undo: () => void;
  redo: () => void;

  startCandidate: (requestId: string, modules: Array<{ key: string; label: string }>) => void;
  appendCandidateDelta: (key: string, delta: string) => void;
  markCandidateModule: (key: string, state: CandidateModuleState['state'], message?: string) => void;
  finishCandidate: (status: LessonCandidate['status'], message?: string) => void;
  clearCandidate: () => void;
  candidateResults: (keys?: string[]) => ModuleFillResult[];
  adoptCandidate: (keys?: string[]) => string[];
}

const HISTORY_LIMIT = 60;

export function createLessonWorkbenchStore(initial?: {
  data?: LessonPlanData;
  modules?: LessonModuleEntry[];
  removed?: LessonModuleEntry[];
  style?: Partial<LessonWorkbenchStyleWire>;
}): StoreApi<LessonWorkbenchState> {
  const data = cloneLessonData(initial?.data ?? emptyLessonData());
  const modules = (initial?.modules ?? defaultModuleLayout()).map((entry) => ({ ...entry }));
  return createStore<LessonWorkbenchState>()((set, get) => {
    const mutateContent = (produce: () => Partial<LessonWorkbenchState> | void) =>
      set((state) => {
        const patch = produce() ?? {};
        return {
          ...patch,
          past: [...state.past, { data: cloneLessonData(state.data), modules: state.modules.map((m) => ({ ...m })) }].slice(
            -HISTORY_LIMIT,
          ),
          future: [],
          revision: state.revision + 1,
        };
      });
    return {
      data,
      modules,
      removed: initial?.removed ?? [],
      style: normalizeStyle(initial?.style),
      activeModuleId: modules[0]?.id ?? '',
      revision: 0,
      past: [],
      future: [],
      candidate: null,

      setData: (patch) => mutateContent(() => ({ data: { ...get().data, ...patch } })),
      updateData: (updater) => mutateContent(() => ({ data: updater(cloneLessonData(get().data)) })),
      replaceContent: (nextData, options) =>
        set((state) => ({
          data: cloneLessonData(nextData),
          past: options?.resetHistory ? [] : state.past,
          future: options?.resetHistory ? [] : state.future,
          revision: state.revision + 1,
        })),

      setStyle: (patch) => set((state) => ({ style: normalizeStyle({ ...state.style, ...patch }) })),
      setActiveModule: (id) => set({ activeModuleId: id }),

      addCustomModule: (label) => {
        const id = `${CUSTOM_MODULE_PREFIX}${newId()}`;
        mutateContent(() => ({
          modules: [
            ...get().modules,
            {
              id,
              kind: 'custom' as const,
              label: label.trim() || '自定义模块',
              hidden: false,
              body: '',
            },
          ],
        }));
        set({ activeModuleId: id });
        return id;
      },
      renameCustomModule: (id, label) =>
        mutateContent(() => ({
          modules: get().modules.map((entry) =>
            entry.id === id && entry.kind === 'custom'
              ? { ...entry, label: label.trim() || '自定义模块' }
              : entry,
          ),
        })),
      setCustomBody: (id, body) =>
        mutateContent(() => ({
          modules: get().modules.map((entry) => (entry.id === id ? { ...entry, body } : entry)),
        })),

      removeModule: (id) => {
        const target = get().modules.find((entry) => entry.id === id);
        if (!target || target.kind === 'builtin') return; // 基本信息等固定模块只能隐藏
        mutateContent(() => ({
          modules: get().modules.filter((entry) => entry.id !== id),
          removed: [...get().removed.filter((entry) => entry.id !== id), target],
        }));
        if (get().activeModuleId === id) set({ activeModuleId: get().modules[0]?.id ?? '' });
      },
      restoreModule: (id) => {
        const target = get().removed.find((entry) => entry.id === id);
        if (!target) return;
        mutateContent(() => ({
          modules: [...get().modules, { ...target, hidden: false }],
          removed: get().removed.filter((entry) => entry.id !== id),
        }));
        set({ activeModuleId: id });
      },
      toggleHidden: (id) =>
        mutateContent(() => ({
          modules: get().modules.map((entry) =>
            entry.id === id ? { ...entry, hidden: !entry.hidden } : entry,
          ),
        })),
      moveModule: (id, delta) => {
        const list = get().modules;
        const index = list.findIndex((entry) => entry.id === id);
        const target = index + delta;
        if (index < 0 || target < 0 || target >= list.length) return;
        mutateContent(() => {
          const next = [...list];
          const [item] = next.splice(index, 1);
          next.splice(target, 0, item);
          return { modules: next };
        });
      },
      reorderModule: (fromIndex, toIndex) => {
        const list = get().modules;
        if (
          fromIndex === toIndex ||
          fromIndex < 0 ||
          toIndex < 0 ||
          fromIndex >= list.length ||
          toIndex >= list.length
        )
          return;
        mutateContent(() => {
          const next = [...list];
          const [item] = next.splice(fromIndex, 1);
          next.splice(toIndex, 0, item);
          return { modules: next };
        });
      },

      undo: () =>
        set((state) => {
          const previous = state.past.at(-1);
          if (!previous) return state;
          return {
            data: previous.data,
            modules: previous.modules,
            past: state.past.slice(0, -1),
            future: [{ data: cloneLessonData(state.data), modules: state.modules }, ...state.future],
            revision: state.revision + 1,
          };
        }),
      redo: () =>
        set((state) => {
          const next = state.future[0];
          if (!next) return state;
          return {
            data: next.data,
            modules: next.modules,
            past: [...state.past, { data: cloneLessonData(state.data), modules: state.modules }].slice(-HISTORY_LIMIT),
            future: state.future.slice(1),
            revision: state.revision + 1,
          };
        }),

      startCandidate: (requestId, moduleList) =>
        set({
          candidate: {
            requestId,
            status: 'streaming',
            order: moduleList.map((entry) => entry.key),
            modules: Object.fromEntries(
              moduleList.map((entry) => [
                entry.key,
                { key: entry.key, label: entry.label, text: '', state: 'pending' as const },
              ]),
            ),
          },
        }),
      appendCandidateDelta: (key, delta) =>
        set((state) => {
          const candidate = state.candidate;
          if (!candidate || !candidate.modules[key]) return state;
          const target = candidate.modules[key];
          return {
            candidate: {
              ...candidate,
              modules: {
                ...candidate.modules,
                [key]: { ...target, text: target.text + delta, state: 'streaming' },
              },
            },
          };
        }),
      markCandidateModule: (key, moduleState, message) =>
        set((state) => {
          const candidate = state.candidate;
          if (!candidate || !candidate.modules[key]) return state;
          return {
            candidate: {
              ...candidate,
              modules: {
                ...candidate.modules,
                [key]: { ...candidate.modules[key], state: moduleState, ...(message ? { message } : {}) },
              },
            },
          };
        }),
      finishCandidate: (status, message) =>
        set((state) => (state.candidate ? { candidate: { ...state.candidate, status, ...(message ? { message } : {}) } } : state)),
      clearCandidate: () => set({ candidate: null }),

      candidateResults: (keys) => {
        const candidate = get().candidate;
        if (!candidate) return [];
        const list = keys ?? candidate.order;
        return list
          .filter((key) => candidate.modules[key] && candidate.modules[key].text.trim().length > 0)
          .map((key) => parseModuleText(key, candidate.modules[key].text));
      },
      adoptCandidate: (keys) => {
        const candidate = get().candidate;
        if (!candidate) return [];
        const adoptedKeys = (keys ?? candidate.order).filter(
          (key) => candidate.modules[key]?.text.trim().length > 0,
        );
        if (adoptedKeys.length === 0) return [];
        const results = get().candidateResults(adoptedKeys);
        const nextData = applyFillToData(get().data, results);
        mutateContent(() => ({ data: nextData }));
        set((state) => {
          if (!state.candidate) return state;
          // 「采用全部」（不指定模块）在采纳所有已产出的文本后结束候选；
          // 逐模块采用只移出该模块，其余候选继续保留给教师逐一确认。
          if (!keys) return { candidate: null };
          const modules = { ...state.candidate.modules };
          for (const key of adoptedKeys) {
            if (modules[key]) modules[key] = { ...modules[key], adopted: true };
          }
          return { candidate: { ...state.candidate, modules } };
        });
        return adoptedKeys;
      },
    };
  });
}

/** 新建流程中的一个空工作台实例（与 store 解耦，供测试与首屏使用）。 */
export function createEmptyWorkbenchState() {
  return {
    data: emptyLessonData(),
    modules: defaultModuleLayout(),
    removed: [] as LessonModuleEntry[],
    style: normalizeStyle(undefined),
  };
}

export type LessonWorkbenchStore = ReturnType<typeof createLessonWorkbenchStore>;
