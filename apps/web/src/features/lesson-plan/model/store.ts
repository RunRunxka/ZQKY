import { createStore } from 'zustand/vanilla';
import type { LessonPlanData } from './types';
import { exampleData } from './defaults';
export interface LessonState {
  data: LessonPlanData;
  past: LessonPlanData[];
  future: LessonPlanData[];
  revision: number;
  set: (patch: Partial<LessonPlanData>) => void;
  replace: (data: LessonPlanData) => void;
  hydrate: (data: LessonPlanData, revision: number) => void;
  undo: () => void;
  redo: () => void;
}
export function createLessonStore(initial: LessonPlanData = exampleData) {
  return createStore<LessonState>()((set) => ({
    data: structuredClone(initial),
    past: [],
    future: [],
    revision: 0,
    set: (patch) =>
      set((s) => ({
        data: { ...s.data, ...patch },
        past: [...s.past, s.data].slice(-80),
        future: [],
        revision: s.revision + 1,
      })),
    replace: (data) =>
      set((s) => ({
        data: structuredClone(data),
        past: [...s.past, s.data].slice(-80),
        future: [],
        revision: s.revision + 1,
      })),
    hydrate: (data, revision) => set({ data, past: [], future: [], revision }),
    undo: () =>
      set((s) =>
        s.past.length
          ? {
              data: s.past.at(-1)!,
              past: s.past.slice(0, -1),
              future: [s.data, ...s.future],
              revision: s.revision + 1,
            }
          : s,
      ),
    redo: () =>
      set((s) =>
        s.future.length
          ? {
              data: s.future[0],
              past: [...s.past, s.data],
              future: s.future.slice(1),
              revision: s.revision + 1,
            }
          : s,
      ),
  }));
}
