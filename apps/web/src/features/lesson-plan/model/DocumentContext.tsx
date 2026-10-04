'use client';
import { createContext, useContext, type MutableRefObject } from 'react';
import type { AnalysisContextInput, LessonRevisionView, LessonView } from '@/contracts/lesson-plans';
import type { LessonWorkspaceServices } from './workspace-services';
import { defaultSourceApi } from './workspace-services';
import { lessonPlanApi } from '@/services/lesson-plans-api';

export interface DocumentSelection { subjectId: string; classId: string; context: AnalysisContextInput | null }
export interface DocumentOperationState { busy: boolean; unknown: boolean }
export interface DocumentOperationPublisher { publish: (state: DocumentOperationState) => boolean; isCurrent: () => boolean; release: () => void }
export interface DocumentController {
  mode: 'local' | 'server' | 'history';
  documentId?: string;
  initialAnalysisRunId?: string;
  initialRouteError?: string;
  view: LessonView | null;
  api: typeof lessonPlanApi;
  sources: typeof defaultSourceApi;
  services: LessonWorkspaceServices;
  selection: DocumentSelection;
  setSelection: (selection: DocumentSelection) => void;
  openDocument: (id: string, revisionId?: string) => Promise<void>;
  openLocal: () => Promise<void>;
  leave: MutableRefObject<(() => Promise<boolean>) | null>;
  pendingOperation: MutableRefObject<DocumentOperationState>;
  pendingOperationState: Readonly<DocumentOperationState>;
  bindPendingOperation: () => DocumentOperationPublisher;
  onSaved: (view: LessonView) => void;
  pendingCopy: LessonRevisionView | null;
  copyHistory: (revision: LessonRevisionView) => Promise<void>;
  finishCopy: () => void;
  candidateId: string | null;
  setCandidateId: (id: string | null) => void;
}
export const LessonDocumentContext = createContext<DocumentController | null>(null);
export function useLessonDocument() {
  const value = useContext(LessonDocumentContext);
  if (!value) throw new Error('LessonDocumentContext required');
  return value;
}
