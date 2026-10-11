import type { Metadata } from 'next';
import { WorkspaceShell } from '@/components/layout/WorkspaceShell';
import { PapersWorkspacePage } from '@/features/assessments/PapersWorkspacePage';

export const metadata: Metadata = { title: '智启课源 · 试卷管理' };

export default function AssessmentsPapersPage() {
  return (
    <WorkspaceShell pageTitle="试卷管理">
      <PapersWorkspacePage />
    </WorkspaceShell>
  );
}
