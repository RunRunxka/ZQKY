import type { Metadata } from 'next';
import { WorkspaceShell } from '@/components/layout/WorkspaceShell';
import { RosterWorkspacePage } from '@/features/assessments/RosterWorkspacePage';

export const metadata: Metadata = { title: '智启课源 · 班级管理' };

export default function AssessmentsRosterPage() {
  return (
    <WorkspaceShell pageTitle="班级管理">
      <RosterWorkspacePage />
    </WorkspaceShell>
  );
}
