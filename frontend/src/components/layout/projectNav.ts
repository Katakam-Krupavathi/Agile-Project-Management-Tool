import type { ProjectRole } from '../../lib/types';
import type { ProjectNavItem } from './AppShell';

export function buildProjectNav(
  projectId: string | undefined,
  role?: ProjectRole,
): ProjectNavItem[] {
  if (!projectId) return [];
  const items: ProjectNavItem[] = [
    { to: `/projects/${projectId}`, label: 'Workspace', end: true },
    { to: `/projects/${projectId}/activity`, label: 'Activity' },
    { to: `/projects/${projectId}/reports`, label: 'Reports' },
  ];
  if (role === 'owner') {
    items.push({ to: `/projects/${projectId}/members`, label: 'Members' });
  }
  return items;
}
