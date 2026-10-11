'use client';
import { useState } from 'react';
import { RosterPanel } from './RosterPanel';

/** 班级管理独立页（C4-3）：复用五步工作区的 RosterPanel，自持选择/刷新状态。 */
export function RosterWorkspacePage() {
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  return (
    <RosterPanel
      selectedClassId={selectedClassId}
      onSelectClass={(classId) => setSelectedClassId(classId)}
      refreshToken={refreshToken}
      onChanged={() => setRefreshToken((value) => value + 1)}
    />
  );
}
