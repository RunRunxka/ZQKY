import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { WorkspaceShell } from '@/components/layout/WorkspaceShell';
import { PlannedModulePage } from '@/components/layout/PlannedModulePage';
import { navigation } from '@/services/navigation';
import type { PlannedNavigationItem } from '@/contracts/navigation';

function getPlannedItem(planned: string): PlannedNavigationItem | undefined {
  return navigation.find(
    (n): n is PlannedNavigationItem => n.path === `/${planned}` && n.status === 'planned',
  );
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ planned: string }>;
}): Promise<Metadata> {
  const { planned } = await params;
  const item = getPlannedItem(planned);
  return { title: item ? `智启课源 · ${item.label}（规划中）` : '智启课源' };
}

export default async function PlannedPage({ params }: { params: Promise<{ planned: string }> }) {
  const { planned } = await params;
  const item = getPlannedItem(planned);
  if (!item) notFound();
  return (
    <WorkspaceShell pageTitle={item.label}>
      <PlannedModulePage item={item} />
    </WorkspaceShell>
  );
}
